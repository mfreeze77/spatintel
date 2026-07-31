#!/usr/bin/env python3
"""Verify a consolidated Progress 10 delivery envelope and its nested project checkpoint."""
from __future__ import annotations

import argparse
import hashlib
import json
import stat
import tempfile
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_delivery_envelope import INDEX_NAME, SCHEMA
from tools.checkpoint_common import CheckpointFileRecord, content_root, sha256_file, validate_relative_path
from tools.verify_progress10_checkpoint import verify_archive as verify_project_checkpoint

MAX_FILES = 1000
MAX_FILE_BYTES = 3 * 1024 * 1024 * 1024
MAX_TOTAL_BYTES = 10 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 300.0


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    path: str | None = None


def _fail(findings: list[Finding], code: str, message: str, path: str | None = None) -> None:
    findings.append(Finding(code, message, path))


def _safe_extract(archive: zipfile.ZipFile, destination: Path, findings: list[Finding]) -> str | None:
    infos = archive.infolist()
    if len(infos) > MAX_FILES:
        _fail(findings, "OUTER_FILE_LIMIT", f"archive contains {len(infos)} entries")
    names: set[str] = set()
    top_levels: set[str] = set()
    total = 0
    for info in infos:
        try:
            safe = validate_relative_path(info.filename.rstrip("/") if info.is_dir() else info.filename)
        except ValueError as exc:
            _fail(findings, "OUTER_UNSAFE_PATH", str(exc), info.filename)
            continue
        if info.filename in names:
            _fail(findings, "OUTER_DUPLICATE_MEMBER", "duplicate ZIP member", info.filename)
            continue
        names.add(info.filename)
        top_levels.add(PurePosixPath(safe).parts[0])
        mode = (info.external_attr >> 16) & 0o170000
        if mode == stat.S_IFLNK:
            _fail(findings, "OUTER_SYMLINK", "symlink members are prohibited", info.filename)
        if info.flag_bits & 0x1:
            _fail(findings, "OUTER_ENCRYPTED_MEMBER", "encrypted members are prohibited", info.filename)
        if info.is_dir():
            continue
        total += info.file_size
        if info.file_size > MAX_FILE_BYTES:
            _fail(findings, "OUTER_MEMBER_SIZE", "member exceeds size limit", info.filename)
        if info.compress_size == 0 and info.file_size:
            _fail(findings, "OUTER_COMPRESSION", "nonempty member has zero compressed size", info.filename)
        elif info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            _fail(findings, "OUTER_COMPRESSION_RATIO", "member compression ratio exceeds limit", info.filename)
    if total > MAX_TOTAL_BYTES:
        _fail(findings, "OUTER_TOTAL_SIZE", "archive exceeds total expansion limit")
    if len(top_levels) != 1:
        _fail(findings, "OUTER_TOP_LEVEL", f"expected one top-level directory, got {sorted(top_levels)}")
        return None
    top = next(iter(top_levels))
    for info in infos:
        if info.is_dir():
            continue
        try:
            safe = validate_relative_path(info.filename)
        except ValueError:
            continue
        target = destination.joinpath(*PurePosixPath(safe).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        with archive.open(info, "r") as source, target.open("wb") as output:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                size += len(chunk)
                if size > MAX_FILE_BYTES:
                    _fail(findings, "OUTER_RUNTIME_SIZE", "member exceeded extraction limit", info.filename)
                    break
                digest.update(chunk)
                output.write(chunk)
        target.chmod(((info.external_attr >> 16) & 0o777) or 0o644)
    return top


def verify(archive_path: Path) -> dict[str, Any]:
    archive_path = archive_path.resolve()
    findings: list[Finding] = []
    facts: dict[str, Any] = {}
    if not archive_path.is_file():
        _fail(findings, "OUTER_ARCHIVE_MISSING", "delivery archive does not exist", str(archive_path))
        return _report(archive_path, facts, findings)
    facts["archive_sha256"] = sha256_file(archive_path)
    facts["archive_size"] = archive_path.stat().st_size
    with tempfile.TemporaryDirectory(prefix="sip-delivery-verify-") as temporary:
        extract = Path(temporary) / "extract"
        extract.mkdir()
        try:
            with zipfile.ZipFile(archive_path) as archive:
                top = _safe_extract(archive, extract, findings)
        except (OSError, zipfile.BadZipFile) as exc:
            _fail(findings, "OUTER_ZIP_INVALID", str(exc), str(archive_path))
            return _report(archive_path, facts, findings)
        if top is None:
            return _report(archive_path, facts, findings)
        facts["top_level"] = top
        root = extract / top
        index_path = root / INDEX_NAME
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            _fail(findings, "OUTER_INDEX_INVALID", str(exc), INDEX_NAME)
            return _report(archive_path, facts, findings)
        if not isinstance(index, dict) or index.get("schema") != SCHEMA:
            _fail(findings, "OUTER_INDEX_SCHEMA", "unsupported delivery index schema", INDEX_NAME)
            return _report(archive_path, facts, findings)
        if index.get("top_level") != top:
            _fail(findings, "OUTER_INDEX_TOP_LEVEL", "index top level differs from archive", INDEX_NAME)
        exclusion = index.get("self_exclusion") if isinstance(index.get("self_exclusion"), dict) else {}
        if exclusion.get("path") != INDEX_NAME or exclusion.get("included_in_archive") is not True or exclusion.get("excluded_from_listed_payload") is not True or not exclusion.get("reason"):
            _fail(findings, "OUTER_INDEX_SELF_EXCLUSION", "index self-exclusion is not explicit", INDEX_NAME)
        records_raw = index.get("files")
        expected: dict[str, CheckpointFileRecord] = {}
        if not isinstance(records_raw, list):
            _fail(findings, "OUTER_INDEX_FILES", "files must be a list", INDEX_NAME)
            records_raw = []
        for raw in records_raw:
            try:
                record = CheckpointFileRecord(
                    path=validate_relative_path(str(raw["path"])),
                    size=int(raw["size"]),
                    sha256=str(raw["sha256"]),
                    mode=str(raw["mode"]),
                    kind=str(raw.get("kind", "file")),
                )
            except (KeyError, TypeError, ValueError) as exc:
                _fail(findings, "OUTER_INDEX_RECORD", str(exc), INDEX_NAME)
                continue
            if record.path in expected:
                _fail(findings, "OUTER_INDEX_DUPLICATE", "duplicate payload path", record.path)
            expected[record.path] = record
        actual = {path.relative_to(root).as_posix(): path for path in root.iterdir() if path.is_file() and path.name != INDEX_NAME}
        for missing in sorted(set(expected) - set(actual)):
            _fail(findings, "OUTER_LISTED_MISSING", "listed file is missing", missing)
        for extra in sorted(set(actual) - set(expected)):
            _fail(findings, "OUTER_UNEXPECTED_FILE", "unexpected unlisted file", extra)
        for relative, record in expected.items():
            path = actual.get(relative)
            if path is None:
                continue
            if path.stat().st_size != record.size:
                _fail(findings, "OUTER_SIZE_MISMATCH", f"expected {record.size}, got {path.stat().st_size}", relative)
            if sha256_file(path) != record.sha256:
                _fail(findings, "OUTER_HASH_MISMATCH", "payload hash differs", relative)
            if f"{stat.S_IMODE(path.stat().st_mode):04o}" != record.mode:
                _fail(findings, "OUTER_MODE_MISMATCH", "payload mode differs", relative)
        root_hash = content_root(expected.values())
        facts["payload_content_root_sha256"] = root_hash
        facts["payload_file_count"] = len(expected)
        if root_hash != index.get("payload_content_root_sha256"):
            _fail(findings, "OUTER_CONTENT_ROOT", "payload content root differs", INDEX_NAME)
        if int(index.get("payload_file_count", -1)) != len(expected):
            _fail(findings, "OUTER_FILE_COUNT", "payload file count differs", INDEX_NAME)
        if int(index.get("payload_total_bytes", -1)) != sum(item.size for item in expected.values()):
            _fail(findings, "OUTER_TOTAL_BYTES", "payload byte count differs", INDEX_NAME)
        project = index.get("project_checkpoint") if isinstance(index.get("project_checkpoint"), dict) else {}
        project_relative = str(project.get("path", ""))
        project_path = root / project_relative
        if not project_path.is_file():
            _fail(findings, "OUTER_PROJECT_MISSING", "nested project checkpoint is missing", project_relative)
        else:
            actual_hash = sha256_file(project_path)
            facts["project_checkpoint_sha256"] = actual_hash
            if actual_hash != project.get("sha256"):
                _fail(findings, "OUTER_PROJECT_HASH", "nested project checkpoint hash differs", project_relative)
            sha_path = root / str(project.get("sha256_file", ""))
            if not sha_path.is_file() or actual_hash not in sha_path.read_text(encoding="utf-8", errors="replace"):
                _fail(findings, "OUTER_PROJECT_SHA_FILE", "nested project checksum file is missing or incorrect", str(project.get("sha256_file", "")))
            verification_path = root / str(project.get("verification_report", ""))
            try:
                nested_report = json.loads(verification_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                _fail(findings, "OUTER_PROJECT_REPORT", str(exc), str(project.get("verification_report", "")))
                nested_report = None
            if isinstance(nested_report, dict):
                if nested_report.get("status") != "passed_complete" or nested_report.get("facts", {}).get("archive_sha256") != actual_hash:
                    _fail(findings, "OUTER_PROJECT_REPORT_BINDING", "nested verification report differs from project ZIP", str(project.get("verification_report", "")))
            live_report = verify_project_checkpoint(project_path)
            facts["nested_checkpoint_status"] = live_report.get("status")
            facts["nested_checkpoint_finding_count"] = live_report.get("finding_count")
            if live_report.get("status") != "passed_complete":
                _fail(findings, "OUTER_PROJECT_REVERIFY", "nested project checkpoint failed independent re-verification", project_relative)
    return _report(archive_path, facts, findings)


def _report(archive: Path, facts: dict[str, Any], findings: list[Finding]) -> dict[str, Any]:
    return {
        "schema": "sip.delivery-envelope-verification/v1",
        "status": "passed_complete" if not findings else "failed",
        "archive": str(archive),
        "facts": facts,
        "finding_count": len(findings),
        "findings": [asdict(item) for item in findings],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.archive)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    raise SystemExit(0 if report["status"] == "passed_complete" else 1)


if __name__ == "__main__":
    main()
