from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from sip.canonical import canonical_sha256, sha256_bytes
from sip.contracts import ManualExternalReceiptContract
from sip.database import (
    AuditEventRow,
    OutboxEventRow,
    HybridSceneViewRow,
    InteractionProfileRow,
    OperationRow,
    ProviderManifestRevisionRow,
    ProviderPromotionRow,
    RepresentationAssetRow,
    RepresentationBindingRow,
    SceneCommitRow,
    SpatialConversionRow,
)
from sip.errors import AuthenticationError, AuthorizationError, ConflictError, NotFoundError, ValidationError
from sip.models import Audience, AuthorityClass, Classification, ProvenanceRef, RepresentationKind, SourceClass
from sip.temporal import db_now
from sip.model_governance import lingbot_checkpoint_denied_manifest

PURPOSE = "hybrid_fixture"
FRAME_ID = "hybrid-world"


def _license(component: str, seed: str) -> dict[str, object]:
    return {
        "component": component,
        "title": f"Synthetic {component} license evidence",
        "license_id": "Apache-2.0",
        "source_url": f"local://licenses/{seed}/{component}",
        "document_sha256": canonical_sha256({"seed": seed, "component": component}),
        "review_state": "verified",
    }


def _descriptor(
    provider_id: str,
    *,
    version: str = "1.0.0",
    provider_class: str = "local_open_source",
    external: bool = False,
    input_roles: list[str] | None = None,
    output_roles: list[str] | None = None,
    capabilities: list[str] | None = None,
    approval_state: str = "approved",
    license_state: str = "verified",
    allowed_classifications: list[str] | None = None,
    deployment_modes: list[str] | None = None,
    model_manifest_ids: list[str] | None = None,
) -> dict[str, object]:
    reviewed = datetime.now(UTC) - timedelta(days=1)
    if provider_class == "manual_external":
        mode = "manual_external"
        deployment = "manual_external"
    elif provider_class == "external_api":
        mode = "external_api"
        deployment = "managed_cloud"
    else:
        mode = "isolated_container"
        deployment = "local_only"
    evidence = [
        _license("code", provider_id),
        _license("dependencies", provider_id),
        _license("output", provider_id),
    ]
    if model_manifest_ids:
        evidence.extend([_license("weights", provider_id), _license("dataset", provider_id)])
    for item in evidence:
        item["review_state"] = license_state
    return {
        "schema": "sip.provider-capability/v1.1",
        "schema_version": "1.1.0",
        "provider_id": provider_id,
        "provider_version": version,
        "provider_class": provider_class,
        "source_url": f"local://providers/{provider_id}",
        "source_revision": f"revision-{version}",
        "executable_digest": canonical_sha256({"provider": provider_id, "version": version}),
        "execution_modes": [mode],
        "deployment_modes": deployment_modes or [deployment],
        "input_roles": input_roles or ["metric_mesh"],
        "output_roles": output_roles or ["interaction_proxy"],
        "capabilities": capabilities or ["mesh_to_surface", "collision_proxy"],
        "supported_formats": {"input": ["model/gltf-binary"], "output": ["model/gltf-binary"]},
        "coordinate_contract": {
            "units": "meter",
            "handedness": "right",
            "up_axes": ["y"],
            "preserves_input_frame": True,
            "scale_behavior": "preserve",
            "requires_explicit_inverse_for_normalization": True,
        },
        "reproducibility": {"deterministic": True, "seed_policy": "fixed"},
        "security": {
            "network_required": False,
            "approved_egress_domains": [],
            "writes_outside_job_workspace": False,
            "supports_read_only_inputs": True,
            "supports_write_only_staging": True,
            "transient_cleanup": "verified",
            "external_processing": external,
        },
        "recovery": {
            "cancellation_bound_seconds": 30,
            "checkpoint_supported": True,
            "resume_supported": True,
            "cleanup_supported": True,
            "checkpoint_schema_version": "1.0.0",
            "objective_progress_units": ["frames", "tiles"],
        },
        "data_governance": {
            "source_data_use": "requested_operation_only",
            "training_use": "prohibited",
            "public_demonstration": "prohibited",
            "unrelated_retention": "prohibited",
            "processing_regions": ["local"],
            "subprocessor_disclosure_complete": True,
            "deletion_verification": "provider_receipt" if external else "platform_verified",
            "data_use_terms_sha256": canonical_sha256({"provider": provider_id, "data-use": "requested-only"}),
        },
        "license_manifest_id": f"license-{provider_id}",
        "license_evidence": evidence,
        "model_manifest_ids": model_manifest_ids or [],
        "dependency_inventory": [
            {"name": "synthetic-geometry", "version": "1.0.0", "sha256": canonical_sha256(provider_id)}
        ],
        "benchmark_profile_ids": ["hybrid-cpu-reference-v1"],
        "allowed_classifications": allowed_classifications or ["internal"],
        "allowed_purposes": [PURPOSE],
        "allowed_regions": ["local"],
        "prohibited_purposes": ["life_safety_certification"],
        "output_rights": "commercial_derivatives_allowed",
        "retention_days": 0,
        "approval_state": approval_state,
        "reviewed_at": reviewed,
        "review_due_at": reviewed + timedelta(days=365),
        "expires_at": reviewed + timedelta(days=365),
        "signed_by": "provider-governance",
    }


def _promote(
    context,
    provider_id: str,
    *,
    state: str = "active",
    data_classifications: list[str] | None = None,
    execution_zones: list[str] | None = None,
    hardware_profiles: list[str] | None = None,
) -> dict[str, object]:
    now = datetime.now(UTC)
    return context.providers.promote(
        provider_id,
        state=state,
        data_classifications=data_classifications or ["internal"],
        scene_classes=["building"],
        output_roles=["interaction_proxy"],
        intended_uses=["picking", "collision"],
        execution_zones=execution_zones or ["local-cpu"],
        hardware_profiles=hardware_profiles or ["cpu-reference"],
        benchmark_evidence_hash=canonical_sha256({"benchmark": provider_id}),
        policy_snapshot_hash=canonical_sha256({"policy": provider_id}),
        valid_from=now - timedelta(minutes=1),
        valid_until=now + timedelta(days=1),
        actor_id="provider-governance",
    )


def _frame_scene_asset(
    context,
    tenant_id: str,
    project_id: str,
    actor: str,
    *,
    data: bytes = b"synthetic metric source" * 16,
    source_class: SourceClass = SourceClass.DIRECT_CAPTURE,
    authority_class: AuthorityClass = AuthorityClass.EVIDENCE,
    classification: Classification = Classification.INTERNAL,
):
    try:
        context.spatial_data.register_frame(
            tenant_id=tenant_id,
            project_id=project_id,
            name="Hybrid world",
            convention="right_handed_y_up_meters",
            units="meter",
            original_units="meter",
            axis_convention="+X right, +Y up, -Z forward",
            axis_directions={"x": "+X right", "y": "+Y up", "z": "-Z forward"},
            handedness="right",
            origin_description="governed hybrid fixture",
            source="synthetic_fixture",
            actor_id=actor,
            frame_id=FRAME_ID,
        )
    except ConflictError as exc:
        if exc.code != "FRAME_EXISTS":
            raise
    scene = context.scene.create_scene(tenant_id, project_id, name="Hybrid governed room", actor_id=actor)
    asset = context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=data,
        media_type="model/gltf-binary",
        original_name="source.glb",
        classification=classification,
        retention_class="test",
        source_class=source_class,
        authority_class=authority_class,
        provenance=ProvenanceRef(source_ids=["synthetic-governed-hybrid"], output_hash=sha256_bytes(data)),
        actor_id=actor,
    )
    return scene, asset


def _request(tenant_id: str, project_id: str, scene: dict[str, str], asset, actor: str, *, key: str, deployment: str = "local_only", allow_external: bool = False, role: str = "metric_mesh") -> dict[str, object]:
    return {
        "schema": "sip.spatial-conversion.request/1.1",
        "tenant_id": tenant_id,
        "project_id": project_id,
        "scene_id": scene["scene_id"],
        "scene_revision_id": scene["commit_id"],
        "purpose": PURPOSE,
        "intended_uses": ["picking", "collision"],
        "output_roles": ["interaction_proxy"],
        "source_assets": [
            {
                "asset_id": asset.asset_id,
                "role": role,
                "sha256": asset.sha256,
                "coordinate_frame_id": FRAME_ID,
            }
        ],
        "reference_assets": [],
        "constraints": {"maximum_output_multiplier": 4.0, "estimate_profile": "test-v1"},
        "policy_context": {
            "scene_class": "building",
            "execution_zone": "local-cpu",
            "hardware_profile": "cpu-reference",
            "region": "local",
            "deployment_mode": deployment,
            "commercial": True,
            "audience": "project",
            "allowed_audiences": ["project"],
            "allow_external_transfer": allow_external,
        },
        "provider_selector": {
            "required_capabilities": ["mesh_to_surface"],
            "forbidden_capabilities": ["unbounded_external_upload"],
        },
        "requested_by": actor,
        "idempotency_key": key,
    }


def _register_profile(context, use: str) -> dict[str, object]:
    return context.hybrid.register_interaction_profile(
        profile_id=f"profile-{use}-v1",
        profile_type=use,
        version="1.0.0",
        actor={"shape": "capsule", "radius_m": 0.3, "height_m": 1.8},
        intended_uses=[use],
        limits={"maximum_error_m": 0.02},
        behavior={"fallback": "disable_use"},
        validation={"method": "deterministic-fixture", "passed": True, "validated_safety_claims": []},
        safety_claims=[],
        validator_id=f"profile-validator-{use}",
        validator_manifest_hash=canonical_sha256({"profile-validator": use}),
        validation_evidence_hash=canonical_sha256({"profile-evidence": use}),
        validated_at=datetime.now(UTC),
        created_by="validation-admin",
    )


def _validate(context, conversion_id: str, tenant_id: str, project_id: str, representation_id: str, use: str, *, error_m: float = 0.01):
    profile = _register_profile(context, use)
    return context.hybrid.validate_candidate(
        conversion_id,
        tenant_id=tenant_id,
        project_id=project_id,
        intended_use=use,
        profile_id=str(profile["profile_id"]),
        profile_version=str(profile["version"]),
        validator_id=f"independent-validator-{use}",
        validator_manifest_hash=canonical_sha256({"validator": use}),
        metrics={"error_m": error_m},
        thresholds={"error_m": {"max": 0.02}},
        coverage={"passed": True, "fraction": 1.0},
        topology={"passed": True, "watertight_required": False},
        coordinate_validation={"passed": True, "frame_id": FRAME_ID},
        behavior_validation={"passed": True, "use": use},
    )


def _complete(context, admitted: dict[str, object], tenant_id: str, project_id: str, actor: str):
    output_data = b"disposable interaction proxy" * 4
    output = context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=output_data,
        media_type="model/gltf-binary",
        original_name="interaction-proxy.glb",
        classification=Classification.INTERNAL,
        retention_class="test",
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        provenance=ProvenanceRef(source_ids=[str(admitted["conversion_id"])], output_hash=sha256_bytes(output_data)),
        actor_id=actor,
    )
    completed = context.hybrid.complete_candidate(
        str(admitted["worker_token"]),
        output_asset_id=output.asset_id,
        output_asset_sha256=output.sha256,
        output_role="interaction_proxy",
        kind=RepresentationKind.INTERACTION,
        coordinate_frame_id=FRAME_ID,
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        lossy=True,
        intended_uses=["picking", "collision"],
        prohibited_uses=["verified_measurement", "survey_grade"],
        quality={"provider_claim": "candidate_only"},
        support_map={"anchors": [], "metric_resolution_required": True},
        worker_receipt_hash=canonical_sha256({"worker": admitted["conversion_id"]}),
        candidate_core_hash=canonical_sha256({"candidate": output.sha256}),
        format_metadata={"format": "glb", "version": "2.0"},
        limitations=["non_authoritative"],
        information_losses=["texture_removed", "surface_decimated"],
    )
    return completed, output


@pytest.mark.integration
@pytest.mark.security
def test_provider_descriptor_revision_promotion_and_tamper_fail_closed(bootstrapped) -> None:
    """REQ: ARCHHYB-004, RECPROV-001, RECPROV-002, RECPROV-004, SECEXT-001, SECEXT-002, SECEXT-006, SECEXT-010 provider execution requires intact signed descriptor revisions, complete data-use facts, and scoped promotions before source access."""
    context, tenant_id, project_id, actor = bootstrapped
    context.providers.register(
        {
            "provider_id": "legacy-provider",
            "version": "0.1.0",
            "source_url": "local://legacy",
            "source_revision": "legacy",
            "license_id": "Apache-2.0",
            "approval_state": "approved",
            "allowed_classifications": ["internal"],
            "allowed_purposes": [PURPOSE],
            "allowed_regions": ["local"],
        },
        actor_id=actor,
    )
    with pytest.raises(ValidationError) as legacy:
        _promote(context, "legacy-provider")
    assert legacy.value.code == "PROVIDER_CAPABILITY_DESCRIPTOR_REQUIRED"

    incomplete = _descriptor("unknown-data-use-provider")
    incomplete.pop("data_governance")
    with pytest.raises(ValidationError) as missing_governance:
        context.providers.register(incomplete, actor_id=actor)
    assert missing_governance.value.code == "PROVIDER_CAPABILITY_INCOMPLETE"

    registered = context.providers.register(_descriptor("strict-provider"), actor_id=actor)
    promoted = _promote(context, "strict-provider")
    selected = context.providers.select(
        classification="internal",
        purpose=PURPOSE,
        region="local",
        deployment_mode="local_only",
        scene_class="building",
        output_roles=["interaction_proxy"],
        intended_uses=["picking", "collision"],
        execution_zone="local-cpu",
        hardware_profile="cpu-reference",
        required_capabilities=["mesh_to_surface"],
    )
    assert selected["provider_manifest_hash"] == registered["manifest_hash"]
    assert selected["promotion_hash"] == promoted["promotion_hash"]
    with context.database.session() as session:
        revision = session.get(ProviderManifestRevisionRow, registered["manifest_hash"])
        assert revision is not None
        promotion = session.get(ProviderPromotionRow, promoted["promotion_id"])
        assert promotion is not None
        promotion.signature = "0" * 64
    with pytest.raises(AuthorizationError) as tampered:
        context.providers.select(
            classification="internal",
            purpose=PURPOSE,
            region="local",
            deployment_mode="local_only",
            scene_class="building",
            output_roles=["interaction_proxy"],
            intended_uses=["picking", "collision"],
            execution_zone="local-cpu",
            hardware_profile="cpu-reference",
            required_capabilities=["mesh_to_surface"],
        )
    assert tampered.value.code == "HYB_PROVIDER_NO_ELIGIBLE_MATCH"


@pytest.mark.integration
@pytest.mark.security
def test_conversion_admission_worker_scope_progress_idempotency_and_cancel(bootstrapped) -> None:
    """REQ: ARCHHYB-003, HYBAPI-002, HYBAPI-004, RECPROV-003, RECPROV-006, SECEXT-007 admission is immutable, coordinate/authority records are explicit, worker credentials are least-privilege, and operations are resumable/cancellable."""
    context, tenant_id, project_id, actor = bootstrapped
    scene, source = _frame_scene_asset(context, tenant_id, project_id, actor)
    context.providers.register(_descriptor("local-provider"), actor_id=actor)
    _promote(context, "local-provider")

    bad = _request(tenant_id, project_id, scene, source, actor, key="bad-hash")
    bad["source_assets"][0]["sha256"] = "0" * 64  # type: ignore[index]
    with pytest.raises(ValidationError) as mismatch:
        context.hybrid.create_conversion(bad, actor_id=actor)
    assert mismatch.value.code == "HYB_SOURCE_HASH_MISMATCH"
    with context.database.session() as session:
        rejected = session.scalar(
            select(OutboxEventRow).where(
                OutboxEventRow.event_type == "representation.operation.rejected",
                OutboxEventRow.tenant_id == tenant_id,
                OutboxEventRow.project_id == project_id,
            )
        )
        denial = session.scalar(
            select(AuditEventRow).where(
                AuditEventRow.action == "hybrid_conversion:admit",
                AuditEventRow.outcome == "denied",
            )
        )
        assert rejected is not None
        assert rejected.payload_json["error_code"] == "HYB_SOURCE_HASH_MISMATCH"
        assert rejected.payload_json["operation_created"] is False
        assert denial is not None
        assert denial.details_json["request_hash"] == rejected.payload_json["request_hash"]

    request = _request(tenant_id, project_id, scene, source, actor, key="conversion-1")
    admitted = context.hybrid.create_conversion(request, actor_id=actor)
    claims = context.hybrid.token_codec.decode(str(admitted["worker_token"]))
    assert claims["publication_permission"] is False
    assert set(claims["permissions"]) == {"asset:read_exact", "quarantine:write", "operation:checkpoint", "operation:complete"}
    assert claims["input_assets"] == [{"asset_id": source.asset_id, "sha256": source.sha256, "role": "metric_mesh"}]
    assert claims["output_staging_scope"]["mode"] == "write_only_quarantine"
    with context.database.session() as session:
        operation = session.get(OperationRow, admitted["operation_id"])
        assert operation is not None
        immutable = operation.input_json
        assert immutable["source_assets"][0]["sha256"] == source.sha256
        assert immutable["source_assets"][0]["role"] == "metric_mesh"
        assert immutable["source_assets"][0]["coordinate_frame_id"] == FRAME_ID
        assert immutable["intended_uses"] == ["picking", "collision"]
        assert immutable["constraints"]["maximum_output_multiplier"] == 4.0
        assert immutable["effective_classification"] == "internal"
        assert immutable["idempotency_key"] == "conversion-1"
        assert immutable["validated_sources"][0]["authority_class"] == "evidence"

    replay = context.hybrid.create_conversion(request, actor_id=actor)
    assert replay["idempotent_replay"] is True and replay["worker_token"] is None
    changed = dict(request)
    changed["constraints"] = {"maximum_output_multiplier": 5.0}
    with pytest.raises(ConflictError) as conflict:
        context.hybrid.create_conversion(changed, actor_id=actor)
    assert conflict.value.code == "HYB_IDEMPOTENCY_PAYLOAD_CONFLICT"

    progress = {
        "conversion_id": admitted["conversion_id"],
        "sequence": 1,
        "stage": "surface extraction",
        "completed_work_units": 10,
        "total_work_units": 100,
        "work_unit_name": "frames",
        "resource_use": {"cpu_seconds": 1.0},
        "warnings": [],
        "last_durable_checkpoint_hash": canonical_sha256({"checkpoint": 1}),
        "estimated_output_bytes": 128,
    }
    assert context.hybrid.record_progress(str(admitted["worker_token"]), progress)["sequence"] == 1
    assert context.hybrid.record_progress(str(admitted["worker_token"]), progress)["sequence"] == 1
    regressed = {**progress, "sequence": 2, "completed_work_units": 9}
    with pytest.raises(ConflictError) as regression:
        context.hybrid.record_progress(str(admitted["worker_token"]), regressed)
    assert regression.value.code == "HYB_PROGRESS_REGRESSION"

    cancelled = context.hybrid.cancel_conversion(
        str(admitted["conversion_id"]), tenant_id=tenant_id, project_id=project_id, actor_id=actor
    )
    assert cancelled["state"] == "cancel_requested"
    with pytest.raises(AuthenticationError) as inactive:
        context.hybrid.record_progress(str(admitted["worker_token"]), {**progress, "sequence": 2, "completed_work_units": 20})
    assert inactive.value.code == "HYB_WORKER_CONVERSION_INACTIVE"

    other_tenant = context.tenancy.create_tenant("Other", tenant_id="tenant-other-hybrid", actor_id="system")
    other_project = context.tenancy.create_project(other_tenant, "Other", vertical="platform", classification="internal", project_id="project-other-hybrid", actor_id="other")
    other_data = b"other tenant source" * 16
    other_asset = context.assets.ingest_bytes(
        tenant_id=other_tenant,
        project_id=other_project,
        data=other_data,
        media_type="model/gltf-binary",
        original_name="other.glb",
        classification=Classification.INTERNAL,
        retention_class="test",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["other-tenant-fixture"], output_hash=sha256_bytes(other_data)),
        actor_id="other",
    )
    cross = _request(tenant_id, project_id, scene, other_asset, actor, key="cross-tenant")
    with pytest.raises(NotFoundError):
        context.hybrid.create_conversion(cross, actor_id=actor)


@pytest.mark.integration
@pytest.mark.security
def test_quarantine_independent_validation_atomic_publication_and_view_reauthorization(bootstrapped) -> None:
    """REQ: ARCHHYB-002, ARCHHYB-005, DATHYB-005, RECHYB-005, RECPROV-005, RECPROV-007, HYBRUN-001, HYBRUN-002, HYBRUN-007 candidates remain quarantined until independent use-specific review, atomic publication, and server-side view reauthorization."""
    context, tenant_id, project_id, actor = bootstrapped
    scene, source = _frame_scene_asset(context, tenant_id, project_id, actor)
    context.providers.register(_descriptor("publication-provider"), actor_id=actor)
    _promote(context, "publication-provider")
    admitted = context.hybrid.create_conversion(_request(tenant_id, project_id, scene, source, actor, key="publish-1"), actor_id=actor)
    completed, output = _complete(context, admitted, tenant_id, project_id, actor)
    representation_id = str(completed["representation_id"])
    with context.database.session() as session:
        rep = session.get(RepresentationAssetRow, representation_id)
        assert rep is not None and rep.state == "quarantined" and rep.disposable is True
    with pytest.raises(ConflictError):
        context.publisher.publish(representation_id, commit_id=scene["commit_id"], role="interaction_proxy", publisher_id="publisher")

    picking = _validate(context, str(admitted["conversion_id"]), tenant_id, project_id, representation_id, "picking")
    replay = context.hybrid.validate_candidate(
        str(admitted["conversion_id"]),
        tenant_id=tenant_id,
        project_id=project_id,
        intended_use="picking",
        profile_id="profile-picking-v1",
        profile_version="1.0.0",
        validator_id="independent-validator-picking",
        validator_manifest_hash=canonical_sha256({"validator": "picking"}),
        metrics={"error_m": 0.01},
        thresholds={"error_m": {"max": 0.02}},
        coverage={"passed": True, "fraction": 1.0},
        topology={"passed": True, "watertight_required": False},
        coordinate_validation={"passed": True, "frame_id": FRAME_ID},
        behavior_validation={"passed": True, "use": "picking"},
    )
    assert replay["validation_id"] == picking["validation_id"]
    _validate(context, str(admitted["conversion_id"]), tenant_id, project_id, representation_id, "collision")

    binding_id = context.publisher.publish(
        representation_id,
        commit_id=scene["commit_id"],
        role="interaction_proxy",
        publisher_id="publisher",
        intended_uses=["picking", "collision"],
    )
    with context.database.session() as session:
        conversion = session.get(SpatialConversionRow, admitted["conversion_id"])
        binding = session.get(RepresentationBindingRow, binding_id)
        assert conversion is not None and conversion.state == "validated"
        assert binding is not None and binding.representation_id == representation_id

    context.policy.create_identity(tenant_id, "hybrid-viewer", "Hybrid Viewer")
    context.policy.bind_role(
        binding_id="hybrid-viewer-role",
        tenant_id=tenant_id,
        project_id=project_id,
        identity_id="hybrid-viewer",
        role="viewer",
        purposes=[PURPOSE],
    )
    principal = context.policy.principal_for(tenant_id, "hybrid-viewer", project_id=project_id, audience=Audience.PROJECT)
    view = context.hybrid.create_view_manifest(
        principal=principal,
        project_id=project_id,
        scene_id=scene["scene_id"],
        scene_revision_id=scene["commit_id"],
        purpose=PURPOSE,
        audience="project",
        device_profile="desktop-reference",
        time_context={"mode": "commit"},
        intended_uses=["picking", "collision"],
    )
    manifest = view["manifest"]
    assert manifest["bindings"] == {"interaction_proxy": [binding_id]}
    rendered = str(manifest)
    assert output.asset_id not in rendered and output.sha256 not in rendered
    assert context.hybrid.verify_view_token(view["token"], principal_id="hybrid-viewer", purpose=PURPOSE)["view_id"] == manifest["view_id"]

    with context.database.session() as session:
        session.get(RepresentationBindingRow, binding_id).superseded_at = db_now()  # type: ignore[union-attr]
    with pytest.raises(AuthorizationError) as invalidated:
        context.hybrid.verify_view_token(view["token"], principal_id="hybrid-viewer", purpose=PURPOSE)
    assert invalidated.value.code == "HYB_VIEW_BINDING_INVALIDATED"


@pytest.mark.integration
@pytest.mark.security
def test_provider_or_validation_snapshot_changes_block_publication(bootstrapped) -> None:
    """REQ: RECPROV-007, DATHYB-010 publication uses the exact admitted provider, scene, candidate, and validation snapshots."""
    context, tenant_id, project_id, actor = bootstrapped
    scene, source = _frame_scene_asset(context, tenant_id, project_id, actor)
    context.providers.register(_descriptor("stale-provider"), actor_id=actor)
    _promote(context, "stale-provider")
    admitted = context.hybrid.create_conversion(_request(tenant_id, project_id, scene, source, actor, key="stale-1"), actor_id=actor)
    completed, _ = _complete(context, admitted, tenant_id, project_id, actor)
    representation_id = str(completed["representation_id"])
    _validate(context, str(admitted["conversion_id"]), tenant_id, project_id, representation_id, "picking")
    _validate(context, str(admitted["conversion_id"]), tenant_id, project_id, representation_id, "collision")

    context.providers.register(_descriptor("stale-provider", version="1.0.1"), actor_id=actor)
    with pytest.raises(AuthorizationError) as stale:
        context.publisher.publish(
            representation_id,
            commit_id=scene["commit_id"],
            role="interaction_proxy",
            publisher_id="publisher",
            intended_uses=["picking", "collision"],
        )
    assert stale.value.code == "PROVIDER_MANIFEST_CHANGED"


@pytest.mark.integration
@pytest.mark.security
def test_manual_external_path_exports_only_non_authoritative_derivatives_and_retains_receipt(bootstrapped) -> None:
    """REQ: RECCLEAN-004, RECPROV-008, RECPROV-009, SECEXT-004, SECEXT-009, PLTIO-008 manual tools use controlled derivative export, custody receipts, exact return hashes, quarantine, and independent validation."""
    context, tenant_id, project_id, actor = bootstrapped
    scene, derivative = _frame_scene_asset(
        context,
        tenant_id,
        project_id,
        actor,
        data=b"redacted non-authoritative derivative" * 16,
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
    )
    context.providers.register(
        _descriptor(
            "manual-provider",
            provider_class="manual_external",
            external=True,
            input_roles=["metric_mesh"],
        ),
        actor_id=actor,
    )
    _promote(context, "manual-provider")
    admitted = context.hybrid.create_conversion(
        _request(
            tenant_id,
            project_id,
            scene,
            derivative,
            actor,
            key="manual-1",
            deployment="manual_external",
            allow_external=True,
        ),
        actor_id=actor,
    )
    exported = context.hybrid.create_manual_export(
        str(admitted["conversion_id"]),
        tenant_id=tenant_id,
        project_id=project_id,
        approved_derivative_asset_ids=[derivative.asset_id],
        actor_id=actor,
    )
    returned_data = b"manual provider output" * 8
    returned = context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=returned_data,
        media_type="model/gltf-binary",
        original_name="manual-return.glb",
        classification=Classification.INTERNAL,
        retention_class="test",
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        provenance=ProvenanceRef(source_ids=[derivative.asset_id], output_hash=sha256_bytes(returned_data)),
        actor_id=actor,
    )
    receipt_body = {
        "transfer_id": exported["transfer_id"],
        "conversion_id": admitted["conversion_id"],
        "tool": "synthetic-manual-tool",
        "tool_version": "1.0.0",
        "account_or_environment": "isolated-test",
        "operator_id": "manual-operator",
        "executed_at": datetime.now(UTC).isoformat(),
        "input_hashes": [derivative.sha256],
        "output_hashes": [returned.sha256],
        "options": {"cleanup": "documented"},
        "processing_location": "local_operator_device",
        "retention_statement": "inputs deleted after verified return",
        "cleanup_actions": ["deleted temporary workspace"],
        "manual_edits": [{"operation": "remove visual artifact"}],
        "evidence_asset_ids": [derivative.asset_id],
    }
    provisional = ManualExternalReceiptContract.model_validate({**receipt_body, "receipt_hash": "0" * 64})
    normalized = provisional.model_dump(mode="json")
    normalized.pop("receipt_hash")
    receipt = {**normalized, "receipt_hash": canonical_sha256(normalized)}
    with pytest.raises(AuthenticationError):
        context.hybrid.record_manual_return(
            str(exported["transfer_id"]),
            tenant_id=tenant_id,
            project_id=project_id,
            one_time_return_code="wrong",
            receipt=receipt,
            returned_outputs=[{"asset_id": returned.asset_id, "sha256": returned.sha256, "role": "interaction_proxy"}],
            actor_id="manual-operator",
        )
    accepted = context.hybrid.record_manual_return(
        str(exported["transfer_id"]),
        tenant_id=tenant_id,
        project_id=project_id,
        one_time_return_code=str(exported["one_time_return_code"]),
        receipt=receipt,
        returned_outputs=[{"asset_id": returned.asset_id, "sha256": returned.sha256, "role": "interaction_proxy"}],
        actor_id="manual-operator",
    )
    assert accepted["state"] == "returned_pending_validation"
    replay = context.hybrid.record_manual_return(
        str(exported["transfer_id"]),
        tenant_id=tenant_id,
        project_id=project_id,
        one_time_return_code=str(exported["one_time_return_code"]),
        receipt=receipt,
        returned_outputs=[{"asset_id": returned.asset_id, "sha256": returned.sha256, "role": "interaction_proxy"}],
        actor_id="manual-operator",
    )
    assert replay["idempotent_replay"] is True

    completed = context.hybrid.complete_candidate(
        str(admitted["worker_token"]),
        output_asset_id=returned.asset_id,
        output_asset_sha256=returned.sha256,
        output_role="interaction_proxy",
        kind=RepresentationKind.INTERACTION,
        coordinate_frame_id=FRAME_ID,
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        lossy=True,
        intended_uses=["picking", "collision"],
        prohibited_uses=["verified_measurement", "automatic_publication"],
        quality={"manual_provider_claim": "candidate_only"},
        support_map={"metric_resolution_required": True},
        worker_receipt_hash=str(accepted["receipt_hash"]),
        candidate_core_hash=canonical_sha256({"manual-return": returned.sha256}),
        limitations=["manual external derivative", "non-authoritative"],
        information_losses=["operator edits", "provider conversion"],
    )
    assert completed["state"] == "quarantined"
    representation_id = str(completed["representation_id"])
    _validate(context, str(admitted["conversion_id"]), tenant_id, project_id, representation_id, "picking")
    _validate(context, str(admitted["conversion_id"]), tenant_id, project_id, representation_id, "collision")
    binding_id = context.publisher.publish(
        representation_id,
        commit_id=scene["commit_id"],
        role="interaction_proxy",
        publisher_id="publisher",
        intended_uses=["picking", "collision"],
    )
    assert binding_id

    # A direct-capture evidence asset is never eligible for the manual external path.
    raw_data = b"raw direct capture" * 16
    raw = context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=raw_data,
        media_type="model/gltf-binary",
        original_name="raw.glb",
        classification=Classification.INTERNAL,
        retention_class="test",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["raw-fixture"], output_hash=sha256_bytes(raw_data)),
        actor_id=actor,
    )
    raw_request = _request(
        tenant_id,
        project_id,
        scene,
        raw,
        actor,
        key="manual-raw",
        deployment="manual_external",
        allow_external=True,
    )
    raw_admitted = context.hybrid.create_conversion(raw_request, actor_id=actor)
    with pytest.raises(AuthorizationError) as raw_denied:
        context.hybrid.create_manual_export(
            str(raw_admitted["conversion_id"]),
            tenant_id=tenant_id,
            project_id=project_id,
            approved_derivative_asset_ids=[raw.asset_id],
            actor_id=actor,
        )
    assert raw_denied.value.code == "HYB_MANUAL_EXPORT_RAW_SOURCE_DENIED"


@pytest.mark.integration
@pytest.mark.security
def test_representation_family_requires_approved_frame_consistent_lods_and_seam_evidence(bootstrapped) -> None:
    """REQ: DATHYB-014, HYBRUN-001 LOD families preserve approved bindings, one frame, monotonic error budgets, and retained seam evidence."""
    context, tenant_id, project_id, actor = bootstrapped
    scene, _ = _frame_scene_asset(context, tenant_id, project_id, actor)
    context.providers.register(
        {
            "provider_id": "local-deterministic-baseline",
            "version": "1.0.0",
            "source_url": "local://providers/local-deterministic-baseline",
            "source_revision": "fixture",
            "license_id": "Apache-2.0",
            "approval_state": "approved",
            "allowed_classifications": ["internal"],
            "allowed_purposes": [PURPOSE],
            "allowed_regions": ["local"],
        },
        actor_id=actor,
    )

    def candidate(seed: str, *, approve: bool = True) -> str:
        data = (f"proxy-{seed}".encode("utf-8")) * 16
        asset = context.assets.ingest_bytes(
            tenant_id=tenant_id,
            project_id=project_id,
            data=data,
            media_type="model/gltf-binary",
            original_name=f"proxy-{seed}.glb",
            classification=Classification.INTERNAL,
            retention_class="test",
            source_class=SourceClass.GENERATED,
            authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
            provenance=ProvenanceRef(source_ids=[f"family:{seed}"], output_hash=sha256_bytes(data)),
            actor_id=actor,
        )
        representation_id = context.representations.create_candidate(
            tenant_id=tenant_id,
            project_id=project_id,
            scene_id=scene["scene_id"],
            asset_id=asset.asset_id,
            kind=RepresentationKind.INTERACTION,
            provider_id="local-deterministic-baseline",
            coordinate_frame_id=FRAME_ID,
            source_class=SourceClass.GENERATED,
            authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
            lossy=True,
            intended_uses=["picking"],
            prohibited_uses=["verified_measurement"],
            quality={"fixture": True},
            provenance={"source_ids": [f"family:{seed}"]},
            support_map={"stable_semantic_ids": True},
            actor_id=actor,
            metadata={"output_role": "interaction_proxy", "truth_label": "disposable interaction proxy"},
        )
        if approve:
            context.representations.review_quality(
                representation_id,
                reviewer_id=f"independent-family-reviewer-{seed}",
                approved_uses=["picking"],
                metrics={"screen_error_px": 1.0},
                passed=True,
            )
        return representation_id

    coarse = candidate("coarse")
    fine = candidate("fine")
    unapproved = candidate("unapproved", approve=False)
    lods = [
        {"level": 0, "representation_id": coarse, "maximum_screen_error_px": 12.0},
        {"level": 1, "representation_id": fine, "maximum_screen_error_px": 3.0},
    ]

    with pytest.raises(ValidationError) as missing_seam:
        context.hybrid.register_representation_family(
            tenant_id=tenant_id,
            project_id=project_id,
            scene_id=scene["scene_id"],
            role="interaction_proxy",
            coordinate_frame_id=FRAME_ID,
            tile_scheme_id="octree-y-up-v1",
            lods=lods,
            seam_validation_report_id=None,
            fallback_representation_id=coarse,
            actor_id=actor,
        )
    assert missing_seam.value.code == "HYB_SEAM_VALIDATION_REQUIRED"

    with pytest.raises(ValidationError) as error_order:
        context.hybrid.register_representation_family(
            tenant_id=tenant_id,
            project_id=project_id,
            scene_id=scene["scene_id"],
            role="interaction_proxy",
            coordinate_frame_id=FRAME_ID,
            tile_scheme_id="octree-y-up-v1",
            lods=[
                {"level": 0, "representation_id": coarse, "maximum_screen_error_px": 3.0},
                {"level": 1, "representation_id": fine, "maximum_screen_error_px": 12.0},
            ],
            seam_validation_report_id="seam-report-order",
            fallback_representation_id=coarse,
            actor_id=actor,
        )
    assert error_order.value.code == "HYB_LOD_ERROR_ORDER_INVALID"

    with pytest.raises(ConflictError) as unreviewed:
        context.hybrid.register_representation_family(
            tenant_id=tenant_id,
            project_id=project_id,
            scene_id=scene["scene_id"],
            role="interaction_proxy",
            coordinate_frame_id=FRAME_ID,
            tile_scheme_id="single-y-up-v1",
            lods=[{"level": 0, "representation_id": unapproved, "maximum_screen_error_px": 12.0}],
            seam_validation_report_id=None,
            fallback_representation_id=None,
            actor_id=actor,
        )
    assert unreviewed.value.code == "HYB_FAMILY_REPRESENTATION_NOT_APPROVED"

    family = context.hybrid.register_representation_family(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        role="interaction_proxy",
        coordinate_frame_id=FRAME_ID,
        tile_scheme_id="octree-y-up-v1",
        lods=list(reversed(lods)),
        seam_validation_report_id="seam-report-sha256:" + canonical_sha256({"family": "fixture"}),
        fallback_representation_id=coarse,
        actor_id=actor,
        family_id="family-governed-fixture",
    )
    assert [item["level"] for item in family["lods"]] == [0, 1]
    replay = context.hybrid.register_representation_family(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        role="interaction_proxy",
        coordinate_frame_id=FRAME_ID,
        tile_scheme_id="octree-y-up-v1",
        lods=list(reversed(lods)),
        seam_validation_report_id="seam-report-sha256:" + canonical_sha256({"family": "fixture"}),
        fallback_representation_id=coarse,
        actor_id=actor,
        family_id="family-governed-fixture",
    )
    assert replay["family_hash"] == family["family_hash"]


@pytest.mark.integration
@pytest.mark.security
def test_worker_lease_rotation_is_bounded_and_supersedes_prior_credentials(bootstrapped) -> None:
    """REQ: HYBAPI-004, SECEXT-007 durable operation-scoped worker leases rotate, remain short-lived and token-bounded, and cannot be replayed after supersession."""
    context, tenant_id, project_id, actor = bootstrapped
    scene, source = _frame_scene_asset(context, tenant_id, project_id, actor)
    context.providers.register(_descriptor("lease-provider"), actor_id=actor)
    _promote(context, "lease-provider")
    request = _request(tenant_id, project_id, scene, source, actor, key="lease-rotation")
    request["provider_selector"]["preferred_provider_ids"] = ["lease-provider"]  # type: ignore[index]
    admitted = context.hybrid.create_conversion(request, actor_id=actor, worker_lease_ttl_seconds=120)
    old_token = str(admitted["worker_token"])
    progress = {
        "conversion_id": admitted["conversion_id"],
        "sequence": 1,
        "stage": "lease fixture",
        "completed_work_units": 1,
        "total_work_units": 10,
        "work_unit_name": "frames",
        "resource_use": {"cpu_seconds": 0.1},
        "warnings": [],
        "last_durable_checkpoint_hash": canonical_sha256({"lease": 1}),
        "estimated_output_bytes": 64,
    }
    context.hybrid.record_progress(old_token, progress)

    renewed = context.hybrid.renew_worker_lease(old_token, lease_ttl_seconds=45)
    new_token = str(renewed["worker_token"])
    new_claims = context.hybrid.token_codec.decode(new_token)
    assert renewed["credential_generation"] == 2
    assert new_claims["exp"] - new_claims["iat"] == 45
    operation = context.operations.get(str(admitted["operation_id"]))
    assert operation["lease_owner"] == new_claims["workload_identity"]
    lease_expires_at = operation["lease_expires_at"]
    if lease_expires_at.tzinfo is None:
        lease_expires_at = lease_expires_at.replace(tzinfo=UTC)
    assert lease_expires_at <= datetime.fromtimestamp(new_claims["exp"], UTC) + timedelta(seconds=1)

    with pytest.raises(AuthenticationError) as superseded:
        context.hybrid.record_progress(old_token, {**progress, "sequence": 2, "completed_work_units": 2})
    assert superseded.value.code == "HYB_WORKER_CREDENTIAL_SUPERSEDED"
    assert context.hybrid.record_progress(new_token, {**progress, "sequence": 2, "completed_work_units": 2})["sequence"] == 2

    with context.database.session() as session:
        renewal = session.scalar(select(OutboxEventRow).where(
            OutboxEventRow.event_type == "representation.worker_lease.renewed",
            OutboxEventRow.aggregate_id == admitted["conversion_id"],
        ))
        assert renewal is not None
        assert renewal.payload_json["credential_generation"] == 2
        assert "worker_token" not in renewal.payload_json


@pytest.mark.integration
@pytest.mark.security
def test_provider_failure_retains_cleanup_evidence_and_preserves_published_binding(bootstrapped) -> None:
    """REQ: ARCHHYB-007, HYBRUN-001, HYBRUN-007 provider failure is durable and cannot mutate source evidence, the accepted scene revision, or the prior published representation."""
    context, tenant_id, project_id, actor = bootstrapped
    scene, source = _frame_scene_asset(context, tenant_id, project_id, actor)
    context.providers.register(_descriptor("failure-provider"), actor_id=actor)
    _promote(context, "failure-provider")
    source_bytes_before = context.assets.read(tenant_id, project_id, source.asset_id, actor_id=actor)
    with context.database.session() as session:
        scene_commit_before = session.get(SceneCommitRow, scene["commit_id"])
        assert scene_commit_before is not None
        scene_snapshot_hash_before = scene_commit_before.snapshot_hash

    first_request = _request(tenant_id, project_id, scene, source, actor, key="failure-prior")
    first_request["provider_selector"]["preferred_provider_ids"] = ["failure-provider"]  # type: ignore[index]
    first = context.hybrid.create_conversion(first_request, actor_id=actor)
    completed, _ = _complete(context, first, tenant_id, project_id, actor)
    representation_id = str(completed["representation_id"])
    _validate(context, str(first["conversion_id"]), tenant_id, project_id, representation_id, "picking")
    _validate(context, str(first["conversion_id"]), tenant_id, project_id, representation_id, "collision")
    binding_id = context.publisher.publish(
        representation_id,
        commit_id=scene["commit_id"],
        role="interaction_proxy",
        publisher_id="publisher",
        intended_uses=["picking", "collision"],
    )

    replacement_request = _request(tenant_id, project_id, scene, source, actor, key="failure-replacement")
    replacement_request["provider_selector"]["preferred_provider_ids"] = ["failure-provider"]  # type: ignore[index]
    replacement = context.hybrid.create_conversion(replacement_request, actor_id=actor)
    cleanup_hash = canonical_sha256({"cleanup": replacement["conversion_id"], "workspace_removed": True})
    failed = context.hybrid.report_provider_failure(
        str(replacement["worker_token"]),
        error_code="PROVIDER_OOM",
        retryable=True,
        cleanup_receipt_hash=cleanup_hash,
        cleanup_verified=True,
        last_durable_checkpoint_hash=canonical_sha256({"checkpoint": "before-oom"}),
        resource_use={"peak_memory_bytes": 1024},
    )
    assert failed["state"] == "failed_retryable"
    assert failed["preserved_binding_ids"] == [binding_id]
    replay = context.hybrid.report_provider_failure(
        str(replacement["worker_token"]),
        error_code="PROVIDER_OOM",
        retryable=True,
        cleanup_receipt_hash=cleanup_hash,
        cleanup_verified=True,
        last_durable_checkpoint_hash=canonical_sha256({"checkpoint": "before-oom"}),
        resource_use={"peak_memory_bytes": 1024},
    )
    assert replay["idempotent_replay"] is True

    with context.database.session() as session:
        binding = session.get(RepresentationBindingRow, binding_id)
        operation = session.get(OperationRow, replacement["operation_id"])
        failure = session.scalar(select(OutboxEventRow).where(
            OutboxEventRow.event_type == "representation.operation.failed",
            OutboxEventRow.aggregate_id == replacement["conversion_id"],
        ))
        assert binding is not None and binding.superseded_at is None and binding.representation_id == representation_id
        assert operation is not None and operation.state == "failed"
        assert operation.error_json["cleanup_receipt_hash"] == cleanup_hash
        assert failure is not None and failure.payload_json["preserved_binding_ids"] == [binding_id]
        scene_commit_after = session.get(SceneCommitRow, scene["commit_id"])
        assert scene_commit_after is not None and scene_commit_after.snapshot_hash == scene_snapshot_hash_before
    assert context.assets.read(tenant_id, project_id, source.asset_id, actor_id=actor) == source_bytes_before
    assert context.assets.get(tenant_id, project_id, source.asset_id).sha256 == source.sha256

    with pytest.raises(AuthenticationError) as inactive:
        context.hybrid.record_progress(str(replacement["worker_token"]), {
            "conversion_id": replacement["conversion_id"],
            "sequence": 1,
            "stage": "invalid after failure",
            "completed_work_units": 1,
            "total_work_units": 1,
            "work_unit_name": "frames",
            "resource_use": {},
            "warnings": [],
        })
    assert inactive.value.code == "HYB_WORKER_CONVERSION_INACTIVE"


@pytest.mark.integration
@pytest.mark.security
def test_provider_admission_denials_fail_closed_and_retain_safe_evidence(bootstrapped) -> None:
    """REQ: ARCHHYB-004, ARCHHYB-006, RECPROV-004, RECPROV-006, SECEXT-001, SECEXT-002, SECEXT-005, SECEXT-006 model, license, promotion, classification, external-transfer, and quota gates fail closed before source access."""
    context, tenant_id, project_id, actor = bootstrapped
    scene, source = _frame_scene_asset(context, tenant_id, project_id, actor)

    context.providers.register(_descriptor("license-denied", license_state="missing"), actor_id=actor)
    _promote(context, "license-denied")
    license_request = _request(tenant_id, project_id, scene, source, actor, key="license-denied")
    license_request["provider_selector"]["preferred_provider_ids"] = ["license-denied"]  # type: ignore[index]
    with pytest.raises(AuthorizationError) as license_denial:
        context.hybrid.create_conversion(license_request, actor_id=actor)
    assert license_denial.value.code == "HYB_PROVIDER_LICENSE_EVIDENCE_INCOMPLETE"

    component_incomplete = _descriptor("license-components-denied")
    component_incomplete["license_evidence"] = [
        item for item in component_incomplete["license_evidence"] if item["component"] != "dependencies"
    ]
    context.providers.register(component_incomplete, actor_id=actor)
    _promote(context, "license-components-denied")
    component_request = _request(tenant_id, project_id, scene, source, actor, key="license-components-denied")
    component_request["provider_selector"]["preferred_provider_ids"] = ["license-components-denied"]  # type: ignore[index]
    with pytest.raises(AuthorizationError) as component_denial:
        context.hybrid.create_conversion(component_request, actor_id=actor)
    assert component_denial.value.code == "HYB_PROVIDER_LICENSE_EVIDENCE_INCOMPLETE"

    context.providers.register(
        _descriptor("external-no-approval", provider_class="external_api", external=True),
        actor_id=actor,
    )
    _promote(context, "external-no-approval")
    external_request = _request(
        tenant_id, project_id, scene, source, actor, key="external-no-approval", deployment="managed_cloud"
    )
    external_request["provider_selector"]["preferred_provider_ids"] = ["external-no-approval"]  # type: ignore[index]
    with pytest.raises(AuthorizationError) as external_denial:
        context.hybrid.create_conversion(external_request, actor_id=actor)
    assert external_denial.value.code == "HYB_EXTERNAL_TRANSFER_NOT_APPROVED"

    critical_scene, critical_asset = _frame_scene_asset(
        context,
        tenant_id,
        project_id,
        actor,
        data=b"critical spatial source" * 16,
        classification=Classification.CRITICAL_INFRASTRUCTURE,
    )
    context.providers.register(
        _descriptor(
            "external-critical",
            provider_class="external_api",
            external=True,
            allowed_classifications=["critical_infrastructure"],
        ),
        actor_id=actor,
    )
    _promote(context, "external-critical", data_classifications=["critical_infrastructure"])
    critical_request = _request(
        tenant_id, project_id, critical_scene, critical_asset, actor, key="external-critical", deployment="managed_cloud", allow_external=True
    )
    critical_request["provider_selector"]["preferred_provider_ids"] = ["external-critical"]  # type: ignore[index]
    with pytest.raises(AuthorizationError) as critical_denial:
        context.hybrid.create_conversion(critical_request, actor_id=actor)
    assert critical_denial.value.code == "HYB_SENSITIVE_EXTERNAL_PROCESSING_DENIED", critical_denial.value.details

    context.providers.register(_descriptor("shadow-commercial"), actor_id=actor)
    _promote(context, "shadow-commercial", state="shadow")
    shadow_request = _request(tenant_id, project_id, scene, source, actor, key="shadow-commercial")
    shadow_request["provider_selector"]["preferred_provider_ids"] = ["shadow-commercial"]  # type: ignore[index]
    with pytest.raises(AuthorizationError) as shadow_denial:
        context.hybrid.create_conversion(shadow_request, actor_id=actor)
    assert shadow_denial.value.code == "HYB_PROVIDER_PROMOTION_NOT_PRODUCTION_ELIGIBLE"

    denied_model = lingbot_checkpoint_denied_manifest()
    context.models.register(denied_model, actor_id=actor)
    context.providers.register(
        _descriptor("model-denied", model_manifest_ids=[str(denied_model["model_id"])]),
        actor_id=actor,
    )
    _promote(context, "model-denied")
    model_request = _request(tenant_id, project_id, scene, source, actor, key="model-denied")
    model_request["provider_selector"]["preferred_provider_ids"] = ["model-denied"]  # type: ignore[index]
    with pytest.raises(AuthorizationError) as model_denial:
        context.hybrid.create_conversion(model_request, actor_id=actor)
    assert model_denial.value.code in {"MODEL_NOT_APPROVED", "MODEL_EXECUTION_DENIED"}

    context.providers.register(_descriptor("quota-denied"), actor_id=actor)
    _promote(context, "quota-denied")
    context.admission.set_quota(
        tenant_id=tenant_id,
        project_id=project_id,
        resource_type="hybrid_provider_input_bytes",
        unit="bytes",
        period_seconds=3600,
        soft_limit=1,
        hard_limit=1,
        actor_id=actor,
    )
    quota_request = _request(tenant_id, project_id, scene, source, actor, key="quota-denied")
    quota_request["provider_selector"]["preferred_provider_ids"] = ["quota-denied"]  # type: ignore[index]
    with pytest.raises(ConflictError) as quota_denial:
        context.hybrid.create_conversion(quota_request, actor_id=actor)
    assert quota_denial.value.code == "QUOTA_HARD_LIMIT"
    with context.database.session() as session:
        operation = session.scalar(select(OperationRow).where(OperationRow.idempotency_key == "hybrid:quota-denied"))
        if operation is None:
            operation = session.scalar(select(OperationRow).where(OperationRow.idempotency_key == "quota-denied"))
        assert operation is not None and operation.state == "quarantined"
        rejection = session.scalar(select(OutboxEventRow).where(
            OutboxEventRow.event_type == "representation.operation.rejected",
            OutboxEventRow.aggregate_id == operation.operation_id,
        ))
        assert rejection is not None and rejection.payload_json["operation_created"] is True
        assert "source_assets" not in rejection.payload_json


@pytest.mark.integration
@pytest.mark.security
def test_spatial_classification_signals_raise_the_floor_and_block_sensitive_external_egress(bootstrapped, monkeypatch) -> None:
    """REQ: ARCHHYB-006, SECEXT-003, SECEXT-005 geometry, layout, relationship, and security-context signals raise classification and deny unapproved external processing before byte access."""
    context, tenant_id, project_id, actor = bootstrapped
    scene, source = _frame_scene_asset(context, tenant_id, project_id, actor)
    context.providers.register(
        _descriptor("restricted-local", allowed_classifications=["restricted"]),
        actor_id=actor,
    )
    _promote(context, "restricted-local", data_classifications=["restricted"])
    request = _request(tenant_id, project_id, scene, source, actor, key="classification-floor")
    request["policy_context"]["spatial_sensitivity"] = [
        "private_residential_layout",
        "liveforever_sensitive_relationships",
    ]
    request["policy_context"]["classification_review_evidence_hash"] = canonical_sha256({
        "review": "private layout and relationship disclosure",
    })
    request["provider_selector"]["preferred_provider_ids"] = ["restricted-local"]  # type: ignore[index]
    admitted = context.hybrid.create_conversion(request, actor_id=actor)
    with context.database.session() as session:
        conversion = session.get(SpatialConversionRow, admitted["conversion_id"])
        assert conversion is not None
        decision = conversion.admission_decision_json
    assert decision["classification"] == "restricted"
    classification_context = decision["classification_context"]
    assert classification_context["external_processing_denied"] is True
    assert {item.get("signal") for item in classification_context["basis"] if item["type"] == "spatial_sensitivity"} == {
        "private_residential_layout",
        "liveforever_sensitive_relationships",
    }

    context.providers.register(
        _descriptor(
            "restricted-external",
            provider_class="external_api",
            external=True,
            allowed_classifications=["restricted"],
            deployment_modes=["managed_cloud"],
        ),
        actor_id=actor,
    )
    _promote(context, "restricted-external", data_classifications=["restricted"])
    external = _request(
        tenant_id, project_id, scene, source, actor, key="classification-external", deployment="managed_cloud", allow_external=True
    )
    external["policy_context"]["spatial_sensitivity"] = ["private_residential_layout"]
    external["provider_selector"]["preferred_provider_ids"] = ["restricted-external"]  # type: ignore[index]
    reads: list[str] = []

    def unexpected_read(digest: str) -> bytes:
        reads.append(digest)
        raise AssertionError("source bytes were read before external-provider admission completed")

    monkeypatch.setattr(context.assets.store, "read_bytes", unexpected_read)
    with pytest.raises(AuthorizationError) as denied:
        context.hybrid.create_conversion(external, actor_id=actor)
    assert denied.value.code == "HYB_SENSITIVE_EXTERNAL_PROCESSING_DENIED"
    assert reads == []

    unknown = _request(tenant_id, project_id, scene, source, actor, key="classification-unknown")
    unknown["policy_context"]["spatial_sensitivity"] = ["operator_assumed_safe"]
    unknown["provider_selector"]["preferred_provider_ids"] = ["restricted-local"]  # type: ignore[index]
    with pytest.raises(AuthorizationError) as unknown_denial:
        context.hybrid.create_conversion(unknown, actor_id=actor)
    assert unknown_denial.value.code == "HYB_SPATIAL_SENSITIVITY_UNKNOWN"
    assert reads == []


@pytest.mark.integration
@pytest.mark.security
def test_provider_training_public_demo_and_retention_require_separate_server_side_authorization(bootstrapped, monkeypatch) -> None:
    """REQ: SECEXT-001, SECEXT-002, SECEXT-008 provider training, public demonstration, and source retention cannot be authorized by the conversion request itself."""
    context, tenant_id, project_id, actor = bootstrapped
    scene, source = _frame_scene_asset(context, tenant_id, project_id, actor)
    reads: list[str] = []

    def unexpected_read(digest: str) -> bytes:
        reads.append(digest)
        raise AssertionError("source bytes were read before secondary-use policy admission completed")

    monkeypatch.setattr(context.assets.store, "read_bytes", unexpected_read)
    for provider_id, governance_patch, expected_code in (
        ("training-purpose-denied", {"training_use": "separate_authorization_required"}, "HYB_PROVIDER_SECONDARY_USE_NOT_AUTHORIZED"),
        ("public-demo-denied", {"public_demonstration": "separate_authorization_required"}, "HYB_PROVIDER_SECONDARY_USE_NOT_AUTHORIZED"),
    ):
        descriptor = _descriptor(provider_id)
        descriptor["data_governance"] = {**descriptor["data_governance"], **governance_patch}
        context.providers.register(descriptor, actor_id=actor)
        _promote(context, provider_id)
        request = _request(tenant_id, project_id, scene, source, actor, key=provider_id)
        request["policy_context"]["approved_secondary_uses"] = ["provider_training", "public_demonstration"]
        request["provider_selector"]["preferred_provider_ids"] = [provider_id]  # type: ignore[index]
        with pytest.raises(AuthorizationError) as denied:
            context.hybrid.create_conversion(request, actor_id=actor)
        assert denied.value.code == expected_code

    retained = _descriptor("retention-denied")
    retained["retention_days"] = 1
    context.providers.register(retained, actor_id=actor)
    _promote(context, "retention-denied")
    retention_request = _request(tenant_id, project_id, scene, source, actor, key="retention-denied")
    retention_request["policy_context"]["maximum_provider_retention_days"] = 365
    retention_request["provider_selector"]["preferred_provider_ids"] = ["retention-denied"]  # type: ignore[index]
    with pytest.raises(AuthorizationError) as retention_denial:
        context.hybrid.create_conversion(retention_request, actor_id=actor)
    assert retention_denial.value.code == "HYB_PROVIDER_RETENTION_NOT_AUTHORIZED"
    assert reads == []


@pytest.mark.integration
@pytest.mark.security
def test_candidate_role_size_validation_and_profile_integrity_fail_closed(bootstrapped) -> None:
    """REQ: ARCHHYB-005, DATHYB-005, RECHYB-005, RECPROV-005, HYBRUN-006 candidate type, byte envelope, validator independence, use-specific actor profile evidence, and safety-claim ceilings are enforced."""
    context, tenant_id, project_id, actor = bootstrapped
    scene, source = _frame_scene_asset(context, tenant_id, project_id, actor)
    context.providers.register(_descriptor("candidate-guard-provider"), actor_id=actor)
    _promote(context, "candidate-guard-provider")

    request = _request(tenant_id, project_id, scene, source, actor, key="candidate-role-guard")
    request["constraints"] = {"maximum_output_multiplier": 0.1, "estimate_profile": "small-output"}
    request["provider_selector"]["preferred_provider_ids"] = ["candidate-guard-provider"]  # type: ignore[index]
    admitted = context.hybrid.create_conversion(request, actor_id=actor)
    output_data = b"oversized proxy output" * 32
    output = context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=output_data,
        media_type="model/gltf-binary",
        original_name="oversized.glb",
        classification=Classification.INTERNAL,
        retention_class="test",
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        provenance=ProvenanceRef(source_ids=[str(admitted["conversion_id"])], output_hash=sha256_bytes(output_data)),
        actor_id=actor,
    )
    base_completion = dict(
        output_asset_id=output.asset_id,
        output_asset_sha256=output.sha256,
        output_role="interaction_proxy",
        coordinate_frame_id=FRAME_ID,
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        lossy=True,
        intended_uses=["picking", "collision"],
        prohibited_uses=["verified_measurement"],
        quality={"provider_claim": "candidate_only"},
        support_map={"metric_resolution_required": True},
        worker_receipt_hash=canonical_sha256({"worker": admitted["conversion_id"]}),
        candidate_core_hash=canonical_sha256({"candidate": output.sha256}),
    )
    with pytest.raises(ValidationError) as role_kind:
        context.hybrid.complete_candidate(str(admitted["worker_token"]), kind=RepresentationKind.VISUAL, **base_completion)
    assert role_kind.value.code == "HYB_OUTPUT_ROLE_KIND_MISMATCH"
    with pytest.raises(AuthorizationError) as oversized:
        context.hybrid.complete_candidate(str(admitted["worker_token"]), kind=RepresentationKind.INTERACTION, **base_completion)
    assert oversized.value.code == "HYB_OUTPUT_BYTE_ENVELOPE_EXCEEDED"

    valid_request = _request(tenant_id, project_id, scene, source, actor, key="candidate-validation-guard")
    valid_request["provider_selector"]["preferred_provider_ids"] = ["candidate-guard-provider"]  # type: ignore[index]
    valid = context.hybrid.create_conversion(valid_request, actor_id=actor)
    completed, _ = _complete(context, valid, tenant_id, project_id, actor)
    representation_id = str(completed["representation_id"])
    _register_profile(context, "picking")
    with pytest.raises(AuthorizationError) as unsafe_profile:
        context.hybrid.register_interaction_profile(
            profile_id="profile-navigation-unverified-safety",
            profile_type="navigation",
            version="1.0.0",
            actor={"shape": "capsule", "radius_m": 0.3, "height_m": 1.8},
            intended_uses=["navigation"],
            limits={"maximum_error_m": 0.02},
            behavior={"fallback": "disable_use"},
            validation={"method": "deterministic-fixture", "passed": True, "validated_safety_claims": []},
            safety_claims=["egress_compliance", "accessibility_compliance", "robotics_safety"],
            validator_id="independent-navigation-profile-validator",
            validator_manifest_hash=canonical_sha256({"validator": "navigation-profile"}),
            validation_evidence_hash=canonical_sha256({"evidence": "navigation-profile"}),
            validated_at=datetime.now(UTC),
            created_by="validation-admin",
        )
    assert unsafe_profile.value.code == "HYB_UNVALIDATED_SAFETY_CLAIM"

    with pytest.raises(AuthorizationError) as self_validation:
        context.hybrid.validate_candidate(
            str(valid["conversion_id"]),
            tenant_id=tenant_id,
            project_id=project_id,
            intended_use="picking",
            profile_id="profile-picking-v1",
            profile_version="1.0.0",
            validator_id=actor,
            validator_manifest_hash=canonical_sha256({"validator": actor}),
            metrics={"error_m": 0.01},
            thresholds={"error_m": {"max": 0.02}},
            coverage={"passed": True},
            topology={"passed": True},
            coordinate_validation={"passed": True},
            behavior_validation={"passed": True},
        )
    assert self_validation.value.code == "HYB_VALIDATOR_NOT_INDEPENDENT"

    failed = context.hybrid.validate_candidate(
        str(valid["conversion_id"]),
        tenant_id=tenant_id,
        project_id=project_id,
        intended_use="picking",
        profile_id="profile-picking-v1",
        profile_version="1.0.0",
        validator_id="independent-failed-validator",
        validator_manifest_hash=canonical_sha256({"validator": "failed"}),
        metrics={"error_m": 0.03},
        thresholds={"error_m": {"max": 0.02}},
        coverage={"passed": True},
        topology={"passed": True},
        coordinate_validation={"passed": True},
        behavior_validation={"passed": True},
    )
    assert failed["passed"] is False
    with context.database.session() as session:
        assert session.get(SpatialConversionRow, valid["conversion_id"]).state == "quality_failed"  # type: ignore[union-attr]
        profile = session.get(InteractionProfileRow, "profile-picking-v1")
        assert profile is not None
        profile.validation_json = {**profile.validation_json, "profile_signature": "0" * 64}
    with pytest.raises(AuthorizationError) as tampered_profile:
        context.hybrid.validate_candidate(
            str(valid["conversion_id"]),
            tenant_id=tenant_id,
            project_id=project_id,
            intended_use="picking",
            profile_id="profile-picking-v1",
            profile_version="1.0.0",
            validator_id="independent-second-validator",
            validator_manifest_hash=canonical_sha256({"validator": "second"}),
            metrics={"error_m": 0.01},
            thresholds={"error_m": {"max": 0.02}},
            coverage={"passed": True},
            topology={"passed": True},
            coordinate_validation={"passed": True},
            behavior_validation={"passed": True},
        )
    assert tampered_profile.value.code == "HYB_INTERACTION_PROFILE_INTEGRITY_INVALID"

@pytest.mark.integration
@pytest.mark.security
def test_retryable_failure_resumes_only_after_verified_cleanup_and_policy_reauthorization(bootstrapped) -> None:
    """REQ: RECPROV-009, HYBAPI-004 retryable work resumes with a new exact token only after verified cleanup and current policy admission."""
    context, tenant_id, project_id, actor = bootstrapped
    scene, source = _frame_scene_asset(context, tenant_id, project_id, actor)
    context.providers.register(_descriptor("resume-provider"), actor_id=actor)
    _promote(context, "resume-provider")
    request = _request(tenant_id, project_id, scene, source, actor, key="retryable-resume")
    request["provider_selector"]["preferred_provider_ids"] = ["resume-provider"]  # type: ignore[index]
    admitted = context.hybrid.create_conversion(request, actor_id=actor, worker_lease_ttl_seconds=120)
    original_token = str(admitted["worker_token"])
    cleanup_hash = canonical_sha256({"cleanup": admitted["conversion_id"], "verified": True})
    failed = context.hybrid.report_provider_failure(
        original_token,
        error_code="TRANSIENT_PROVIDER_FAILURE",
        retryable=True,
        cleanup_receipt_hash=cleanup_hash,
        cleanup_verified=True,
        last_durable_checkpoint_hash=canonical_sha256({"checkpoint": "resume-safe"}),
        resource_use={"peak_memory_bytes": 2048},
    )
    assert failed["state"] == "failed_retryable"

    renewed = context.hybrid.renew_worker_lease(original_token, lease_ttl_seconds=60)
    assert renewed["resumed_retryable_failure"] is True
    assert renewed["worker_lease_generation"] == 2
    resumed_token = str(renewed["worker_token"])
    with context.database.session() as session:
        row = session.get(SpatialConversionRow, admitted["conversion_id"])
        assert row is not None
        assert row.state == "admitted"
        assert row.failure_hash == failed["failure_hash"]
        assert row.cleanup_receipt_hash == cleanup_hash
        assert row.worker_token_hash == sha256_bytes(resumed_token.encode("utf-8"))
        assert row.worker_lease_generation == 2

    with pytest.raises(AuthenticationError) as superseded:
        context.hybrid.record_progress(original_token, {
            "conversion_id": admitted["conversion_id"],
            "sequence": 1,
            "stage": "stale-resume-token",
            "completed_work_units": 1,
            "total_work_units": 2,
            "work_unit_name": "frames",
            "resource_use": {},
            "warnings": [],
        })
    assert superseded.value.code in {"HYB_WORKER_CREDENTIAL_SUPERSEDED", "HYB_WORKER_TOKEN_SUPERSEDED"}

    resumed_progress = context.hybrid.record_progress(resumed_token, {
        "conversion_id": admitted["conversion_id"],
        "sequence": 1,
        "stage": "resumed-from-checkpoint",
        "completed_work_units": 1,
        "total_work_units": 2,
        "work_unit_name": "frames",
        "resource_use": {"cpu_seconds": 0.2},
        "warnings": [],
        "last_durable_checkpoint_hash": canonical_sha256({"checkpoint": "resumed-1"}),
    })
    assert resumed_progress["sequence"] == 1
    assert context.operations.get(str(admitted["operation_id"]))["state"] == "running"


@pytest.mark.integration
@pytest.mark.security
def test_worker_renewal_fails_when_admitted_provider_revision_is_no_longer_current(bootstrapped) -> None:
    """REQ: RECPROV-004 provider/model governance is re-evaluated when a worker lease rotates."""
    context, tenant_id, project_id, actor = bootstrapped
    scene, source = _frame_scene_asset(context, tenant_id, project_id, actor)
    context.providers.register(_descriptor("renewal-stale-provider"), actor_id=actor)
    _promote(context, "renewal-stale-provider")
    request = _request(tenant_id, project_id, scene, source, actor, key="renewal-stale")
    request["provider_selector"]["preferred_provider_ids"] = ["renewal-stale-provider"]  # type: ignore[index]
    admitted = context.hybrid.create_conversion(request, actor_id=actor)

    context.providers.register(_descriptor("renewal-stale-provider", version="1.0.1"), actor_id=actor)
    with pytest.raises(AuthorizationError) as stale:
        context.hybrid.renew_worker_lease(str(admitted["worker_token"]), lease_ttl_seconds=60)
    assert stale.value.code == "HYB_PROVIDER_SNAPSHOT_STALE"

    with context.database.session() as session:
        row = session.get(SpatialConversionRow, admitted["conversion_id"])
        assert row is not None
        assert row.worker_lease_generation == 1
        assert row.state == "admitted"


@pytest.mark.integration
@pytest.mark.security
def test_arcres_005_provider_region_failure_never_moves_data_to_unapproved_region(bootstrapped, monkeypatch) -> None:
    """REQ: ARCRES-005 provider-region failure is fail-closed and never reads or moves source bytes to an unapproved region."""
    context, tenant_id, project_id, actor = bootstrapped
    scene, source = _frame_scene_asset(context, tenant_id, project_id, actor, data=b"region-bound-source" * 32)
    context.providers.register(
        _descriptor(
            "region-bound-external",
            provider_class="external_api",
            external=True,
            deployment_modes=["managed_cloud"],
        ),
        actor_id=actor,
    )
    _promote(context, "region-bound-external", execution_zones=["local-cpu"])
    request = _request(
        tenant_id,
        project_id,
        scene,
        source,
        actor,
        key="unapproved-region",
        deployment="managed_cloud",
        allow_external=True,
    )
    request["policy_context"]["region"] = "unapproved-region"  # type: ignore[index]
    request["provider_selector"]["preferred_provider_ids"] = ["region-bound-external"]  # type: ignore[index]
    reads: list[str] = []

    def unexpected_read(digest: str) -> bytes:
        reads.append(digest)
        raise AssertionError("source bytes were read before region admission completed")

    monkeypatch.setattr(context.assets.store, "read_bytes", unexpected_read)
    with pytest.raises(AuthorizationError) as denied:
        context.hybrid.create_conversion(request, actor_id=actor)
    assert denied.value.code in {"HYB_PROVIDER_NO_ELIGIBLE_MATCH", "HYB_PROVIDER_PROCESSING_REGION_DENIED"}
    assert reads == []
