"""Shared deterministic checkpoint packaging primitives."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
MANIFEST_PATH = "CHECKPOINT_CONTENT_MANIFEST.json"


@dataclass(frozen=True)
class CheckpointFileRecord:
    path: str
    size: int
    sha256: str
    mode: str
    kind: str = "file"


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def pretty_json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_relative_path(value: str) -> str:
    if not value or "\x00" in value or "\\" in value:
        raise ValueError(f"unsafe ZIP path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe ZIP path: {value!r}")
    return path.as_posix()


def stage_records(stage_root: Path, *, excluded: Iterable[str] = (MANIFEST_PATH,)) -> list[CheckpointFileRecord]:
    excluded_set = set(excluded)
    records: list[CheckpointFileRecord] = []
    for path in sorted(stage_root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"checkpoint staging cannot contain symlinks: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(stage_root).as_posix()
        validate_relative_path(relative)
        if relative in excluded_set:
            continue
        mode = stat.S_IMODE(path.stat().st_mode)
        records.append(
            CheckpointFileRecord(
                path=relative,
                size=path.stat().st_size,
                sha256=sha256_file(path),
                mode=f"{mode:04o}",
            )
        )
    return records


def content_root(records: Iterable[CheckpointFileRecord | dict[str, object]]) -> str:
    normalized: list[dict[str, object]] = []
    for item in records:
        payload = asdict(item) if isinstance(item, CheckpointFileRecord) else dict(item)
        normalized.append(
            {
                "kind": str(payload.get("kind", "file")),
                "mode": str(payload["mode"]),
                "path": str(payload["path"]),
                "sha256": str(payload["sha256"]),
                "size": int(payload["size"]),
            }
        )
    normalized.sort(key=lambda item: str(item["path"]))
    return sha256_bytes(canonical_json(normalized))


def build_content_manifest(stage_root: Path, *, checkpoint_id: str, top_level: str) -> dict[str, object]:
    records = stage_records(stage_root)
    return {
        "schema": "sip.checkpoint-content-manifest/v1",
        "checkpoint_id": checkpoint_id,
        "top_level": top_level,
        "excluded_from_content_root": [MANIFEST_PATH],
        "file_count": len(records),
        "total_uncompressed_bytes": sum(item.size for item in records),
        "content_root_sha256": content_root(records),
        "files": [asdict(item) for item in records],
    }


def write_deterministic_zip(stage_root: Path, destination: Path, *, top_level: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True) as archive:
        for path in sorted(stage_root.rglob("*")):
            if not path.is_file():
                continue
            relative = validate_relative_path(path.relative_to(stage_root).as_posix())
            info = zipfile.ZipInfo(f"{top_level}/{relative}", date_time=FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (stat.S_IMODE(path.stat().st_mode) or 0o644) << 16
            info.flag_bits |= 0x800
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    os.replace(temporary, destination)
