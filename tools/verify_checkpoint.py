#!/usr/bin/env python3
"""Independently verify a SIP checkpoint ZIP and all source/evidence provenance."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.checkpoint_common import MANIFEST_PATH, CheckpointFileRecord, canonical_json, content_root, sha256_file, validate_relative_path
from tools.source_identity import source_identity

EXPECTED_SPEC_SHA256 = "84b570464b98b1baf3107789af22edad2a14086e5420df35a961f5fb16980bb8"
MILESTONE_WORDING = (
    "Checkpoint 04 implements and verifies the governed hybrid-representation kernel defined by the enclosed "
    "milestone scope. The complete hybrid runtime, renderer, benchmark, external-provider, and production-approval "
    "requirements remain incomplete."
)
MAX_FILES = 100_000
MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 250.0
REQUIRED_EVIDENCE_CATEGORIES = {
    "source_commit",
    "source_root",
    "python_matrix",
    "swift_tests",
    "web_tests",
    "contracts",
    "migrations",
    "infrastructure",
    "security",
    "licensing",
    "requirements",
    "benchmarks",
    "demonstrations",
    "preservation_export",
    "independent_restore",
    "release_readiness",
}


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    path: str | None = None


class Verification:
    def __init__(self, archive: Path) -> None:
        self.archive = archive
        self.findings: list[Finding] = []
        self.facts: dict[str, Any] = {}

    def fail(self, code: str, message: str, path: str | None = None) -> None:
        self.findings.append(Finding(code, message, path))


def _read_json(path: Path, verification: Verification, *, code: str) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        verification.fail(code, str(exc), str(path))
        return None
    if not isinstance(value, dict):
        verification.fail(code, "JSON document must be an object", str(path))
        return None
    return value


def _validate_zip_metadata(archive: zipfile.ZipFile, verification: Verification) -> tuple[str | None, dict[str, zipfile.ZipInfo]]:
    infos = archive.infolist()
    if len(infos) > MAX_FILES:
        verification.fail("ZIP_FILE_LIMIT", f"archive contains {len(infos)} entries; maximum is {MAX_FILES}")
    names: dict[str, zipfile.ZipInfo] = {}
    top_levels: set[str] = set()
    total = 0
    for info in infos:
        try:
            safe = validate_relative_path(info.filename.rstrip("/")) if info.filename.endswith("/") else validate_relative_path(info.filename)
        except ValueError as exc:
            verification.fail("ZIP_UNSAFE_PATH", str(exc), info.filename)
            continue
        if info.filename in names:
            verification.fail("ZIP_DUPLICATE_PATH", "duplicate ZIP member", info.filename)
            continue
        names[info.filename] = info
        top_levels.add(PurePosixPath(safe).parts[0])
        mode = (info.external_attr >> 16) & 0o170000
        if mode == stat.S_IFLNK:
            verification.fail("ZIP_SYMLINK", "symlink members are prohibited", info.filename)
        if info.flag_bits & 0x1:
            verification.fail("ZIP_ENCRYPTED_MEMBER", "encrypted ZIP members are prohibited", info.filename)
        if info.is_dir():
            continue
        total += info.file_size
        if info.file_size > MAX_FILE_BYTES:
            verification.fail("ZIP_MEMBER_SIZE_LIMIT", f"member exceeds {MAX_FILE_BYTES} bytes", info.filename)
        if info.compress_size == 0 and info.file_size > 0:
            verification.fail("ZIP_INVALID_COMPRESSION", "nonempty member has zero compressed size", info.filename)
        elif info.compress_size > 0 and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            verification.fail("ZIP_COMPRESSION_RATIO", f"compression ratio exceeds {MAX_COMPRESSION_RATIO}", info.filename)
    if total > MAX_TOTAL_BYTES:
        verification.fail("ZIP_TOTAL_SIZE_LIMIT", f"archive expands to {total} bytes; maximum is {MAX_TOTAL_BYTES}")
    if len(top_levels) != 1:
        verification.fail("ZIP_TOP_LEVEL", f"archive must contain exactly one top-level directory; found {sorted(top_levels)}")
        return None, names
    return next(iter(top_levels)), names


def _extract_checked(archive: zipfile.ZipFile, destination: Path, verification: Verification) -> None:
    for info in archive.infolist():
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
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_FILE_BYTES:
                    verification.fail("ZIP_MEMBER_RUNTIME_LIMIT", "member exceeded runtime extraction limit", info.filename)
                    break
                digest.update(chunk)
                output.write(chunk)
        mode = (info.external_attr >> 16) & 0o777
        target.chmod(mode or 0o644)


def _verify_manifest(root: Path, verification: Verification) -> dict[str, Any] | None:
    path = root / MANIFEST_PATH
    manifest = _read_json(path, verification, code="MANIFEST_INVALID")
    if manifest is None:
        return None
    if manifest.get("schema") != "sip.checkpoint-content-manifest/v1":
        verification.fail("MANIFEST_SCHEMA", "unsupported checkpoint manifest schema", MANIFEST_PATH)
    files = manifest.get("files")
    if not isinstance(files, list):
        verification.fail("MANIFEST_FILES", "manifest files must be a list", MANIFEST_PATH)
        return manifest
    expected: dict[str, dict[str, Any]] = {}
    for raw in files:
        if not isinstance(raw, dict):
            verification.fail("MANIFEST_RECORD", "file record must be an object", MANIFEST_PATH)
            continue
        try:
            relative = validate_relative_path(str(raw["path"]))
            record = {
                "path": relative,
                "size": int(raw["size"]),
                "sha256": str(raw["sha256"]),
                "mode": str(raw["mode"]),
                "kind": str(raw.get("kind", "file")),
            }
        except (KeyError, TypeError, ValueError) as exc:
            verification.fail("MANIFEST_RECORD", str(exc), MANIFEST_PATH)
            continue
        if relative in expected:
            verification.fail("MANIFEST_DUPLICATE", "duplicate manifest path", relative)
        expected[relative] = record
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.relative_to(root).as_posix() != MANIFEST_PATH
    }
    if actual_paths != set(expected):
        for missing in sorted(set(expected) - actual_paths):
            verification.fail("MANIFEST_FILE_MISSING", "manifested file is absent", missing)
        for extra in sorted(actual_paths - set(expected)):
            verification.fail("MANIFEST_FILE_UNLISTED", "archive file is not in manifest", extra)
    for relative, record in expected.items():
        path = root / relative
        if not path.is_file():
            continue
        if path.stat().st_size != record["size"]:
            verification.fail("MANIFEST_SIZE_MISMATCH", f"expected {record['size']}, got {path.stat().st_size}", relative)
        actual_hash = sha256_file(path)
        if actual_hash != record["sha256"]:
            verification.fail("MANIFEST_HASH_MISMATCH", f"expected {record['sha256']}, got {actual_hash}", relative)
        actual_mode = f"{stat.S_IMODE(path.stat().st_mode):04o}"
        if actual_mode != record["mode"]:
            verification.fail("MANIFEST_MODE_MISMATCH", f"expected {record['mode']}, got {actual_mode}", relative)
    records = [CheckpointFileRecord(**record) for record in expected.values()]
    actual_root = content_root(records)
    if actual_root != manifest.get("content_root_sha256"):
        verification.fail("CONTENT_ROOT_MISMATCH", f"expected {manifest.get('content_root_sha256')}, got {actual_root}", MANIFEST_PATH)
    if int(manifest.get("file_count", -1)) != len(records):
        verification.fail("MANIFEST_FILE_COUNT", f"expected {manifest.get('file_count')}, got {len(records)}", MANIFEST_PATH)
    verification.facts["content_root_sha256"] = actual_root
    verification.facts["manifest_file_count"] = len(records)
    return manifest


def _git(*args: str, cwd: Path, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=cwd, input=input_bytes, capture_output=True, check=False)


def _verify_git_and_source(root: Path, verification: Verification) -> dict[str, Any] | None:
    source_commit_path = root / "SOURCE_COMMIT.json"
    record = _read_json(source_commit_path, verification, code="SOURCE_COMMIT_INVALID")
    if record is None:
        return None
    required = (
        "commit", "parent", "tree", "branch", "commit_timestamp", "source_tree_root_sha256",
        "source_root_policy_sha256", "git_bundle", "source_archive", "source_file_manifest",
        "clean_working_tree_attestation",
    )
    for field in required:
        if not record.get(field):
            verification.fail("SOURCE_COMMIT_FIELD", f"missing required field {field}", "SOURCE_COMMIT.json")
    commit = str(record.get("commit", ""))
    parent = str(record.get("parent", ""))
    tree = str(record.get("tree", ""))
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        verification.fail("SOURCE_COMMIT_SHA", "commit must be a full lowercase SHA-1", "SOURCE_COMMIT.json")
    if not re.fullmatch(r"[0-9a-f]{40}", parent):
        verification.fail("SOURCE_PARENT_SHA", "parent must be a full lowercase SHA-1", "SOURCE_COMMIT.json")
    if not re.fullmatch(r"[0-9a-f]{40}", tree):
        verification.fail("SOURCE_TREE_SHA", "tree must be a full lowercase SHA-1", "SOURCE_COMMIT.json")
    branch = str(record.get("branch", ""))
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", branch) or ".." in branch or branch.startswith("/") or branch.endswith("/"):
        verification.fail("SOURCE_BRANCH", "branch name is invalid", "SOURCE_COMMIT.json")
    if record.get("working_tree_clean_at_package") is not True or record.get("tested_detached_worktree") is not True:
        verification.fail("SOURCE_WORKTREE_ATTESTATION", "source was not attested clean and detached", "SOURCE_COMMIT.json")
    attestation = record.get("clean_working_tree_attestation")
    if not isinstance(attestation, dict):
        verification.fail("SOURCE_ATTESTATION_INVALID", "clean_working_tree_attestation must be an object", "SOURCE_COMMIT.json")
    else:
        for key, expected in (
            ("commit", commit),
            ("parent", parent),
            ("tree", tree),
            ("branch", branch),
            ("source_tree_root_sha256", record.get("source_tree_root_sha256")),
        ):
            if attestation.get(key) != expected:
                verification.fail("SOURCE_ATTESTATION_MISMATCH", f"attestation.{key} differs from source record", "SOURCE_COMMIT.json")
        if attestation.get("clean_before_tests") is not True or attestation.get("detached") is not True:
            verification.fail("SOURCE_ATTESTATION_STATE", "test source was not clean and detached", "SOURCE_COMMIT.json")
    source_dir = root / "source"
    if not source_dir.is_dir():
        verification.fail("SOURCE_TREE_MISSING", "source directory is missing", "source")
        return record
    try:
        identity = source_identity(source_dir)
    except Exception as exc:  # noqa: BLE001 - verifier must retain diagnostic
        verification.fail("SOURCE_ROOT_ERROR", str(exc), "source")
        return record
    actual_root = str(identity["source_tree_root_sha256"])
    if actual_root != record.get("source_tree_root_sha256"):
        verification.fail("SOURCE_ROOT_MISMATCH", f"expected {record.get('source_tree_root_sha256')}, got {actual_root}", "source")
    if identity.get("policy_sha256") != record.get("source_root_policy_sha256"):
        verification.fail("SOURCE_POLICY_MISMATCH", "source-root policy hash differs", "source/governance/source-root-policy.json")
    if int(identity.get("file_count", -1)) != int(record.get("source_root_file_count", -2)):
        verification.fail("SOURCE_FILE_COUNT_MISMATCH", "source-root file count differs", "SOURCE_COMMIT.json")
    verification.facts["source_tree_root_sha256"] = actual_root
    verification.facts["source_commit"] = commit
    bundle_relative = str(record.get("git_bundle", {}).get("path", "")) if isinstance(record.get("git_bundle"), dict) else ""
    archive_relative = str(record.get("source_archive", {}).get("path", "")) if isinstance(record.get("source_archive"), dict) else ""
    source_manifest_relative = str(record.get("source_file_manifest", {}).get("path", "")) if isinstance(record.get("source_file_manifest"), dict) else ""
    for label, relative, payload in (
        ("GIT_BUNDLE", bundle_relative, record.get("git_bundle")),
        ("SOURCE_ARCHIVE", archive_relative, record.get("source_archive")),
        ("SOURCE_FILE_MANIFEST", source_manifest_relative, record.get("source_file_manifest")),
    ):
        try:
            validate_relative_path(relative)
        except ValueError as exc:
            verification.fail(f"{label}_PATH", str(exc), "SOURCE_COMMIT.json")
            continue
        path = root / relative
        if not path.is_file():
            verification.fail(f"{label}_MISSING", "referenced artifact is missing", relative)
            continue
        if isinstance(payload, dict):
            if path.stat().st_size != int(payload.get("size", -1)):
                verification.fail(f"{label}_SIZE", "artifact size differs", relative)
            if sha256_file(path) != payload.get("sha256"):
                verification.fail(f"{label}_HASH", "artifact hash differs", relative)
    bundle = root / bundle_relative
    if bundle.is_file() and re.fullmatch(r"[0-9a-f]{40}", commit) and re.fullmatch(r"[0-9a-f]{40}", parent):
        with tempfile.TemporaryDirectory(prefix="sip-checkpoint-git-") as temporary:
            bare = Path(temporary) / "repo.git"
            init = _git("init", "--bare", str(bare), cwd=Path(temporary))
            if init.returncode != 0:
                verification.fail("GIT_INIT_FAILED", init.stderr.decode(errors="replace"))
            else:
                verify = _git("bundle", "verify", str(bundle), cwd=bare)
                if verify.returncode != 0:
                    verification.fail("GIT_BUNDLE_VERIFY", verify.stderr.decode(errors="replace"), bundle_relative)
                branch_ref = f"refs/heads/{branch}"
                fetch = _git("fetch", str(bundle), f"{branch_ref}:refs/heads/checkpoint", cwd=bare)
                if fetch.returncode != 0:
                    verification.fail("GIT_BUNDLE_FETCH", fetch.stderr.decode(errors="replace"), bundle_relative)
                else:
                    for object_id, code in ((commit, "GIT_COMMIT_MISSING"), (parent, "GIT_PARENT_MISSING")):
                        exists = _git("cat-file", "-e", f"{object_id}^{{commit}}", cwd=bare)
                        if exists.returncode != 0:
                            verification.fail(code, f"object {object_id} not present in bundle", bundle_relative)
                    actual_tree = _git("show", "-s", "--format=%T", commit, cwd=bare).stdout.decode().strip()
                    if actual_tree != tree:
                        verification.fail("GIT_TREE_MISMATCH", f"expected {tree}, got {actual_tree}", bundle_relative)
                    parents = _git("show", "-s", "--format=%P", commit, cwd=bare).stdout.decode().strip().split()
                    if not parents or parents[0] != parent:
                        verification.fail("GIT_PARENT_MISMATCH", f"expected first parent {parent}, got {parents}", bundle_relative)
                    actual_timestamp = _git("show", "-s", "--format=%cI", commit, cwd=bare).stdout.decode().strip()
                    if actual_timestamp != str(record.get("commit_timestamp")):
                        verification.fail("GIT_TIMESTAMP_MISMATCH", f"expected {record.get('commit_timestamp')}, got {actual_timestamp}", bundle_relative)
                    checkout = Path(temporary) / "checkout"
                    checkout.mkdir()
                    archive_bytes = _git("archive", "--format=tar", commit, cwd=bare).stdout
                    with tarfile.open(fileobj=__import__("io").BytesIO(archive_bytes), mode="r:") as tar:
                        tar.extractall(checkout, filter="data")
                    package_files = {p.relative_to(source_dir).as_posix(): p for p in source_dir.rglob("*") if p.is_file()}
                    git_files = {p.relative_to(checkout).as_posix(): p for p in checkout.rglob("*") if p.is_file()}
                    if set(package_files) != set(git_files):
                        verification.fail("SOURCE_GIT_FILESET", "packaged source file set differs from commit tree", "source")
                    else:
                        for relative in sorted(package_files):
                            if sha256_file(package_files[relative]) != sha256_file(git_files[relative]):
                                verification.fail("SOURCE_GIT_HASH", "packaged source bytes differ from commit", f"source/{relative}")
                                break
    source_archive = root / archive_relative
    if source_archive.is_file() and re.fullmatch(r"[0-9a-f]{40}", commit):
        try:
            archived: dict[str, tuple[int, str]] = {}
            archive_prefix: str | None = None
            with tarfile.open(source_archive, "r:gz") as tar:
                for member in tar.getmembers():
                    member_path = PurePosixPath(member.name)
                    if member_path.is_absolute() or any(part in {"", ".", ".."} for part in member_path.parts):
                        verification.fail("SOURCE_ARCHIVE_UNSAFE_PATH", f"unsafe archive member {member.name!r}", archive_relative)
                        continue
                    if not member.isfile():
                        if member.isdir():
                            continue
                        verification.fail("SOURCE_ARCHIVE_SPECIAL_FILE", "source archive may contain only regular files and directories", member.name)
                        continue
                    if len(member_path.parts) < 2:
                        verification.fail("SOURCE_ARCHIVE_PREFIX", "source archive file is missing a single top-level prefix", member.name)
                        continue
                    current_prefix = member_path.parts[0]
                    if archive_prefix is None:
                        archive_prefix = current_prefix
                    elif current_prefix != archive_prefix:
                        verification.fail("SOURCE_ARCHIVE_PREFIX", "source archive contains multiple top-level prefixes", member.name)
                    relative = PurePosixPath(*member_path.parts[1:]).as_posix()
                    validate_relative_path(relative)
                    extracted = tar.extractfile(member)
                    if extracted is None:
                        verification.fail("SOURCE_ARCHIVE_READ", "unable to read regular file", member.name)
                        continue
                    digest = hashlib.sha256()
                    size = 0
                    for chunk in iter(lambda: extracted.read(1024 * 1024), b""):
                        size += len(chunk)
                        if size > MAX_FILE_BYTES:
                            verification.fail("SOURCE_ARCHIVE_SIZE_LIMIT", "source archive member exceeds the per-file limit", member.name)
                            break
                        digest.update(chunk)
                    if relative in archived:
                        verification.fail("SOURCE_ARCHIVE_DUPLICATE", "duplicate source archive member", member.name)
                    archived[relative] = (size, digest.hexdigest())
            package_files = {
                path.relative_to(source_dir).as_posix(): (path.stat().st_size, sha256_file(path))
                for path in source_dir.rglob("*")
                if path.is_file()
            }
            if set(archived) != set(package_files):
                verification.fail("SOURCE_ARCHIVE_FILESET", "source archive file set differs from packaged source", archive_relative)
            else:
                for relative in sorted(package_files):
                    if archived[relative] != package_files[relative]:
                        verification.fail("SOURCE_ARCHIVE_HASH", "source archive bytes differ from packaged source", relative)
                        break
        except (tarfile.TarError, OSError, ValueError) as exc:
            verification.fail("SOURCE_ARCHIVE_INVALID", str(exc), archive_relative)
    source_manifest = _read_json(root / source_manifest_relative, verification, code="SOURCE_FILE_MANIFEST_INVALID")
    if source_manifest:
        for key, expected in (
            ("checkpoint_id", record.get("checkpoint_id")),
            ("commit", commit),
            ("tree", tree),
            ("source_tree_root_sha256", actual_root),
            ("source_root_policy_sha256", record.get("source_root_policy_sha256")),
        ):
            if source_manifest.get(key) != expected:
                verification.fail("SOURCE_FILE_MANIFEST_BINDING", f"{key} differs from source record", source_manifest_relative)
        raw_files = source_manifest.get("files")
        if not isinstance(raw_files, list):
            verification.fail("SOURCE_FILE_MANIFEST_FILES", "files must be an array", source_manifest_relative)
        else:
            expected_files: dict[str, CheckpointFileRecord] = {}
            for raw in raw_files:
                try:
                    item = CheckpointFileRecord(
                        path=validate_relative_path(str(raw["path"])),
                        size=int(raw["size"]),
                        sha256=str(raw["sha256"]),
                        mode=str(raw["mode"]),
                        kind=str(raw.get("kind", "file")),
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    verification.fail("SOURCE_FILE_MANIFEST_RECORD", str(exc), source_manifest_relative)
                    continue
                if item.path in expected_files:
                    verification.fail("SOURCE_FILE_MANIFEST_DUPLICATE", "duplicate source path", item.path)
                expected_files[item.path] = item
            actual_files = {
                path.relative_to(source_dir).as_posix(): path
                for path in source_dir.rglob("*")
                if path.is_file()
            }
            if set(expected_files) != set(actual_files):
                verification.fail("SOURCE_FILE_MANIFEST_FILESET", "source manifest file set differs from packaged source", source_manifest_relative)
            for relative, item in expected_files.items():
                path = actual_files.get(relative)
                if path is None:
                    continue
                if path.stat().st_size != item.size or sha256_file(path) != item.sha256:
                    verification.fail("SOURCE_FILE_MANIFEST_HASH", "source manifest size or hash differs", relative)
                if f"{stat.S_IMODE(path.stat().st_mode):04o}" != item.mode:
                    verification.fail("SOURCE_FILE_MANIFEST_MODE", "source manifest mode differs", relative)
            manifest_root = content_root(expected_files.values())
            if manifest_root != source_manifest.get("complete_source_content_root_sha256"):
                verification.fail("SOURCE_FILE_MANIFEST_ROOT", "complete source content root differs", source_manifest_relative)
            if int(source_manifest.get("file_count", -1)) != len(expected_files):
                verification.fail("SOURCE_FILE_MANIFEST_COUNT", "source manifest file count differs", source_manifest_relative)
    return record


def _checkpoint_facts(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("facts")
    return value if isinstance(value, dict) else {}


def _verify_evidence_wrapper(
    *,
    root: Path,
    category: str,
    relative: str,
    facts: dict[str, Any],
    verification: Verification,
) -> None:
    wrapper = _read_json(root / relative, verification, code="EVIDENCE_WRAPPER_INVALID")
    if wrapper is None:
        return
    if wrapper.get("schema") != "sip.authoritative-evidence/v1":
        verification.fail("EVIDENCE_WRAPPER_SCHEMA", f"{category} has an unsupported schema", relative)
    for key, expected in (
        ("category", category),
        ("checkpoint_id", facts.get("checkpoint_id")),
        ("source_commit", facts.get("commit")),
        ("source_tree_root_sha256", facts.get("source_tree_root_sha256")),
    ):
        if wrapper.get(key) != expected:
            verification.fail("EVIDENCE_WRAPPER_BINDING", f"{category}.{key} differs from checkpoint facts", relative)
    status = wrapper.get("status")
    if status not in {"passed_complete", "passed_with_external_gaps", "blocked", "failed"}:
        verification.fail("EVIDENCE_WRAPPER_STATUS", f"invalid status {status!r}", relative)
    artifacts = wrapper.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        verification.fail("EVIDENCE_WRAPPER_ARTIFACTS", "wrapper must identify at least one artifact", relative)
        return
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            verification.fail("EVIDENCE_ARTIFACT_RECORD", "artifact record must be an object", relative)
            continue
        artifact_relative = str(artifact.get("path", ""))
        try:
            validate_relative_path(artifact_relative)
        except ValueError as exc:
            verification.fail("EVIDENCE_ARTIFACT_PATH", str(exc), relative)
            continue
        path = root / artifact_relative
        if not path.is_file():
            verification.fail("EVIDENCE_ARTIFACT_MISSING", f"{category} artifact is missing", artifact_relative)
            continue
        expected_hash = artifact.get("sha256")
        if expected_hash and sha256_file(path) != expected_hash:
            verification.fail("EVIDENCE_ARTIFACT_HASH", f"{category} artifact hash differs", artifact_relative)
        if "size" in artifact and path.stat().st_size != int(artifact.get("size", -1)):
            verification.fail("EVIDENCE_ARTIFACT_SIZE", f"{category} artifact size differs", artifact_relative)
    if category == "python_matrix":
        matrix_path = root / "build/reports/test-matrix.json"
        matrix = _read_json(matrix_path, verification, code="PYTHON_MATRIX_INVALID")
        if matrix:
            evidence = matrix.get("evidence") if isinstance(matrix.get("evidence"), dict) else {}
            totals = matrix.get("totals") if isinstance(matrix.get("totals"), dict) else {}
            if matrix.get("status") not in {"passed", "passed_complete"}:
                verification.fail("PYTHON_MATRIX_STATUS", "Python matrix is not passing", str(matrix_path.relative_to(root)))
            if evidence.get("git_commit") != facts.get("commit"):
                verification.fail("PYTHON_MATRIX_COMMIT", "Python matrix is bound to another commit", str(matrix_path.relative_to(root)))
            if evidence.get("source_tree_root_sha256") != facts.get("source_tree_root_sha256"):
                verification.fail("PYTHON_MATRIX_SOURCE_ROOT", "Python matrix is bound to another source root", str(matrix_path.relative_to(root)))
            if bool(evidence.get("git_dirty")):
                verification.fail("PYTHON_MATRIX_DIRTY", "Python matrix was executed from a dirty worktree", str(matrix_path.relative_to(root)))
            for key in ("failures", "errors", "skipped"):
                if int(totals.get(key, -1)) != 0:
                    verification.fail("PYTHON_MATRIX_RESULT", f"Python matrix {key} must be zero", str(matrix_path.relative_to(root)))
            if int(totals.get("tests", -1)) != int(facts.get("python_tests_passed", -2)):
                verification.fail("PYTHON_MATRIX_COUNT", "Python matrix count differs from checkpoint facts", str(matrix_path.relative_to(root)))


def _verify_status_and_evidence(root: Path, verification: Verification, source_record: dict[str, Any] | None) -> None:
    checkpoint_path = root / "build/checkpoints/progress-04-r1.json"
    checkpoint = _read_json(checkpoint_path, verification, code="CHECKPOINT_RECORD_INVALID")
    if checkpoint is None:
        return
    facts = _checkpoint_facts(checkpoint)
    required_fact_fields = (
        "checkpoint_id", "branch", "commit", "parent", "tree", "source_tree_root_sha256", "working_tree_clean",
        "python_tests_passed", "python_baseline_tests_passed", "python_remediation_tests_passed",
        "swift_tests_passed", "web_runtime_tests_passed", "web_source_checks_passed",
        "requirements_total", "requirements_by_status", "next_cluster",
    )
    for field in required_fact_fields:
        if field not in facts:
            verification.fail("CHECKPOINT_FACT_MISSING", f"missing fact {field}", "build/checkpoints/progress-04-r1.json")
    if source_record:
        for field in ("commit", "parent", "tree", "branch", "source_tree_root_sha256"):
            if facts.get(field) != source_record.get(field):
                verification.fail("CHECKPOINT_SOURCE_CONTRADICTION", f"{field} differs from SOURCE_COMMIT.json", "build/checkpoints/progress-04-r1.json")
    if facts.get("working_tree_clean") is not True or facts.get("tested_detached_worktree") is not True:
        verification.fail("CHECKPOINT_WORKTREE_ATTESTATION", "checkpoint must attest a clean detached tested worktree", "build/checkpoints/progress-04-r1.json")
    if int(facts.get("python_baseline_tests_passed", -1)) != 197:
        verification.fail("CHECKPOINT_BASELINE_COUNT", "the retained Progress 04 Python baseline must equal 197", "build/checkpoints/progress-04-r1.json")
    if int(facts.get("python_tests_passed", -1)) - 197 != int(facts.get("python_remediation_tests_passed", -2)):
        verification.fail("CHECKPOINT_REMEDIATION_COUNT", "current, baseline, and remediation Python counts are inconsistent", "build/checkpoints/progress-04-r1.json")
    latest = _read_json(root / "build/release/latest.json", verification, code="LATEST_INVALID")
    if latest:
        for key in ("checkpoint_id", "commit", "source_tree_root_sha256"):
            if latest.get(key) != facts.get(key):
                verification.fail("LATEST_CONTRADICTION", f"latest.{key} differs from checkpoint facts", "build/release/latest.json")
    milestone = _read_json(root / "MILESTONE_SCOPE_PROGRESS_04.json", verification, code="MILESTONE_SCOPE_INVALID")
    if milestone:
        for key in ("checkpoint_id", "source_commit", "source_tree_root_sha256"):
            expected = facts.get("commit") if key == "source_commit" else facts.get(key)
            if milestone.get(key) != expected:
                verification.fail("MILESTONE_SCOPE_CONTRADICTION", f"{key} differs from checkpoint facts", "MILESTONE_SCOPE_PROGRESS_04.json")
        if milestone.get("authoritative_wording") != MILESTONE_WORDING:
            verification.fail("MILESTONE_WORDING", "milestone wording is broader than the authorized checkpoint scope", "MILESTONE_SCOPE_PROGRESS_04.json")
        included = milestone.get("included_requirements", [])
        deferred = milestone.get("deferred_requirements", [])
        if not isinstance(included, list) or any(not isinstance(item, dict) for item in included):
            verification.fail("MILESTONE_SCOPE_INCLUDED", "included_requirements must be a list of objects", "MILESTONE_SCOPE_PROGRESS_04.json")
        else:
            for item in included:
                if item.get("status") == "VERIFIED" and not item.get("evidence_paths"):
                    verification.fail("MILESTONE_VERIFIED_WITHOUT_EVIDENCE", f"{item.get('requirement_id')} lacks evidence", "MILESTONE_SCOPE_PROGRESS_04.json")
                if item.get("status") == "NOT_STARTED":
                    verification.fail("MILESTONE_NOT_STARTED_INCLUDED", f"{item.get('requirement_id')} cannot be included", "MILESTONE_SCOPE_PROGRESS_04.json")
        if not isinstance(deferred, list) or any(not isinstance(item, dict) for item in deferred):
            verification.fail("MILESTONE_SCOPE_DEFERRED", "deferred_requirements must be a list of objects", "MILESTONE_SCOPE_PROGRESS_04.json")
        ledger = _read_json(root / "source/requirements/requirements-ledger.json", verification, code="SOURCE_LEDGER_INVALID")
        if ledger and isinstance(ledger.get("requirements"), list) and isinstance(included, list) and isinstance(deferred, list):
            hybrid = {
                str(item.get("requirement_id")): str(item.get("implementation_status"))
                for item in ledger["requirements"]
                if isinstance(item, dict) and str(item.get("requirement_id", "")).startswith("HYB")
            }
            scoped = {
                str(item.get("requirement_id")): str(item.get("status"))
                for item in [*included, *deferred]
                if isinstance(item, dict)
            }
            if len(hybrid) != 48 or scoped != hybrid:
                verification.fail("MILESTONE_LEDGER_DRIFT", "milestone scope does not exactly partition all 48 HYB requirements", "MILESTONE_SCOPE_PROGRESS_04.json")
            expected_counts = {"VERIFIED": 8, "IMPLEMENTED_UNVERIFIED": 9, "NOT_STARTED": 31}
            actual_counts = {status: sum(value == status for value in hybrid.values()) for status in expected_counts}
            if actual_counts != expected_counts:
                verification.fail("MILESTONE_STATUS_DRIFT", f"expected {expected_counts}, got {actual_counts}", "MILESTONE_SCOPE_PROGRESS_04.json")
    evidence_index = _read_json(root / "build/evidence/AUTHORITATIVE_EVIDENCE_INDEX.json", verification, code="EVIDENCE_INDEX_INVALID")
    if evidence_index:
        entries = evidence_index.get("authoritative")
        if not isinstance(entries, dict):
            verification.fail("EVIDENCE_INDEX_ENTRIES", "authoritative must be an object", "build/evidence/AUTHORITATIVE_EVIDENCE_INDEX.json")
        else:
            missing = REQUIRED_EVIDENCE_CATEGORIES - set(entries)
            extra = set(entries) - REQUIRED_EVIDENCE_CATEGORIES
            if missing:
                verification.fail("EVIDENCE_CATEGORY_MISSING", f"missing categories: {sorted(missing)}", "build/evidence/AUTHORITATIVE_EVIDENCE_INDEX.json")
            if extra:
                verification.fail("EVIDENCE_CATEGORY_EXTRA", f"unexpected categories: {sorted(extra)}", "build/evidence/AUTHORITATIVE_EVIDENCE_INDEX.json")
            seen_paths: set[str] = set()
            for category, entry in entries.items():
                if not isinstance(entry, dict):
                    verification.fail("EVIDENCE_ENTRY", f"{category} must be an object", "build/evidence/AUTHORITATIVE_EVIDENCE_INDEX.json")
                    continue
                relative = str(entry.get("path", ""))
                try:
                    validate_relative_path(relative)
                except ValueError as exc:
                    verification.fail("EVIDENCE_PATH", str(exc), "build/evidence/AUTHORITATIVE_EVIDENCE_INDEX.json")
                    continue
                if relative in seen_paths:
                    verification.fail("EVIDENCE_DUPLICATE_CURRENT", f"multiple categories point to {relative}", "build/evidence/AUTHORITATIVE_EVIDENCE_INDEX.json")
                seen_paths.add(relative)
                path = root / relative
                if not path.is_file():
                    verification.fail("EVIDENCE_FILE_MISSING", f"{category} artifact is absent", relative)
                    continue
                if sha256_file(path) != entry.get("sha256"):
                    verification.fail("EVIDENCE_HASH_MISMATCH", f"{category} artifact hash differs", relative)
                if entry.get("source_commit") != facts.get("commit") or entry.get("source_tree_root_sha256") != facts.get("source_tree_root_sha256"):
                    verification.fail("EVIDENCE_BINDING_MISMATCH", f"{category} is not bound to current source", relative)
                _verify_evidence_wrapper(
                    root=root,
                    category=category,
                    relative=relative,
                    facts=facts,
                    verification=verification,
                )
    for markdown in ("IMPLEMENTATION_STATUS.md", "RESUME_IMPLEMENTATION.md", "requirements/coverage-report.md"):
        path = root / markdown
        if not path.is_file():
            verification.fail("STATUS_FILE_MISSING", "required status document is absent", markdown)
            continue
        text = path.read_text(encoding="utf-8")
        for value, label in (
            (facts.get("commit"), "commit"),
            (facts.get("source_tree_root_sha256"), "source root"),
            (str(facts.get("python_tests_passed")), "current Python test count"),
            (str(facts.get("python_baseline_tests_passed")), "baseline Python test count"),
        ):
            if value is not None and str(value) not in text:
                verification.fail("STATUS_FILE_STALE", f"document does not contain current {label}", markdown)
    verification.facts["checkpoint_id"] = facts.get("checkpoint_id")


def verify_archive(archive_path: Path) -> dict[str, Any]:
    archive_path = archive_path.resolve()
    verification = Verification(archive_path)
    if not archive_path.is_file():
        verification.fail("ARCHIVE_MISSING", "checkpoint ZIP does not exist", str(archive_path))
        return _report(verification)
    verification.facts["archive_sha256"] = sha256_file(archive_path)
    verification.facts["archive_size"] = archive_path.stat().st_size
    with tempfile.TemporaryDirectory(prefix="sip-checkpoint-verify-") as temporary:
        extract_root = Path(temporary) / "extract"
        extract_root.mkdir()
        try:
            with zipfile.ZipFile(archive_path) as archive:
                top_level, _ = _validate_zip_metadata(archive, verification)
                _extract_checked(archive, extract_root, verification)
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            verification.fail("ZIP_INVALID", str(exc), str(archive_path))
            return _report(verification)
        if top_level is None:
            return _report(verification)
        root = extract_root / top_level
        verification.facts["top_level"] = top_level
        manifest = _verify_manifest(root, verification)
        if manifest and manifest.get("top_level") != top_level:
            verification.fail("MANIFEST_TOP_LEVEL", f"expected {top_level}, got {manifest.get('top_level')}", MANIFEST_PATH)
        spec = root / "source/spec/source/Spatial-Intelligence-Platform-Spec-v1.1.zip"
        if not spec.is_file():
            verification.fail("SPEC_ARCHIVE_MISSING", "authoritative specification ZIP is absent", str(spec.relative_to(root)))
        elif sha256_file(spec) != EXPECTED_SPEC_SHA256:
            verification.fail("SPEC_ARCHIVE_HASH", "authoritative specification hash differs", str(spec.relative_to(root)))
        else:
            verification.facts["specification_sha256"] = EXPECTED_SPEC_SHA256
        source_record = _verify_git_and_source(root, verification)
        _verify_status_and_evidence(root, verification, source_record)
    return _report(verification)


def _report(verification: Verification) -> dict[str, Any]:
    return {
        "schema": "sip.checkpoint-verification-report/v1",
        "status": "passed_complete" if not verification.findings else "failed",
        "archive": str(verification.archive),
        "facts": verification.facts,
        "finding_count": len(verification.findings),
        "findings": [asdict(item) for item in verification.findings],
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
