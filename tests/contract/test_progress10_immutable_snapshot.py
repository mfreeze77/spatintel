from __future__ import annotations

import json
from pathlib import Path

import tools.audit_progress10_traceability as progress10
from tools.build_progress10_scope import main as progress10_scope_main


def _json_copy(tmp_path: Path, source: Path, mutate) -> Path:
    value = json.loads(source.read_text(encoding="utf-8"))
    mutate(value)
    destination = tmp_path / source.name
    destination.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def test_progress10_later_test_addition_does_not_rewrite_closed_snapshot(
    tmp_path: Path, monkeypatch
) -> None:
    """REQ: TSTGATE-003 a later test addition stays cumulative and does not rewrite the closed snapshot."""
    current = tmp_path / "implementation-map.json"
    current.write_text('{"requirements":{"ARCRES-001":{"test_ids":["later-test"]}}}\n', encoding="utf-8")
    monkeypatch.setattr(progress10, "CURRENT_IMPLEMENTATION_MAP", current)
    assert progress10.validate_accepted_snapshot()["status"] == "passed_complete"


def test_progress10_current_status_can_improve_without_historical_status_rewrite(
    tmp_path: Path, monkeypatch
) -> None:
    """REQ: TSTGATE-003 cumulative verification can improve while the accepted historical status stays frozen."""

    def improve(value: dict) -> None:
        item = next(entry for entry in value["requirements"] if entry["requirement_id"] == "OPSDR-001")
        item["implementation_status"] = "VERIFIED"

    monkeypatch.setattr(progress10, "LEDGER", _json_copy(tmp_path, progress10.LEDGER, improve))
    assert progress10.validate_accepted_snapshot()["status"] == "passed_complete"


def test_progress10_required_snapshot_field_deletion_fails_closed(tmp_path: Path, monkeypatch) -> None:
    """REQ: TSTGATE-003 deletion of accepted milestone metadata fails the historical audit closed."""
    mutated = _json_copy(
        tmp_path,
        progress10.AUDIT,
        lambda value: value.pop("requirements_audited"),
    )
    monkeypatch.setattr(progress10, "AUDIT", mutated)
    report = progress10.validate_accepted_snapshot()
    assert report["status"] == "failed"
    assert any(item["code"] == "AUDIT_FIELDS_MISSING" for item in report["findings"])


def test_progress10_linked_test_change_requires_governed_amendment(tmp_path: Path, monkeypatch) -> None:
    """REQ: TSTGATE-003 accepted linked-test mutation fails without a governed amendment mechanism."""

    def mutate(value: dict) -> None:
        value["requirements_audited"][0]["direct_tests"][0]["test_id"] = "tests/new.py::test_new"

    monkeypatch.setattr(progress10, "AUDIT", _json_copy(tmp_path, progress10.AUDIT, mutate))
    report = progress10.validate_accepted_snapshot()
    codes = {item["code"] for item in report["findings"]}
    assert "AUDIT_SNAPSHOT_DRIFT" in codes
    assert "ACCEPTED_LINKED_TEST_SET_DRIFT" in codes


def test_progress10_current_implementation_map_changes_do_not_create_historical_drift(
    tmp_path: Path, monkeypatch
) -> None:
    """REQ: TSTGATE-003 cumulative implementation-map changes are not historical equality inputs."""
    current = tmp_path / "implementation-map.json"
    current.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(progress10, "CURRENT_IMPLEMENTATION_MAP", current)
    report = progress10.validate_accepted_snapshot()
    assert report["status"] == "passed_complete"
    assert report["current_cumulative_implementation_map_compared"] is False


def test_progress10_historical_scope_and_snapshot_mutation_are_detected(
    tmp_path: Path, monkeypatch
) -> None:
    """REQ: TSTGATE-003 historical scope and audit mutations are independently detected."""
    scope = tmp_path / "scope.json"
    scope.write_bytes(progress10.SCOPE.read_bytes() + b" ")
    audit = tmp_path / "audit.json"
    audit.write_bytes(progress10.AUDIT.read_bytes() + b" ")
    monkeypatch.setattr(progress10, "SCOPE", scope)
    monkeypatch.setattr(progress10, "AUDIT", audit)
    report = progress10.validate_accepted_snapshot()
    codes = {item["code"] for item in report["findings"]}
    assert {"SCOPE_SNAPSHOT_DRIFT", "AUDIT_SNAPSHOT_DRIFT"} <= codes


def test_progress10_scope_tool_refuses_historical_regeneration(monkeypatch) -> None:
    """REQ: TSTGATE-003 the Progress 10 scope tool validates but never rewrites accepted history."""
    scope_before = progress10.SCOPE.read_bytes()
    audit_before = progress10.AUDIT.read_bytes()
    monkeypatch.setattr("sys.argv", ["build_progress10_scope.py", "--check"])
    assert progress10_scope_main() == 0
    assert progress10.SCOPE.read_bytes() == scope_before
    assert progress10.AUDIT.read_bytes() == audit_before


def test_progress11_traceability_remains_complete_after_progress10_snapshot_repair() -> None:
    """REQ: TSTGATE-003 Progress 11 cumulative traceability remains complete after historical isolation."""
    from tools.audit_progress11_traceability import build

    report = build()
    assert report["status"] == "passed_complete"
    assert report["finding_count"] == 0
