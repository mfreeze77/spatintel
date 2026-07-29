"""Fail-closed ZIP and checksum validation for portable vertical packages."""
from __future__ import annotations

import json
import re
import stat
import zipfile
from pathlib import PurePosixPath
from typing import Any, Iterable

from .canonical import merkle_root, sha256_bytes
from .errors import ValidationError

MAX_MEMBER_COUNT = 10_000
MAX_MEMBER_BYTES = 2 * 1024 * 1024 * 1024
MAX_TOTAL_BYTES = 10 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def validate_zip_members(
    infos: Iterable[zipfile.ZipInfo],
    *,
    code_prefix: str,
    max_members: int = MAX_MEMBER_COUNT,
    max_member_bytes: int = MAX_MEMBER_BYTES,
    max_total_bytes: int = MAX_TOTAL_BYTES,
    max_compression_ratio: int = MAX_COMPRESSION_RATIO,
) -> list[str]:
    """Validate a ZIP member list without extracting any bytes.

    Rejects duplicate names, absolute/parent/backslash paths, drive prefixes,
    symlinks and other non-regular Unix member types, oversized expansions, and
    suspicious compression ratios. The returned names are normalized, ordered
    exactly as provided, and safe for direct lookup in the already-open archive.
    """

    items = list(infos)
    if len(items) > max_members:
        raise ValidationError(f"{code_prefix}_MEMBER_COUNT", "archive contains too many members")
    names: list[str] = []
    seen: set[str] = set()
    total = 0
    for info in items:
        raw = info.filename
        normalized = raw.replace("\\", "/")
        path = PurePosixPath(normalized)
        unsafe = (
            raw != normalized
            or not path.parts
            or path.is_absolute()
            or ".." in path.parts
            or any(part in {"", "."} for part in path.parts)
            or (path.parts and ":" in path.parts[0])
            or normalized.endswith("/")
        )
        if unsafe:
            raise ValidationError(f"{code_prefix}_ARCHIVE_UNSAFE", "archive contains an unsafe member path", {"path": raw})
        if normalized in seen:
            raise ValidationError(f"{code_prefix}_ARCHIVE_UNSAFE", "archive contains duplicate members", {"path": normalized})
        seen.add(normalized)
        unix_mode = (info.external_attr >> 16) & 0o177777
        file_type = stat.S_IFMT(unix_mode)
        if file_type not in {0, stat.S_IFREG}:
            raise ValidationError(f"{code_prefix}_ARCHIVE_UNSAFE", "archive contains a non-regular member", {"path": normalized})
        if info.file_size > max_member_bytes:
            raise ValidationError(f"{code_prefix}_MEMBER_TOO_LARGE", "archive member exceeds the configured size limit", {"path": normalized})
        total += info.file_size
        if total > max_total_bytes:
            raise ValidationError(f"{code_prefix}_ARCHIVE_TOO_LARGE", "archive expands beyond the configured total size limit")
        if info.file_size and info.compress_size == 0:
            raise ValidationError(f"{code_prefix}_COMPRESSION_RATIO", "archive member has an invalid compressed size", {"path": normalized})
        if info.compress_size and info.file_size / info.compress_size > max_compression_ratio:
            raise ValidationError(f"{code_prefix}_COMPRESSION_RATIO", "archive member exceeds the configured compression-ratio limit", {"path": normalized})
        names.append(normalized)
    return names


def verify_checksum_manifest(
    archive: zipfile.ZipFile,
    names: Iterable[str],
    *,
    allowed_members: set[str],
    required_members: set[str],
    code_prefix: str,
) -> dict[str, Any]:
    """Verify an exact, complete SHA-256 manifest for a bounded package profile.

    ``checksums.json`` is metadata about the archive and therefore is the only
    member omitted from its own file map. Every other archive member must be
    explicitly permitted by the package profile and covered by the manifest.
    This prevents a valid checksum set for a small subset from blessing
    unchecked scripts, replacement viewers, or other hidden payloads.
    """

    ordered_names = list(names)
    name_set = set(ordered_names)
    findings: list[dict[str, Any]] = []

    missing_required = sorted(required_members - name_set)
    for name in missing_required:
        findings.append({"path": name, "reason": "required_member_missing"})

    unexpected_members = sorted(name_set - allowed_members)
    for name in unexpected_members:
        findings.append({"path": name, "reason": "unexpected_member"})

    manifest: Any = None
    if "checksums.json" not in name_set:
        findings.append({"path": "checksums.json", "reason": "checksum_manifest_missing"})
    else:
        try:
            manifest = json.loads(archive.read("checksums.json"), object_pairs_hook=_strict_json_object)
        except (json.JSONDecodeError, UnicodeDecodeError, KeyError, RuntimeError, ValueError):
            findings.append({"path": "checksums.json", "reason": "checksum_manifest_invalid_json"})

    files: dict[str, str] = {}
    declared_root = ""
    if manifest is not None:
        if not isinstance(manifest, dict):
            findings.append({"path": "checksums.json", "reason": "checksum_manifest_not_object"})
        else:
            if manifest.get("algorithm") != "sha256":
                findings.append({"path": "checksums.json", "reason": "checksum_algorithm_invalid"})
            raw_files = manifest.get("files")
            if not isinstance(raw_files, dict) or not raw_files:
                findings.append({"path": "checksums.json", "reason": "checksum_file_map_empty_or_invalid"})
            else:
                for raw_name, raw_digest in raw_files.items():
                    if not isinstance(raw_name, str) or not raw_name:
                        findings.append({"path": "checksums.json", "reason": "checksum_path_invalid"})
                        continue
                    if not isinstance(raw_digest, str) or _SHA256_RE.fullmatch(raw_digest) is None:
                        findings.append({"path": raw_name, "reason": "checksum_digest_invalid"})
                        continue
                    files[raw_name] = raw_digest
            raw_root = manifest.get("root_hash")
            if not isinstance(raw_root, str) or _SHA256_RE.fullmatch(raw_root) is None:
                findings.append({"path": "checksums.json", "reason": "checksum_root_invalid"})
            else:
                declared_root = raw_root

    expected_coverage = name_set - {"checksums.json"}
    declared_coverage = set(files)
    for name in sorted(expected_coverage - declared_coverage):
        findings.append({"path": name, "reason": "member_unchecked"})
    for name in sorted(declared_coverage - expected_coverage):
        findings.append({"path": name, "reason": "checksum_entry_without_member"})
    if "checksums.json" in declared_coverage:
        findings.append({"path": "checksums.json", "reason": "checksum_manifest_self_reference"})

    for name, expected in sorted(files.items()):
        if name not in name_set:
            continue
        try:
            actual = sha256_bytes(archive.read(name))
        except (KeyError, RuntimeError):
            findings.append({"path": name, "reason": "member_unreadable"})
            continue
        if actual != expected:
            findings.append({"path": name, "reason": "hash_mismatch"})

    actual_root = merkle_root(sorted(files.items())) if files else ""
    if declared_root and actual_root != declared_root:
        findings.append({"path": "checksums.json", "reason": "root_mismatch"})

    return {
        "valid": not findings,
        "findings": findings,
        "root_hash": actual_root,
        "algorithm": "sha256",
        "checked_members": len(files),
        "archive_members": len(ordered_names),
    }
