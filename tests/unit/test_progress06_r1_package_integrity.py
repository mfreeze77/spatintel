from __future__ import annotations

import json
from pathlib import Path
import stat
import zipfile

import pytest

from sip.canonical import merkle_root, sha256_bytes
from sip.construction import ConstructionService, OWNER_HANDOFF_MEMBERS
from sip.liveforever import LiveForeverService, PRESERVATION_MEMBERS


def _info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def _write_package(
    path: Path,
    members: set[str],
    *,
    extra: dict[str, bytes] | None = None,
    omit_checksums_for: set[str] | None = None,
    algorithm: str = "sha256",
    digest_override: dict[str, str] | None = None,
    root_override: str | None = None,
    empty_manifest: bool = False,
) -> None:
    payloads = {
        name: (f"synthetic payload for {name}\n").encode()
        for name in sorted(members - {"checksums.json"})
    }
    payloads.update(extra or {})
    checks = {
        name: sha256_bytes(payload)
        for name, payload in sorted(payloads.items())
        if name not in (omit_checksums_for or set())
    }
    checks.update(digest_override or {})
    manifest = {
        "algorithm": algorithm,
        "files": {} if empty_manifest else checks,
        "root_hash": root_override if root_override is not None else merkle_root(sorted(checks.items())),
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in sorted(payloads.items()):
            archive.writestr(_info(name), payload)
        archive.writestr(_info("checksums.json"), json.dumps(manifest, sort_keys=True).encode())


CASES = [
    ("construction", ConstructionService.verify_owner_handoff, OWNER_HANDOFF_MEMBERS),
    ("liveforever", LiveForeverService.verify_preservation_release, PRESERVATION_MEMBERS),
]


@pytest.mark.unit
@pytest.mark.parametrize("label,verifier,members", CASES)
def test_progress06_r1_vertical_verifier_accepts_only_complete_exact_sha256_manifest(
    tmp_path: Path,
    label: str,
    verifier,
    members: set[str],
) -> None:
    """REQ: CONHAND-006, LIFPRESV-001 every permitted member is SHA256-covered and exact package profiles verify."""
    path = tmp_path / f"{label}-valid.zip"
    _write_package(path, members)
    result = verifier(path)
    assert result["valid"] is True
    assert result["findings"] == []
    assert result["checked_members"] == len(members) - 1
    assert result["archive_members"] == len(members)
    assert len(result["root_hash"]) == 64
    assert len(result["zip_sha256"]) == 64


@pytest.mark.unit
@pytest.mark.parametrize("label,verifier,members", CASES)
def test_progress06_r1_vertical_verifier_rejects_unexpected_member_even_when_checksummed(
    tmp_path: Path,
    label: str,
    verifier,
    members: set[str],
) -> None:
    """REQ: CONHAND-006, LIFPRESV-001 unexpected executable or payload members fail closed even when their digest is declared."""
    path = tmp_path / f"{label}-evil.zip"
    _write_package(path, members, extra={"evil.js": b"alert('unexpected')"})
    result = verifier(path)
    assert result["valid"] is False
    assert {item["reason"] for item in result["findings"]} >= {"unexpected_member"}


@pytest.mark.unit
@pytest.mark.parametrize("label,verifier,members", CASES)
def test_progress06_r1_vertical_verifier_rejects_empty_partial_and_malformed_manifests(
    tmp_path: Path,
    label: str,
    verifier,
    members: set[str],
) -> None:
    """REQ: CONHAND-006, LIFPRESV-001 empty, partial, unsupported-algorithm, and malformed checksum manifests fail closed."""
    first_member = sorted(members - {"checksums.json"})[0]
    variants = [
        ("empty", {"empty_manifest": True, "root_override": "0" * 64}, {"checksum_file_map_empty_or_invalid", "member_unchecked"}),
        ("partial", {"omit_checksums_for": {first_member}}, {"member_unchecked"}),
        ("algorithm", {"algorithm": "md5"}, {"checksum_algorithm_invalid"}),
        ("digest", {"digest_override": {first_member: "not-a-sha256"}}, {"checksum_digest_invalid", "member_unchecked"}),
        ("root", {"root_override": "g" * 64}, {"checksum_root_invalid"}),
    ]
    for suffix, kwargs, expected_reasons in variants:
        path = tmp_path / f"{label}-{suffix}.zip"
        _write_package(path, members, **kwargs)
        result = verifier(path)
        assert result["valid"] is False, (suffix, result)
        reasons = {item["reason"] for item in result["findings"]}
        assert reasons & expected_reasons, (suffix, reasons)


@pytest.mark.unit
@pytest.mark.parametrize("label,verifier,members", CASES)
def test_progress06_r1_vertical_verifier_rejects_tampered_required_content(
    tmp_path: Path,
    label: str,
    verifier,
    members: set[str],
) -> None:
    """REQ: CONHAND-006, LIFPRESV-001 altered required content is detected against the retained checksum manifest."""
    path = tmp_path / f"{label}-tampered.zip"
    _write_package(path, members)
    with zipfile.ZipFile(path) as original:
        payloads = {name: original.read(name) for name in original.namelist()}
    target = sorted(members - {"checksums.json"})[0]
    payloads[target] = b"tampered content"
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in sorted(payloads.items()):
            archive.writestr(_info(name), payload)
    result = verifier(path)
    assert result["valid"] is False
    assert any(item["path"] == target and item["reason"] == "hash_mismatch" for item in result["findings"])


@pytest.mark.unit
@pytest.mark.parametrize("label,verifier,members", CASES)
def test_progress06_r1_vertical_verifier_rejects_duplicate_checksum_manifest_keys(
    tmp_path: Path,
    label: str,
    verifier,
    members: set[str],
) -> None:
    """REQ: CONHAND-006, LIFPRESV-001 duplicate checksum-manifest keys cannot shadow governed package identity."""
    path = tmp_path / f"{label}-duplicate-key.zip"
    payloads = {name: f"synthetic payload for {name}\n".encode() for name in sorted(members - {"checksums.json"})}
    checks = {name: sha256_bytes(payload) for name, payload in sorted(payloads.items())}
    root = merkle_root(sorted(checks.items()))
    files_json = json.dumps(checks, sort_keys=True)
    duplicate_manifest = (
        '{"algorithm":"sha256","files":' + files_json + ',"files":' + files_json + ',"root_hash":"' + root + '"}'
    ).encode()
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in sorted(payloads.items()):
            archive.writestr(_info(name), payload)
        archive.writestr(_info("checksums.json"), duplicate_manifest)
    result = verifier(path)
    assert result["valid"] is False
    assert any(item["reason"] == "checksum_manifest_invalid_json" for item in result["findings"])
