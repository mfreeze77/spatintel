from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from botocore.exceptions import ClientError

from sip.assets import S3ContentAddressedStore
from sip.canonical import sha256_bytes
from sip.config import Settings
from sip.errors import ValidationError
from sip.security import EnvelopeCipher


class _Paginator:
    def __init__(self, client: "FakeS3") -> None:
        self.client = client

    def paginate(self, *, Bucket: str, Prefix: str) -> list[dict[str, Any]]:
        assert Bucket == self.client.bucket
        return [{"Contents": [{"Key": key} for key in sorted(self.client.objects) if key.startswith(Prefix)]}]


class FakeS3:
    def __init__(self, bucket: str = "sip-evidence") -> None:
        self.bucket = bucket
        self.objects: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _error(code: str, operation: str) -> ClientError:
        return ClientError({"Error": {"Code": code, "Message": code}}, operation)

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        assert Bucket == self.bucket
        if Key not in self.objects:
            raise self._error("404", "HeadObject")
        obj = self.objects[Key]
        return {"Metadata": dict(obj["Metadata"]), "ContentLength": len(obj["Body"])}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, Metadata: dict[str, str] | None = None, IfNoneMatch: str | None = None, **kwargs: Any) -> dict[str, Any]:
        assert Bucket == self.bucket
        if IfNoneMatch == "*" and Key in self.objects:
            raise self._error("PreconditionFailed", "PutObject")
        self.objects[Key] = {"Body": bytes(Body), "Metadata": dict(Metadata or {}), "Options": kwargs}
        return {"ETag": sha256_bytes(bytes(Body))}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        assert Bucket == self.bucket
        if Key not in self.objects:
            raise self._error("NoSuchKey", "GetObject")
        obj = self.objects[Key]
        return {"Body": io.BytesIO(obj["Body"]), "Metadata": dict(obj["Metadata"])}

    def delete_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        assert Bucket == self.bucket
        self.objects.pop(Key, None)
        return {}

    def copy_object(self, *, Bucket: str, Key: str, CopySource: dict[str, str], Metadata: dict[str, str], **kwargs: Any) -> dict[str, Any]:
        assert Bucket == self.bucket
        source = CopySource["Key"]
        if source not in self.objects:
            raise self._error("NoSuchKey", "CopyObject")
        body = self.objects[source]["Body"]
        self.objects[Key] = {"Body": body, "Metadata": dict(Metadata), "Options": kwargs}
        return {}

    def get_paginator(self, name: str) -> _Paginator:
        assert name == "list_objects_v2"
        return _Paginator(self)


@pytest.mark.integration
def test_s3_content_addressed_store_is_atomic_encrypted_and_rewrappable(tmp_path: Path) -> None:
    client = FakeS3()
    store = S3ContentAddressedStore(
        bucket=client.bucket,
        prefix="tenant-data",
        cipher=EnvelopeCipher(b"a" * 32, "key-v1"),
        client=client,
        kms_key_id="arn:aws:kms:us-east-2:123456789012:key/example",
    )
    payloads = [b"immutable evidence one", b"immutable evidence two"]
    digests = [sha256_bytes(payload) for payload in payloads]

    for digest, payload in zip(digests, payloads, strict=True):
        metadata = store.write_bytes(digest, payload)
        assert metadata["key_id"] == "key-v1"
        assert store.read_bytes(digest) == payload
        assert store.storage_key(digest).startswith("s3://sip-evidence/tenant-data/objects/")
        assert client.objects[store.key_for(digest)]["Body"] != payload
        # Idempotent immutable replay returns the committed envelope.
        assert store.write_bytes(digest, payload) == metadata

    before = {digest: sha256_bytes(client.objects[store.key_for(digest)]["Body"]) for digest in digests}
    rotation = store.rotate_envelope_key(EnvelopeCipher(b"b" * 32, "key-v2"))
    after = {digest: sha256_bytes(client.objects[store.key_for(digest)]["Body"]) for digest in digests}
    assert rotation == {
        "old_key_id": "key-v1",
        "new_key_id": "key-v2",
        "object_count": 2,
        "ciphertext_unchanged": True,
    }
    assert before == after
    assert [store.read_bytes(digest) for digest in digests] == payloads

    destination = tmp_path / "portable-backup"
    store.copy_to(destination)
    for digest in digests:
        assert (destination / digest[:2] / digest[2:4] / f"{digest}.enc").is_file()
        assert (destination / digest[:2] / digest[2:4] / f"{digest}.meta.json").is_file()

    count_before_probe = len(client.objects)
    store.probe()
    assert len(client.objects) == count_before_probe


@pytest.mark.security
def test_s3_store_detects_ciphertext_tampering() -> None:
    client = FakeS3()
    store = S3ContentAddressedStore(
        bucket=client.bucket,
        prefix="sip",
        cipher=EnvelopeCipher(b"c" * 32, "key-v1"),
        client=client,
    )
    payload = b"chain-of-custody"
    digest = sha256_bytes(payload)
    store.write_bytes(digest, payload)
    client.objects[store.key_for(digest)]["Body"] += b"tamper"
    with pytest.raises(Exception):
        store.read_bytes(digest)


@pytest.mark.security
def test_production_settings_fail_closed_without_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIP_ENV", "production")
    monkeypatch.delenv("SIP_MASTER_KEY_B64", raising=False)
    monkeypatch.delenv("SIP_SIGNING_KEY_B64", raising=False)
    with pytest.raises(ValueError, match="SIP_MASTER_KEY_B64 is required"):
        Settings.from_env()


def test_s3_store_rejects_invalid_digest() -> None:
    client = FakeS3()
    store = S3ContentAddressedStore(bucket=client.bucket, prefix="", cipher=EnvelopeCipher(b"d" * 32, "key"), client=client)
    with pytest.raises(ValidationError, match="content hash"):
        store.key_for("not-a-sha256")
