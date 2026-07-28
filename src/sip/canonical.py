from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any, Iterable


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | os.PathLike[str]) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def new_uuid() -> str:
    return str(uuid.uuid4())


def merkle_root(entries: Iterable[tuple[str, str]]) -> str:
    leaves = [sha256_bytes(f"{path}\0{digest}".encode()) for path, digest in sorted(entries)]
    if not leaves:
        return sha256_bytes(b"")
    while len(leaves) > 1:
        if len(leaves) % 2:
            leaves.append(leaves[-1])
        leaves = [sha256_bytes((leaves[i] + leaves[i + 1]).encode()) for i in range(0, len(leaves), 2)]
    return leaves[0]
