from __future__ import annotations

import json
from pathlib import Path

from tools.audit_progress06_traceability import (
    AUTHORIZED_EPICS,
    DESTINATION,
    SCOPE_DESTINATION,
    build,
    build_scope,
)

ROOT = Path(__file__).resolve().parents[2]


def test_progress06_traceability_semantically_audits_all_authorized_epics() -> None:
    """REQ: TSTGATE-003 every Progress 06 scoped mapping is audited and each linked automated test declares the linked requirement ID."""
    report = build()
    scope = build_scope()
    assert report["status"] == "passed_complete"
    assert report["finding_count"] == 0
    assert report["authorized_epics"] == list(AUTHORIZED_EPICS)
    assert report["scope_requirement_count"] == 206
    assert scope["counts"]["total"] == 206
    assert scope["counts"]["included"] + scope["counts"]["deferred"] == 206
    for item in report["audited_requirements"]:
        assert item["all_linked_tests_declare_requirement_id"] is True
        if item["status"] == "VERIFIED":
            assert item["coverage_classification"] == "direct"
            assert item["linked_test_count"] > 0
        if item["coverage_classification"] == "deferred":
            assert item["status"] == "NOT_STARTED"
            assert item["linked_test_count"] == 0


def test_progress06_scope_and_traceability_artifacts_have_no_drift() -> None:
    """REQ: TSTGATE-003 the committed Progress 06 scope and semantic traceability audit are deterministic."""
    assert DESTINATION.read_text(encoding="utf-8") == json.dumps(build(), indent=2, sort_keys=True) + "\n"
    assert SCOPE_DESTINATION.read_text(encoding="utf-8") == json.dumps(build_scope(), indent=2, sort_keys=True) + "\n"
