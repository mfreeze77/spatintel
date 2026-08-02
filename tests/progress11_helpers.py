from __future__ import annotations

from pathlib import Path
from typing import Any

from sip.canonical import canonical_sha256
from sip.context import PlatformContext, temporary_settings
from sip.release_assurance import GATE_TYPES

DEFAULT_EXTERNAL_GATES = {
    "accessibility",
    "license_model_rights",
    "load_performance",
    "sbom_vulnerability",
}


def bootstrap_release(tmp_path: Path, *, name: str = "p11") -> dict[str, Any]:
    context = PlatformContext.create(temporary_settings(tmp_path / name))
    tenant = context.tenancy.create_tenant(
        f"{name} tenant",
        tenant_id=f"{name}-tenant",
        actor_id="bootstrap",
    )
    project = context.tenancy.create_project(
        tenant,
        f"{name} project",
        vertical="platform",
        classification="internal",
        project_id=f"{name}-project",
        actor_id="bootstrap",
    )
    return {"context": context, "tenant": tenant, "project": project}


def campaign_body(project_id: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "checkpoint_id": "sip-v1.1.0-progress-11",
        "release_class": "development",
        "scope": {
            "epic": "QA-002",
            "requirement_ids": ["CONAUTH-001", "LIFCONS-001", "TSTGATE-009", "TSTSEC-001"],
        },
        "test_data": {
            "classification": "synthetic",
            "customer_data": False,
            "human_subjects": False,
            "retention": "checkpoint_evidence",
        },
        "operating_envelope": {
            "profiles": ["local_reference", "synthetic_cpu_reference"],
            "prohibited_uses": ["production", "survey_grade", "human_subject_pilot"],
            "production_authorized": False,
        },
        "limitations": [
            {"code": "EXTERNAL_VALIDATION_REQUIRED", "status": "external_validation_required"}
        ],
        "support_plan": {
            "owner": "SIP Engineering",
            "escalation": ["security", "privacy", "recovery", "release_governance"],
        },
        "recovery_plan": {
            "rollback": True,
            "open_export": True,
            "prior_release": "sip-v1.1.0-progress-10",
        },
    }


def create_campaign(env: dict[str, Any]) -> dict[str, Any]:
    return env["context"].release_assurance.create_campaign(
        tenant_id=env["tenant"],
        actor_id="release-manager",
        **campaign_body(env["project"]),
    )


def release_artifact_manifest(*, marker: str = "fixture") -> dict[str, Any]:
    artifact = {
        "path": f"build/reports/progress11-{marker}.json",
        "sha256": canonical_sha256({"marker": marker, "kind": "progress11-release-fixture"}),
        "byte_count": len(marker.encode("utf-8")),
        "media_type": "application/json",
    }
    artifacts = [artifact]
    return {
        "schema": "sip.release-artifacts/v1",
        "artifacts": artifacts,
        "content_root_sha256": canonical_sha256(artifacts),
        "signed": True,
        "signature_reference": f"signature://progress11-test/{marker}",
    }


def complete_campaign(
    env: dict[str, Any],
    *,
    external_gates: set[str] | None = None,
    sign_candidate: bool = True,
) -> dict[str, Any]:
    campaign = create_campaign(env)
    service = env["context"].release_assurance
    campaign_id = campaign["campaign_id"]

    scenarios: dict[str, dict[str, Any]] = {}
    for scenario_type, requirement_id in (
        ("construction", "CONAUTH-001"),
        ("liveforever", "LIFCONS-001"),
    ):
        digest = canonical_sha256(
            {"campaign_id": campaign_id, "scenario_type": scenario_type, "fixture": "controlled"}
        )
        scenarios[scenario_type] = service.record_scenario(
            campaign_id=campaign_id,
            tenant_id=env["tenant"],
            project_id=env["project"],
            scenario_type=scenario_type,
            profile=f"synthetic_{scenario_type}_reference",
            evidence_class="synthetic",
            input_hashes={"fixture": digest},
            output_hashes={"report": digest},
            metrics={"assertions_passed": 1, "assertions_total": 1},
            assertions=[{"requirement_id": requirement_id, "passed": True}],
            evidence=[
                {
                    "path": f"build/reports/progress11-{scenario_type}.json",
                    "sha256": digest,
                }
            ],
            environment={"profile": "local_reference", "synthetic": True, "production": False},
            status="passed",
            actor_id=f"qa-{scenario_type}-runner",
        )

    selected_external_gates = DEFAULT_EXTERNAL_GATES if external_gates is None else external_gates
    gates: dict[str, dict[str, Any]] = {}
    for gate_type in sorted(GATE_TYPES):
        external = gate_type in selected_external_gates
        evidence_hash = canonical_sha256({"campaign_id": campaign_id, "gate_type": gate_type})
        gates[gate_type] = service.record_gate(
            campaign_id=campaign_id,
            tenant_id=env["tenant"],
            gate_type=gate_type,
            required=True,
            execution_status="not_executed" if external else "completed_successfully",
            control_status="passed_with_external_gaps" if external else "passed_complete",
            thresholds={"required_failures": 0, "production_authorized": False},
            result={"failures": 0, "production_authorized": False},
            findings=[{"code": f"{gate_type.upper()}_EXTERNAL_VALIDATION_REQUIRED"}] if external else [],
            evidence=[]
            if external
            else [
                {
                    "path": f"build/reports/progress11-{gate_type}.json",
                    "sha256": evidence_hash,
                }
            ],
            external_gap=external,
            actor_id="qa-gate-runner",
        )

    restored_hash = canonical_sha256({"campaign_id": campaign_id, "release": "progress-10"})
    rollback = service.record_rollback(
        campaign_id=campaign_id,
        tenant_id=env["tenant"],
        from_release="sip-v1.1.0-progress-11-candidate",
        to_release="sip-v1.1.0-progress-10",
        recovery_point_id="synthetic-progress10-recovery-point",
        before_hashes={"project_root": restored_hash},
        after_hashes={"project_root": restored_hash},
        steps=[{"step": "quiesce"}, {"step": "restore_prior_release"}, {"step": "reconcile_hashes"}],
        verification={
            "migration_reversed": True,
            "data_reconciled": True,
            "audit_chain_valid": True,
            "data_loss": False,
        },
        status="passed",
        actor_id="qa-recovery-runner",
    )

    result: dict[str, Any] = {
        "campaign": campaign,
        "scenarios": scenarios,
        "gates": gates,
        "rollback": rollback,
    }
    if sign_candidate:
        result["candidate"] = service.evaluate_and_sign_candidate(
            campaign_id=campaign_id,
            tenant_id=env["tenant"],
            source_commit="d" * 40,
            source_root_sha256="e" * 64,
            release_manifest=release_artifact_manifest(),
            signer_key_id="progress11-test-ed25519",
            actor_id="release-manager",
        )
    return result
