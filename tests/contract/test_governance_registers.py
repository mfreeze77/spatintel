from __future__ import annotations

import json
from pathlib import Path

from tools.generate_service_catalog import generate as generate_service_catalog

ROOT = Path(__file__).resolve().parents[2]


def _json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_open_question_register_is_falsifiable_owned_and_fail_safe() -> None:
    """REQ: GOVOPEN-001, GOVOPEN-002, GOVOPEN-003, GOVOPEN-004, GOVOPEN-005 unresolved high-risk assumptions have owners, experiments, evidence rules, and safe defaults."""
    register = _json("governance/open-questions.json")
    mandated = {
        "OQ-LINGBOT-CHECKPOINT-RIGHTS",
        "OQ-LINGBOT-HARDWARE-ENVELOPE",
        "OQ-LONG-BUILDING-DRIFT",
        "OQ-DYNAMIC-SCENE-BEHAVIOR",
        "OQ-CROSS-SESSION-REPEATABILITY",
    }
    questions = {item["id"]: item for item in register["questions"]}
    assert mandated <= set(questions)
    for question in questions.values():
        assert question["owner"] and question["policy_owner"]
        assert question["default_safe_behavior"]
        experiment = question["falsifiable_experiment"]
        assert experiment["acceptance_threshold"]
        assert experiment["input_hashes_required"]
        assert experiment["output_hashes_required"]
        assert experiment["environment_manifest_required"]
        assert experiment["analysis_required"] and experiment["conclusion_required"]
        if question["priority"] == "P0" and question["status"] != "CLOSED":
            assert question["release_blocking"] is True


def test_risk_register_covers_critical_hybrid_risks_and_one_day_review_policy() -> None:
    """REQ: GOVRISK-006, GOVRISK-007, GOVRISK-008, GOVRISK-009 critical hybrid risks have tests, monitors, playbooks, fallback, review, acceptance, and closure controls."""
    register = _json("governance/risk-register.json")
    assert register["critical_increase_policy"]["review_deadline"] == "one_business_day"
    mandated = {
        "RISK-PROXY-AUTHORITY-CONFUSION",
        "RISK-PROVIDER-DATA-EGRESS",
        "RISK-PROTECTED-GEOMETRY-LOSS",
        "RISK-ANCHOR-DRIFT",
        "RISK-IMMERSIVE-SAFETY",
        "RISK-DERIVATIVE-REDACTION",
        "RISK-PROVIDER-LOCK-IN",
    }
    risks = {item["id"]: item for item in register["risks"]}
    assert mandated <= set(risks)
    for risk in risks.values():
        assert risk["requirement_ids"]
        assert risk["test_ids"]
        assert risk["monitors"]
        assert all((ROOT / path).is_file() for path in risk["incident_playbooks"])
        assert risk["fail_safe_mode"]
        assert risk["scene_classes"] and risk["intended_uses"]
        assert risk["local_native_fallback"]
        assert risk["impact_analysis_procedure"]
        if risk["risk_acceptance"] is not None:
            assert risk["risk_acceptance"]["expires_at"]
        if risk["status"] == "CLOSED":
            assert risk["closure_evidence"] and risk["residual_risk"]


def test_service_catalog_is_complete_generated_and_owns_recovery_behavior() -> None:
    """REQ: ARCSVC-001, ARCSVC-003, ARCSVC-004, ARCSVC-005 every service and worker has ownership, contracts, dependencies, SLO, recovery, blast radius, shutdown, and retry behavior."""
    retained = _json("governance/service-catalog.json")
    assert retained == generate_service_catalog()
    components = retained["components"]
    expected = len([p for p in (ROOT / "services").iterdir() if (p / "service.json").is_file()]) + len(
        [p for p in (ROOT / "workers").iterdir() if (p / "worker-manifest.json").is_file()]
    )
    assert len(components) == expected
    assert len({item["name"] for item in components}) == expected
    for component in components:
        assert component["owner"]
        assert (ROOT / component["repository_path"]).is_dir()
        assert component["slo"]
        assert component["recovery_strategy"]
        assert component["blast_radius"]
        assert component["retry_safety"]
        assert component["rpo"] and component["rto"]
        assert component["degraded_behavior"]
        assert component["shutdown"]["in_flight_behavior"]
        assert component["dependency_controls"]["connect_timeout_seconds"] > 0
        if component["kind"] == "worker":
            assert component["publication_permission"] is False
            assert component["owned_tables"] == []


def test_table_ownership_conflicts_are_only_explicit_shared_kernel_exceptions() -> None:
    """REQ: ARCSVC-002 table write ownership is exclusive except for enumerated shared-kernel exceptions."""
    catalog = _json("governance/service-catalog.json")
    owners: dict[str, set[str]] = {}
    for component in catalog["components"]:
        if component["kind"] != "service":
            continue
        for table in component["owned_tables"]:
            owners.setdefault(table, set()).add(component["name"])
    exceptions = {key: set(value) for key, value in catalog["shared_kernel_exceptions"].items()}
    for table, table_owners in owners.items():
        if len(table_owners) > 1:
            assert table in exceptions
            assert table_owners == exceptions[table]


def test_adr_index_links_requirements_risks_benchmarks_source_and_exit_strategy() -> None:
    """REQ: ARCADR-001, ARCADR-002, ARCADR-003, ARCADR-005 material decisions are indexed and link requirements, risk, benchmark/source evidence, and exit strategy."""
    index = _json("docs/adr/index.json")
    assert len(index["adrs"]) >= 7
    ids = [item["id"] for item in index["adrs"]]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))
    for item in index["adrs"]:
        path = ROOT / item["path"]
        text = path.read_text(encoding="utf-8")
        for section in index["required_sections"]:
            assert f"## {section}" in text
        assert item["requirement_ids"]
        for prefix in ("- Risks:", "- Benchmarks:", "- Source evidence:", "- Exit/export strategy:", "- Security/privacy review:"):
            assert prefix in text
