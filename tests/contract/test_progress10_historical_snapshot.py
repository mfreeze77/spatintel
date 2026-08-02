from __future__ import annotations

import json
from pathlib import Path

import tools.audit_progress10_traceability as progress10


def _mutated_json(tmp_path: Path, source: Path, mutate) -> Path:
    value = json.loads(source.read_text(encoding="utf-8"))
    mutate(value)
    destination = tmp_path / source.name
    destination.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def test_progress10_accepted_snapshot_is_immutable_and_valid() -> None:
    """REQ: TSTGATE-003 accepted Progress 10 scope, audit, and source identity remain immutable."""
    report = progress10.validate_accepted_snapshot()
    assert report["status"] == "passed_complete"
    assert report["finding_count"] == 0
    assert report["historical_snapshot"] is True
    assert report["scope_sha256"] == progress10.EXPECTED_SCOPE_SHA256
    assert report["audit_sha256"] == progress10.EXPECTED_AUDIT_SHA256
    assert report["checkpoint"]["commit"] == progress10.EXPECTED_COMMIT
    assert report["checkpoint"]["source_root_sha256"] == progress10.EXPECTED_SOURCE_ROOT


def test_later_status_improvement_does_not_rewrite_accepted_progress10_status(
    tmp_path: Path, monkeypatch
) -> None:
    """REQ: TSTGATE-003 cumulative status may improve without rewriting the accepted Progress 10 status."""

    def improve(value: dict) -> None:
        item = next(entry for entry in value["requirements"] if entry["requirement_id"] == "ARCRES-001")
        item["implementation_status"] = "VERIFIED"

    monkeypatch.setattr(progress10, "LEDGER", _mutated_json(tmp_path, progress10.LEDGER, improve))
    report = progress10.validate_accepted_snapshot()
    assert report["status"] == "passed_complete"


def test_current_global_implementation_map_is_not_a_historical_equality_input(
    tmp_path: Path, monkeypatch
) -> None:
    """REQ: TSTGATE-003 current cumulative mappings cannot create historical Progress 10 drift."""
    changed = tmp_path / "implementation-map.json"
    changed.write_text('{"requirements":{"ARCRES-001":{"test_ids":["new-test"]}}}\n', encoding="utf-8")
    monkeypatch.setattr(progress10, "CURRENT_IMPLEMENTATION_MAP", changed)
    report = progress10.validate_accepted_snapshot()
    assert report["status"] == "passed_complete"
    assert report["current_cumulative_implementation_map_compared"] is False


def test_missing_historical_snapshot_field_fails_closed(tmp_path: Path, monkeypatch) -> None:
    """REQ: TSTGATE-003 deletion of a required accepted snapshot field fails closed."""
    mutated = _mutated_json(
        tmp_path,
        progress10.SCOPE,
        lambda value: value.pop("accepted_base_commit"),
    )
    monkeypatch.setattr(progress10, "SCOPE", mutated)
    report = progress10.validate_accepted_snapshot()
    codes = {item["code"] for item in report["findings"]}
    assert report["status"] == "failed"
    assert {"SCOPE_SNAPSHOT_DRIFT", "SCOPE_FIELDS_MISSING", "ACCEPTED_BASE_MISMATCH"} <= codes


def test_ungoverned_historical_linked_test_change_is_rejected(tmp_path: Path, monkeypatch) -> None:
    """REQ: TSTGATE-003 accepted linked-test identifiers require an explicit governed amendment."""

    def mutate(value: dict) -> None:
        value["included_requirements"][0]["direct_tests"][0]["test_id"] = "tests/missing.py::test_missing"

    monkeypatch.setattr(progress10, "SCOPE", _mutated_json(tmp_path, progress10.SCOPE, mutate))
    report = progress10.validate_accepted_snapshot()
    codes = {item["code"] for item in report["findings"]}
    assert report["status"] == "failed"
    assert "SCOPE_SNAPSHOT_DRIFT" in codes
    assert "ACCEPTED_LINKED_TEST_MISSING" in codes


def test_snapshot_scope_and_audit_byte_mutation_are_detected(tmp_path: Path, monkeypatch) -> None:
    """REQ: TSTGATE-003 byte changes to either accepted Progress 10 record are detected."""
    scope = tmp_path / "scope.json"
    scope.write_bytes(progress10.SCOPE.read_bytes() + b"\n")
    audit = tmp_path / "audit.json"
    audit.write_bytes(progress10.AUDIT.read_bytes() + b"\n")
    monkeypatch.setattr(progress10, "SCOPE", scope)
    monkeypatch.setattr(progress10, "AUDIT", audit)
    report = progress10.validate_accepted_snapshot()
    codes = {item["code"] for item in report["findings"]}
    assert {"SCOPE_SNAPSHOT_DRIFT", "AUDIT_SNAPSHOT_DRIFT"} <= codes


def test_missing_accepted_test_or_requirement_fails_referential_integrity(monkeypatch) -> None:
    """REQ: TSTGATE-003 accepted requirements and linked tests retain current referential integrity."""
    catalog = progress10._tests()
    scope = json.loads(progress10.SCOPE.read_text(encoding="utf-8"))
    removed = scope["included_requirements"][0]["direct_tests"][0]["test_id"]
    assert removed in catalog
    catalog.pop(removed)
    monkeypatch.setattr(progress10, "_tests", lambda: catalog)
    report = progress10.validate_accepted_snapshot()
    assert report["status"] == "failed"
    assert any(item["code"] == "ACCEPTED_LINKED_TEST_MISSING" for item in report["findings"])


def test_progress11_and_all_closed_milestone_audits_remain_complete() -> None:
    """REQ: TSTGATE-003 the Progress 10 repair preserves every closed audit and Progress 11 traceability."""
    from tools.audit_progress05_traceability import build as progress05
    from tools.audit_progress06_r1_traceability import build as progress06_r1
    from tools.audit_progress06_r2_traceability import build as progress06_r2
    from tools.audit_progress06_traceability import validate_accepted_snapshot as progress06
    from tools.audit_progress07_traceability import _verify_accepted_snapshot as progress07
    from tools.audit_progress08_traceability import _verify_accepted_snapshot as progress08
    from tools.audit_progress09_traceability import build as progress09
    from tools.audit_progress11_traceability import build as progress11

    reports = [
        progress05(),
        progress06(),
        progress06_r1()[0],
        progress06_r2(),
        progress07(),
        progress08(),
        progress09(),
        progress10.validate_accepted_snapshot(),
        progress11(),
    ]
    assert all(report["status"] == "passed_complete" for report in reports)
    assert all(report.get("finding_count", 0) == 0 for report in reports)
