from __future__ import annotations

import json
from pathlib import Path

from tools.audit_progress06_traceability import (
    ACCEPTED_AUDIT_SHA256,
    ACCEPTED_SCOPE_SHA256,
    AUTHORIZED_EPICS,
    DESTINATION,
    SCOPE_DESTINATION,
    validate_accepted_snapshot,
)

ROOT = Path(__file__).resolve().parents[2]


def test_progress06_traceability_preserves_the_true_north_accepted_snapshot() -> None:
    """REQ: TSTGATE-003 accepted Progress 06 scope and audit stay immutable after later requirements are implemented."""
    report = validate_accepted_snapshot()
    assert report["status"] == "passed_complete"
    assert report["finding_count"] == 0
    assert report["requirements"] == 206
    assert report["included"] == 118
    assert report["deferred"] == 88
    assert report["scope_sha256"] == ACCEPTED_SCOPE_SHA256
    assert report["audit_sha256"] == ACCEPTED_AUDIT_SHA256

    scope = json.loads(SCOPE_DESTINATION.read_text(encoding="utf-8"))
    audit = json.loads(DESTINATION.read_text(encoding="utf-8"))
    assert scope["authorized_epics"] == list(AUTHORIZED_EPICS)
    assert audit["authorized_epics"] == list(AUTHORIZED_EPICS)
    assert audit["status"] == "passed_complete"
    assert audit["finding_count"] == 0


def test_progress06_historical_scope_does_not_hide_current_progress10_truth() -> None:
    """REQ: TSTGATE-003 later implementation belongs in the global ledger and Progress 10 scope, not the closed Progress 06 snapshot."""
    historical = json.loads(SCOPE_DESTINATION.read_text(encoding="utf-8"))
    historical_deferred = {item["requirement_id"] for item in historical["deferred_requirements"]}
    assert "LIFPRESV-002" in historical_deferred

    ledger_payload = json.loads((ROOT / "requirements/requirements-ledger.json").read_text(encoding="utf-8"))
    ledger = {item["requirement_id"]: item for item in ledger_payload["requirements"]}
    assert ledger["LIFPRESV-002"]["implementation_status"] != "NOT_STARTED"

    progress10 = json.loads((ROOT / "requirements/MILESTONE_SCOPE_PROGRESS_10.json").read_text(encoding="utf-8"))
    current_ids = {item["requirement_id"] for item in progress10["included_requirements"]}
    assert "LIFPRESV-002" in current_ids
