from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path


def _module(root: Path):
    path = Path(__file__).resolve().parents[2] / "tools" / "build_traceability_map.py"
    spec = importlib.util.spec_from_file_location("sip_traceability_evidence_tool", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.ROOT = root
    module.CANONICAL_PYTHON_SUITES = ("contract",)
    module._current_source_tree_root = lambda: "a" * 64
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_traceability_rejects_stale_or_tampered_canonical_junit(tmp_path: Path) -> None:
    """REQ: TSTSTRAT-002 traceability may consume only exact current-source, digest-bound canonical test evidence."""
    root = tmp_path / "repo"
    report_root = root / "build" / "reports" / "tests"
    report_root.mkdir(parents=True)
    junit = report_root / "contract.xml"
    junit.write_text(
        '<testsuite tests="1" failures="0" errors="0" skipped="0">'
        '<testcase classname="tests.contract.test_fixture" name="test_exact" />'
        "</testsuite>",
        encoding="utf-8",
    )
    evidence = {
        "schema": "sip.test-suite-evidence/v1",
        "result": {
            "name": "contract",
            "status": "passed",
            "exit_code": 0,
            "failures": 0,
            "errors": 0,
            "source_tree_root_sha256": "a" * 64,
            "junit_path": "build/reports/tests/contract.xml",
            "junit_sha256": _sha256(junit),
        },
    }
    sidecar = report_root / "contract.evidence.json"
    sidecar.write_text(json.dumps(evidence), encoding="utf-8")

    module = _module(root)
    assert module._python_test_results() == {
        "tests/contract/test_fixture.py::test_exact": "passed"
    }

    evidence["result"]["source_tree_root_sha256"] = "b" * 64
    sidecar.write_text(json.dumps(evidence), encoding="utf-8")
    assert module._python_test_results() == {}

    evidence["result"]["source_tree_root_sha256"] = "a" * 64
    sidecar.write_text(json.dumps(evidence), encoding="utf-8")
    junit.write_text(junit.read_text(encoding="utf-8") + "<!-- tampered -->", encoding="utf-8")
    assert module._python_test_results() == {}


def test_source_traceability_generation_is_build_order_independent() -> None:
    """CONTROL: committed traceability declarations do not depend on post-commit build outputs."""
    path = Path(__file__).resolve().parents[2] / "tools" / "build_traceability_map.py"
    spec = importlib.util.spec_from_file_location("sip_traceability_source_mode", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    def forbidden() -> dict[str, str]:
        raise AssertionError("source mode must not read current test evidence")

    module._python_test_results = forbidden
    module._swift_report_passed = lambda: (_ for _ in ()).throw(
        AssertionError("source mode must not read the Swift report")
    )
    generated = module.build(declared_source_state=True)
    committed = json.loads(module.DESTINATION.read_text(encoding="utf-8"))
    assert generated == committed


def test_post_commit_traceability_gate_requires_every_declared_artifact(tmp_path: Path) -> None:
    """REQ: TSTSTRAT-002 evidence-bound traceability fails closed on a missing declared artifact."""
    root = tmp_path / "repo"
    root.mkdir()
    module = _module(root)
    payload = {
        "requirements": {
            "TSTSTRAT-002": {
                "test_result_evidence_paths": [
                    "build/reports/test-matrix.json",
                    "build/reports/tests/contract.xml",
                ]
            }
        }
    }
    (root / "build/reports").mkdir(parents=True)
    (root / "build/reports/test-matrix.json").write_text("{}\n", encoding="utf-8")
    assert module._missing_declared_evidence(payload) == ["build/reports/tests/contract.xml"]


def test_swift_fixture_pass_with_external_gaps_counts_as_linked_test_evidence(tmp_path: Path) -> None:
    """CONTROL: local Swift tests may pass while hardware acceptance remains explicitly external."""
    root = tmp_path / "repo"
    report = root / "build/reports/swift-test-report.json"
    report.parent.mkdir(parents=True)
    report.write_text(
        json.dumps(
            {
                "schema": "sip.test-report/v1",
                "status": "passed_with_external_gaps",
                "tests_passed": 13,
                "tests_failed": 0,
                "limitations": ["LiDAR and physical-device acceptance remain external."],
            }
        ),
        encoding="utf-8",
    )
    module = _module(root)
    assert module._swift_report_passed() is True

    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["tests_failed"] = 1
    report.write_text(json.dumps(payload), encoding="utf-8")
    assert module._swift_report_passed() is False

def test_evidence_traceability_loads_canonical_result_snapshot_once() -> None:
    """REQ: TSTSTRAT-002 evidence checking reads one immutable result snapshot per build."""
    path = Path(__file__).resolve().parents[2] / "tools" / "build_traceability_map.py"
    spec = importlib.util.spec_from_file_location("sip_traceability_single_snapshot", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    calls = {"python": 0, "swift": 0}
    test_ids = [
        "tests/contract/test_fixture.py::test_exact",
        "tests/contract/test_fixture.py::test_second",
    ]
    module._tests_by_requirement = lambda: {"TSTSTRAT-002": test_ids}

    def python_results() -> dict[str, str]:
        calls["python"] += 1
        return {test_id: "passed" for test_id in test_ids}

    def swift_result() -> bool:
        calls["swift"] += 1
        return True

    module._python_test_results = python_results
    module._swift_report_passed = swift_result

    generated = module.build()

    assert generated["requirements"]["TSTSTRAT-002"]["linked_tests_passed"] is True
    assert calls == {"python": 1, "swift": 1}
