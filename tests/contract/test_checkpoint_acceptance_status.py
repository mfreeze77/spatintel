from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools import run_checkpoint_acceptance as acceptance


def test_acceptance_relative_output_is_rooted_in_repository(tmp_path, monkeypatch) -> None:
    """REQ: TSTGATE-003 checkpoint evidence output is deterministic even when the CLI receives a relative path."""
    monkeypatch.setattr(acceptance, "ROOT", tmp_path)
    resolved = acceptance._rooted_output_path(Path("build/reports/checkpoint-acceptance-gates.json"))
    assert resolved == (tmp_path / "build/reports/checkpoint-acceptance-gates.json").resolve()
    assert resolved.relative_to(tmp_path).as_posix() == "build/reports/checkpoint-acceptance-gates.json"


def test_acceptance_separates_command_execution_from_child_control_completeness(tmp_path, monkeypatch) -> None:
    """REQ: TSTGATE-003 successful command execution cannot erase declared external control gaps."""
    monkeypatch.setattr(acceptance, "ROOT", tmp_path)
    monkeypatch.setitem(acceptance.TARGET_REPORT_PATHS, "synthetic-control", "build/reports/control.json")
    report = tmp_path / "build/reports/control.json"
    report.parent.mkdir(parents=True)
    report.write_text(json.dumps({"status": "passed_with_external_gaps", "external_validation_required": ["scanner"]}))

    evidence = acceptance._control_evidence("synthetic-control", transcript="", exit_code=0)
    assert evidence["execution_status"] == "completed_successfully"
    assert evidence["control_status"] == "passed_with_external_gaps"
    assert evidence["status"] == "passed_with_external_gaps"
    assert evidence["child_declared_status"] == "passed_with_external_gaps"
    assert evidence["child_report_path"] == "build/reports/control.json"
    assert len(evidence["child_report_sha256"]) == 64


def test_acceptance_preserves_blocked_child_and_distinguishes_command_error(tmp_path, monkeypatch) -> None:
    """REQ: TSTGATE-003 blocked controls and failed command execution remain distinguishable evidence."""
    monkeypatch.setattr(acceptance, "ROOT", tmp_path)
    monkeypatch.setitem(acceptance.TARGET_REPORT_PATHS, "synthetic-blocked", "blocked.json")
    (tmp_path / "blocked.json").write_text(json.dumps({"status": "blocked"}))

    completed = acceptance._control_evidence("synthetic-blocked", transcript="", exit_code=0)
    assert completed == {
        "execution_status": "completed_successfully",
        "control_status": "blocked",
        "status": "blocked",
        "child_declared_status": "blocked",
        "child_report_path": "blocked.json",
        "child_report_sha256": completed["child_report_sha256"],
    }
    failed = acceptance._control_evidence("synthetic-blocked", transcript="", exit_code=9)
    assert failed["execution_status"] == "completed_with_error"
    assert failed["control_status"] == "blocked"


def test_acceptance_snapshots_each_child_report_before_a_shared_path_is_overwritten(tmp_path, monkeypatch) -> None:
    """REQ: TSTGATE-003 each command retains immutable child control bytes even when targets share a report path."""
    monkeypatch.setattr(acceptance, "ROOT", tmp_path)
    shared = tmp_path / "build/reports/release-report.json"
    shared.parent.mkdir(parents=True)
    log_root = tmp_path / "build/evidence/gates"

    first_payload = b'{"status":"passed_with_external_gaps","target":"release"}\n'
    shared.write_bytes(first_payload)
    first = acceptance._snapshot_child_report(
        "release",
        acceptance._control_evidence("release", transcript="", exit_code=0),
        log_root=log_root,
    )

    second_payload = b'{"status":"blocked","target":"release-mode"}\n'
    shared.write_bytes(second_payload)
    second = acceptance._snapshot_child_report(
        "release-mode",
        acceptance._control_evidence("release-mode", transcript="", exit_code=0),
        log_root=log_root,
    )

    first_path = tmp_path / first["child_report_path"]
    second_path = tmp_path / second["child_report_path"]
    assert first_path.read_bytes() == first_payload
    assert second_path.read_bytes() == second_payload
    assert first["child_report_sha256"] == hashlib.sha256(first_payload).hexdigest()
    assert second["child_report_sha256"] == hashlib.sha256(second_payload).hexdigest()
    assert first_path != second_path
