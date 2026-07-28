#!/usr/bin/env python3
"""Independently verify a SIP Progress 05 checkpoint ZIP and its source/evidence provenance."""
from __future__ import annotations

import argparse
import json
import tempfile
import sys
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_progress05_checkpoint import (
    CHECKPOINT_ID,
    EXPECTED_SPEC_SHA256,
    MILESTONE_WORDING,
    P05_SCOPE_IDS,
    REQUIRED_EVIDENCE_CATEGORIES,
    TOP_LEVEL,
)
from tools.checkpoint_common import MANIFEST_PATH, sha256_file, validate_relative_path
from tools.verify_checkpoint import (
    Verification,
    _checkpoint_facts,
    _extract_checked,
    _read_json,
    _report,
    _validate_zip_metadata,
    _verify_evidence_wrapper,
    _verify_git_and_source,
    _verify_manifest,
)

EXPECTED_PREDECESSOR_ZIP_SHA256 = "892f5b9d1995b2016eb80a524989af4813bfa408788e439edf0996a470b73bf5"
EXPECTED_IMPORT_COMMIT = "36e9c44d21a9c47d85971ee945daec8fc98e26d6"
EXPECTED_ACCEPTED_P04_COMMIT = "8fe87d030c68157c50b477de8d2480065ca0b6a8"
EXPECTED_ACCEPTED_P04_ZIP_SHA256 = "0d5a2584b412d05d8cff933d8170d6faa411a7cc6be095356995442517254079"


def _verify_bound_runtime_report(
    root: Path,
    verification: Verification,
    *,
    relative: str,
    facts: dict[str, Any],
    minimum_tests: int,
    minimum_source_checks: int = 0,
) -> None:
    report = _read_json(root / relative, verification, code="RUNTIME_REPORT_INVALID")
    if report is None:
        return
    git = report.get("git") if isinstance(report.get("git"), dict) else {}
    if git.get("commit") != facts.get("commit") or git.get("source_tree_root_sha256") != facts.get("source_tree_root_sha256"):
        verification.fail("RUNTIME_REPORT_BINDING", "runtime report is bound to another source", relative)
    if git.get("working_tree_clean_before_tests") is not True:
        verification.fail("RUNTIME_REPORT_DIRTY", "runtime report did not begin from a clean worktree", relative)
    if report.get("status") not in {"passed", "passed_complete", "passed_with_external_gaps"}:
        verification.fail("RUNTIME_REPORT_STATUS", f"invalid passing status {report.get('status')!r}", relative)
    if int(report.get("tests_failed", -1)) != 0 or int(report.get("tests_passed", -1)) < minimum_tests:
        verification.fail("RUNTIME_REPORT_COUNT", "runtime test counts do not meet the checkpoint minimum", relative)
    if minimum_source_checks and int(report.get("source_invariant_checks", -1)) < minimum_source_checks:
        verification.fail("RUNTIME_SOURCE_CHECK_COUNT", "web source checks do not meet the checkpoint minimum", relative)


def _verify_predecessor(root: Path, verification: Verification) -> None:
    relative = "PREDECESSOR_CHECKPOINT.json"
    record = _read_json(root / relative, verification, code="PREDECESSOR_INVALID")
    source_record = _read_json(root / "source/PREDECESSOR_CHECKPOINT.json", verification, code="SOURCE_PREDECESSOR_INVALID")
    if record is None or source_record is None:
        return
    if record != source_record:
        verification.fail("PREDECESSOR_COPY_MISMATCH", "package and committed predecessor records differ", relative)
    predecessor = record.get("predecessor") if isinstance(record.get("predecessor"), dict) else {}
    mapping = record.get("import_mapping") if isinstance(record.get("import_mapping"), dict) else {}
    accepted = record.get("accepted_checkpoint") if isinstance(record.get("accepted_checkpoint"), dict) else {}
    checks = [
        (predecessor.get("zip_sha256"), EXPECTED_PREDECESSOR_ZIP_SHA256, "predecessor ZIP hash"),
        (mapping.get("commit"), EXPECTED_IMPORT_COMMIT, "import commit"),
        (accepted.get("commit"), EXPECTED_ACCEPTED_P04_COMMIT, "accepted Progress 04-R1 commit"),
        (accepted.get("project_zip_sha256"), EXPECTED_ACCEPTED_P04_ZIP_SHA256, "accepted Progress 04-R1 ZIP hash"),
    ]
    for actual, expected, label in checks:
        if actual != expected:
            verification.fail("PREDECESSOR_MAPPING_MISMATCH", f"{label} differs", relative)


def _verify_status_and_evidence(root: Path, verification: Verification, source_record: dict[str, Any] | None) -> None:
    checkpoint_relative = "build/checkpoints/progress-05.json"
    checkpoint = _read_json(root / checkpoint_relative, verification, code="CHECKPOINT_RECORD_INVALID")
    if checkpoint is None:
        return
    facts = _checkpoint_facts(checkpoint)
    required_fields = {
        "checkpoint_id", "branch", "commit", "parent", "tree", "source_tree_root_sha256", "working_tree_clean",
        "python_tests_passed", "swift_tests_passed", "web_runtime_tests_passed", "web_source_checks_passed",
        "desktop_tests_passed", "generated_contract_artifacts", "requirements_total", "requirements_by_status",
        "next_cluster", "production_authorized",
    }
    for field in sorted(required_fields):
        if field not in facts:
            verification.fail("CHECKPOINT_FACT_MISSING", f"missing checkpoint fact {field}", checkpoint_relative)
    if facts.get("checkpoint_id") != CHECKPOINT_ID:
        verification.fail("CHECKPOINT_ID", f"expected {CHECKPOINT_ID}, got {facts.get('checkpoint_id')}", checkpoint_relative)
    if checkpoint.get("milestone_wording") != MILESTONE_WORDING:
        verification.fail("CHECKPOINT_WORDING", "checkpoint wording differs from the authorized Progress 05 scope", checkpoint_relative)
    if checkpoint.get("release_posture") != "blocked" or facts.get("production_authorized") is not False:
        verification.fail("CHECKPOINT_RELEASE_POSTURE", "production release must remain blocked", checkpoint_relative)
    if facts.get("working_tree_clean") is not True or facts.get("tested_detached_worktree") is not True:
        verification.fail("CHECKPOINT_WORKTREE", "checkpoint was not tested from a clean detached worktree", checkpoint_relative)
    if int(facts.get("requirements_total", -1)) != 1028:
        verification.fail("CHECKPOINT_REQUIREMENT_COUNT", "checkpoint must retain all 1,028 requirements", checkpoint_relative)
    if int(facts.get("python_tests_passed", -1)) < 220:
        verification.fail("CHECKPOINT_TEST_BASELINE", "Progress 05 Python matrix is below the authorized baseline", checkpoint_relative)
    if int(facts.get("swift_tests_passed", -1)) < 13 or int(facts.get("web_runtime_tests_passed", -1)) < 12 or int(facts.get("web_source_checks_passed", -1)) < 26 or int(facts.get("desktop_tests_passed", -1)) < 15:
        verification.fail("CHECKPOINT_RUNTIME_BASELINE", "one or more runtime profiles are below the Progress 05 minimum", checkpoint_relative)
    if source_record:
        for key in ("commit", "parent", "tree", "branch", "source_tree_root_sha256"):
            if facts.get(key) != source_record.get(key):
                verification.fail("CHECKPOINT_SOURCE_CONTRADICTION", f"checkpoint {key} differs from SOURCE_COMMIT.json", checkpoint_relative)

    latest_relative = "build/release/latest.json"
    latest = _read_json(root / latest_relative, verification, code="LATEST_INVALID")
    if latest:
        for key in ("checkpoint_id", "commit", "tree", "branch", "source_tree_root_sha256"):
            if latest.get(key) != facts.get(key):
                verification.fail("LATEST_CONTRADICTION", f"latest.{key} differs from checkpoint facts", latest_relative)
        if latest.get("readiness") != "blocked" or latest.get("production_authorized") is not False:
            verification.fail("LATEST_RELEASE_POSTURE", "latest pointer must remain production blocked", latest_relative)

    milestone_relative = "MILESTONE_SCOPE_PROGRESS_05.json"
    milestone = _read_json(root / milestone_relative, verification, code="MILESTONE_SCOPE_INVALID")
    if milestone:
        for key in ("checkpoint_id", "source_commit", "source_tree_root_sha256"):
            expected = facts.get("commit") if key == "source_commit" else facts.get(key)
            if milestone.get(key) != expected:
                verification.fail("MILESTONE_SCOPE_CONTRADICTION", f"{key} differs from checkpoint facts", milestone_relative)
        if milestone.get("authoritative_wording") != MILESTONE_WORDING:
            verification.fail("MILESTONE_WORDING", "milestone wording differs", milestone_relative)
        scope_ids = milestone.get("scope_requirement_ids")
        if not isinstance(scope_ids, list) or set(map(str, scope_ids)) != P05_SCOPE_IDS:
            verification.fail("MILESTONE_SCOPE_IDS", "Progress 05 scope IDs differ from the authorized set", milestone_relative)
        included = milestone.get("included_requirements")
        deferred = milestone.get("deferred_requirements")
        if not isinstance(included, list) or not isinstance(deferred, list):
            verification.fail("MILESTONE_SCOPE_PARTITION", "included and deferred requirements must be lists", milestone_relative)
        else:
            scoped = {
                str(item.get("requirement_id")): str(item.get("status"))
                for item in [*included, *deferred]
                if isinstance(item, dict)
            }
            ledger = _read_json(root / "source/requirements/requirements-ledger.json", verification, code="SOURCE_LEDGER_INVALID")
            if ledger and isinstance(ledger.get("requirements"), list):
                expected = {
                    str(item.get("requirement_id")): str(item.get("implementation_status"))
                    for item in ledger["requirements"]
                    if isinstance(item, dict) and str(item.get("requirement_id")) in P05_SCOPE_IDS
                }
                if scoped != expected or set(scoped) != P05_SCOPE_IDS:
                    verification.fail("MILESTONE_LEDGER_DRIFT", "milestone scope does not exactly match the source ledger", milestone_relative)
                counts: dict[str, int] = {}
                for item in ledger["requirements"]:
                    if isinstance(item, dict):
                        status = str(item.get("implementation_status"))
                        counts[status] = counts.get(status, 0) + 1
                if facts.get("requirements_by_status") != dict(sorted(counts.items())):
                    verification.fail("REQUIREMENT_STATUS_DRIFT", "checkpoint status counts differ from the source ledger", checkpoint_relative)
            for item in included:
                if not isinstance(item, dict):
                    verification.fail("MILESTONE_SCOPE_RECORD", "included requirement must be an object", milestone_relative)
                    continue
                if item.get("status") == "NOT_STARTED":
                    verification.fail("MILESTONE_NOT_STARTED_INCLUDED", f"{item.get('requirement_id')} cannot be included", milestone_relative)
                if item.get("status") == "VERIFIED" and not item.get("evidence_paths"):
                    verification.fail("MILESTONE_VERIFIED_WITHOUT_EVIDENCE", f"{item.get('requirement_id')} lacks evidence", milestone_relative)

    evidence_relative = "build/evidence/AUTHORITATIVE_EVIDENCE_INDEX.json"
    index = _read_json(root / evidence_relative, verification, code="EVIDENCE_INDEX_INVALID")
    if index:
        for key, expected in (("checkpoint_id", CHECKPOINT_ID), ("source_commit", facts.get("commit")), ("source_tree_root_sha256", facts.get("source_tree_root_sha256"))):
            if index.get(key) != expected:
                verification.fail("EVIDENCE_INDEX_BINDING", f"{key} differs", evidence_relative)
        entries = index.get("authoritative")
        if not isinstance(entries, dict):
            verification.fail("EVIDENCE_INDEX_ENTRIES", "authoritative must be an object", evidence_relative)
        else:
            if set(entries) != REQUIRED_EVIDENCE_CATEGORIES:
                verification.fail("EVIDENCE_CATEGORIES", f"expected {sorted(REQUIRED_EVIDENCE_CATEGORIES)}, got {sorted(entries)}", evidence_relative)
            seen: set[str] = set()
            for category, entry in entries.items():
                if not isinstance(entry, dict):
                    verification.fail("EVIDENCE_ENTRY", f"{category} must be an object", evidence_relative)
                    continue
                relative = str(entry.get("path", ""))
                try:
                    validate_relative_path(relative)
                except ValueError as exc:
                    verification.fail("EVIDENCE_PATH", str(exc), evidence_relative)
                    continue
                if relative in seen:
                    verification.fail("EVIDENCE_DUPLICATE_CURRENT", f"duplicate current wrapper {relative}", evidence_relative)
                seen.add(relative)
                path = root / relative
                if not path.is_file():
                    verification.fail("EVIDENCE_FILE_MISSING", f"{category} wrapper is absent", relative)
                    continue
                if sha256_file(path) != entry.get("sha256"):
                    verification.fail("EVIDENCE_HASH_MISMATCH", f"{category} wrapper hash differs", relative)
                if entry.get("source_commit") != facts.get("commit") or entry.get("source_tree_root_sha256") != facts.get("source_tree_root_sha256"):
                    verification.fail("EVIDENCE_BINDING_MISMATCH", f"{category} wrapper differs from current source", relative)
                _verify_evidence_wrapper(root=root, category=category, relative=relative, facts=facts, verification=verification)

    _verify_bound_runtime_report(root, verification, relative="build/reports/swift-test-report.json", facts=facts, minimum_tests=13)
    _verify_bound_runtime_report(root, verification, relative="build/reports/web-runtime-test-report.json", facts=facts, minimum_tests=12, minimum_source_checks=26)
    _verify_bound_runtime_report(root, verification, relative="build/reports/desktop-review-test-report.json", facts=facts, minimum_tests=15)

    readiness_relative = "build/reports/release-readiness-progress-05.json"
    readiness = _read_json(root / readiness_relative, verification, code="RELEASE_READINESS_INVALID")
    if readiness:
        source = readiness.get("source") if isinstance(readiness.get("source"), dict) else {}
        if readiness.get("checkpoint_id") != CHECKPOINT_ID or readiness.get("status") != "blocked" or readiness.get("production_authorized") is not False:
            verification.fail("RELEASE_READINESS_POSTURE", "Progress 05 release readiness must remain blocked", readiness_relative)
        if source.get("commit") != facts.get("commit") or source.get("source_tree_root_sha256") != facts.get("source_tree_root_sha256"):
            verification.fail("RELEASE_READINESS_BINDING", "release readiness is bound to another source", readiness_relative)

    for markdown in ("IMPLEMENTATION_STATUS.md", "RESUME_IMPLEMENTATION.md", "requirements/coverage-report.md", "FINAL_IMPLEMENTATION_REPORT.md"):
        path = root / markdown
        if not path.is_file():
            verification.fail("STATUS_FILE_MISSING", "required status document is absent", markdown)
            continue
        text = path.read_text(encoding="utf-8")
        for value, label in (
            (facts.get("commit"), "commit"),
            (facts.get("source_tree_root_sha256"), "source root"),
            (str(facts.get("python_tests_passed")), "Python test count"),
        ):
            if value is not None and str(value) not in text:
                verification.fail("STATUS_FILE_STALE", f"document does not contain current {label}", markdown)
        if "Production" not in text or not any(word in text for word in ("NO-GO", "blocked", "fail-closed")):
            verification.fail("STATUS_RELEASE_POSTURE", "status document does not state the blocked production posture", markdown)
    readme = root / "README_CHECKPOINT.md"
    if not readme.is_file() or f"git clone -b {facts.get('branch')}" not in readme.read_text(encoding="utf-8"):
        verification.fail("BUNDLE_CLONE_DOCUMENTATION", "checkpoint README lacks the explicit branch clone command", "README_CHECKPOINT.md")
    verification.facts["checkpoint_id"] = facts.get("checkpoint_id")


def verify_archive(archive_path: Path) -> dict[str, Any]:
    archive_path = archive_path.resolve()
    verification = Verification(archive_path)
    if not archive_path.is_file():
        verification.fail("ARCHIVE_MISSING", "checkpoint ZIP does not exist", str(archive_path))
        return _report(verification)
    verification.facts["archive_sha256"] = sha256_file(archive_path)
    verification.facts["archive_size"] = archive_path.stat().st_size
    with tempfile.TemporaryDirectory(prefix="sip-progress05-verify-") as temporary:
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
        verification.facts["top_level"] = top_level
        if top_level != TOP_LEVEL:
            verification.fail("ZIP_TOP_LEVEL_NAME", f"expected {TOP_LEVEL}, got {top_level}")
        root = extract_root / top_level
        manifest = _verify_manifest(root, verification)
        if manifest:
            if manifest.get("top_level") != top_level:
                verification.fail("MANIFEST_TOP_LEVEL", f"expected {top_level}, got {manifest.get('top_level')}", MANIFEST_PATH)
            if manifest.get("checkpoint_id") != CHECKPOINT_ID:
                verification.fail("MANIFEST_CHECKPOINT_ID", f"expected {CHECKPOINT_ID}, got {manifest.get('checkpoint_id')}", MANIFEST_PATH)
        spec = root / "source/spec/source/Spatial-Intelligence-Platform-Spec-v1.1.zip"
        if not spec.is_file():
            verification.fail("SPEC_ARCHIVE_MISSING", "authoritative specification ZIP is absent", str(spec.relative_to(root)))
        elif sha256_file(spec) != EXPECTED_SPEC_SHA256:
            verification.fail("SPEC_ARCHIVE_HASH", "authoritative specification hash differs", str(spec.relative_to(root)))
        else:
            verification.facts["specification_sha256"] = EXPECTED_SPEC_SHA256
        source_record = _verify_git_and_source(root, verification)
        if source_record and source_record.get("checkpoint_id") != CHECKPOINT_ID:
            verification.fail("SOURCE_CHECKPOINT_ID", "SOURCE_COMMIT.json identifies another checkpoint", "SOURCE_COMMIT.json")
        _verify_predecessor(root, verification)
        _verify_status_and_evidence(root, verification, source_record)
    return _report(verification)


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
