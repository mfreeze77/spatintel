from __future__ import annotations

import json
from pathlib import Path

from tools.audit_progress05_traceability import DESTINATION, P05_SCOPE_IDS, build

ROOT = Path(__file__).resolve().parents[2]


def test_progress05_traceability_is_semantically_audited_and_linked_tests_declare_ids() -> None:
    """REQ: TSTGATE-003 all Progress 05 mappings are audited and each linked test declares its requirement ID."""
    report = build()
    assert report["status"] == "passed_complete"
    assert report["finding_count"] == 0
    assert {item["requirement_id"] for item in report["audited_requirements"]} == P05_SCOPE_IDS
    for item in report["audited_requirements"]:
        assert item["all_linked_tests_declare_requirement_id"] is True
        if item["status"] == "VERIFIED":
            assert item["coverage_classification"] == "direct"
            assert item["linked_test_count"] > 0


def test_progress05_traceability_audit_artifact_has_no_drift() -> None:
    """REQ: TSTGATE-003 the committed semantic traceability audit is deterministic and complete."""
    expected = json.dumps(build(), indent=2, sort_keys=True) + "\n"
    assert DESTINATION.read_text(encoding="utf-8") == expected
