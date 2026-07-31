from __future__ import annotations

import base64
import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from botocore.exceptions import ClientError
from sqlalchemy import func, select

from .audit import AuditService
from .canonical import canonical_json, new_uuid, sha256_bytes, sha256_file
from .database import AssetRefRow, AssetRow, Database, MultipartChunkRow, MultipartUploadRow, ProjectRow
from .errors import ConflictError, NotFoundError, ValidationError
from .models import AuthorityClass, Classification, ProvenanceRef, SourceClass
from .security import EnvelopeCipher, SignedTokenCodec
from .temporal import db_now


@dataclass(frozen=True)
class AssetReference:
    asset_id: str
    sha256: str
    byte_count: int
    media_type: str
    original_name: str
    classification: str
    source_class: str
    authority_class: str


class ContentAddressedStore(Protocol):
    cipher: EnvelopeCipher

    def storage_key(self, digest: str) -> str: ...
    def write_bytes(self, digest: str, data: bytes) -> dict[str, Any]: ...
    def read_bytes(self, digest: str) -> bytes: ...
    def read_metadata(self, digest: str) -> dict[str, Any]: ...
    def delete(self, digest: str) -> None: ...
    def rotate_envelope_key(self, new_cipher: EnvelopeCipher) -> dict[str, Any]: ...
    def copy_to(self, destination: Path) -> None: ...
    def probe(self) -> None: ...


def _validate_digest(digest: str) -> None:
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValidationError("HASH_INVALID", "content hash must be lowercase SHA-256")


class LocalContentAddressedStore:
    def __init__(self, root: Path, cipher: EnvelopeCipher) -> None:
        self.root = root
        self.cipher = cipher
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, digest: str) -> Path:
        _validate_digest(digest)
        return self.root / digest[:2] / digest[2:4] / f"{digest}.enc"

    def metadata_path_for(self, digest: str) -> Path:
        return self.path_for(digest).with_suffix(".meta.json")

    def storage_key(self, digest: str) -> str:
        return str(self.path_for(digest).relative_to(self.root))

    def write_bytes(self, digest: str, data: bytes) -> dict[str, Any]:
        if sha256_bytes(data) != digest:
            raise ValidationError("CONTENT_HASH_MISMATCH", "payload does not match requested content hash")
        destination = self.path_for(digest)
        metadata_path = self.metadata_path_for(digest)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and metadata_path.exists():
            existing = self.read_bytes(digest)
            if existing != data:
                raise ConflictError("CAS_COLLISION", "existing object does not match content hash")
            return json.loads(metadata_path.read_text())
        ciphertext, metadata = self.cipher.encrypt(data, aad=digest.encode())
        fd, temp_name = tempfile.mkstemp(prefix=f".{digest}.", dir=destination.parent)
        metadata_fd, metadata_temp_name = tempfile.mkstemp(prefix=f".{digest}.meta.", dir=destination.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(ciphertext)
                handle.flush()
                os.fsync(handle.fileno())
            with os.fdopen(metadata_fd, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(metadata, sort_keys=True, indent=2) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, destination)
            os.replace(metadata_temp_name, metadata_path)
            _fsync_directory(destination.parent)
        finally:
            for candidate in (temp_name, metadata_temp_name):
                if os.path.exists(candidate):
                    os.unlink(candidate)
        return metadata

    def read_metadata(self, digest: str) -> dict[str, Any]:
        metadata_path = self.metadata_path_for(digest)
        if not metadata_path.exists():
            raise NotFoundError("content_object", digest)
        return json.loads(metadata_path.read_text())

    def read_bytes(self, digest: str) -> bytes:
        path = self.path_for(digest)
        if not path.exists():
            raise NotFoundError("content_object", digest)
        metadata = self.read_metadata(digest)
        plaintext = self.cipher.decrypt(path.read_bytes(), metadata, aad=digest.encode())
        if sha256_bytes(plaintext) != digest:
            raise ValidationError("OBJECT_INTEGRITY_FAILED", "decrypted object does not match its content hash")
        return plaintext

    def delete(self, digest: str) -> None:
        self.path_for(digest).unlink(missing_ok=True)
        self.metadata_path_for(digest).unlink(missing_ok=True)

    def rotate_envelope_key(self, new_cipher: EnvelopeCipher) -> dict[str, Any]:
        old_key_id = self.cipher.key_id
        object_count = 0
        ciphertext_before: dict[str, str] = {}
        for path in sorted(self.root.rglob("*.enc")):
            digest = path.stem
            ciphertext_before[digest] = sha256_file(path)
            metadata_path = path.with_suffix(".meta.json")
            metadata = json.loads(metadata_path.read_text())
            replacement = self.cipher.rewrap(metadata, aad=digest.encode(), new_cipher=new_cipher)
            metadata_path.write_text(json.dumps(replacement, sort_keys=True, indent=2) + "\n")
            object_count += 1
        self.cipher = new_cipher
        unchanged = all(sha256_file(self.path_for(digest)) == prior for digest, prior in ciphertext_before.items())
        return {
            "old_key_id": old_key_id,
            "new_key_id": new_cipher.key_id,
            "object_count": object_count,
            "ciphertext_unchanged": unchanged,
        }

    def copy_to(self, destination: Path) -> None:
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(self.root, destination)

    def probe(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        probe = self.root / ".readiness-probe"
        probe.write_bytes(b"ready")
        with probe.open("rb") as handle:
            if handle.read() != b"ready":
                raise ValidationError("OBJECT_STORE_PROBE_FAILED", "object-store readiness probe did not round trip")
        probe.unlink(missing_ok=True)


class S3ContentAddressedStore:
    """S3-compatible immutable encrypted CAS.

    The plaintext hash is the stable content identity. The object body contains only
    client-side AES-GCM ciphertext. Envelope metadata is atomically attached as S3 user
    metadata, avoiding a two-object commit race. Optional SSE-KMS provides a second
    storage-layer envelope for AWS profiles.
    """

    _ENVELOPE_METADATA = "sip-envelope-b64"

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str,
        cipher: EnvelopeCipher,
        client: Any,
        kms_key_id: str | None = None,
    ) -> None:
        if not bucket:
            raise ValueError("S3 bucket is required")
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.cipher = cipher
        self.client = client
        self.kms_key_id = kms_key_id

    def key_for(self, digest: str) -> str:
        _validate_digest(digest)
        suffix = f"objects/{digest[:2]}/{digest[2:4]}/{digest}.enc"
        return f"{self.prefix}/{suffix}" if self.prefix else suffix

    def storage_key(self, digest: str) -> str:
        return f"s3://{self.bucket}/{self.key_for(digest)}"

    def _put_options(self) -> dict[str, Any]:
        if not self.kms_key_id:
            return {}
        return {
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": self.kms_key_id,
            "BucketKeyEnabled": True,
        }

    @staticmethod
    def _encode_metadata(metadata: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(canonical_json(metadata)).decode("ascii")

    @staticmethod
    def _decode_metadata(metadata: dict[str, str]) -> dict[str, Any]:
        encoded = metadata.get(S3ContentAddressedStore._ENVELOPE_METADATA)
        if not encoded:
            raise ValidationError("OBJECT_ENVELOPE_MISSING", "S3 object has no SIP envelope metadata")
        try:
            return json.loads(base64.urlsafe_b64decode(encoded.encode("ascii")))
        except Exception as exc:
            raise ValidationError("OBJECT_ENVELOPE_INVALID", "S3 envelope metadata is malformed") from exc

    @staticmethod
    def _error_code(exc: ClientError) -> str:
        return str(exc.response.get("Error", {}).get("Code", ""))

    @classmethod
    def _is_missing(cls, exc: ClientError) -> bool:
        return cls._error_code(exc) in {"404", "NoSuchKey", "NotFound"}

    @classmethod
    def _is_precondition(cls, exc: ClientError) -> bool:
        return cls._error_code(exc) in {"412", "PreconditionFailed", "ConditionalRequestConflict"}

    def read_metadata(self, digest: str) -> dict[str, Any]:
        key = self.key_for(digest)
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if self._is_missing(exc):
                raise NotFoundError("content_object", digest) from exc
            raise
        return self._decode_metadata(response.get("Metadata", {}))

    def write_bytes(self, digest: str, data: bytes) -> dict[str, Any]:
        if sha256_bytes(data) != digest:
            raise ValidationError("CONTENT_HASH_MISMATCH", "payload does not match requested content hash")
        try:
            metadata = self.read_metadata(digest)
        except NotFoundError:
            metadata = None
        if metadata is not None:
            if self.read_bytes(digest) != data:
                raise ConflictError("CAS_COLLISION", "existing S3 object does not match content hash")
            return metadata
        ciphertext, metadata = self.cipher.encrypt(data, aad=digest.encode())
        key = self.key_for(digest)
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=ciphertext,
                ContentType="application/octet-stream",
                Metadata={
                    self._ENVELOPE_METADATA: self._encode_metadata(metadata),
                    "sip-plaintext-sha256": digest,
                    "sip-format": "encrypted-cas-v1",
                },
                IfNoneMatch="*",
                **self._put_options(),
            )
        except ClientError as exc:
            if not self._is_precondition(exc):
                raise
            # A concurrent immutable writer won. Retry the complete integrity check
            # because the winner's body and metadata become visible atomically.
            for _ in range(10):
                try:
                    existing = self.read_bytes(digest)
                    if existing != data:
                        raise ConflictError("CAS_COLLISION", "concurrent S3 object does not match content hash")
                    return self.read_metadata(digest)
                except NotFoundError:
                    time.sleep(0.05)
            raise ConflictError("CAS_COMMIT_INCOMPLETE", "concurrent S3 content commit did not become visible") from exc
        return metadata

    def _get_ciphertext(self, digest: str) -> tuple[bytes, dict[str, Any]]:
        key = self.key_for(digest)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if self._is_missing(exc):
                raise NotFoundError("content_object", digest) from exc
            raise
        body = response["Body"].read()
        return body, self._decode_metadata(response.get("Metadata", {}))

    def read_bytes(self, digest: str) -> bytes:
        ciphertext, metadata = self._get_ciphertext(digest)
        plaintext = self.cipher.decrypt(ciphertext, metadata, aad=digest.encode())
        if sha256_bytes(plaintext) != digest:
            raise ValidationError("OBJECT_INTEGRITY_FAILED", "decrypted S3 object does not match its content hash")
        return plaintext

    def delete(self, digest: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self.key_for(digest))

    def _iter_keys(self) -> list[str]:
        base = f"{self.prefix}/objects/" if self.prefix else "objects/"
        paginator = self.client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=base):
            keys.extend(item["Key"] for item in page.get("Contents", []) if item["Key"].endswith(".enc"))
        return sorted(keys)

    @staticmethod
    def _digest_from_key(key: str) -> str:
        digest = Path(key).stem
        _validate_digest(digest)
        return digest

    def rotate_envelope_key(self, new_cipher: EnvelopeCipher) -> dict[str, Any]:
        old_key_id = self.cipher.key_id
        unchanged = True
        count = 0
        for key in self._iter_keys():
            digest = self._digest_from_key(key)
            ciphertext, metadata = self._get_ciphertext(digest)
            before = sha256_bytes(ciphertext)
            replacement = self.cipher.rewrap(metadata, aad=digest.encode(), new_cipher=new_cipher)
            self.client.copy_object(
                Bucket=self.bucket,
                Key=key,
                CopySource={"Bucket": self.bucket, "Key": key},
                MetadataDirective="REPLACE",
                ContentType="application/octet-stream",
                Metadata={
                    self._ENVELOPE_METADATA: self._encode_metadata(replacement),
                    "sip-plaintext-sha256": digest,
                    "sip-format": "encrypted-cas-v1",
                },
                **self._put_options(),
            )
            after_ciphertext, _ = self._get_ciphertext(digest)
            unchanged = unchanged and before == sha256_bytes(after_ciphertext)
            count += 1
        if not unchanged:
            raise ValidationError("KEY_ROTATION_CIPHERTEXT_CHANGED", "S3 envelope rotation changed application ciphertext")
        self.cipher = new_cipher
        return {
            "old_key_id": old_key_id,
            "new_key_id": new_cipher.key_id,
            "object_count": count,
            "ciphertext_unchanged": True,
        }

    def copy_to(self, destination: Path) -> None:
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        manifest: list[dict[str, Any]] = []
        for key in self._iter_keys():
            digest = self._digest_from_key(key)
            ciphertext, metadata = self._get_ciphertext(digest)
            target = destination / digest[:2] / digest[2:4] / f"{digest}.enc"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(ciphertext)
            target.with_suffix(".meta.json").write_text(json.dumps(metadata, sort_keys=True, indent=2) + "\n")
            manifest.append({"digest": digest, "source_key": key, "ciphertext_sha256": sha256_bytes(ciphertext)})
        (destination / "_s3-export-manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")

    def probe(self) -> None:
        key = f"{self.prefix + '/' if self.prefix else ''}_health/{os.urandom(8).hex()}"
        payload = b"ready"
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=payload,
            ContentType="application/octet-stream",
            **self._put_options(),
        )
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        if response["Body"].read() != payload:
            raise ValidationError("OBJECT_STORE_PROBE_FAILED", "S3 readiness probe did not round trip")
        self.client.delete_object(Bucket=self.bucket, Key=key)


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class AssetService:
    def __init__(
        self,
        database: Database,
        store: ContentAddressedStore,
        audit: AuditService,
        token_codec: SignedTokenCodec,
        *,
        multipart_root: Path | None = None,
    ) -> None:
        self.database = database
        self.store = store
        self.audit = audit
        self.token_codec = token_codec
        self.multipart_root = multipart_root or Path("runtime/multipart")
        self.multipart_root.mkdir(parents=True, exist_ok=True)
        self.deployment: Any | None = None

    def set_deployment_service(self, deployment: Any) -> None:
        self.deployment = deployment

    def ingest_bytes(
        self,
        *,
        tenant_id: str,
        project_id: str,
        data: bytes,
        media_type: str,
        original_name: str,
        classification: Classification,
        retention_class: str,
        source_class: SourceClass,
        authority_class: AuthorityClass,
        provenance: ProvenanceRef,
        actor_id: str,
        asset_id: str | None = None,
        deployment_region: str | None = None,
        asset_class: str = "generic_asset",
    ) -> AssetReference:
        if self.deployment is not None:
            self.deployment.authorize_if_configured(
                tenant_id=tenant_id,
                project_id=project_id,
                admission_type="asset_upload",
                region=deployment_region,
                request={"asset_class": asset_class, "byte_count": len(data), "media_type": media_type},
                actor_id=actor_id,
            )
        digest = sha256_bytes(data)
        metadata = self.store.write_bytes(digest, data)
        # A storage API acknowledgement is not publication evidence. Read the immutable
        # object back through the configured backend and verify plaintext identity before
        # any database object or tenant/project reference becomes visible.
        persisted = self.store.read_bytes(digest)
        persisted_digest = sha256_bytes(persisted)
        if persisted_digest != digest or persisted != data:
            raise ValidationError(
                "OBJECT_POST_WRITE_VERIFICATION_FAILED",
                "object-store bytes failed post-write integrity verification",
                {"expected_sha256": digest, "actual_sha256": persisted_digest},
            )
        asset_id = asset_id or new_uuid()
        with self.database.session() as session:
            project = session.get(ProjectRow, project_id)
            if not project or project.tenant_id != tenant_id:
                raise NotFoundError("project", project_id)
            existing_ref = session.get(AssetRefRow, asset_id)
            if existing_ref is not None:
                if (
                    existing_ref.tenant_id != tenant_id
                    or existing_ref.project_id != project_id
                    or existing_ref.sha256 != digest
                    or existing_ref.tombstoned_at is not None
                ):
                    raise ConflictError(
                        "ASSET_IDEMPOTENCY_CONFLICT",
                        "asset identifier is already bound to different content or scope",
                        {"asset_id": asset_id},
                    )
                existing_object = session.get(AssetRow, digest)
                if existing_object is None:
                    raise ValidationError("OBJECT_REFERENCE_BROKEN", "asset object metadata is missing")
                return AssetReference(
                    asset_id=existing_ref.asset_id,
                    sha256=existing_ref.sha256,
                    byte_count=existing_object.byte_count,
                    media_type=existing_object.media_type,
                    original_name=existing_ref.original_name,
                    classification=existing_ref.classification,
                    source_class=existing_ref.source_class,
                    authority_class=existing_ref.authority_class,
                )
            obj = session.get(AssetRow, digest)
            if obj is None:
                obj = AssetRow(
                    sha256=digest,
                    byte_count=len(data),
                    media_type=media_type,
                    storage_key=self.store.storage_key(digest),
                    encryption_metadata=metadata,
                )
                session.add(obj)
                # Flush the content object before inserting a tenant/project reference.
                # The ORM models deliberately avoid cross-tenant relationships, so SQLAlchemy
                # cannot infer insert ordering from an object relationship alone.
                session.flush()
            elif obj.byte_count != len(data):
                raise ConflictError("CAS_METADATA_CONFLICT", "stored object metadata conflicts with payload")
            session.add(
                AssetRefRow(
                    asset_id=asset_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    sha256=digest,
                    original_name=original_name,
                    classification=classification.value,
                    retention_class=retention_class,
                    source_class=source_class.value,
                    authority_class=authority_class.value,
                    provenance_json=provenance.model_dump(mode="json"),
                    created_by=actor_id,
                )
            )
            session.flush()
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="asset:ingest",
                resource_type="asset",
                resource_id=asset_id,
                outcome="allowed",
                details={"sha256": digest, "bytes": len(data), "classification": classification.value},
                session=session,
            )
        return AssetReference(
            asset_id=asset_id,
            sha256=digest,
            byte_count=len(data),
            media_type=media_type,
            original_name=original_name,
            classification=classification.value,
            source_class=source_class.value,
            authority_class=authority_class.value,
        )

    def get(self, tenant_id: str, project_id: str, asset_id: str) -> AssetReference:
        with self.database.session() as session:
            ref = session.get(AssetRefRow, asset_id)
            if not ref or ref.tenant_id != tenant_id or ref.project_id != project_id or ref.tombstoned_at is not None:
                raise NotFoundError("asset", asset_id)
            obj = session.get(AssetRow, ref.sha256)
            if obj is None:
                raise ValidationError("OBJECT_REFERENCE_BROKEN", "asset object metadata is missing")
            return AssetReference(
                asset_id=ref.asset_id,
                sha256=ref.sha256,
                byte_count=obj.byte_count,
                media_type=obj.media_type,
                original_name=ref.original_name,
                classification=ref.classification,
                source_class=ref.source_class,
                authority_class=ref.authority_class,
            )

    def read(self, tenant_id: str, project_id: str, asset_id: str, *, actor_id: str) -> bytes:
        ref = self.get(tenant_id, project_id, asset_id)
        payload = self.store.read_bytes(ref.sha256)
        self.audit.append(
            tenant_id=tenant_id,
            project_id=project_id,
            actor_id=actor_id,
            action="asset:read",
            resource_type="asset",
            resource_id=asset_id,
            outcome="allowed",
            details={"sha256": ref.sha256},
        )
        return payload

    def issue_read_token(self, tenant_id: str, project_id: str, asset_id: str, *, subject_id: str, ttl_seconds: int = 300) -> str:
        if ttl_seconds <= 0 or ttl_seconds > 3600:
            raise ValidationError("SIGNED_URL_TTL_INVALID", "signed asset token TTL must be between 1 and 3600 seconds")
        asset = self.get(tenant_id, project_id, asset_id)
        token = self.token_codec.encode(
            {"sub": subject_id, "tenant_id": tenant_id, "project_id": project_id, "asset_id": asset_id, "action": "asset:read"},
            ttl_seconds=ttl_seconds,
        )
        self.audit.append(
            tenant_id=tenant_id,
            project_id=project_id,
            actor_id=subject_id,
            action="asset:read_token_issue",
            resource_type="asset",
            resource_id=asset_id,
            outcome="allowed",
            details={
                "action": "asset:read",
                "ttl_seconds": ttl_seconds,
                "classification": asset.classification,
            },
        )
        return token

    def read_with_token(self, token: str) -> bytes:
        claims = self.token_codec.decode(token)
        if claims.get("action") != "asset:read":
            raise ValidationError("TOKEN_ACTION_INVALID", "token is not authorized for asset reads")
        return self.read(claims["tenant_id"], claims["project_id"], claims["asset_id"], actor_id=claims["sub"])

    def tombstone(self, tenant_id: str, project_id: str, asset_id: str, *, actor_id: str, dry_run: bool = True) -> dict[str, Any]:
        with self.database.session() as session:
            ref = session.get(AssetRefRow, asset_id)
            if not ref or ref.tenant_id != tenant_id or ref.project_id != project_id:
                raise NotFoundError("asset", asset_id)
            if ref.legal_hold:
                raise ConflictError("LEGAL_HOLD_ACTIVE", "asset is under legal hold")
            others = int(
                session.scalar(
                    select(func.count())
                    .select_from(AssetRefRow)
                    .where(AssetRefRow.sha256 == ref.sha256, AssetRefRow.asset_id != asset_id, AssetRefRow.tombstoned_at.is_(None))
                )
                or 0
            )
            result = {
                "asset_id": asset_id,
                "sha256": ref.sha256,
                "other_active_references": others,
                "physical_object_will_be_removed": others == 0,
                "dry_run": dry_run,
            }
            if dry_run:
                return result
            if ref.tombstoned_at is None:
                ref.tombstoned_at = db_now()
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="asset:tombstone",
                resource_type="asset",
                resource_id=asset_id,
                outcome="allowed",
                details=result,
                session=session,
            )
            digest = ref.sha256
        if result["physical_object_will_be_removed"]:
            self.store.delete(digest)
        return result

    def begin_multipart(
        self,
        *,
        tenant_id: str,
        project_id: str,
        expected_sha256: str,
        expected_bytes: int,
        media_type: str,
        metadata: dict[str, Any],
        actor_id: str,
        deployment_region: str | None = None,
        asset_class: str = "generic_asset",
    ) -> str:
        if expected_bytes < 0:
            raise ValidationError("UPLOAD_SIZE_INVALID", "expected upload size cannot be negative")
        if len(expected_sha256) != 64 or any(character not in "0123456789abcdef" for character in expected_sha256):
            raise ValidationError("UPLOAD_HASH_INVALID", "expected upload hash must be lowercase SHA-256")
        if self.deployment is not None:
            self.deployment.authorize_if_configured(
                tenant_id=tenant_id,
                project_id=project_id,
                admission_type="asset_upload",
                region=deployment_region,
                request={"asset_class": asset_class, "byte_count": expected_bytes, "media_type": media_type, "multipart": True},
                actor_id=actor_id,
            )
        metadata = {**metadata, "deployment_region": deployment_region, "asset_class": asset_class}
        upload_id = new_uuid()
        with self.database.session() as session:
            project = session.get(ProjectRow, project_id)
            if not project or project.tenant_id != tenant_id:
                raise NotFoundError("project", project_id)
            session.add(
                MultipartUploadRow(
                    upload_id=upload_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    expected_sha256=expected_sha256,
                    expected_bytes=expected_bytes,
                    media_type=media_type,
                    metadata_json=metadata,
                    created_by=actor_id,
                )
            )
        (self.multipart_root / upload_id).mkdir(parents=True, exist_ok=False)
        return upload_id

    def multipart_status(self, upload_id: str, *, tenant_id: str, project_id: str | None = None) -> dict[str, Any]:
        """Return only persisted, hash-verified chunks so a client can resume safely.

        The lookup is deliberately scoped before any upload metadata is returned.  A
        caller from another tenant receives the same not-found response as an unknown
        upload and cannot use upload IDs as an existence oracle.
        """
        with self.database.session() as session:
            upload = session.get(MultipartUploadRow, upload_id)
            if (
                upload is None
                or upload.tenant_id != tenant_id
                or (project_id is not None and upload.project_id != project_id)
            ):
                raise NotFoundError("multipart_upload", upload_id)
            chunks = list(
                session.scalars(
                    select(MultipartChunkRow)
                    .where(MultipartChunkRow.upload_id == upload_id)
                    .order_by(MultipartChunkRow.part_number)
                )
            )
            verified_parts: list[dict[str, Any]] = []
            for chunk in chunks:
                path = Path(chunk.path)
                if not path.is_file():
                    raise ConflictError(
                        "UPLOAD_PART_BYTES_MISSING",
                        "persisted multipart metadata references missing chunk bytes",
                        {"part_number": chunk.part_number},
                    )
                actual_hash = sha256_file(path)
                actual_bytes = path.stat().st_size
                if actual_hash != chunk.sha256 or actual_bytes != chunk.byte_count:
                    raise ValidationError(
                        "UPLOAD_PART_INTEGRITY_FAILED",
                        "persisted multipart chunk failed resume integrity verification",
                        {"part_number": chunk.part_number},
                    )
                verified_parts.append(
                    {
                        "part_number": chunk.part_number,
                        "sha256": chunk.sha256,
                        "bytes": chunk.byte_count,
                    }
                )
            return {
                "upload_id": upload.upload_id,
                "tenant_id": upload.tenant_id,
                "project_id": upload.project_id,
                "state": upload.state,
                "expected_sha256": upload.expected_sha256,
                "expected_bytes": upload.expected_bytes,
                "media_type": upload.media_type,
                "verified_parts": verified_parts,
                "verified_bytes": sum(item["bytes"] for item in verified_parts),
                "next_part_number": (verified_parts[-1]["part_number"] + 1) if verified_parts else 1,
            }

    def put_part(
        self,
        upload_id: str,
        part_number: int,
        data: bytes,
        expected_sha256: str,
        *,
        tenant_id: str,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        if part_number < 1:
            raise ValidationError("UPLOAD_PART_INVALID", "part number must be positive")
        digest = sha256_bytes(data)
        if digest != expected_sha256:
            raise ValidationError("UPLOAD_PART_HASH_MISMATCH", "multipart chunk hash mismatch")
        part_dir = self.multipart_root / upload_id
        if not part_dir.exists():
            raise NotFoundError("multipart_upload", upload_id)
        path = part_dir / f"{part_number:08d}.part"
        with self.database.session() as session:
            upload = session.get(MultipartUploadRow, upload_id)
            if (
                upload is None
                or upload.tenant_id != tenant_id
                or (project_id is not None and upload.project_id != project_id)
            ):
                raise NotFoundError("multipart_upload", upload_id)
            if upload.state != "open":
                raise ConflictError("UPLOAD_NOT_OPEN", "multipart upload is not open")
            prior = session.scalar(select(MultipartChunkRow).where(MultipartChunkRow.upload_id == upload_id, MultipartChunkRow.part_number == part_number))
            if prior:
                if prior.sha256 != digest or prior.byte_count != len(data):
                    raise ConflictError("UPLOAD_PART_CONFLICT", "part metadata conflicts")
                if not path.is_file() or sha256_file(path) != digest:
                    raise ValidationError("UPLOAD_PART_INTEGRITY_FAILED", "existing multipart chunk bytes failed integrity verification")
                return {"part_number": part_number, "sha256": digest, "bytes": len(data), "already_verified": True}
            else:
                if path.exists() and sha256_file(path) != digest:
                    raise ConflictError("UPLOAD_PART_CONFLICT", "part number already exists with different bytes")
                temporary = path.with_suffix(".part.tmp")
                temporary.write_bytes(data)
                if sha256_file(temporary) != digest:
                    temporary.unlink(missing_ok=True)
                    raise ValidationError("UPLOAD_PART_WRITE_FAILED", "multipart chunk changed during durable write")
                temporary.replace(path)
                session.add(
                    MultipartChunkRow(
                        chunk_id=new_uuid(), upload_id=upload_id, part_number=part_number, sha256=digest, byte_count=len(data), path=str(path)
                    )
                )
        return {"part_number": part_number, "sha256": digest, "bytes": len(data), "already_verified": False}

    def complete_multipart(
        self,
        upload_id: str,
        *,
        original_name: str,
        classification: Classification,
        retention_class: str,
        source_class: SourceClass,
        authority_class: AuthorityClass,
        provenance: ProvenanceRef,
        actor_id: str,
        tenant_id: str,
        project_id: str | None = None,
    ) -> AssetReference:
        with self.database.session() as session:
            upload = session.get(MultipartUploadRow, upload_id)
            if (
                upload is None
                or upload.tenant_id != tenant_id
                or (project_id is not None and upload.project_id != project_id)
            ):
                raise NotFoundError("multipart_upload", upload_id)
            if upload.state != "open":
                raise ConflictError("UPLOAD_NOT_OPEN", "multipart upload is not open")
            chunks = list(session.scalars(select(MultipartChunkRow).where(MultipartChunkRow.upload_id == upload_id).order_by(MultipartChunkRow.part_number)))
            if not chunks:
                raise ValidationError("UPLOAD_EMPTY", "multipart upload has no chunks")
            if [c.part_number for c in chunks] != list(range(1, len(chunks) + 1)):
                raise ValidationError("UPLOAD_PART_GAP", "multipart parts must be contiguous starting at one")
            tenant_id, project_id, media_type = upload.tenant_id, upload.project_id, upload.media_type
            expected_digest, expected_bytes = upload.expected_sha256, upload.expected_bytes
            deployment_region = upload.metadata_json.get("deployment_region")
            asset_class = str(upload.metadata_json.get("asset_class", "generic_asset"))
        data = b"".join(Path(chunk.path).read_bytes() for chunk in chunks)
        if len(data) != expected_bytes or sha256_bytes(data) != expected_digest:
            raise ValidationError("UPLOAD_FINAL_INTEGRITY_FAILED", "multipart payload does not match expected size and hash")
        result = self.ingest_bytes(
            tenant_id=tenant_id,
            project_id=project_id,
            data=data,
            media_type=media_type,
            original_name=original_name,
            classification=classification,
            retention_class=retention_class,
            source_class=source_class,
            authority_class=authority_class,
            provenance=provenance,
            actor_id=actor_id,
            deployment_region=deployment_region,
            asset_class=asset_class,
        )
        with self.database.session() as session:
            upload = session.get(MultipartUploadRow, upload_id)
            assert upload is not None
            upload.state = "completed"
            upload.completed_at = db_now()
        shutil.rmtree(self.multipart_root / upload_id, ignore_errors=True)
        return result
