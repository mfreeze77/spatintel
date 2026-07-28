#!/usr/bin/env python3
"""Build a deterministic consolidated delivery envelope with a self-excluding exact payload index."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import tempfile
import sys
import zipfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.checkpoint_common import CheckpointFileRecord, FIXED_ZIP_TIME, content_root, sha256_file, validate_relative_path

INDEX_NAME = "DELIVERY_INDEX.json"
SCHEMA = "sip.delivery-envelope-index/v1"


def _record(path: Path, *, relative: str) -> CheckpointFileRecord:
    return CheckpointFileRecord(
        path=validate_relative_path(relative),
        size=path.stat().st_size,
        sha256=sha256_file(path),
        mode=f"{stat.S_IMODE(path.stat().st_mode):04o}",
    )


def _write_zip(root: Path, destination: Path, *, top_level: str) -> None:
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True) as archive:
        for path in sorted(root.iterdir(), key=lambda item: item.name):
            if not path.is_file() or path.is_symlink():
                raise RuntimeError(f"delivery payload must contain regular files only: {path}")
            relative = validate_relative_path(path.name)
            info = zipfile.ZipInfo(f"{top_level}/{relative}", FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (stat.S_IMODE(path.stat().st_mode) or 0o644) << 16
            info.flag_bits |= 0x800
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    os.replace(temporary, destination)


def build(
    *,
    delivery_id: str,
    top_level: str,
    project_zip: Path,
    project_sha256: Path,
    project_verification: Path,
    files: list[Path],
    output: Path,
) -> dict[str, Any]:
    sources = [project_zip, project_sha256, project_verification, *files]
    if any(not path.is_file() or path.is_symlink() for path in sources):
        missing = [str(path) for path in sources if not path.is_file() or path.is_symlink()]
        raise RuntimeError(f"delivery source files are missing or unsafe: {missing}")
    basenames = [path.name for path in sources]
    if len(basenames) != len(set(basenames)):
        raise RuntimeError("delivery source basenames must be unique")
    if INDEX_NAME in basenames:
        raise RuntimeError(f"{INDEX_NAME} is generated and may not be supplied")
    validate_relative_path(top_level)
    with tempfile.TemporaryDirectory(prefix="sip-delivery-envelope-") as temporary:
        stage = Path(temporary) / top_level
        stage.mkdir(parents=True)
        for source in sources:
            shutil.copy2(source, stage / source.name)
        records = [_record(path, relative=path.name) for path in sorted(stage.iterdir(), key=lambda item: item.name)]
        index = {
            "schema": SCHEMA,
            "delivery_id": delivery_id,
            "top_level": top_level,
            "created_at": datetime.now(UTC).isoformat(),
            "self_exclusion": {
                "path": INDEX_NAME,
                "included_in_archive": True,
                "excluded_from_listed_payload": True,
                "reason": "The delivery index cannot contain its own hash without a recursive identity; every other archive file is listed exactly once.",
            },
            "project_checkpoint": {
                "path": project_zip.name,
                "sha256": sha256_file(project_zip),
                "sha256_file": project_sha256.name,
                "verification_report": project_verification.name,
            },
            "payload_file_count": len(records),
            "payload_total_bytes": sum(item.size for item in records),
            "payload_content_root_sha256": content_root(records),
            "files": [asdict(item) for item in records],
        }
        (stage / INDEX_NAME).write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _write_zip(stage, output, top_level=top_level)
    return {
        "schema": "sip.delivery-envelope-build-report/v1",
        "status": "passed_complete",
        "delivery_id": delivery_id,
        "archive": str(output),
        "archive_sha256": sha256_file(output),
        "archive_size": output.stat().st_size,
        "payload_file_count": index["payload_file_count"],
        "payload_content_root_sha256": index["payload_content_root_sha256"],
        "project_checkpoint_sha256": index["project_checkpoint"]["sha256"],
        "index_self_excluded": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delivery-id", required=True)
    parser.add_argument("--top-level", required=True)
    parser.add_argument("--project-zip", type=Path, required=True)
    parser.add_argument("--project-sha256", type=Path, required=True)
    parser.add_argument("--project-verification", type=Path, required=True)
    parser.add_argument("--file", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = build(
        delivery_id=args.delivery_id,
        top_level=args.top_level,
        project_zip=args.project_zip.resolve(),
        project_sha256=args.project_sha256.resolve(),
        project_verification=args.project_verification.resolve(),
        files=[path.resolve() for path in args.file],
        output=args.output.resolve(),
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
