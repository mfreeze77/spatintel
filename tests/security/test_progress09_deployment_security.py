from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from sip.database import AutoscalingAdmissionRow, DeploymentAdmissionRow
from sip.errors import AuthorizationError, ValidationError
from sip.models import AuthorityClass, Classification, ProvenanceRef, SourceClass
from sip.temporal import db_now
from tests.progress09_helpers import assign_profile, aws_environment_args, bootstrap, profile_args, residency_args


def _profile(context, *, name="secure-profile", mode="hybrid", digest="e"):
    return context.deployment.register_profile(**profile_args(name=name, mode=mode, digest_character=digest), actor_id="deployment-admin")


def test_progress09_profile_and_production_admission_fail_closed_on_unpinned_or_missing_evidence(tmp_path: Path) -> None:
    """REQ: ARCDEP-002, OPSAWS-001, OPSAWS-002, OPSAWS-003, OPSAWS-004, OPSAWS-005, OPSAWS-006 profile/AWS controls reject unpinned, public, unencrypted, unaudited, nonreplaceable, or structurally incomplete production paths."""
    context, _, _ = bootstrap(tmp_path, name="p09-prod-deny")
    profile = _profile(context)
    bad = profile_args(name="unpinned", digest_character="f")
    bad["service_images"]["control-api"] = "ghcr.io/sip/control-api:latest"
    with pytest.raises(ValidationError) as unpinned:
        context.deployment.register_profile(**bad, actor_id="deployment-admin")
    assert unpinned.value.code == "DEPLOYMENT_IMAGE_UNPINNED"

    environment = context.deployment.register_aws_environment(**aws_environment_args(), actor_id="cloud-admin")
    assert environment["production_approved"] is False
    assert environment["evidence_class"] == "synthetic_structural"
    broken = aws_environment_args()
    broken["object_store"]["public_access"] = True
    with pytest.raises(ValidationError) as public_store:
        context.deployment.register_aws_environment(**broken, actor_id="cloud-admin")
    assert public_store.value.code == "AWS_PRIVATE_DATA_PLANE_REQUIRED"

    with pytest.raises(AuthorizationError) as denied:
        context.deployment.production_admission(
            deployment_profile_id=profile["deployment_profile_id"], aws_environment_id=environment["aws_environment_id"],
            evidence={"executed_compose": True, "default_deny_network": True}, actor_id="release-manager",
        )
    assert denied.value.code == "DEPLOYMENT_PRODUCTION_EVIDENCE_INCOMPLETE"
    assert "profile_external_approval" in denied.value.details["obligations"]


def test_progress09_cdn_rejects_raw_or_restricted_origins_and_requires_current_signed_authorization(tmp_path: Path) -> None:
    """REQ: OPSAWS-004 CDN delivery is limited to immutable redacted derivatives with signed, short-lived authorization and no raw asset origin."""
    context, tenant, project = bootstrap(tmp_path, name="p09-cdn")
    provenance = ProvenanceRef(source_ids=["p09-cdn-fixture"], output_hash="1" * 64, notes="deterministic Progress 09 fixture")
    raw = context.assets.ingest_bytes(
        tenant_id=tenant, project_id=project, data=b"raw", media_type="application/octet-stream", original_name="raw.bin",
        classification=Classification.INTERNAL, retention_class="fixture", source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE, provenance=provenance, actor_id="fixture",
    )
    with pytest.raises(AuthorizationError) as raw_denied:
        context.deployment.register_cdn_derivative(
            tenant_id=tenant, project_id=project, asset_id=raw.asset_id, immutable_sha256=raw.sha256,
            redaction_profile="public-redaction-v1", redaction_hash="2" * 64, authorization_token="short-lived-token",
            expires_at=db_now() + timedelta(minutes=5), actor_id="cdn-publisher",
        )
    assert raw_denied.value.code == "CDN_RAW_OR_RESTRICTED_ASSET_DENIED"

    derivative = context.assets.ingest_bytes(
        tenant_id=tenant, project_id=project, data=b"redacted", media_type="application/octet-stream", original_name="redacted.bin",
        classification=Classification.INTERNAL, retention_class="fixture", source_class=SourceClass.INFERRED,
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE, provenance=provenance, actor_id="fixture",
    )
    with pytest.raises(ValidationError) as expired:
        context.deployment.register_cdn_derivative(
            tenant_id=tenant, project_id=project, asset_id=derivative.asset_id, immutable_sha256=derivative.sha256,
            redaction_profile="public-redaction-v1", redaction_hash="3" * 64, authorization_token="expired",
            expires_at=db_now() - timedelta(seconds=1), actor_id="cdn-publisher",
        )
    assert expired.value.code == "CDN_AUTHORIZATION_EXPIRED"
    delivery = context.deployment.register_cdn_derivative(
        tenant_id=tenant, project_id=project, asset_id=derivative.asset_id, immutable_sha256=derivative.sha256,
        redaction_profile="public-redaction-v1", redaction_hash="3" * 64, authorization_token="valid-token",
        expires_at=db_now() + timedelta(minutes=5), actor_id="cdn-publisher",
    )
    assert delivery["state"] == "active"


def test_progress09_admission_does_not_accept_caller_precomputed_decisions_and_retains_denials(tmp_path: Path) -> None:
    """REQ: ARCDEP-003, OPSHYB-002 residency and transfer admission is server-computed, fail-closed, and retains denial evidence."""
    context, tenant, project = bootstrap(tmp_path, name="p09-precomputed")
    profile = _profile(context)
    residency = context.deployment.register_residency_policy(tenant_id=tenant, project_id=project, **residency_args(), actor_id="residency-officer")
    assign_profile(context, tenant, project, profile["deployment_profile_id"], residency["residency_policy_id"])
    with pytest.raises(ValidationError) as caller_decision:
        context.deployment.authorize_admission(
            tenant_id=tenant, project_id=project, admission_type="worker_schedule", deployment_profile_id=profile["deployment_profile_id"],
            region="us-east-1", request={"worker_class": "reference-worker", "precomputed_allow": True}, actor_id="scheduler",
        )
    assert caller_decision.value.code == "DEPLOYMENT_ADMISSION_PRECOMPUTED_PROHIBITED"
    with pytest.raises(AuthorizationError):
        context.deployment.authorize_admission(
            tenant_id=tenant, project_id=project, admission_type="worker_schedule", deployment_profile_id=profile["deployment_profile_id"],
            region="eu-west-1", request={"worker_class": "reference-worker"}, actor_id="scheduler",
        )
    with context.database.session() as session:
        assert session.scalar(select(func.count()).select_from(DeploymentAdmissionRow).where(DeploymentAdmissionRow.tenant_id == tenant, DeploymentAdmissionRow.project_id == project, DeploymentAdmissionRow.decision == "deny")) == 1


def test_progress09_autoscaling_simultaneous_replay_is_governed(tmp_path: Path) -> None:
    """REQ: ARCDEP-005, OPSAWS-003 simultaneous autoscaling admission cannot escape a raw uniqueness failure or create duplicate decisions."""
    context, tenant, project = bootstrap(tmp_path, name="p09-autoscale-race")
    policy = context.deployment.register_autoscaling_policy(
        tenant_id=tenant, project_id=project, queue_class="gpu", revision="1.0.0", min_replicas=0, max_replicas=2,
        tenant_concurrency_limit=4, profile_quotas={"gpu-a10": 2}, global_budget_limit=50.0, currency="USD",
        dead_letter={"enabled": True, "queue": "gpu-dlq", "max_attempts": 3}, restricted_egress=True, actor_id="deployment-admin",
    )
    barrier = threading.Barrier(2)

    def invoke():
        barrier.wait(timeout=10)
        return context.deployment.admit_autoscaling(
            tenant_id=tenant, project_id=project, autoscaling_policy_id=policy["autoscaling_policy_id"], compute_profile="gpu-a10",
            requested_replicas=2, current_tenant_jobs=0, projected_cost=10.0, current_replicas=0, actor_id="autoscaler",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: invoke(), range(2)))
    assert {item["autoscaling_admission_id"] for item in results}.__len__() == 1
    assert sorted(item["idempotent_replay"] for item in results) == [False, True]
    with context.database.session() as session:
        assert session.scalar(select(func.count()).select_from(AutoscalingAdmissionRow).where(AutoscalingAdmissionRow.tenant_id == tenant, AutoscalingAdmissionRow.project_id == project)) == 1


def test_progress09_aws_manifests_reject_raw_secret_material(tmp_path: Path) -> None:
    """REQ: ARCDEP-002, OPSAWS-002, OPSAWS-005 cloud manifests retain only opaque secret references and never raw credentials or private material."""
    context, _, _ = bootstrap(tmp_path, name="p09-aws-secrets")
    for mutate in (
        lambda value: value["database"].update({"password": "SUPERSECRET"}),
        lambda value: value["secrets"].update({"client_secret": "raw-client-secret"}),
        lambda value: value["kms"].update({"private_key": "-----BEGIN PRIVATE KEY-----"}),
    ):
        manifest = aws_environment_args()
        mutate(manifest)
        with pytest.raises(ValidationError) as denied:
            context.deployment.register_aws_environment(**manifest, actor_id="cloud-admin")
        assert denied.value.code == "DEPLOYMENT_RAW_SECRET_PROHIBITED"


def test_progress09_deployment_boundaries_are_tenant_and_project_scoped(tmp_path: Path) -> None:
    """REQ: ARCDEP-003, OPSHYB-002, OPSHYB-003 deployment admission, residency, and edge records fail closed across tenant and project boundaries."""
    context, tenant_a, project_a = bootstrap(tmp_path, name="p09-scope-a")
    tenant_b = context.tenancy.create_tenant("tenant b", tenant_id="p09-scope-b-tenant", actor_id="bootstrap")
    project_b = context.tenancy.create_project(tenant_b, "project b", vertical="platform", classification="internal", project_id="p09-scope-b-project", actor_id="bootstrap")
    profile = _profile(context, name="scoped-profile", mode="hybrid", digest="c")
    policy = context.deployment.register_residency_policy(tenant_id=tenant_a, project_id=project_a, **residency_args(), actor_id="residency-officer")
    assign_profile(context, tenant_a, project_a, profile["deployment_profile_id"], policy["residency_policy_id"])
    with pytest.raises(AuthorizationError) as cross_policy:
        context.deployment.assign_project_profile(
            tenant_id=tenant_b, project_id=project_b, deployment_profile_id=profile["deployment_profile_id"],
            residency_policy_id=policy["residency_policy_id"], transfer_policy_id=None, revision="1.0.0",
            feature_overrides={}, cloud_dependencies_acknowledged=True, actor_id="deployment-admin",
        )
    assert cross_policy.value.code == "DEPLOYMENT_RESIDENCY_SCOPE_MISMATCH"
    with pytest.raises(AuthorizationError):
        context.deployment.authorize_admission(
            tenant_id=tenant_b, project_id=project_b, admission_type="worker_schedule",
            deployment_profile_id=profile["deployment_profile_id"], region="us-east-1",
            request={"worker_class": "reference-worker"}, actor_id="scheduler",
        )
