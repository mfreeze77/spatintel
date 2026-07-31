from __future__ import annotations

from pathlib import Path

import pytest

from sip.errors import AuthorizationError, ValidationError
from sip.models import AuthorityClass, Classification, ProvenanceRef, SourceClass
from tests.progress09_helpers import assign_profile, bootstrap, profile_args, residency_args


def _register(context, **overrides):
    payload = profile_args(**overrides)
    return context.deployment.register_profile(**payload, actor_id="deployment-admin")


def _residency(context, tenant: str, project: str):
    return context.deployment.register_residency_policy(
        tenant_id=tenant,
        project_id=project,
        **residency_args(),
        actor_id="residency-officer",
    )


def test_progress09_profiles_pin_runtime_contracts_and_disclose_cloud_dependence(tmp_path: Path) -> None:
    """REQ: ARCDEP-001, ARCDEP-002, OPSHYB-001, OPSHYB-006 deployment profiles pin images, infrastructure, secrets, network/resource controls, canonical contracts, and feature availability."""
    context, tenant, project = bootstrap(tmp_path, name="p09-profile")
    profile = _register(context)
    assert profile["mode"] == "hybrid"
    assert profile["production_approved"] is False
    assert set(profile["canonical_contracts"]) == {"package", "scene", "evidence", "export"}
    assert all(item["sha256"] for item in profile["canonical_contracts"].values())
    assert all("@sha256:" in value for value in profile["service_images"].values())
    assert all(value.startswith(("secret://", "vault://")) for value in profile["secret_references"].values())
    assert profile["network_policy"]["default_deny_ingress"] is True
    assert profile["network_policy"]["default_deny_egress"] is True
    feature = context.deployment.feature_availability(profile_id=profile["deployment_profile_id"], feature="gpu_reconstruction")
    assert feature["requires_cloud_connectivity"] is True
    assert feature["when_unavailable"] == "queue_or_use_cpu_reference"
    assert feature["administrator_notice"]

    residency = _residency(context, tenant, project)
    with pytest.raises(AuthorizationError) as denied:
        assign_profile(context, tenant, project, profile["deployment_profile_id"], residency["residency_policy_id"], cloud_ack=False)
    assert denied.value.code == "DEPLOYMENT_CLOUD_DEPENDENCY_ACK_REQUIRED"
    binding = assign_profile(context, tenant, project, profile["deployment_profile_id"], residency["residency_policy_id"])
    assert binding["cloud_dependencies_acknowledged"] is True

    bad = profile_args(name="bad-secrets", digest_character="2")
    bad["secret_references"] = {"database": "plaintext-password"}
    with pytest.raises(ValidationError) as secret:
        context.deployment.register_profile(**bad, actor_id="deployment-admin")
    assert secret.value.code == "DEPLOYMENT_SECRET_REFERENCE_INVALID"


def test_progress09_residency_is_enforced_before_upload_and_worker_scheduling(tmp_path: Path) -> None:
    """REQ: ARCDEP-003 residency and deployment-profile admission occur before asset upload and worker scheduling."""
    context, tenant, project = bootstrap(tmp_path, name="p09-residency")
    profile = _register(context)
    residency = _residency(context, tenant, project)
    assign_profile(context, tenant, project, profile["deployment_profile_id"], residency["residency_policy_id"])
    provenance = ProvenanceRef(source_ids=["synthetic-progress09"], output_hash="3" * 64, notes="deterministic Progress 09 fixture")

    with pytest.raises(AuthorizationError) as missing_region:
        context.assets.ingest_bytes(
            tenant_id=tenant, project_id=project, data=b"synthetic", media_type="application/octet-stream",
            original_name="synthetic.bin", classification=Classification.INTERNAL, retention_class="fixture",
            source_class=SourceClass.INFERRED, authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
            provenance=provenance, actor_id="capture", asset_class="generic_asset",
        )
    assert missing_region.value.code == "DEPLOYMENT_REGION_REQUIRED"

    with pytest.raises(AuthorizationError) as wrong_region:
        context.assets.ingest_bytes(
            tenant_id=tenant, project_id=project, data=b"synthetic", media_type="application/octet-stream",
            original_name="synthetic.bin", classification=Classification.INTERNAL, retention_class="fixture",
            source_class=SourceClass.INFERRED, authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
            provenance=provenance, actor_id="capture", deployment_region="eu-west-1", asset_class="generic_asset",
        )
    assert wrong_region.value.code in {"DEPLOYMENT_REGION_DENIED", "DEPLOYMENT_RESIDENCY_DENIED", "DEPLOYMENT_RESIDENCY_REGION_DENIED"}

    asset = context.assets.ingest_bytes(
        tenant_id=tenant, project_id=project, data=b"synthetic", media_type="application/octet-stream",
        original_name="synthetic.bin", classification=Classification.INTERNAL, retention_class="fixture",
        source_class=SourceClass.INFERRED, authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        provenance=provenance, actor_id="capture", deployment_region="us-east-1", asset_class="generic_asset",
    )
    assert asset.sha256

    with pytest.raises(AuthorizationError):
        context.operations.create(
            tenant_id=tenant, project_id=project, operation_type="normalize", idempotency_key="wrong-region",
            input_manifest={"deployment_region": "eu-west-1", "worker_class": "reference-worker"}, actor_id="scheduler",
        )
    operation = context.operations.create(
        tenant_id=tenant, project_id=project, operation_type="normalize", idempotency_key="allowed-region",
        input_manifest={"deployment_region": "us-east-1", "worker_class": "reference-worker", "compute_profile": "cpu-reference"}, actor_id="scheduler",
    )
    assert operation["operation_id"]
