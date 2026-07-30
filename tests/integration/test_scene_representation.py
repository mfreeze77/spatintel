from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from sip.database import RepresentationAssetRow
from sip.errors import AuthorizationError, ConflictError, ValidationError
from sip.models import Audience, AuthorityClass, Classification, ProvenanceRef, RepresentationKind, SourceClass
from sip.scene import ProxyHit


@pytest.mark.integration
def test_datgit_datscene_stable_entities_commits_diff_and_rollback(bootstrapped) -> None:
    """REQ: DATSCENE-001, DATGIT-005, DATHYB-006 stable entities survive commit/diff/rollback without primitive-local identity."""
    context, tenant_id, project_id, actor = bootstrapped
    context.spatial_data.register_frame(
        tenant_id=tenant_id,
        project_id=project_id,
        name="World",
        convention="right_handed_y_up_meters",
        units="meter",
        original_units="meter",
        axis_convention="+X right, +Y up, -Z forward",
        axis_directions={"x": "+X right", "y": "+Y up", "z": "-Z forward"},
        handedness="right",
        origin_description="synthetic stable entity origin",
        source="synthetic_fixture",
        actor_id=actor,
        frame_id="world",
    )
    scene = context.scene.create_scene(tenant_id, project_id, name="Room", actor_id=actor)
    entity_id = context.scene.create_entity(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        entity_type="room",
        name="Mechanical Room",
        attributes={"number": "M101"},
        source_class=SourceClass.OBSERVED,
        authority_class=AuthorityClass.EVIDENCE,
        confidence=1.0,
        provenance=ProvenanceRef(source_ids=["capture:fixture"]),
        policy={"audience": "project"},
        stable_support={"frame_id": "world", "point": [0, 0, 0]},
        actor_id=actor,
    )
    first = context.scene.commit(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        branch="main",
        expected_head=scene["commit_id"],
        message="Add room",
        actor_id=actor,
    )
    assert entity_id in context.scene.diff(scene["commit_id"], first["commit_id"])["entities"]["added"]
    rolled = context.scene.rollback_branch(tenant_id, project_id, scene["scene_id"], "main", scene["commit_id"], actor_id=actor)
    assert rolled["snapshot_hash"]
    with pytest.raises(Exception) as missing_project:
        context.scene.create_scene(tenant_id, "project-missing", name="Invalid", actor_id=actor)
    assert getattr(missing_project.value, "code", None) == "NOT_FOUND"
    with pytest.raises(Exception) as missing_frame:
        context.scene.create_entity(
            tenant_id=tenant_id,
            project_id=project_id,
            scene_id=scene["scene_id"],
            entity_type="object",
            name="Missing frame anchor",
            attributes={},
            source_class=SourceClass.OBSERVED,
            authority_class=AuthorityClass.EVIDENCE,
            confidence=1,
            provenance=ProvenanceRef(source_ids=["fixture"]),
            policy={},
            stable_support={"frame_id": "missing-frame", "point": [0, 0, 0]},
            actor_id=actor,
        )
    assert getattr(missing_frame.value, "code", None) == "NOT_FOUND"
    with pytest.raises(ValidationError):
        context.scene.create_entity(
            tenant_id=tenant_id,
            project_id=project_id,
            scene_id=scene["scene_id"],
            entity_type="object",
            name="Bad anchor",
            attributes={},
            source_class=SourceClass.OBSERVED,
            authority_class=AuthorityClass.EVIDENCE,
            confidence=1,
            provenance=ProvenanceRef(source_ids=["fixture"]),
            policy={},
            stable_support={"triangle_id": 5},
            actor_id=actor,
        )


@pytest.mark.integration
@pytest.mark.security
def test_hybrid_provider_quarantine_quality_publisher_and_proxy_measurement_guard(bootstrapped) -> None:
    """REQ: DATHYB-001, DATHYB-005, HYBRUN-003, HYBRUN-004, HYBRUN-007, OPSTHR-009, OPSTHR-010, RECHYB-002, RECHYB-005 candidate/publication separation, typed proxy hits, metric re-resolution, and verified-measurement authority fail closed."""
    context, tenant_id, project_id, actor = bootstrapped
    context.spatial_data.register_frame(
        tenant_id=tenant_id,
        project_id=project_id,
        name="World",
        convention="right_handed_y_up_meters",
        units="meter",
        original_units="meter",
        axis_convention="+X right, +Y up, -Z forward",
        axis_directions={"x": "+X right", "y": "+Y up", "z": "-Z forward"},
        handedness="right",
        origin_description="synthetic hybrid origin",
        source="synthetic_fixture",
        actor_id=actor,
        frame_id="world",
    )
    source_asset = context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=b"synthetic measurement source",
        media_type="application/octet-stream",
        original_name="measurement-source.bin",
        classification=Classification.INTERNAL,
        retention_class="test",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["synthetic-fixture"]),
        actor_id=actor,
    )
    proxy_asset = context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=b"synthetic disposable interaction proxy",
        media_type="model/gltf-binary",
        original_name="interaction-proxy.glb",
        classification=Classification.INTERNAL,
        retention_class="test",
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        provenance=ProvenanceRef(source_ids=[source_asset.asset_id]),
        actor_id=actor,
    )
    for provider_id in ("local-tsdf", "local-baseline"):
        context.providers.register(
            {
                "provider_id": provider_id,
                "version": "1.1.0",
                "source_url": f"local://sip/{provider_id}",
                "source_revision": "deterministic-reference",
                "license_id": "Apache-2.0",
                "approval_state": "approved",
                "allowed_classifications": ["internal"],
                "allowed_purposes": ["hybrid_fixture"],
                "allowed_regions": ["local"],
            },
            actor_id=actor,
        )
    scene = context.scene.create_scene(tenant_id, project_id, name="Hybrid room", actor_id=actor)
    metric = context.representations.create_candidate(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        asset_id=source_asset.asset_id,
        kind=RepresentationKind.METRIC,
        provider_id="local-tsdf",
        coordinate_frame_id="world",
        source_class=SourceClass.MEASURED,
        authority_class=AuthorityClass.METRIC,
        lossy=False,
        intended_uses=["measurement", "render"],
        prohibited_uses=[],
        quality={"rmse_m": 0.005},
        provenance={"source_ids": [source_asset.asset_id]},
        support_map={},
        actor_id=actor,
    )
    context.representations.review_quality(metric, reviewer_id="geometry-reviewer", approved_uses=["measurement", "render"], metrics={"rmse_m": 0.005}, passed=True)
    context.publisher.publish(metric, commit_id=scene["commit_id"], role="measurement", publisher_id="publisher")
    with pytest.raises(ValidationError) as legacy_error:
        context.representations.create_candidate(
            tenant_id=tenant_id,
            project_id=project_id,
            scene_id=scene["scene_id"],
            asset_id="asset-invalid-proxy",
            kind=RepresentationKind.INTERACTION,
            provider_id="local-baseline",
            coordinate_frame_id="world",
            source_class=SourceClass.GENERATED,
            authority_class="interaction",  # type: ignore[arg-type]
            lossy=True,
            intended_uses=["picking"],
            prohibited_uses=["verified_measurement"],
            quality={},
            provenance={"source_ids": [metric]},
            support_map={},
            actor_id=actor,
        )
    assert legacy_error.value.code == "INTERACTION_AUTHORITY_INVALID"

    proxy = context.representations.create_candidate(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        asset_id=proxy_asset.asset_id,
        kind=RepresentationKind.INTERACTION,
        provider_id="local-baseline",
        coordinate_frame_id="world",
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        lossy=True,
        intended_uses=["picking", "collision", "navigation"],
        prohibited_uses=["verified_measurement"],
        quality={"collision_coverage": 1.0},
        provenance={"source_ids": [metric]},
        support_map={"metric_representation_id": metric, "max_reprojection_error_m": 0.01, "anchors": []},
        actor_id=actor,
    )
    with context.database.session() as session:
        proxy_row = session.get(RepresentationAssetRow, proxy)
        assert proxy_row is not None
        assert proxy_row.authority_class == "derived_non_authoritative"
        assert proxy_row.authority_ceiling == "derived_non_authoritative"
        assert proxy_row.disposable is True
    with pytest.raises(ConflictError):
        context.publisher.publish(proxy, commit_id=scene["commit_id"], role="picking", publisher_id="publisher")
    context.representations.review_quality(proxy, reviewer_id="interaction-reviewer", approved_uses=["picking", "collision"], metrics={"raycast_p95_ms": 2}, passed=True)
    context.publisher.publish(proxy, commit_id=scene["commit_id"], role="picking", publisher_id="publisher")
    resolved = context.scene.resolve_proxy_hit(
        tenant_id,
        project_id,
        ProxyHit(representation_id=proxy, world_point=[1, 1, 1], normal=[0, 1, 0], support_hint={}),
    )
    assert resolved["authoritative_measurement_allowed"] is True
    measured_candidate = context.scene.create_measurement(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        entity_id=None,
        value=1.0,
        unit="m",
        uncertainty=0.01,
        source_asset_ids=resolved["metric_source_asset_ids"],
        calibration={"resolution": "support_map_metric_reprojection"},
        verifier_id=None,
        verified=False,
        actor_id=actor,
        originating_representation_id=proxy,
        interaction_hit=resolved["interaction_hit"],
        geometry={"type": "segment", "start": [0.0, 0.0, 0.0], "end": [1.0, 0.0, 0.0]},
        coordinate_frame_id="world",
        permitted_uses=["reference", "facility_operations"],
    )
    measured_record = context.scene.get_measurement(tenant_id, project_id, scene["scene_id"], measured_candidate)
    assert measured_record["interaction_hit"]["representation_id"] == proxy
    assert measured_record["resolved_metric_evidence"]["metric_representation_id"] == metric
    assert measured_record["resolved_metric_evidence"]["estimated_residual_m"] == 0.01
    assert measured_record["verification_status"] == "measured"
    assert measured_record["authority_class"] == "metric"
    with pytest.raises(ValidationError) as error:
        context.scene.create_measurement(
            tenant_id=tenant_id,
            project_id=project_id,
            scene_id=scene["scene_id"],
            entity_id=None,
            value=1.0,
            unit="m",
            uncertainty=0.01,
            source_asset_ids=[source_asset.asset_id],
            calibration={"method": "fixture"},
            verifier_id="verifier",
            verified=True,
            actor_id=actor,
            originating_representation_id=proxy,
            geometry={"type": "segment", "start": [0.0, 0.0, 0.0], "end": [1.0, 0.0, 0.0]},
            coordinate_frame_id="world",
        )
    assert error.value.code == "PROXY_MEASUREMENT_CANNOT_BE_VERIFIED"


@pytest.mark.integration
@pytest.mark.privacy
def test_representation_publication_rechecks_inherited_policy_and_consent(bootstrapped) -> None:
    """REQ: DATHYB-012, LFC CONSENT derivatives cannot publish with unresolved, widened, or revoked policy."""
    context, tenant_id, project_id, actor = bootstrapped
    context.spatial_data.register_frame(
        tenant_id=tenant_id,
        project_id=project_id,
        name="Policy world",
        convention="right_handed_y_up_meters",
        units="meter",
        original_units="meter",
        axis_convention="+X right, +Y up, -Z forward",
        axis_directions={"x": "+X right", "y": "+Y up", "z": "-Z forward"},
        handedness="right",
        origin_description="publication policy fixture",
        source="synthetic_fixture",
        actor_id=actor,
        frame_id="policy-world",
    )
    context.providers.register(
        {
            "provider_id": "policy-provider",
            "version": "1.0.0",
            "source_url": "local://policy-provider",
            "source_revision": "fixture",
            "license_id": "Apache-2.0",
            "approval_state": "approved",
            "allowed_classifications": ["internal"],
            "allowed_purposes": ["display_visual"],
            "allowed_regions": ["local"],
        },
        actor_id=actor,
    )
    source = context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=b"policy source",
        media_type="application/octet-stream",
        original_name="policy-source.bin",
        classification=Classification.INTERNAL,
        retention_class="test",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["synthetic-fixture"]),
        actor_id=actor,
    )
    output = context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=b"policy visual output",
        media_type="model/gltf-binary",
        original_name="policy-output.glb",
        classification=Classification.INTERNAL,
        retention_class="test",
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.VISUAL,
        provenance=ProvenanceRef(source_ids=[source.asset_id]),
        actor_id=actor,
    )
    scene = context.scene.create_scene(tenant_id, project_id, name="Policy scene", actor_id=actor)

    unresolved = context.representations.create_candidate(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        asset_id=output.asset_id,
        kind=RepresentationKind.VISUAL,
        provider_id="policy-provider",
        coordinate_frame_id="policy-world",
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.VISUAL,
        lossy=False,
        intended_uses=["display_visual"],
        prohibited_uses=[],
        quality={},
        provenance={"source_ids": ["unresolved-source-id"]},
        support_map={},
        format_metadata={"format": "glb"},
        actor_id=actor,
    )
    context.representations.review_quality(
        unresolved,
        reviewer_id="policy-reviewer",
        approved_uses=["display_visual"],
        metrics={"schema_valid": True},
        passed=True,
    )
    with pytest.raises(AuthorizationError) as blocked:
        context.publisher.publish(
            unresolved,
            commit_id=scene["commit_id"],
            role="display_visual",
            publisher_id="publisher",
        )
    assert blocked.value.code == "REPRESENTATION_POLICY_BLOCKED"

    grant_id = context.liveforever.grant_consent(
        tenant_id=tenant_id,
        project_id=project_id,
        subject_id="policy-subject",
        granted_by=actor,
        purposes=["display_visual"],
        audiences=[Audience.PROJECT],
        scopes=["representation:publish"],
        derivative_policy={"propagate_revocation": True},
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    governed = context.representations.create_candidate(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        asset_id=output.asset_id,
        kind=RepresentationKind.VISUAL,
        provider_id="policy-provider",
        coordinate_frame_id="policy-world",
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.VISUAL,
        lossy=False,
        intended_uses=["display_visual"],
        prohibited_uses=[],
        quality={},
        provenance={"source_ids": [source.asset_id]},
        support_map={},
        format_metadata={"format": "glb"},
        privacy_inheritance={
            "consent_grant_ids": [grant_id],
            "allowed_audiences": ["project"],
            "allowed_purposes": ["display_visual"],
            "required_scopes": ["representation:publish"],
        },
        actor_id=actor,
    )
    context.representations.review_quality(
        governed,
        reviewer_id="policy-reviewer",
        approved_uses=["display_visual"],
        metrics={"schema_valid": True},
        passed=True,
    )
    with pytest.raises(AuthorizationError) as widened:
        context.publisher.publish(
            governed,
            commit_id=scene["commit_id"],
            role="display_visual",
            audience_policy={"allowed_audiences": ["private"], "purpose": "display_visual"},
            publisher_id="publisher",
        )
    assert widened.value.code == "REPRESENTATION_AUDIENCE_WIDENING_DENIED"

    context.liveforever.revoke_consent(grant_id, tenant_id=tenant_id, project_id=project_id, actor_id=actor, reason="publication policy fixture")
    with pytest.raises(AuthorizationError) as revoked:
        context.publisher.publish(
            governed,
            commit_id=scene["commit_id"],
            role="display_visual",
            audience_policy={"allowed_audiences": ["project"], "purpose": "display_visual"},
            publisher_id="publisher",
        )
    assert revoked.value.code == "REPRESENTATION_CONSENT_INVALID"
