#!/usr/bin/env python3
"""Canonical SIP source identity shared by tests, traceability, releases, and checkpoints."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping

DEFAULT_POLICY = Path("governance/source-root-policy.json")


@dataclass(frozen=True)
class SourceFileRecord:
    path: str
    mode: str
    bytes: int
    sha256: str


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_policy(root: Path, policy_path: Path | None = None) -> dict[str, object]:
    root = root.resolve()
    path = (policy_path or (root / DEFAULT_POLICY)).resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "sip.source-root-policy/v1":
        raise ValueError(f"unsupported source-root policy schema: {payload.get('schema')!r}")
    for key in ("excluded_directory_names", "excluded_path_prefixes", "excluded_paths"):
        value = payload.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise ValueError(f"invalid source-root policy field: {key}")
    return payload


def is_source_path(relative: str, *, policy: Mapping[str, object]) -> bool:
    normalized = relative.replace("\\", "/").lstrip("./")
    if not normalized or normalized.startswith("/"):
        return False
    excluded_paths = set(str(item) for item in policy["excluded_paths"])
    if normalized in excluded_paths:
        return False
    prefixes = tuple(str(item) for item in policy["excluded_path_prefixes"])
    if any(normalized == prefix.rstrip("/") or normalized.startswith(prefix) for prefix in prefixes):
        return False
    excluded_names = set(str(item) for item in policy["excluded_directory_names"])
    parts = Path(normalized).parts
    return not any(part in excluded_names for part in parts)


def iter_source_files(root: Path, *, policy: Mapping[str, object] | None = None) -> Iterable[Path]:
    root = root.resolve()
    loaded = dict(policy or load_policy(root))
    excluded_names = set(str(item) for item in loaded["excluded_directory_names"])
    for current_root, directories, filenames in os.walk(root, topdown=True):
        directories[:] = sorted(item for item in directories if item not in excluded_names)
        directory = Path(current_root)
        for filename in sorted(filenames):
            path = directory / filename
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if is_source_path(relative, policy=loaded):
                yield path


def source_file_records(root: Path, *, policy: Mapping[str, object] | None = None) -> list[SourceFileRecord]:
    root = root.resolve()
    loaded = dict(policy or load_policy(root))
    records: list[SourceFileRecord] = []
    for path in iter_source_files(root, policy=loaded):
        mode = stat.S_IMODE(path.stat().st_mode)
        records.append(
            SourceFileRecord(
                path=path.relative_to(root).as_posix(),
                mode=f"{mode:04o}",
                bytes=path.stat().st_size,
                sha256=sha256_file(path),
            )
        )
    return sorted(records, key=lambda item: item.path)


def source_tree_root(root: Path, *, policy: Mapping[str, object] | None = None) -> str:
    records = [asdict(item) for item in source_file_records(root, policy=policy)]
    return sha256_bytes(canonical_json(records))


def source_identity(root: Path, *, policy_path: Path | None = None) -> dict[str, object]:
    root = root.resolve()
    policy = load_policy(root, policy_path)
    records = source_file_records(root, policy=policy)
    policy_file = (policy_path or (root / DEFAULT_POLICY)).resolve()
    return {
        "schema": "sip.source-identity/v1",
        "source_tree_root_sha256": sha256_bytes(canonical_json([asdict(item) for item in records])),
        "policy_path": policy_file.relative_to(root).as_posix(),
        "policy_sha256": sha256_file(policy_file),
        "file_count": len(records),
        "total_bytes": sum(item.bytes for item in records),
        "files": [asdict(item) for item in records],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = source_identity(args.root)
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
