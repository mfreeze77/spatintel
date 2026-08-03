#!/usr/bin/env python3
"""Independently verify a Progress 11 QA-002 project checkpoint."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import tarfile
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.checkpoint_common import CheckpointFileRecord, MANIFEST_PATH, content_root, sha256_file, validate_relative_path
from tools.source_identity import source_identity

CHECKPOINT_ID = "sip-v1.1.0-progress-11"
TOP_LEVEL = "Spatial-Intelligence-Platform-v1.1.0-progress-11"
EXPECTED_BRANCH = "progress-11-release-gates"
EXPECTED_BASE_COMMIT = "ab409f6ac7ca583535f69e5806b7a3bdbfe08214"
EXPECTED_BASE_ZIP_SHA256 = "46d850b6035d0ee86386ff256aabdc65751d49398f6ea4e4084eb4d50d6c669c"
EXPECTED_BASE_OUTER_SHA256 = "1e0c962a59a55a2a6395179c98467778ff56e2e394319b0ca46367551b5027dc"
EXPECTED_BASE_SOURCE_ROOT = "0c93009874f99c72c3670d6cfca47af00ff04b762e4f4ddddffa20ab03ed8678"
EXPECTED_SPEC_SHA256 = "84b570464b98b1baf3107789af22edad2a14086e5420df35a961f5fb16980bb8"
EXPECTED_SCOPE_TOTAL = 96
EXPECTED_INCLUDED = 96
EXPECTED_DEFERRED = 0
EXPECTED_MIGRATION_PATH = "source/migrations/versions/0021_progress11_release_assurance.py"
MIN_PYTHON_TESTS = 455


def _matrix_counts(totals: dict[str, Any]) -> tuple[int, int, int, int]:
    """Normalize the canonical matrix totals schema and historical aliases."""

    passed = int(totals.get("tests", totals.get("passed", 0)))
    failed = int(totals.get("failures", totals.get("failed", 0)))
    errors = int(totals.get("errors", 0))
    skipped = int(totals.get("skipped", 0))
    return passed, failed, errors, skipped


def _audited_requirement_ids(value: object) -> set[str]:
    """Return an exact unique requirement-id set for the audit's canonical list."""

    if not isinstance(value, list):
        return set()
    identifiers = {
        str(item.get("requirement_id"))
        for item in value
        if isinstance(item, dict) and isinstance(item.get("requirement_id"), str)
    }
    return identifiers if len(identifiers) == len(value) else set()


EXPECTED_MIGRATION_BYTES = 11821
EXPECTED_MIGRATION_SHA256 = "0cb8f6d60e9a8a1f90b4d341116467fb81089b7ffaa07480544c749505d279ff"
MAX_FILES = 10000
MAX_FILE_BYTES = 4 * 1024 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 400.0


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    path: str | None = None


class Verification:
    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self.facts: dict[str, Any] = {}

    def fail(self, code: str, message: str, path: str | None = None) -> None:
        self.findings.append(Finding(code, message, path))


def _verify_bundle_integrity(bundle: Path, verification: Verification) -> None:
    """Verify a bundle without assuming the caller is inside a Git repository."""

    with tempfile.TemporaryDirectory(prefix="sip-p11-bundle-verify-") as temp:
        verification_repository = Path(temp) / "verification.git"
        result = subprocess.run(
            ["git", "init", "--bare", "-q", str(verification_repository)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            verification.fail("GIT_VERIFY_REPOSITORY", result.stderr or result.stdout, bundle.name)
            return
        result = subprocess.run(
            ["git", "bundle", "verify", str(bundle)],
            cwd=verification_repository,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            verification.fail("GIT_BUNDLE_INVALID", result.stderr or result.stdout, bundle.name)


def _load(path: Path, verification: Verification, code: str) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        verification.fail(code, str(exc), path.as_posix())
        return None
    if not isinstance(value, dict):
        verification.fail(code, "expected JSON object", path.as_posix())
        return None
    return value


def _safe_extract_zip(archive: zipfile.ZipFile, destination: Path, verification: Verification) -> str | None:
    infos = archive.infolist()
    if len(infos) > MAX_FILES:
        verification.fail("FILE_LIMIT", f"archive contains {len(infos)} entries")
    names: set[str] = set()
    top_levels: set[str] = set()
    total = 0
    for info in infos:
        try:
            safe = validate_relative_path(info.filename.rstrip("/") if info.is_dir() else info.filename)
        except ValueError as exc:
            verification.fail("UNSAFE_PATH", str(exc), info.filename)
            continue
        if info.filename in names:
            verification.fail("DUPLICATE_MEMBER", "duplicate ZIP member", info.filename)
            continue
        names.add(info.filename)
        top_levels.add(PurePosixPath(safe).parts[0])
        mode = (info.external_attr >> 16) & 0o170000
        if mode == stat.S_IFLNK:
            verification.fail("SYMLINK_MEMBER", "symlink ZIP members are prohibited", info.filename)
        if info.flag_bits & 0x1:
            verification.fail("ENCRYPTED_MEMBER", "encrypted ZIP members are prohibited", info.filename)
        if info.is_dir():
            continue
        total += info.file_size
        if info.file_size > MAX_FILE_BYTES:
            verification.fail("MEMBER_SIZE", "ZIP member exceeds size limit", info.filename)
        if info.compress_size == 0 and info.file_size:
            verification.fail("ZERO_COMPRESSED_SIZE", "nonempty member has zero compressed size", info.filename)
        elif info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            verification.fail("COMPRESSION_RATIO", "ZIP member compression ratio exceeds limit", info.filename)
    if total > MAX_TOTAL_BYTES:
        verification.fail("TOTAL_SIZE", "ZIP expanded size exceeds limit")
    if top_levels != {TOP_LEVEL}:
        verification.fail("TOP_LEVEL", f"expected {TOP_LEVEL}, got {sorted(top_levels)}")
        return None
    for info in infos:
        if info.is_dir():
            continue
        try:
            safe = validate_relative_path(info.filename)
        except ValueError:
            continue
        target = destination.joinpath(*PurePosixPath(safe).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info, "r") as source, target.open("wb") as output:
            shutil_copy(source, output, verification, info.filename)
        target.chmod(((info.external_attr >> 16) & 0o777) or 0o644)
    return TOP_LEVEL


def shutil_copy(source: Any, output: Any, verification: Verification, path: str) -> None:
    size = 0
    while True:
        chunk = source.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_FILE_BYTES:
            verification.fail("RUNTIME_SIZE", "member exceeded extraction limit", path)
            break
        output.write(chunk)


def _verify_manifest(root: Path, verification: Verification) -> dict[str, Any] | None:
    manifest = _load(root / MANIFEST_PATH, verification, "MANIFEST_INVALID")
    if manifest is None:
        return None
    if manifest.get("checkpoint_id") != CHECKPOINT_ID or manifest.get("top_level") != TOP_LEVEL:
        verification.fail("MANIFEST_IDENTITY", "checkpoint manifest identity differs", MANIFEST_PATH)
    raw = manifest.get("files")
    if not isinstance(raw, list):
        verification.fail("MANIFEST_FILES", "manifest files must be a list", MANIFEST_PATH)
        return manifest
    expected: dict[str, CheckpointFileRecord] = {}
    for item in raw:
        try:
            record = CheckpointFileRecord(
                path=validate_relative_path(str(item["path"])),
                size=int(item["size"]),
                sha256=str(item["sha256"]),
                mode=str(item["mode"]),
                kind=str(item.get("kind", "file")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            verification.fail("MANIFEST_RECORD", str(exc), MANIFEST_PATH)
            continue
        if record.path in expected:
            verification.fail("MANIFEST_DUPLICATE", "duplicate manifest record", record.path)
        expected[record.path] = record
    actual = {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file() and path.relative_to(root).as_posix() != MANIFEST_PATH
    }
    for missing in sorted(set(expected) - set(actual)):
        verification.fail("LISTED_MISSING", "manifest-listed file is missing", missing)
    for extra in sorted(set(actual) - set(expected)):
        verification.fail("UNLISTED_FILE", "unexpected unlisted file", extra)
    for relative, record in expected.items():
        path = actual.get(relative)
        if path is None:
            continue
        if path.stat().st_size != record.size:
            verification.fail("SIZE_MISMATCH", f"expected {record.size}, got {path.stat().st_size}", relative)
        if sha256_file(path) != record.sha256:
            verification.fail("HASH_MISMATCH", "file SHA-256 differs", relative)
        mode = "0755" if stat.S_IMODE(path.stat().st_mode) & 0o111 else "0644"
        expected_mode = "0755" if int(record.mode, 8) & 0o111 else "0644"
        if mode != expected_mode:
            verification.fail("MODE_MISMATCH", f"expected {expected_mode}, got {mode}", relative)
    root_hash = content_root(expected.values())
    verification.facts["content_root_sha256"] = root_hash
    verification.facts["manifest_file_count"] = len(expected)
    verification.facts["manifest_total_bytes"] = sum(item.size for item in expected.values())
    if root_hash != manifest.get("content_root_sha256"):
        verification.fail("CONTENT_ROOT", "aggregate checkpoint content root differs", MANIFEST_PATH)
    if int(manifest.get("file_count", -1)) != len(expected):
        verification.fail("FILE_COUNT", "manifest file count differs", MANIFEST_PATH)
    return manifest


def _verify_source(root: Path, verification: Verification) -> dict[str, Any] | None:
    source_record = _load(root / "SOURCE_COMMIT.json", verification, "SOURCE_COMMIT_INVALID")
    source_manifest = _load(root / "SOURCE_FILE_MANIFEST.json", verification, "SOURCE_MANIFEST_INVALID")
    if source_record is None or source_manifest is None:
        return source_record
    commit = str(source_record.get("commit", ""))
    tree = str(source_record.get("tree", ""))
    if source_record.get("checkpoint_id") != CHECKPOINT_ID or source_record.get("branch") != EXPECTED_BRANCH:
        verification.fail("SOURCE_IDENTITY", "source commit record identity differs", "SOURCE_COMMIT.json")
    if source_record.get("accepted_base_commit") != EXPECTED_BASE_COMMIT:
        verification.fail("SOURCE_BASE", "source commit record has wrong accepted base", "SOURCE_COMMIT.json")
    source_dir = root / "source"
    try:
        identity = source_identity(source_dir)
    except Exception as exc:
        verification.fail("SOURCE_ROOT_ERROR", str(exc), "source")
        identity = None
    if identity:
        verification.facts["source_tree_root_sha256"] = identity["source_tree_root_sha256"]
        verification.facts["source_root_file_count"] = identity["file_count"]
        if identity["source_tree_root_sha256"] != source_record.get("source_tree_root_sha256"):
            verification.fail("SOURCE_ROOT", "packaged source root differs from source record", "source")

    records = source_manifest.get("files") if isinstance(source_manifest.get("files"), list) else []
    expected_paths: set[str] = set()
    for item in records:
        if not isinstance(item, dict):
            verification.fail("SOURCE_MANIFEST_RECORD", "source manifest record must be an object")
            continue
        relative = str(item.get("path", ""))
        try:
            validate_relative_path(relative)
        except ValueError as exc:
            verification.fail("SOURCE_MANIFEST_PATH", str(exc), relative)
            continue
        expected_paths.add(relative)
        path = source_dir / relative
        if not path.is_file():
            verification.fail("SOURCE_FILE_MISSING", "source manifest file is missing", relative)
            continue
        if path.stat().st_size != int(item.get("size", -1)) or sha256_file(path) != item.get("sha256"):
            verification.fail("SOURCE_FILE_MISMATCH", "source file size or hash differs", relative)
        actual_mode = "0755" if stat.S_IMODE(path.stat().st_mode) & 0o111 else "0644"
        if actual_mode != item.get("mode"):
            verification.fail("SOURCE_MODE_MISMATCH", "source executable mode differs", relative)
    actual_paths = {path.relative_to(source_dir).as_posix() for path in source_dir.rglob("*") if path.is_file()}
    if actual_paths != expected_paths:
        verification.fail("SOURCE_FILE_SET", "source manifest file set differs from extracted source")
    if int(source_manifest.get("file_count", -1)) != len(records):
        verification.fail("SOURCE_FILE_COUNT", "source manifest file count differs")

    artifacts = root / "artifacts"
    bundles = list(artifacts.glob(f"Spatial-Intelligence-Platform-v1.1.0-progress-11-{commit}.bundle"))
    archives = list(artifacts.glob(f"Spatial-Intelligence-Platform-v1.1.0-{commit}.tar.gz"))
    if len(bundles) != 1:
        verification.fail("GIT_BUNDLE_MISSING", "exact Progress 11 Git bundle is missing", "artifacts")
    else:
        bundle = bundles[0]
        _verify_bundle_integrity(bundle, verification)
        with tempfile.TemporaryDirectory(prefix="sip-p11-bundle-") as temp:
            temporary = Path(temp)
            clone = temporary / "clone"
            result = subprocess.run(["git", "clone", "-q", "-b", EXPECTED_BRANCH, str(bundle), str(clone)], capture_output=True, text=True, check=False)
            if result.returncode != 0:
                verification.fail("GIT_CLONE_FAILED", result.stderr, bundle.name)
            else:
                def git(*args: str) -> str:
                    return subprocess.check_output(["git", *args], cwd=clone, text=True).strip()
                if git("rev-parse", "HEAD") != commit or git("show", "-s", "--format=%T", "HEAD") != tree:
                    verification.fail("GIT_COMMIT_TREE", "bundle clone commit or tree differs", bundle.name)
                if subprocess.run(["git", "merge-base", "--is-ancestor", EXPECTED_BASE_COMMIT, commit], cwd=clone).returncode != 0:
                    verification.fail("GIT_ANCESTRY", "accepted Progress 10 commit is not an ancestor", bundle.name)
                if git("status", "--porcelain=v1"):
                    verification.fail("GIT_CLONE_DIRTY", "bundle clone is dirty", bundle.name)
    if len(archives) != 1:
        verification.fail("SOURCE_ARCHIVE_MISSING", "exact committed-source archive is missing", "artifacts")
    else:
        with tempfile.TemporaryDirectory(prefix="sip-p11-source-archive-") as temp:
            extracted = Path(temp) / "source"
            extracted.mkdir()
            try:
                with tarfile.open(archives[0], "r:gz") as archive:
                    for member in archive.getmembers():
                        if member.issym() or member.islnk() or member.name.startswith("/") or ".." in PurePosixPath(member.name).parts:
                            raise ValueError(f"unsafe source archive member: {member.name}")
                    archive.extractall(extracted, filter="data")
            except Exception as exc:
                verification.fail("SOURCE_ARCHIVE_INVALID", str(exc), archives[0].name)
            else:
                archive_paths = {path.relative_to(extracted).as_posix(): path for path in extracted.rglob("*") if path.is_file()}
                if set(archive_paths) != expected_paths:
                    verification.fail("SOURCE_ARCHIVE_FILE_SET", "source archive file set differs", archives[0].name)
                for item in records:
                    path = archive_paths.get(str(item.get("path")))
                    if path and (path.stat().st_size != int(item.get("size", -1)) or sha256_file(path) != item.get("sha256")):
                        verification.fail("SOURCE_ARCHIVE_FILE", "source archive file differs", str(item.get("path")))
    verification.facts.update({"commit": commit, "tree": tree, "branch": source_record.get("branch")})
    return source_record


def _verify_control_records(root: Path, verification: Verification, source_record: dict[str, Any] | None) -> None:
    scope = _load(root / "MILESTONE_SCOPE_PROGRESS_11.json", verification, "SCOPE_INVALID")
    audit = _load(root / "progress-11-traceability-audit.json", verification, "TRACEABILITY_INVALID")
    ledger = _load(root / "source/requirements/requirements-ledger.json", verification, "LEDGER_INVALID")
    acceptance = _load(root / "build/reports/checkpoint-acceptance-gates.json", verification, "ACCEPTANCE_INVALID")
    matrix = _load(root / "build/reports/test-matrix.json", verification, "MATRIX_INVALID")
    checkpoint = _load(root / "build/checkpoints/progress-11.json", verification, "CHECKPOINT_INVALID")
    readiness = _load(root / "build/reports/release-readiness-progress-11.json", verification, "READINESS_INVALID")
    index = _load(root / "build/evidence/AUTHORITATIVE_EVIDENCE_INDEX.json", verification, "EVIDENCE_INDEX_INVALID")
    if not all((scope, audit, ledger, acceptance, matrix, checkpoint, readiness, index, source_record)):
        return
    included = scope.get("included_requirements", [])
    deferred = scope.get("deferred_requirements", [])
    ids = {str(item.get("requirement_id")) for item in included if isinstance(item, dict)}
    if scope.get("checkpoint_id") != CHECKPOINT_ID or scope.get("accepted_base_commit") != EXPECTED_BASE_COMMIT:
        verification.fail("SCOPE_IDENTITY", "milestone scope identity differs", "MILESTONE_SCOPE_PROGRESS_11.json")
    if len(included) != EXPECTED_INCLUDED or len(deferred) != EXPECTED_DEFERRED or len(ids) != EXPECTED_SCOPE_TOTAL:
        verification.fail("SCOPE_COUNTS", "milestone scope count differs", "MILESTONE_SCOPE_PROGRESS_11.json")
    if scope.get("authorized_epics") != ["QA-002"] or scope.get("progress_12_authorized") is not False or scope.get("production_authorized") is not False:
        verification.fail("SCOPE_POSTURE", "scope authorization posture differs", "MILESTONE_SCOPE_PROGRESS_11.json")
    if (
        audit.get("status") != "passed_complete"
        or int(audit.get("finding_count", -1)) != 0
        or _audited_requirement_ids(audit.get("requirements_audited")) != ids
    ):
        verification.fail("TRACEABILITY", "Progress 11 traceability audit is not complete", "progress-11-traceability-audit.json")
    requirements = ledger.get("requirements") if isinstance(ledger.get("requirements"), list) else []
    if len(requirements) != 1028:
        verification.fail("LEDGER_COUNT", "requirements ledger does not contain 1,028 records")
    pview = next((item for item in requirements if isinstance(item, dict) and item.get("requirement_id") == "PLTVIEW-007"), {})
    if pview.get("implementation_status") != "IMPLEMENTED_UNVERIFIED":
        verification.fail("PLTVIEW_STATUS", "PLTVIEW-007 was promoted without mounted evidence")
    source = acceptance.get("source", {})
    if acceptance.get("checkpoint_id") != CHECKPOINT_ID or source.get("commit") != source_record.get("commit") or source.get("source_tree_root_sha256") != source_record.get("source_tree_root_sha256"):
        verification.fail("ACCEPTANCE_BINDING", "acceptance is not bound to packaged source")
    if acceptance.get("status") not in {"passed_complete", "passed_with_external_gaps"} or int(acceptance.get("required_failure_count", -1)) != 0:
        verification.fail("ACCEPTANCE_STATUS", "checkpoint acceptance did not pass required local gates")
    if acceptance.get("progress_12_authorized") is not False or acceptance.get("production_authorized") is not False:
        verification.fail("ACCEPTANCE_POSTURE", "acceptance authorizes Progress 12 or production")
    totals = matrix.get("totals", {})
    passed, failed, errors, skipped = _matrix_counts(totals)
    verification.facts["python_tests_passed"] = passed
    if passed < MIN_PYTHON_TESTS or any((failed, errors, skipped)):
        verification.fail("MATRIX", "Python matrix has insufficient passes or nonzero findings")
    if checkpoint.get("checkpoint_id") != CHECKPOINT_ID or checkpoint.get("commit") != source_record.get("commit") or checkpoint.get("source_tree_root_sha256") != source_record.get("source_tree_root_sha256"):
        verification.fail("CHECKPOINT_BINDING", "checkpoint record is not bound to source")
    if checkpoint.get("progress_12_authorized") is not False or checkpoint.get("production_authorized") is not False:
        verification.fail("CHECKPOINT_POSTURE", "checkpoint authorizes Progress 12 or production")
    if readiness.get("status") != "blocked" or readiness.get("progress_12_authorized") is not False or readiness.get("production_authorized") is not False:
        verification.fail("READINESS_POSTURE", "release readiness must remain blocked")
    if index.get("checkpoint_id") != CHECKPOINT_ID or index.get("commit") != source_record.get("commit") or index.get("source_tree_root_sha256") != source_record.get("source_tree_root_sha256"):
        verification.fail("EVIDENCE_INDEX_BINDING", "authoritative evidence index is not source-bound")
    for item in index.get("artifacts", []):
        if not isinstance(item, dict):
            verification.fail("EVIDENCE_INDEX_RECORD", "evidence index record must be an object")
            continue
        relative = str(item.get("path", ""))
        path = root / relative
        if not path.is_file() or sha256_file(path) != item.get("sha256") or path.stat().st_size != int(item.get("byte_count", -1)):
            verification.fail("EVIDENCE_INDEX_ARTIFACT", "authoritative evidence artifact differs", relative)

    migration = root / EXPECTED_MIGRATION_PATH
    if not migration.is_file():
        verification.fail("MIGRATION_MISSING", "append-only Progress 11 migration is missing", EXPECTED_MIGRATION_PATH)
    else:
        migration_sha = sha256_file(migration)
        if migration.stat().st_size != EXPECTED_MIGRATION_BYTES or migration_sha != EXPECTED_MIGRATION_SHA256:
            verification.fail("MIGRATION_BYTES", "Progress 11 migration bytes differ from the locked revision", EXPECTED_MIGRATION_PATH)
        checkpoint_migration = checkpoint.get("migration", {})
        if checkpoint_migration.get("path") != EXPECTED_MIGRATION_PATH.removeprefix("source/") or checkpoint_migration.get("sha256") != migration_sha or int(checkpoint_migration.get("byte_count", -1)) != migration.stat().st_size:
            verification.fail("MIGRATION_LOCK", "Progress 11 migration lock differs", EXPECTED_MIGRATION_PATH)
        migration_manifest = _load(root / "source/migrations/manifest.json", verification, "MIGRATION_MANIFEST_INVALID")
        if migration_manifest:
            manifest_path = EXPECTED_MIGRATION_PATH.removeprefix("source/")
            matches = [
                item
                for item in migration_manifest.get("migrations", [])
                if isinstance(item, dict) and item.get("path") == manifest_path
            ]
            if len(matches) != 1 or int(matches[0].get("byte_count", -1)) != EXPECTED_MIGRATION_BYTES or matches[0].get("sha256") != EXPECTED_MIGRATION_SHA256:
                verification.fail("MIGRATION_MANIFEST_LOCK", "migration manifest does not retain the exact 0021 revision", "source/migrations/manifest.json")
    spec = root / "source/spec/source/Spatial-Intelligence-Platform-Spec-v1.1.zip"
    if not spec.is_file() or sha256_file(spec) != EXPECTED_SPEC_SHA256:
        verification.fail("SPECIFICATION", "authoritative specification hash differs", spec.as_posix())
    predecessor = _load(root / "PREDECESSOR_CHECKPOINT.json", verification, "PREDECESSOR_INVALID")
    if predecessor:
        p10 = predecessor.get("accepted_progress_10_checkpoint", {})
        expected = {
            "commit": EXPECTED_BASE_COMMIT,
            "project_zip_sha256": EXPECTED_BASE_ZIP_SHA256,
            "outer_delivery_zip_sha256": EXPECTED_BASE_OUTER_SHA256,
            "source_tree_root_sha256": EXPECTED_BASE_SOURCE_ROOT,
        }
        for key, value in expected.items():
            if p10.get(key) != value:
                verification.fail("PREDECESSOR_IDENTITY", f"Progress 10 predecessor {key} differs", "PREDECESSOR_CHECKPOINT.json")


def verify_archive(archive_path: Path) -> dict[str, Any]:
    archive_path = archive_path.resolve()
    verification = Verification()
    if not archive_path.is_file():
        verification.fail("ARCHIVE_MISSING", "checkpoint archive does not exist", str(archive_path))
        return _report(archive_path, verification)
    verification.facts["archive_sha256"] = sha256_file(archive_path)
    verification.facts["archive_size"] = archive_path.stat().st_size
    with tempfile.TemporaryDirectory(prefix="sip-progress11-verify-") as temporary:
        extraction = Path(temporary) / "extract"
        extraction.mkdir()
        try:
            with zipfile.ZipFile(archive_path) as archive:
                top = _safe_extract_zip(archive, extraction, verification)
        except (OSError, zipfile.BadZipFile) as exc:
            verification.fail("ZIP_INVALID", str(exc), str(archive_path))
            return _report(archive_path, verification)
        if top is None:
            return _report(archive_path, verification)
        root = extraction / top
        _verify_manifest(root, verification)
        source_record = _verify_source(root, verification)
        _verify_control_records(root, verification, source_record)
    return _report(archive_path, verification)


def _report(path: Path, verification: Verification) -> dict[str, Any]:
    return {
        "schema": "sip.checkpoint-verification/v1",
        "checkpoint_id": CHECKPOINT_ID,
        "archive": str(path),
        "status": "passed_complete" if not verification.findings else "failed",
        "finding_count": len(verification.findings),
        "findings": [asdict(item) for item in verification.findings],
        "facts": verification.facts,
        "progress_12_authorized": False,
        "production_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_archive(args.archive)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    raise SystemExit(0 if report["status"] == "passed_complete" else 1)


if __name__ == "__main__":
    main()
