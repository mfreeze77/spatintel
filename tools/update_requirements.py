#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "requirements/spec-index.json"
MAPPING = ROOT / "requirements/implementation-map.json"
JSON_LEDGER = ROOT / "requirements/requirements-ledger.json"
CSV_LEDGER = ROOT / "requirements/requirements-ledger.csv"
SQLITE_LEDGER = ROOT / "requirements/requirements-ledger.sqlite"
TEST_PLANS = ROOT / "tests/spec/requirements"

ALLOWED_OVERLAY_FIELDS = {
    "implementation_status",
    "implementation_files",
    "test_ids",
    "test_result_evidence_paths",
    "external_validation_status",
    "waiver_status",
    "waiver_expiration",
    "notes",
    "owner",
    "first_passing_release",
    "last_regression_result",
    "adr_links",
    "linked_tests_passed",
    "failed_or_missing_test_evidence",
}


def _load() -> tuple[dict[str, Any], dict[str, Any]]:
    return json.loads(BASELINE.read_text(encoding="utf-8")), json.loads(MAPPING.read_text(encoding="utf-8"))


def _merge() -> dict[str, Any]:
    baseline, mapping = _load()
    result = deepcopy(baseline)
    overlays = mapping.get("requirements", {})
    known = {item["requirement_id"] for item in result["requirements"]}
    unknown = sorted(set(overlays) - known)
    if unknown:
        raise ValueError(f"implementation map contains unknown requirement IDs: {unknown}")
    for item in result["requirements"]:
        overlay = overlays.get(item["requirement_id"], {})
        forbidden = sorted(set(overlay) - ALLOWED_OVERLAY_FIELDS)
        if forbidden:
            raise ValueError(f"{item['requirement_id']} has forbidden overlay fields: {forbidden}")
        item.update(deepcopy(overlay))
    epic_overlays = mapping.get("epics", {})
    known_epics = {item["id"] for item in result.get("epics", [])}
    if set(epic_overlays) - known_epics:
        raise ValueError(f"unknown epic overlays: {sorted(set(epic_overlays) - known_epics)}")
    for epic in result.get("epics", []):
        overlay = epic_overlays.get(epic["id"], {})
        if "completed_tasks" in overlay:
            completed = set(overlay["completed_tasks"])
            for task in epic.get("tasks", []):
                task["completed"] = task["id"] in completed
        if "completed" in overlay:
            epic["completed"] = bool(overlay["completed"])
    result["generated_at"] = datetime.now(UTC).isoformat()
    return result


def _write_test_plans(ledger: dict[str, Any]) -> None:
    TEST_PLANS.mkdir(parents=True, exist_ok=True)
    expected: set[Path] = set()
    for requirement in ledger["requirements"]:
        path = ROOT / requirement["test_plan_path"]
        expected.add(path.resolve())
        implementation = requirement.get("implementation_files", [])
        tests = requirement.get("test_ids", [])
        evidence = requirement.get("test_result_evidence_paths", [])
        plan = {
            "schema_version": "1.0",
            "requirement_id": requirement["requirement_id"],
            "priority": requirement["priority"],
            "source": {
                "document": requirement["source_document"],
                "line": requirement["source_line"],
                "section": requirement["source_section"],
            },
            "requirement": requirement["text"],
            "verification_method": requirement["verification_method"],
            "implementation_status": requirement["implementation_status"],
            "implementation_files": implementation,
            "automated_test_ids": tests,
            "retained_evidence": evidence,
            "controlled_procedure": [
                "Verify all listed implementation files exist at the reviewed commit.",
                "Execute each listed automated test or the documented controlled procedure in an isolated environment.",
                "Retain machine-readable results, input/output hashes, toolchain, code revision, and environment profile.",
                "Confirm negative/failure behavior and authority, consent, security, recovery, or licensing controls applicable to the requirement.",
                "Update the ledger only after evidence paths exist and independently match the claimed result.",
            ],
            "external_validation": {
                "status": requirement.get("external_validation_status", "NOT_REQUIRED"),
                "owner": requirement.get("owner", "UNASSIGNED"),
                "gap": requirement.get("notes", ""),
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(plan, sort_keys=False, width=120), encoding="utf-8")
    for path in TEST_PLANS.glob("*.yaml"):
        if path.resolve() not in expected:
            path.unlink()


def _write_csv(ledger: dict[str, Any]) -> None:
    fields = [
        "requirement_id",
        "priority",
        "implementation_status",
        "source_document",
        "source_line",
        "source_section",
        "text",
        "verification_method",
        "owner",
        "release_gate",
        "external_validation_status",
        "waiver_status",
        "waiver_expiration",
        "implementation_files",
        "test_ids",
        "test_result_evidence_paths",
        "dependency_ids",
        "epic_ids",
        "notes",
    ]
    with CSV_LEDGER.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fields, lineterminator="\n")
        writer.writeheader()
        for requirement in ledger["requirements"]:
            row = {key: requirement.get(key) for key in fields}
            for key in ["implementation_files", "test_ids", "test_result_evidence_paths", "dependency_ids", "epic_ids"]:
                row[key] = json.dumps(row[key], separators=(",", ":"))
            writer.writerow(row)


def _write_sqlite(ledger: dict[str, Any]) -> None:
    if SQLITE_LEDGER.exists():
        SQLITE_LEDGER.unlink()
    connection = sqlite3.connect(SQLITE_LEDGER)
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute(
            """CREATE TABLE requirements (
                requirement_id TEXT PRIMARY KEY,
                priority TEXT NOT NULL,
                implementation_status TEXT NOT NULL,
                source_document TEXT NOT NULL,
                source_line INTEGER NOT NULL,
                source_section TEXT NOT NULL,
                requirement_text TEXT NOT NULL,
                verification_method TEXT NOT NULL,
                owner TEXT NOT NULL,
                release_gate TEXT,
                external_validation_status TEXT NOT NULL,
                waiver_status TEXT NOT NULL,
                waiver_expiration TEXT,
                implementation_files_json TEXT NOT NULL,
                test_ids_json TEXT NOT NULL,
                evidence_paths_json TEXT NOT NULL,
                dependency_ids_json TEXT NOT NULL,
                epic_ids_json TEXT NOT NULL,
                notes TEXT NOT NULL
            )"""
        )
        connection.execute("CREATE INDEX ix_requirements_priority_status ON requirements(priority, implementation_status)")
        for item in ledger["requirements"]:
            connection.execute(
                "INSERT INTO requirements VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    item["requirement_id"],
                    item["priority"],
                    item["implementation_status"],
                    item["source_document"],
                    item["source_line"],
                    item["source_section"],
                    item["text"],
                    item["verification_method"],
                    item.get("owner", "UNASSIGNED"),
                    item.get("release_gate"),
                    item.get("external_validation_status", "NOT_REQUIRED"),
                    item.get("waiver_status", "NONE"),
                    item.get("waiver_expiration"),
                    json.dumps(item.get("implementation_files", []), sort_keys=True),
                    json.dumps(item.get("test_ids", []), sort_keys=True),
                    json.dumps(item.get("test_result_evidence_paths", []), sort_keys=True),
                    json.dumps(item.get("dependency_ids", []), sort_keys=True),
                    json.dumps(item.get("epic_ids", []), sort_keys=True),
                    item.get("notes", ""),
                ),
            )
        connection.execute("CREATE TABLE documents (path TEXT PRIMARY KEY, payload_json TEXT NOT NULL)")
        for document in ledger.get("documents", []):
            connection.execute("INSERT INTO documents VALUES (?,?)", (document["path"], json.dumps(document, sort_keys=True)))
        connection.execute("CREATE TABLE epics (epic_id TEXT PRIMARY KEY, completed INTEGER NOT NULL, payload_json TEXT NOT NULL)")
        for epic in ledger.get("epics", []):
            connection.execute("INSERT INTO epics VALUES (?,?,?)", (epic["id"], int(epic.get("completed", False)), json.dumps(epic, sort_keys=True)))
        connection.commit()
    finally:
        connection.close()


def _write_reports(ledger: dict[str, Any]) -> None:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for item in ledger["requirements"]:
        counts[item["priority"]][item["implementation_status"]] += 1
    statuses = sorted({status for counter in counts.values() for status in counter})
    lines = [
        "# Requirements coverage report",
        "",
        f"Generated: `{ledger['generated_at']}`",
        "",
        f"Total normative requirements: **{len(ledger['requirements']):,}**",
        "",
        "| Priority | " + " | ".join(statuses) + " | Total |",
        "|---|" + "---:|" * (len(statuses) + 1),
    ]
    for priority in sorted(counts):
        total = sum(counts[priority].values())
        lines.append("| " + priority + " | " + " | ".join(str(counts[priority][status]) for status in statuses) + f" | {total} |")
    verified = [item for item in ledger["requirements"] if item["implementation_status"] == "VERIFIED"]
    external = [item for item in ledger["requirements"] if item["implementation_status"] == "EXTERNAL_VALIDATION_REQUIRED"]
    blocked = [item for item in ledger["requirements"] if item["implementation_status"].startswith("BLOCKED_")]
    lines += [
        "",
        f"Verified: **{len(verified)}**",
        f"External validation required: **{len(external)}**",
        f"Blocked: **{len(blocked)}**",
        "",
        "> Absence from the verified count is not evidence of implementation. Release-mode specification lint remains fail-closed.",
        "",
        "## Governing release posture",
        "",
        "- Progress 07: **authorized as a bounded OPS-001 development milestone** from accepted commit `600e3d81ffb47a88cc0a3041b7fdc7a5901a9fe8`.",
        "- Progress 08: **unauthorized** pending independent True North acceptance of Progress 07.",
        "- Production promotion: **NO-GO**. Production authorization remains fail-closed.",
    ]
    (ROOT / "requirements/coverage-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    ext_lines = ["# External validation", "", "Requirements below need evidence unavailable in the current environment.", ""]
    for item in external:
        ext_lines.append(f"- **{item['requirement_id']}** — owner: `{item.get('owner')}` — {item.get('notes')}")
    if not external:
        ext_lines.append("No requirement is currently classified this way; this does **not** mean external validation is complete.")
    (ROOT / "requirements/external-validation.md").write_text("\n".join(ext_lines) + "\n", encoding="utf-8")

    blocker_lines = ["# Blockers", ""]
    for item in blocked:
        blocker_lines.append(f"- **{item['requirement_id']}** `{item['implementation_status']}` — {item.get('notes')}")
    if not blocked:
        blocker_lines.append("No requirement currently carries a formal blocked status. Unstarted work remains visible in the ledger.")
    (ROOT / "requirements/blockers.md").write_text("\n".join(blocker_lines) + "\n", encoding="utf-8")

    waived = [item for item in ledger["requirements"] if item["implementation_status"] == "WAIVED_WITH_EXPIRATION"]
    waiver_lines = ["# Waivers", ""]
    for item in waived:
        waiver_lines.append(f"- **{item['requirement_id']}** expires `{item.get('waiver_expiration')}` — {item.get('notes')}")
    if not waived:
        waiver_lines.append("No active waivers.")
    (ROOT / "requirements/waivers.md").write_text("\n".join(waiver_lines) + "\n", encoding="utf-8")

    all_counts = Counter(item["implementation_status"] for item in ledger["requirements"])
    status_lines = [
        "# SIP v1.1.0 Implementation Status",
        "",
        "This repository remains under active implementation. The status below is generated from the authoritative ledger; it is not a production-complete claim.",
        "",
        f"- Normative requirements: **{len(ledger['requirements']):,}**",
        f"- Verified: **{all_counts['VERIFIED']:,}**",
        f"- Implemented but unverified: **{all_counts['IMPLEMENTED_UNVERIFIED']:,}**",
        f"- In progress: **{all_counts['IN_PROGRESS']:,}**",
        f"- Not started: **{all_counts['NOT_STARTED']:,}**",
        f"- External validation required: **{all_counts['EXTERNAL_VALIDATION_REQUIRED']:,}**",
        "",
        "Release mode remains fail-closed until every gap is either verified or explicitly governed under the specification's allowed external-validation/waiver rules.",
    ]
    (ROOT / "IMPLEMENTATION_STATUS.md").write_text("\n".join(status_lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply evidence overlays and regenerate the SIP requirements control system")
    parser.add_argument("--check", action="store_true", help="regenerate in memory and fail if committed JSON differs")
    args = parser.parse_args()
    ledger = _merge()
    if args.check:
        existing = json.loads(JSON_LEDGER.read_text(encoding="utf-8"))
        # generated_at is intentionally non-deterministic and excluded from drift comparison.
        existing.pop("generated_at", None)
        candidate = deepcopy(ledger)
        candidate.pop("generated_at", None)
        if existing != candidate:
            raise SystemExit("requirements ledger drift detected; run tools/update_requirements.py")
        return
    JSON_LEDGER.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_csv(ledger)
    _write_sqlite(ledger)
    _write_test_plans(ledger)
    _write_reports(ledger)
    print(json.dumps({"requirements": len(ledger["requirements"]), "test_plans": len(list(TEST_PLANS.glob("*.yaml")))}, sort_keys=True))


if __name__ == "__main__":
    main()
