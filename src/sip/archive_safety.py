"""Fail-closed ZIP metadata and path validation for portable vertical packages."""
from __future__ import annotations

import stat
import zipfile
from pathlib import PurePosixPath
from typing import Iterable

from .errors import ValidationError

MAX_MEMBER_COUNT = 10_000
MAX_MEMBER_BYTES = 2 * 1024 * 1024 * 1024
MAX_TOTAL_BYTES = 10 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200


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
