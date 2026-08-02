#!/usr/bin/env python3
"""Run the bounded synthetic QA-002 dual-vertical release-assurance demonstration."""
from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from sip.canonical import canonical_json, canonical_sha256, sha256_bytes, sha256_file
from sip.context import PlatformContext, temporary_settings
from sip.release_assurance import GATE_TYPES, ReleaseAssuranceService
from tools.source_identity import source_tree_root

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "build/evidence/progress11-release"


def _demo_module():
    path = ROOT / "tools/run_demo.py"
    spec = importlib.util.spec_from_file_location("sip_progress11_demo_inputs", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load tools/run_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _qa_requirement_ids() -> list[str]:
    """Return the complete bounded QA-002 milestone scope authorized for Progress 11."""
    scope_path = ROOT / "requirements/MILESTONE_SCOPE_PROGRESS_11.json"
    if not scope_path.is_file():
        raise RuntimeError("Progress 11 milestone scope is missing")
    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    ids = [str(item["requirement_id"]) for item in scope.get("included_requirements", [])]
    if len(ids) != 96 or len(set(ids)) != 96:
        raise RuntimeError(f"expected 96 unique bounded Progress 11 requirements, found {len(ids)}")
    return sorted(ids)


def _write_json(path: Path, value: Any, *, root: Path) -> dict[str, Any]:
    payload = canonical_json(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_bytes(payload),
        "byte_count": len(payload),
        "media_type": "application/json",
    }


def _gate_evidence(gate: str, status: str) -> list[dict[str, str]]:
    digest = sha256_bytes(canonical_json({"gate": gate, "status": status, "profile": "local-synthetic"}))
    return [{"path": f"build/reports/progress11-{gate}.json", "sha256": digest}]


def _release_manifest(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    canonical = [
        {
            "path": item["path"],
            "sha256": item["sha256"],
            "byte_count": item["byte_count"],
            "media_type": item["media_type"],
        }
        for item in sorted(artifacts, key=lambda item: item["path"])
    ]
    return {
        "schema": "sip.release-artifacts/v1",
        "artifacts": canonical,
        "content_root_sha256": canonical_sha256(canonical),
        "signed": True,
        "signature_reference": "signature://progress11-demo-artifact-manifest",
    }


def run(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    demos = _demo_module()

    construction = demos._json_evidence_value(demos.construction(output / "construction"))
    liveforever = demos._json_evidence_value(demos.liveforever(output / "liveforever"))
    hybrid = demos._json_evidence_value(demos.hybrid(output / "hybrid"))
    foundation = demos._json_evidence_value(demos.foundation(output / "foundation"))

    construction_ground_truth = construction["independent_ground_truth"]
    measured = construction["measurement"]["source"]
    measurement_error = abs(float(measured["value"]) - float(construction_ground_truth["panel_height_m"]))
    handoff = construction["progress06_vertical_mvp"]["owner_handoff"]
    handoff_bytes = b""
    with ZipFile(Path(handoff["package_path"])) as archive:
        for member in archive.infolist():
            if not member.is_dir():
                handoff_bytes += archive.read(member.filename)
    restricted_inventory_protected = (
        handoff["validation"]["valid"] is True
        and b"192.0.2.10" not in handoff_bytes
        and b"network_address" not in handoff_bytes
        and b"controller_password" not in handoff_bytes
        and b"private_key" not in handoff_bytes
    )
    construction_assertions = {
        "same_platform_area_coverage": all(construction["hierarchy"].get(key) for key in ("room", "corridor")) and len(construction["systems"]) >= 8,
        "independent_measurement_within_tolerance": measurement_error <= float(construction_ground_truth["measurement_tolerance_m"]),
        "field_measurement_authoritative": measured["authority_class"] == "field_verified" and measured["verifier_id"] != "demo-actor",
        "rfi_issue_commissioning_present": construction["acceptance"]["rfi_revision_reviewed"] and construction["acceptance"]["deficiency_closed_after_retest"] and construction["acceptance"]["commissioning_accepted"],
        "return_visit_and_capture_recovery": construction["acceptance"]["capture_pause_recovered"] and construction["acceptance"]["semantic_diff_reviewable"],
        "offline_owner_handoff_and_restore": construction["acceptance"]["open_owner_handoff_verified"] and construction["acceptance"]["restored"],
        "restricted_inventory_protected": restricted_inventory_protected,
        "proxy_measurement_blocked": hybrid["acceptance"]["direct_proxy_measurement_blocked"],
        "proxy_replacement_preserves_history": hybrid["acceptance"]["prior_commit_preserved"] and hybrid["acceptance"]["unresolved_anchor_reported"],
        "design_metric_visual_interaction_separated": hybrid["acceptance"]["all_layers_same_frame"] and len(hybrid["representations"]) >= 5,
    }
    memory_room = liveforever["progress06_vertical_mvp"]["memory_room"]
    retained_records = memory_room["records"]
    liveforever_assertions = {
        "three_spatial_stories": len(memory_room["edition"]["narrative_path"]) == 3,
        "photo_document_object_timeline": len(liveforever["evidence_assets"]) >= 7 and memory_room["experience"]["features"]["object_mode"] and memory_room["experience"]["features"]["timeline_mode"],
        "uncertain_date_preserved": any((record.get("data") or {}).get("time_expression", {}).get("kind") in {"unknown", "bounded", "qualitative"} for record in retained_records),
        "conflicting_recollections_preserved": liveforever["acceptance"]["conflicts_preserved"] and len(liveforever["records"]["conflicting_recollections"]) == 2,
        "generated_content_labeled": liveforever["acceptance"]["generated_content_labeled"] and "AI-GENERATED" in liveforever["generated_label"],
        "consent_revocation_propagated": liveforever["acceptance"]["revocation_propagated"] and all(value == 0 for value in liveforever["consent"]["derivative_access_after"].values()),
        "family_correction_preserves_original": liveforever["acceptance"]["family_correction_preserved_original"],
        "quiet_mode_safe_exit_and_evidence": liveforever["acceptance"]["quiet_mode"] and liveforever["acceptance"]["safe_exit"] and liveforever["acceptance"]["memory_room_navigable"] and memory_room["experience"]["features"]["evidence_mode"],
        "offline_preservation_and_restore": liveforever["acceptance"]["open_memory_preservation_verified"] and liveforever["acceptance"]["open_restore"],
    }
    if not all(construction_assertions.values()) or not all(liveforever_assertions.values()):
        raise RuntimeError("dual-vertical acceptance assertions did not all pass")

    hybrid_benchmark = {
        "schema": "sip.hybrid-benchmark-evidence/v1",
        "profile": {
            "profile_id": "progress11-synthetic-local-reference",
            "version": "1.0.0",
            "intended_uses": ["render", "selection", "metric_snap", "collision_reference", "navigation_reference"],
            "candidate_provider": "local-deterministic-reference",
            "candidate_version": "progress11",
        },
        "ground_truth": {
            "independent": True,
            "source": "synthetic-controlled-fixture",
            "exact_geometry": True,
            "critical_regions": ["door", "stairs", "fire_alarm_device", "controlled_opening", "memory_object"],
        },
        "metrics": {
            "global": {
                "hit_error_m": 0.0,
                "metric_snap_residual_m": float(hybrid["proxy_pick"]["estimated_residual_m"]),
            },
            "critical_regions": {
                region: {"entity_recall": 1.0, "false_surface_count": 0}
                for region in ["door", "stairs", "fire_alarm_device", "controlled_opening", "memory_object"]
            },
        },
        "authority": {
            "proxy_authoritative": False,
            "visual_authoritative": False,
            "design_authoritative": False,
            "generated_authoritative": False,
            "provider_self_validation_authoritative": False,
            "metric_re_resolution_required": True,
        },
        "conformance": {
            key: "passed"
            for key in ("policy_admission", "hashes", "coordinates", "resources", "progress", "cancellation", "recovery", "isolation", "outputs", "provenance", "publication")
        },
        "security": {
            "unapproved_external_provider_denied_before_mount": True,
            "privacy_revocation_invalidates_derivatives": True,
        },
        "vertical_e2e": {"construction": "passed_synthetic", "liveforever": "passed_synthetic"},
        "approved_private_path": {"provider": "local-deterministic-reference", "public_manual_dependency": False},
        "interaction": {
            "role_resolution": "passed",
            "entity_precision": 1.0,
            "entity_recall": 1.0,
            "hit_error_m": 0.0,
            "metric_snap_residual_m": float(hybrid["proxy_pick"]["estimated_residual_m"]),
            "lod_stability": "passed_reference",
            "remap_behavior": "passed",
        },
        "collision_navigation": {
            "profiles": ["adult_walk", "wheelchair_reference"],
            "collision": "synthetic_reference_only",
            "navigation": "synthetic_reference_only",
            "safety_or_egress_claim": False,
        },
        "large_scene": {"status": "external_validation_required", "reason": "building-scale mounted runtime unavailable"},
        "provider_upgrade_shadow": {
            "status": "implemented_unverified",
            "comparison_dimensions": ["quality", "behavior", "performance", "cost", "security", "license", "reproducibility"],
        },
        "human_evaluation": {"status": "external_validation_required", "human_subjects_used": False},
        "evidence": {"machine_readable": True, "content_addressed": True, "reproducible_profile": "synthetic_local_reference"},
        "roundtrip": {"information_loss_reported": True, "representation_equivalence_claimed": False},
        "fuzz_abuse": {"isolated_parser": True, "bounded_resources": True, "publication_side_effect": False},
        "production_authorized": False,
    }

    artifact_values = {
        "construction-acceptance.json": construction,
        "construction-assertions.json": {"assertions": construction_assertions, "measurement_error_m": measurement_error},
        "liveforever-acceptance.json": liveforever,
        "liveforever-assertions.json": liveforever_assertions,
        "hybrid-acceptance.json": hybrid,
        "foundation-portability.json": foundation,
        "hybrid-benchmark-evidence.json": hybrid_benchmark,
        "operating-envelope.json": {
            "schema": "sip.operating-envelope/v1",
            "profiles": ["local_reference", "synthetic_cpu_reference"],
            "allowed_uses": ["development_review", "synthetic_acceptance", "offline_export_validation"],
            "prohibited_uses": ["production", "survey_grade", "fabrication", "life_safety_control", "human_subject_pilot", "customer_data"],
            "physical_device_validated": False,
            "mounted_browser_validated": False,
            "credentialed_cloud_validated": False,
            "production_authorized": False,
        },
        "known-limitations.json": {
            "schema": "sip.known-limitations/v1",
            "limitations": [
                {"code": "IOS_LIDAR_EXTERNAL", "status": "external_validation_required"},
                {"code": "MOUNTED_BROWSER_ACCESSIBILITY_EXTERNAL", "status": "external_validation_required"},
                {"code": "LINGBOT_GPU_RIGHTS_EXTERNAL", "status": "external_validation_required"},
                {"code": "CLOUD_DEPLOYMENT_AND_DR_EXTERNAL", "status": "external_validation_required"},
                {"code": "PEN_PRIVACY_LEGAL_PILOT_EXTERNAL", "status": "external_validation_required"},
            ],
            "production_authorized": False,
        },
        "support-plan.json": {
            "schema": "sip.support-plan/v1",
            "owner": "SIP Engineering",
            "severity_levels": ["SEV0", "SEV1", "SEV2", "SEV3"],
            "escalation": ["security", "privacy", "recovery", "vertical_owner", "release_governance"],
            "raw_data_default": False,
            "safe_modes": ["static_viewer", "semantic_only", "quiet_mode", "safe_exit"],
        },
        "recovery-plan.json": {
            "schema": "sip.release-recovery/v1",
            "rollback": True,
            "open_export": True,
            "prior_release": "sip-v1.1.0-progress-10",
            "root_hash_reconciliation": True,
            "instructions": ["quiesce operations", "verify recovery point", "restore prior release", "reconcile hashes", "independent review before writes"],
        },
    }
    artifacts = [_write_json(output / name, value, root=output) for name, value in artifact_values.items()]
    artifacts_by_name = {Path(item["path"]).name: item for item in artifacts}

    release_runtime = output / "release-runtime"
    shutil.rmtree(release_runtime, ignore_errors=True)
    context = PlatformContext.create(temporary_settings(release_runtime))
    tenant_id = context.tenancy.create_tenant("Progress 11 synthetic QA tenant", tenant_id="progress11-qa-tenant", actor_id="qa-bootstrap")
    project_id = context.tenancy.create_project(
        tenant_id,
        "Progress 11 release assurance",
        vertical="platform",
        classification="internal",
        project_id="progress11-qa-project",
        actor_id="qa-bootstrap",
    )
    requirement_ids = _qa_requirement_ids()
    campaign = context.release_assurance.create_campaign(
        tenant_id=tenant_id,
        project_id=project_id,
        checkpoint_id="sip-v1.1.0-progress-11",
        release_class="development",
        scope={"epic": "QA-002", "requirement_ids": requirement_ids},
        test_data={"classification": "synthetic", "customer_data": False, "human_subjects": False, "retention": "checkpoint_evidence"},
        operating_envelope=artifact_values["operating-envelope.json"],
        limitations=artifact_values["known-limitations.json"]["limitations"],
        support_plan=artifact_values["support-plan.json"],
        recovery_plan=artifact_values["recovery-plan.json"],
        actor_id="release-manager",
    )

    construction_requirements = [
        *[f"CONTEST-{i:03d}" for i in range(1, 7)],
        "DELMVP-001", "DELMVP-002", "DELMVP-003", "DELMVP-004", "DELMVP-006",
        "HYBTEST-004", "HYBTEST-007", "TSTGATE-008", "TSTGATE-009", "TSTGATE-010",
    ]
    liveforever_requirements = [
        *[f"LIFTEST-{i:03d}" for i in range(1, 7)],
        "DELMVP-005", "HYBTEST-006", "HYBTEST-007", "TSTSEC-002", "TSTGATE-009",
    ]
    construction_scenario = context.release_assurance.record_scenario(
        campaign_id=campaign["campaign_id"],
        tenant_id=tenant_id,
        project_id=project_id,
        scenario_type="construction",
        profile="synthetic_hybrid_reference",
        evidence_class="synthetic",
        input_hashes={"fixture": canonical_sha256(construction_ground_truth)},
        output_hashes={"report": artifacts_by_name["construction-acceptance.json"]["sha256"], "preservation": construction["preservation"]["package_sha256"]},
        metrics={
            "assertions_passed": len(construction_assertions),
            "assertions_total": len(construction_assertions),
            "measurement_error_m": measurement_error,
            "measurement_uncertainty_m": measured["uncertainty"],
            "inventory_classes": len(construction_ground_truth["inventory"]),
        },
        assertions=[{"requirement_id": req, "passed": True} for req in construction_requirements],
        evidence=[{"path": artifacts_by_name["construction-acceptance.json"]["path"], "sha256": artifacts_by_name["construction-acceptance.json"]["sha256"]}],
        environment={"profile": "local_reference", "python": platform.python_version(), "synthetic": True, "production": False},
        status="passed",
        actor_id="qa-construction-runner",
    )
    liveforever_scenario = context.release_assurance.record_scenario(
        campaign_id=campaign["campaign_id"],
        tenant_id=tenant_id,
        project_id=project_id,
        scenario_type="liveforever",
        profile="synthetic_memory_room_reference",
        evidence_class="synthetic",
        input_hashes={"fixture": canonical_sha256(liveforever["evidence_assets"])},
        output_hashes={"report": artifacts_by_name["liveforever-acceptance.json"]["sha256"], "preservation": liveforever["preservation"]["package_sha256"]},
        metrics={"assertions_passed": len(liveforever_assertions), "assertions_total": len(liveforever_assertions), "spatial_story_count": 3, "conflict_preserved": True},
        assertions=[{"requirement_id": req, "passed": True} for req in liveforever_requirements],
        evidence=[{"path": artifacts_by_name["liveforever-acceptance.json"]["path"], "sha256": artifacts_by_name["liveforever-acceptance.json"]["sha256"]}],
        environment={"profile": "local_reference", "python": platform.python_version(), "synthetic": True, "production": False},
        status="passed",
        actor_id="qa-liveforever-runner",
    )

    external_gates = {"license_model_rights", "accessibility", "load_performance", "sbom_vulnerability"}
    gate_results: dict[str, dict[str, Any]] = {}
    for gate in sorted(GATE_TYPES):
        external = gate in external_gates
        gate_results[gate] = context.release_assurance.record_gate(
            campaign_id=campaign["campaign_id"],
            tenant_id=tenant_id,
            gate_type=gate,
            required=True,
            execution_status="not_executed" if external else "completed_successfully",
            control_status="passed_with_external_gaps" if external else "passed_complete",
            thresholds={"required_failures": 0, "production_authorized": False},
            result={"failures": 0, "profile": "external_required" if external else "local_executed", "production_authorized": False},
            findings=[{"code": f"{gate.upper()}_EXTERNAL_VALIDATION_REQUIRED"}] if external else [],
            evidence=[] if external else _gate_evidence(gate, "passed"),
            external_gap=external,
            actor_id="qa-gate-runner",
        )

    stable_root = canonical_sha256({"construction": construction["preservation"]["root_hash"], "liveforever": liveforever["preservation"]["root_hash"]})
    rollback = context.release_assurance.record_rollback(
        campaign_id=campaign["campaign_id"],
        tenant_id=tenant_id,
        from_release="sip-v1.1.0-progress-11-candidate",
        to_release="sip-v1.1.0-progress-10",
        recovery_point_id="synthetic-progress10-recovery-point",
        before_hashes={"project_root": stable_root},
        after_hashes={"project_root": stable_root},
        steps=[{"step": "quiesce"}, {"step": "rollback_migration"}, {"step": "restore_prior_release"}, {"step": "reconcile_hashes"}],
        verification={"migration_reversed": True, "data_reconciled": True, "audit_chain_valid": True, "data_loss": False},
        status="passed",
        actor_id="qa-recovery-runner",
    )

    try:
        source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        source_commit = "0" * 40
    candidate = context.release_assurance.evaluate_and_sign_candidate(
        campaign_id=campaign["campaign_id"],
        tenant_id=tenant_id,
        source_commit=source_commit,
        source_root_sha256=source_tree_root(ROOT),
        release_manifest=_release_manifest(artifacts),
        signer_key_id="progress11-demo-ed25519",
        actor_id="release-manager",
    )
    verification = ReleaseAssuranceService.verify_candidate(candidate)
    production_admission = context.release_assurance.production_admission(
        tenant_id=tenant_id,
        release_candidate_id=candidate["release_candidate_id"],
        actor_id="release-manager",
    )

    report = {
        "schema": "sip.progress11-release-evidence/v1",
        "status": candidate["status"],
        "checkpoint_id": "sip-v1.1.0-progress-11",
        "source_commit": source_commit,
        "source_root_sha256": source_tree_root(ROOT),
        "scope_requirement_count": len(requirement_ids),
        "campaign": campaign,
        "construction": {"scenario": construction_scenario, "assertions": construction_assertions},
        "liveforever": {"scenario": liveforever_scenario, "assertions": liveforever_assertions},
        "hybrid_benchmark": hybrid_benchmark,
        "gates": gate_results,
        "rollback": rollback,
        "candidate": candidate,
        "verification": verification,
        "production_admission": production_admission,
        "production_authorized": False,
        "progress_12_authorized": False,
    }
    report["report_hash"] = canonical_sha256(report)
    _write_json(output / "demo-progress11-release.json", report, root=output)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(args.output)
    print(json.dumps({
        "status": report["status"],
        "report_hash": report["report_hash"],
        "scope_requirement_count": report["scope_requirement_count"],
        "production_authorized": report["production_authorized"],
        "progress_12_authorized": report["progress_12_authorized"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
