from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SPEC_ROOT = ROOT / "spec/Spatial-Intelligence-Platform-Spec-v1.1"
LEDGER_PATH = ROOT / "requirements/requirements-ledger.json"
IMPLEMENTATION_MAP_PATH = ROOT / "requirements/implementation-map.json"
ALLOWED_STATUSES = {
    "NOT_STARTED",
    "IN_PROGRESS",
    "IMPLEMENTED_UNVERIFIED",
    "VERIFIED",
    "EXTERNAL_VALIDATION_REQUIRED",
    "BLOCKED_LEGAL",
    "BLOCKED_HARDWARE",
    "BLOCKED_CREDENTIAL",
    "BLOCKED_SOURCE_DATA",
    "WAIVED_WITH_EXPIRATION",
    "NOT_APPLICABLE_WITH_RATIONALE",
}
REQUIREMENT_ROW = re.compile(r"^\|\s*([A-Z][A-Z0-9-]+-\d{3})\s*\|\s*(P[012])\s*\|", re.MULTILINE)


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    subject: str
    message: str


def _add(findings: list[Finding], severity: str, code: str, subject: str, message: str) -> None:
    findings.append(Finding(severity, code, subject, message))


def _parse_spec_requirements() -> tuple[dict[str, tuple[str, int, str]], list[tuple[str, str, int]]]:
    parsed: dict[str, tuple[str, int, str]] = {}
    duplicates: list[tuple[str, str, int]] = []
    for path in sorted(SPEC_ROOT.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(SPEC_ROOT).as_posix()
        for match in REQUIREMENT_ROW.finditer(text):
            requirement_id, priority = match.groups()
            line = text.count("\n", 0, match.start()) + 1
            if requirement_id in parsed:
                duplicates.append((requirement_id, relative, line))
            else:
                parsed[requirement_id] = (relative, line, priority)
    return parsed, duplicates


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def run(*, release: bool = False) -> dict[str, Any]:
    findings: list[Finding] = []
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    requirements = ledger.get("requirements", [])
    parsed, source_duplicates = _parse_spec_requirements()

    for requirement_id, document, line in source_duplicates:
        _add(findings, "error", "DUPLICATE_SPEC_REQUIREMENT", requirement_id, f"duplicate normative row at {document}:{line}")

    ledger_ids = [str(item.get("requirement_id", "")) for item in requirements]
    duplicates = sorted({item for item in ledger_ids if ledger_ids.count(item) > 1})
    for requirement_id in duplicates:
        _add(findings, "error", "DUPLICATE_LEDGER_REQUIREMENT", requirement_id, "requirement ID occurs more than once in the ledger")

    missing = sorted(set(parsed) - set(ledger_ids))
    extra = sorted(set(ledger_ids) - set(parsed))
    for requirement_id in missing:
        document, line, _ = parsed[requirement_id]
        _add(findings, "error", "MISSING_LEDGER_ENTRY", requirement_id, f"normative requirement at {document}:{line} is absent from the ledger")
    for requirement_id in extra:
        _add(findings, "error", "LEDGER_ENTRY_NOT_IN_SPEC", requirement_id, "ledger entry has no normative requirement row")

    now = datetime.now(UTC)
    by_id = {str(item.get("requirement_id")): item for item in requirements}
    for requirement_id, item in by_id.items():
        status = item.get("implementation_status")
        if status not in ALLOWED_STATUSES:
            _add(findings, "error", "INVALID_STATUS", requirement_id, f"invalid status: {status}")
        source = SPEC_ROOT / str(item.get("source_document", ""))
        line_number = item.get("source_line")
        if not source.is_file():
            _add(findings, "error", "BROKEN_SOURCE_DOCUMENT", requirement_id, f"missing source: {source}")
        elif not isinstance(line_number, int) or line_number < 1:
            _add(findings, "error", "BROKEN_SOURCE_LINE", requirement_id, f"invalid source line: {line_number}")
        else:
            lines = source.read_text(encoding="utf-8").splitlines()
            if line_number > len(lines) or requirement_id not in lines[line_number - 1]:
                _add(findings, "error", "BROKEN_SOURCE_REFERENCE", requirement_id, f"source line does not contain the requirement ID: {source}:{line_number}")
        expected = parsed.get(requirement_id)
        if expected and item.get("priority") != expected[2]:
            _add(findings, "error", "PRIORITY_DRIFT", requirement_id, f"ledger {item.get('priority')} differs from source {expected[2]}")

        plan = ROOT / str(item.get("test_plan_path", ""))
        if not plan.is_file():
            _add(findings, "error", "TEST_PLAN_MISSING", requirement_id, f"missing controlled test plan: {plan}")
        for implementation_file in item.get("implementation_files", []):
            path = ROOT / implementation_file
            if not path.exists():
                _add(findings, "error", "IMPLEMENTATION_FILE_MISSING", requirement_id, implementation_file)
        for evidence_path in item.get("test_result_evidence_paths", []):
            path = ROOT / evidence_path
            if not path.is_file():
                _add(findings, "error", "EVIDENCE_FILE_MISSING", requirement_id, evidence_path)

        if status == "VERIFIED":
            if not item.get("implementation_files"):
                _add(findings, "error", "VERIFIED_WITHOUT_IMPLEMENTATION", requirement_id, "verified requirement has no implementation files")
            if not item.get("test_ids") or not item.get("test_result_evidence_paths"):
                _add(findings, "error", "VERIFIED_WITHOUT_EVIDENCE", requirement_id, "verified requirement lacks tests or retained evidence")
        if status == "EXTERNAL_VALIDATION_REQUIRED":
            if item.get("owner") in {None, "", "UNASSIGNED"}:
                _add(findings, "error", "EXTERNAL_VALIDATION_OWNER_MISSING", requirement_id, "external validation requires an owner")
            if not item.get("notes"):
                _add(findings, "error", "EXTERNAL_VALIDATION_GAP_UNDOCUMENTED", requirement_id, "external validation requires a precise evidence gap and next action")
        if status == "NOT_APPLICABLE_WITH_RATIONALE" and not item.get("notes"):
            _add(findings, "error", "NOT_APPLICABLE_WITHOUT_RATIONALE", requirement_id, "not-applicable status requires a rationale")
        if status == "WAIVED_WITH_EXPIRATION":
            expiration = _parse_date(item.get("waiver_expiration"))
            if expiration is None:
                _add(findings, "error", "WAIVER_EXPIRATION_MISSING", requirement_id, "waiver has no expiration")
            elif expiration <= now:
                _add(findings, "error", "WAIVER_EXPIRED", requirement_id, f"waiver expired at {expiration.isoformat()}")

        if release:
            if item.get("priority") in {"P0", "P1"} and status not in {
                "VERIFIED",
                "EXTERNAL_VALIDATION_REQUIRED",
                "WAIVED_WITH_EXPIRATION",
                "NOT_APPLICABLE_WITH_RATIONALE",
            }:
                _add(findings, "error", "RELEASE_REQUIREMENT_INCOMPLETE", requirement_id, f"{item.get('priority')} requirement is {status}")
            if item.get("priority") == "P0" and status == "VERIFIED" and not item.get("test_result_evidence_paths"):
                _add(findings, "error", "P0_EVIDENCE_MISSING", requirement_id, "verified P0 requirement lacks retained evidence")

    for epic in ledger.get("epics", []):
        if epic.get("completed") and any(not task.get("completed") for task in epic.get("tasks", [])):
            _add(findings, "error", "COMPLETED_EPIC_HAS_INCOMPLETE_TASK", str(epic.get("id")), "epic is complete but a mandatory task is incomplete")

    if IMPLEMENTATION_MAP_PATH.is_file():
        mapping = json.loads(IMPLEMENTATION_MAP_PATH.read_text(encoding="utf-8"))
        unknown = sorted(set(mapping.get("requirements", {})) - set(by_id))
        for requirement_id in unknown:
            _add(findings, "error", "IMPLEMENTATION_MAP_UNKNOWN_REQUIREMENT", requirement_id, "implementation map references an unknown requirement")

    production_marker = ROOT / "build/release/PRODUCTION_READY"
    if production_marker.exists() and not release:
        _add(findings, "error", "UNSUPPORTED_PRODUCTION_CLAIM", str(production_marker), "production marker may only be evaluated by release-mode lint")

    errors = sum(item.severity == "error" for item in findings)
    warnings = sum(item.severity == "warning" for item in findings)
    status_counts: dict[str, int] = {}
    for item in requirements:
        status_counts[item["implementation_status"]] = status_counts.get(item["implementation_status"], 0) + 1
    return {
        "status": "passed" if errors == 0 else "failed",
        "mode": "release" if release else "structural",
        "spec_requirements": len(parsed),
        "ledger_requirements": len(requirements),
        "errors": errors,
        "warnings": warnings,
        "status_counts": dict(sorted(status_counts.items())),
        "findings": [asdict(item) for item in findings],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate SIP specification traceability and release evidence")
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "build/reports/spec-lint.json")
    args = parser.parse_args()
    report = run(release=args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
