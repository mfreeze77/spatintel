from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sip.spec_lint import run

ROOT = Path(__file__).resolve().parents[2]


def test_spec_lint_indexes_every_normative_requirement() -> None:
    """REQ: GOVDOC-001 every normative requirement remains uniquely indexed and source-addressable."""
    report = run(release=False)
    assert report["status"] == "passed", report["findings"][:20]
    assert report["spec_requirements"] == 1028
    assert report["ledger_requirements"] == 1028


def test_requirements_outputs_are_queryable_and_have_controlled_test_plans() -> None:
    """REQ: TSTSTRAT-001, TSTSTRAT-002 requirements traceability is machine-readable and queryable."""
    ledger = json.loads((ROOT / "requirements/requirements-ledger.json").read_text())
    assert len(ledger["documents"]) == 164
    assert len(ledger["requirements"]) == 1028
    plans = list((ROOT / "tests/spec/requirements").glob("*.yaml"))
    assert len(plans) == 1028
    with sqlite3.connect(ROOT / "requirements/requirements-ledger.sqlite") as connection:
        count = connection.execute("SELECT COUNT(*) FROM requirements").fetchone()[0]
        p0 = connection.execute("SELECT COUNT(*) FROM requirements WHERE priority='P0'").fetchone()[0]
    assert count == 1028
    assert p0 == 504


def test_release_spec_gate_fails_closed_on_unverified_requirements() -> None:
    """REQ: TSTGATE-003 production promotion is denied while mandatory requirements lack evidence."""
    report = run(release=True)
    assert report["status"] == "failed"
    assert any(item["code"] == "RELEASE_REQUIREMENT_INCOMPLETE" for item in report["findings"])


def test_traceability_overlay_is_conservative_and_source_addressable() -> None:
    """CONTROL: the generated evidence overlay never promotes all indexed requirements."""
    actual = json.loads((ROOT / "requirements/implementation-map.json").read_text(encoding="utf-8"))
    assert actual["schema_version"] == "1.0"
    assert actual["epics"] == {}
    assert actual["requirements"]
    statuses = {item["implementation_status"] for item in actual["requirements"].values()}
    assert "VERIFIED" in statuses
    assert {"IN_PROGRESS", "IMPLEMENTED_UNVERIFIED", "EXTERNAL_VALIDATION_REQUIRED"} <= statuses
    assert len(actual["requirements"]) < 1028
    for requirement_id, item in actual["requirements"].items():
        assert requirement_id.count("-") >= 1
        assert item["implementation_files"]
        assert item["test_ids"]
        assert item["last_regression_result"] == "build/reports/test-matrix.json"
        if item["implementation_status"] == "VERIFIED":
            assert item["linked_tests_passed"] is True
            assert item["test_result_evidence_paths"]


def test_test_matrix_contract_is_fail_closed_without_reading_the_live_matrix() -> None:
    """REQ: TSTSTRAT-002 matrix evidence schema and pass claims are checked without a bootstrap loop."""
    import importlib.util
    import sys

    path = ROOT / "tools/run_test_matrix.py"
    spec = importlib.util.spec_from_file_location("sip_test_matrix_contract_tool", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    suite = {
        "name": "contract",
        "status": "passed",
        "exit_code": 0,
        "failures": 0,
        "errors": 0,
        "input_root_sha256": "a" * 64,
        "source_tree_root_sha256": "b" * 64,
        "junit_sha256": "c" * 64,
        "log_sha256": "d" * 64,
    }
    payload = {
        "schema": "sip.test-matrix/v2",
        "evidence": {
            "git_commit": "e" * 40,
            "source_tree_root_sha256": "f" * 64,
            "dependency_snapshot_sha256": "0" * 64,
            "python_version": "3.13",
            "platform": "test-platform",
        },
        "verification_policy": {
            "required_exit_code": 0,
            "maximum_failures": 0,
            "maximum_errors": 0,
            "manual_reviewer": None,
        },
        "status": "passed",
        "findings": [],
        "results": [suite],
    }
    assert module._matrix_contract_findings(payload) == []
    suite["failures"] = 1
    findings = module._matrix_contract_findings(payload)
    assert {item["code"] for item in findings} == {
        "MATRIX_RESULT_PASS_CLAIM_INVALID",
        "MATRIX_STATUS_INCONSISTENT",
    }
