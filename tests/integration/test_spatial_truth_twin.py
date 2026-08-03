from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select

from sip.canonical import canonical_sha256, new_uuid, sha256_bytes
from sip.database import (
    AssetRefRow,
    AuditEventRow,
    AssertionRow,
    DerivationEventRow,
    GeometryAssetManifestRow,
    MeasurementRow,
    OutboxEventRow,
    RepresentationAssetRow,
    RepresentationBindingRow,
    SceneBranchRow,
    SceneCommitRow,
    SpatialAnnotationRow,
    SpatialTransformRow,
)
from sip.errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from sip.models import Audience, AuthorityClass, Classification, ProvenanceRef, RepresentationKind, SignedPrincipal, SourceClass
from sip.temporal import db_now


def _ingest(context, tenant_id: str, project_id: str, actor: str, payload: bytes, name: str):
    return context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=payload,
        media_type="application/octet-stream",
        original_name=name,
        classification=Classification.INTERNAL,
        retention_class="preservation",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(
            source_ids=[f"synthetic-fixture:{name}"],
            output_hash=sha256_bytes(payload),
            validation_result_id=f"fixture-validation:{name}",
        ),
        actor_id=actor,
    )


def _frame(context, tenant_id: str, project_id: str, actor: str, frame_id: str, **overrides):
    body = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "name": frame_id,
        "convention": "right_handed_y_up_meters",
        "units": "meter",
        "original_units": "meter",
        "axis_convention": "+X right, +Y up, -Z forward",
        "axis_directions": {"x": "+X right", "y": "+Y up", "z": "-Z forward"},
        "handedness": "right",
        "origin_description": "synthetic controlled origin",
        "source": "synthetic_fixture",
        "actor_id": actor,
        "frame_id": frame_id,
    }
    body.update(overrides)
    return context.spatial_data.register_frame(**body)


def _provider(context, actor: str, provider_id: str) -> None:
    context.providers.register(
        {
            "provider_id": provider_id,
            "version": "1.0.0",
            "source_url": f"local://{provider_id}",
            "source_revision": "deterministic-fixture",
            "license_id": "Apache-2.0",
            "approval_state": "approved",
            "allowed_classifications": ["internal"],
            "allowed_purposes": ["spatial-truth-test"],
            "allowed_regions": ["local"],
        },
        actor_id=actor,
    )


def _approved_model_manifest(*, model_id: str, actor: str, checkpoint_hash: str) -> dict:
    reviewed_at = datetime.now(UTC) - timedelta(days=1)
    return {
        "schema": "sip.model-manifest/v1.2",
        "schema_version": "1.2.0",
        "model_id": model_id,
        "provider": "sip.synthetic",
        "model_name": "deterministic-lineage-fixture",
        "version": "1.0.0",
        "revision": "fixture-revision-1",
        "checkpoint_hash": checkpoint_hash,
        "source_urls": [f"local://models/{model_id}"],
        "license_documents": [
            {
                "component": component,
                "title": f"Synthetic {component} license evidence",
                "license_id": "Apache-2.0",
                "source_url": f"local://licenses/{model_id}/{component}",
                "document_sha256": canonical_sha256({"model_id": model_id, "component": component}),
                "review_state": "verified",
            }
            for component in ("code", "weights", "dataset", "output")
        ],
        "code_revision": "fixture-code-revision-1",
        "code_license": "Apache-2.0",
        "weights_license": "Apache-2.0",
        "dataset_terms": ["synthetic_fixture_only"],
        "output_terms": "Apache-2.0",
        "approval_state": "approved",
        "usage_scope": "local_internal",
        "allowed_classifications": ["internal"],
        "permitted_uses": ["spatial-truth-test"],
        "prohibited_uses": ["biometric_identification"],
        "geographic_restrictions": {"mode": "allowlist", "values": ["local"]},
        "customer_restrictions": {"mode": "unrestricted", "values": []},
        "allowed_deployments": ["test"],
        "approved_by": actor,
        "reviewed_at": reviewed_at,
        "review_due_at": reviewed_at + timedelta(days=365),
        "expires_at": reviewed_at + timedelta(days=365),
    }


@pytest.mark.integration
def test_datframe_known_basis_round_trip_temporal_transform_and_supersession(bootstrapped) -> None:
    """REQ: DATFRAME-001, DATFRAME-002, DATFRAME-003, DATFRAME-004 explicit frames and transforms pass known-basis and round-trip checks."""
    context, tenant_id, project_id, actor = bootstrapped
    _frame(context, tenant_id, project_id, actor, "frame-building")
    _frame(
        context,
        tenant_id,
        project_id,
        actor,
        "frame-device",
        parent_frame_id="frame-building",
        transform_to_parent=[
            [1.0, 0.0, 0.0, 1.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        uncertainty_m=0.002,
    )
    _frame(context, tenant_id, project_id, actor, "frame-survey")

    first = context.spatial_data.register_transform(
        tenant_id=tenant_id,
        project_id=project_id,
        actor_id=actor,
        source_frame_id="frame-building",
        target_frame_id="frame-survey",
        transform_type="SE3",
        matrix=[
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 2.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        covariance=np.diag([0.0001] * 6).tolist(),
        residual_summary={"rmse_m": 0.004, "inlier_fraction": 1.0},
        uncertainty={"rmse_m": 0.004, "covariance_basis": "se3_tangent"},
        source_type="control",
        authority_class=AuthorityClass.FIELD_VERIFIED,
        calibration_id="cal-synthetic-001",
    )
    forward = context.spatial_data.resolve_transform(tenant_id, project_id, "frame-device", "frame-survey")
    inverse = context.spatial_data.resolve_transform(tenant_id, project_id, "frame-survey", "frame-device")
    basis_origin = np.asarray([0.0, 0.0, 0.0, 1.0])
    forward_matrix = np.asarray(forward["matrix"])
    inverse_matrix = np.asarray(inverse["matrix"])
    transformed_origin = forward_matrix @ basis_origin
    assert np.allclose(transformed_origin, [1.0, 2.0, 0.0, 1.0])
    for basis, expected_endpoint, expected_direction in [
        ([1.0, 0.0, 0.0, 1.0], [2.0, 2.0, 0.0, 1.0], [1.0, 0.0, 0.0]),
        ([0.0, 1.0, 0.0, 1.0], [1.0, 3.0, 0.0, 1.0], [0.0, 1.0, 0.0]),
        ([0.0, 0.0, 1.0, 1.0], [1.0, 2.0, 1.0, 1.0], [0.0, 0.0, 1.0]),
    ]:
        transformed_endpoint = forward_matrix @ np.asarray(basis)
        assert np.allclose(transformed_endpoint, expected_endpoint)
        assert np.allclose(transformed_endpoint[:3] - transformed_origin[:3], expected_direction)
        assert np.allclose(inverse_matrix @ transformed_endpoint, basis)
    camera_ray_endpoint = forward_matrix @ np.asarray([0.0, 0.0, -1.0, 1.0])
    assert np.allclose(camera_ray_endpoint, [1.0, 2.0, -1.0, 1.0])
    assert np.allclose(camera_ray_endpoint[:3] - transformed_origin[:3], [0.0, 0.0, -1.0])
    assert np.allclose(inverse_matrix @ camera_ray_endpoint, [0.0, 0.0, -1.0, 1.0])
    assert forward["transform_ids"] == ["frame:frame-device", first["transform_id"]]
    assert forward["uncertainty_m"] > 0.0

    with pytest.raises(ConflictError) as conflict:
        context.spatial_data.register_transform(
            tenant_id=tenant_id,
            project_id=project_id,
            actor_id=actor,
            source_frame_id="frame-building",
            target_frame_id="frame-survey",
            transform_type="SE3",
            matrix=np.eye(4).tolist(),
            uncertainty={"status": "not_quantified"},
            source_type="registration",
            authority_class=AuthorityClass.METRIC,
        )

    assert conflict.value.code == "TRANSFORM_ACTIVE_CONFLICT"

    replacement = context.spatial_data.register_transform(
        tenant_id=tenant_id,
        project_id=project_id,
        actor_id=actor,
        source_frame_id="frame-building",
        target_frame_id="frame-survey",
        transform_type="SE3",
        matrix=[
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 2.01],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        source_type="control",
        authority_class=AuthorityClass.FIELD_VERIFIED,
        uncertainty={"rmse_m": 0.006},
        supersedes_transform_id=first["transform_id"],
    )
    with context.database.session() as session:
        old = session.get(SpatialTransformRow, first["transform_id"])
        new = session.get(SpatialTransformRow, replacement["transform_id"])
        assert old is not None and old.deprecated_at is not None
        assert new is not None
        old_created_at = old.created_at
        old_deprecated_at = old.deprecated_at
    assert replacement["supersedes_transform_id"] == first["transform_id"]

    # Historical resolution must select the transform that was authoritative at
    # the requested instant rather than the currently active replacement.
    historical_time = old_created_at + (old_deprecated_at - old_created_at) / 2
    historical = context.spatial_data.resolve_transform(
        tenant_id, project_id, "frame-building", "frame-survey", at_time=historical_time
    )
    current = context.spatial_data.resolve_transform(tenant_id, project_id, "frame-building", "frame-survey")
    assert historical["transform_ids"] == [first["transform_id"]]
    assert current["transform_ids"] == [replacement["transform_id"]]
    assert np.allclose(np.asarray(historical["matrix"])[:3, 3], [0.0, 2.0, 0.0])
    assert np.allclose(np.asarray(current["matrix"])[:3, 3], [0.0, 2.01, 0.0])

    with pytest.raises(PydanticValidationError):
        context.spatial_data.register_transform(
            tenant_id=tenant_id,
            project_id=project_id,
            actor_id=actor,
            source_frame_id="frame-device",
            target_frame_id="frame-survey",
            transform_type="SE3",
            matrix=np.eye(4).tolist(),
            scale=1.1,
            uncertainty={"status": "not_quantified"},
            source_type="registration",
            authority_class=AuthorityClass.METRIC,
        )


@pytest.mark.integration
def test_datframe_transform_adapter_conventions_scale_units_and_uncertainty(bootstrapped) -> None:
    """REQ: DATFRAME-002, DATFRAME-003 adapters normalize declared matrix conventions without hidden assumptions."""
    context, tenant_id, project_id, actor = bootstrapped
    for frame_id in (
        "frame-row-source",
        "frame-row-target",
        "frame-column-source",
        "frame-column-target",
        "frame-direction-source",
        "frame-direction-target",
        "frame-sim-source",
        "frame-sim-target",
        "frame-unknown-source",
        "frame-unknown-target",
        "frame-invalid-source",
        "frame-invalid-target",
    ):
        _frame(context, tenant_id, project_id, actor, frame_id)

    canonical = np.asarray(
        [
            [0.0, -1.0, 0.0, 1.0],
            [1.0, 0.0, 0.0, 2.0],
            [0.0, 0.0, 1.0, 3.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    basis = np.asarray([1.0, 0.0, -1.0, 1.0])
    expected = canonical @ basis

    row_vector = context.spatial_data.register_transform(
        tenant_id=tenant_id,
        project_id=project_id,
        actor_id=actor,
        source_frame_id="frame-row-source",
        target_frame_id="frame-row-target",
        transform_type="SE3",
        matrix=canonical.T.tolist(),
        matrix_layout="row_major",
        multiplication_convention="row_vector_post_multiply",
        uncertainty={"translation_sigma_m": 0.01},
        source_type="import",
        authority_class=AuthorityClass.METRIC,
    )
    assert np.allclose(row_vector["canonical_matrix"], canonical)
    row_resolved = context.spatial_data.resolve_transform(
        tenant_id, project_id, "frame-row-source", "frame-row-target"
    )
    assert np.allclose(np.asarray(row_resolved["matrix"]) @ basis, expected)
    assert row_resolved["uncertainty_complete"] is True
    assert row_resolved["uncertainty_m"] == pytest.approx(0.01)

    column_major = context.spatial_data.register_transform(
        tenant_id=tenant_id,
        project_id=project_id,
        actor_id=actor,
        source_frame_id="frame-column-source",
        target_frame_id="frame-column-target",
        transform_type="SE3",
        matrix=canonical.T.tolist(),
        matrix_layout="column_major",
        multiplication_convention="column_vector_pre_multiply",
        uncertainty={"rmse_m": 0.02},
        source_type="import",
        authority_class=AuthorityClass.METRIC,
    )
    assert np.allclose(column_major["canonical_matrix"], canonical)
    column_inverse = context.spatial_data.resolve_transform(
        tenant_id, project_id, "frame-column-target", "frame-column-source"
    )
    assert np.allclose(np.asarray(column_inverse["matrix"]) @ expected, basis)

    # The declaration is target-from-source in millimetres but arrives in the
    # reverse direction. Canonical storage must be source-to-target in metres.
    reverse_mm = np.eye(4, dtype=np.float64)
    reverse_mm[:3, 3] = [-1000.0, -2000.0, -3000.0]
    direction = context.spatial_data.register_transform(
        tenant_id=tenant_id,
        project_id=project_id,
        actor_id=actor,
        source_frame_id="frame-direction-source",
        target_frame_id="frame-direction-target",
        transform_type="SE3",
        matrix=reverse_mm.tolist(),
        direction="target_to_source",
        translation_units="millimeter",
        uncertainty={"status": "not_quantified"},
        source_type="import",
        authority_class=AuthorityClass.METRIC,
    )
    assert np.allclose(np.asarray(direction["canonical_matrix"])[:3, 3], [1.0, 2.0, 3.0])
    direction_resolved = context.spatial_data.resolve_transform(
        tenant_id, project_id, "frame-direction-source", "frame-direction-target"
    )
    assert direction_resolved["uncertainty_complete"] is False
    assert direction_resolved["uncertainty_m"] is None
    assert direction_resolved["unquantified_transform_ids"] == [direction["transform_id"]]

    sim = context.spatial_data.register_transform(
        tenant_id=tenant_id,
        project_id=project_id,
        actor_id=actor,
        source_frame_id="frame-sim-source",
        target_frame_id="frame-sim-target",
        transform_type="SIM3",
        matrix=[
            [1.0, 0.0, 0.0, 0.5],
            [0.0, 1.0, 0.0, -0.5],
            [0.0, 0.0, 1.0, 1.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        scale=2.0,
        uncertainty={"sigma_m": 0.03},
        source_type="registration",
        authority_class=AuthorityClass.METRIC,
    )
    sim_matrix = np.asarray(sim["canonical_matrix"])
    assert np.allclose(sim_matrix[:3, :3], np.eye(3) * 2.0)
    assert np.allclose(sim_matrix @ np.asarray([1.0, 1.0, 1.0, 1.0]), [2.5, 1.5, 3.0, 1.0])

    unknown = context.spatial_data.register_transform(
        tenant_id=tenant_id,
        project_id=project_id,
        actor_id=actor,
        source_frame_id="frame-unknown-source",
        target_frame_id="frame-unknown-target",
        transform_type="SE3",
        matrix=np.eye(4).tolist(),
        uncertainty={"status": "not_quantified"},
        source_type="manual",
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
    )
    unknown_resolved = context.spatial_data.resolve_transform(
        tenant_id, project_id, "frame-unknown-source", "frame-unknown-target"
    )
    assert unknown_resolved["transform_ids"] == [unknown["transform_id"]]
    assert unknown_resolved["uncertainty_complete"] is False
    assert unknown_resolved["uncertainty_m"] is None

    shear = np.eye(4)
    shear[0, 1] = 0.1
    with pytest.raises(ValidationError, match="proper orthonormal rotation"):
        context.spatial_data.register_transform(
            tenant_id=tenant_id,
            project_id=project_id,
            actor_id=actor,
            source_frame_id="frame-invalid-source",
            target_frame_id="frame-invalid-target",
            transform_type="SE3",
            matrix=shear.tolist(),
            uncertainty={"status": "not_quantified"},
            source_type="manual",
            authority_class=AuthorityClass.METRIC,
        )

    reflection = np.eye(4)
    reflection[0, 0] = -1.0
    with pytest.raises(ValidationError, match="proper orthonormal rotation"):
        context.spatial_data.register_transform(
            tenant_id=tenant_id,
            project_id=project_id,
            actor_id=actor,
            source_frame_id="frame-invalid-source",
            target_frame_id="frame-invalid-target",
            transform_type="SE3",
            matrix=reflection.tolist(),
            uncertainty={"status": "not_quantified"},
            source_type="manual",
            authority_class=AuthorityClass.METRIC,
        )


@pytest.mark.integration
def test_datframe_geospatial_pipeline_and_viewer_unit_conversion_are_explicit_and_non_mutating(bootstrapped) -> None:
    """REQ: DATFRAME-004, DATFRAME-005, DATFRAME-006 unit/view conversions retain source declarations and geodetic lineage."""
    context, tenant_id, project_id, actor = bootstrapped
    _frame(
        context,
        tenant_id,
        project_id,
        actor,
        "frame-local-mm",
        original_units="millimeter",
        original_unit_scale_to_meters=0.001,
    )
    _frame(
        context,
        tenant_id,
        project_id,
        actor,
        "frame-geodetic-a",
        semantic_type="geodetic",
        convention="source_native",
        crs_identifier="EPSG:26915",
        vertical_datum="NAVD88",
        geodetic={"horizontal_crs": "EPSG:26915", "vertical_datum": "NAVD88"},
    )
    _frame(
        context,
        tenant_id,
        project_id,
        actor,
        "frame-geodetic-b",
        semantic_type="geodetic",
        convention="source_native",
        crs_identifier="EPSG:4978",
        vertical_datum="ellipsoidal",
        geodetic={"horizontal_crs": "EPSG:4978", "vertical_datum": "ellipsoidal"},
    )
    with pytest.raises(PydanticValidationError):
        context.spatial_data.register_transform(
            tenant_id=tenant_id,
            project_id=project_id,
            actor_id=actor,
            source_frame_id="frame-geodetic-a",
            target_frame_id="frame-geodetic-b",
            transform_type="SE3",
            matrix=np.eye(4).tolist(),
            uncertainty={"horizontal_sigma_m": 0.02, "vertical_sigma_m": 0.04},
            source_type="geodetic",
            authority_class=AuthorityClass.METRIC,
        )
    pipeline = (
        "+proj=pipeline +step +proj=unitconvert +xy_in=m +xy_out=m "
        "+step +proj=cart +ellps=GRS80"
    )
    grid_hash = "7" * 64
    geodetic_transform = context.spatial_data.register_transform(
        tenant_id=tenant_id,
        project_id=project_id,
        actor_id=actor,
        source_frame_id="frame-geodetic-a",
        target_frame_id="frame-geodetic-b",
        transform_type="SE3",
        matrix=np.eye(4).tolist(),
        uncertainty={"horizontal_sigma_m": 0.02, "vertical_sigma_m": 0.04},
        source_type="geodetic",
        authority_class=AuthorityClass.METRIC,
        crs_pipeline=pipeline,
        grid_resources=[
            {
                "name": "synthetic-geoid-grid",
                "sha256": grid_hash,
                "uri": "file:///approved-grids/synthetic-geoid-grid.tif",
                "version": "1.0.0",
            }
        ],
    )
    assert geodetic_transform["crs_pipeline"] == pipeline
    assert geodetic_transform["grid_resources"][0]["sha256"] == grid_hash

    asset = _ingest(context, tenant_id, project_id, actor, b"authoritative geometry bytes", "authoritative.glb")
    manifest = context.spatial_data.register_geometry_manifest(
        tenant_id=tenant_id,
        project_id=project_id,
        actor_id=actor,
        asset_id=asset.asset_id,
        media_type="model/gltf-binary",
        format="glb",
        profile="metric_mesh",
        format_version="2.0",
        coordinate_frame_id="frame-local-mm",
        units="millimeter",
        bounds={"min": [0.0, 0.0, 0.0], "max": [1000.0, 2000.0, 3000.0]},
        counts={"triangles": 12},
        compression={"codec": "none"},
        source_run_id="fixture-unit-boundary-001",
        quality={"schema_valid": True},
        classification="internal",
        validation_state="valid",
    )
    conversion = context.spatial_data.convert_units(
        tenant_id=tenant_id,
        project_id=project_id,
        frame_id="frame-local-mm",
        values=[1000.0, 2000.0, 3000.0],
        from_units="millimeter",
        to_units="meter",
    )
    assert conversion["values"] == [1.0, 2.0, 3.0]
    assert conversion["frame_original_units"] == "millimeter"
    assert context.assets.get(tenant_id, project_id, asset.asset_id).sha256 == asset.sha256
    with context.database.session() as session:
        stored = session.get(GeometryAssetManifestRow, manifest["geometry_manifest_id"])
        assert stored is not None
        assert stored.content_sha256 == asset.sha256
        assert stored.bounds_json == {"min": [0.0, 0.0, 0.0], "max": [1000.0, 2000.0, 3000.0]}


@pytest.mark.integration
@pytest.mark.security
def test_datgeom_manifest_inherits_classification_and_matches_representation(bootstrapped) -> None:
    """REQ: DATGEOM-001, GOVETH-001 geometry metadata cannot weaken or detach authoritative source scope."""
    context, tenant_id, project_id, actor = bootstrapped
    _frame(context, tenant_id, project_id, actor, "frame-geometry-a")
    _frame(context, tenant_id, project_id, actor, "frame-geometry-b")
    _provider(context, actor, "local-geometry-provider")
    scene = context.scene.create_scene(
        tenant_id, project_id, name="Geometry manifest scope", actor_id=actor
    )
    with pytest.raises(ValidationError) as invalid_scene_id:
        context.representations.create_candidate(
            tenant_id=tenant_id,
            project_id=project_id,
            scene_id=scene,  # type: ignore[arg-type]
            asset_id="not-evaluated-after-scene-validation",
            kind=RepresentationKind.METRIC,
            provider_id="local-geometry-provider",
            coordinate_frame_id="frame-geometry-a",
            source_class=SourceClass.MEASURED,
            authority_class=AuthorityClass.METRIC,
            lossy=False,
            intended_uses=["measurement_candidate"],
            prohibited_uses=[],
            quality={"schema_valid": True},
            provenance={"source_ids": []},
            support_map={},
            actor_id=actor,
        )
    assert invalid_scene_id.value.code == "REPRESENTATION_SCENE_ID_INVALID"
    scene_id = scene["scene_id"]
    restricted_bytes = b"restricted metric geometry"
    restricted_asset = context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=restricted_bytes,
        media_type="model/gltf-binary",
        original_name="restricted.glb",
        classification=Classification.RESTRICTED,
        retention_class="preservation",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.METRIC,
        provenance=ProvenanceRef(
            source_ids=["synthetic-restricted-capture"],
            output_hash=sha256_bytes(restricted_bytes),
        ),
        actor_id=actor,
    )
    other_asset = _ingest(
        context, tenant_id, project_id, actor, b"other geometry", "other.glb"
    )
    representation_id = context.representations.create_candidate(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene_id,
        asset_id=restricted_asset.asset_id,
        kind=RepresentationKind.METRIC,
        provider_id="local-geometry-provider",
        coordinate_frame_id="frame-geometry-a",
        source_class=SourceClass.MEASURED,
        authority_class=AuthorityClass.METRIC,
        lossy=False,
        intended_uses=["measurement_candidate"],
        prohibited_uses=["survey_grade"],
        quality={"schema_valid": True},
        provenance={"source_ids": [restricted_asset.asset_id]},
        support_map={},
        actor_id=actor,
        operation_id="geometry-manifest-scope-operation",
    )
    common = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "actor_id": actor,
        "media_type": "model/gltf-binary",
        "format": "glb",
        "profile": "metric_mesh",
        "format_version": "2.0",
        "units": "meter",
        "bounds": {"min": [0, 0, 0], "max": [1, 1, 1]},
        "counts": {"triangles": 12},
        "compression": {"codec": "none"},
        "source_run_id": "geometry-manifest-scope-run",
        "quality": {"schema_valid": True},
        "validation_state": "valid",
    }

    with pytest.raises(ValidationError) as downgrade:
        context.spatial_data.register_geometry_manifest(
            **common,
            asset_id=restricted_asset.asset_id,
            coordinate_frame_id="frame-geometry-a",
            representation_id=representation_id,
            classification="internal",
        )
    assert downgrade.value.code == "GEOMETRY_CLASSIFICATION_DOWNGRADE"

    with pytest.raises(ValidationError) as asset_mismatch:
        context.spatial_data.register_geometry_manifest(
            **common,
            asset_id=other_asset.asset_id,
            coordinate_frame_id="frame-geometry-a",
            representation_id=representation_id,
            classification="internal",
        )
    assert asset_mismatch.value.code == "GEOMETRY_REPRESENTATION_ASSET_MISMATCH"

    with pytest.raises(ValidationError) as frame_mismatch:
        context.spatial_data.register_geometry_manifest(
            **common,
            asset_id=restricted_asset.asset_id,
            coordinate_frame_id="frame-geometry-b",
            representation_id=representation_id,
            classification="restricted",
        )
    assert frame_mismatch.value.code == "GEOMETRY_REPRESENTATION_FRAME_MISMATCH"

    manifest = context.spatial_data.register_geometry_manifest(
        **common,
        asset_id=restricted_asset.asset_id,
        coordinate_frame_id="frame-geometry-a",
        representation_id=representation_id,
        classification="restricted",
    )
    retried = context.spatial_data.register_geometry_manifest(
        **common,
        asset_id=restricted_asset.asset_id,
        coordinate_frame_id="frame-geometry-a",
        representation_id=representation_id,
        classification="restricted",
    )
    assert retried["geometry_manifest_id"] == manifest["geometry_manifest_id"]
    assert retried["classification"] == "restricted"


@pytest.mark.integration
@pytest.mark.security
def test_datevid_datgeom_derivation_is_scoped_idempotent_and_truth_labeled(bootstrapped) -> None:
    """REQ: DATGEOM-001, DATEVID-001, DATEVID-002, DATEVID-003, GOVETH-001 evidence and derivation lineage remain scoped and explicit."""
    context, tenant_id, project_id, actor = bootstrapped
    _frame(context, tenant_id, project_id, actor, "frame-world")
    asset = _ingest(context, tenant_id, project_id, actor, b"synthetic splat bytes", "scene.splat")

    with pytest.raises(PydanticValidationError):
        context.spatial_data.register_geometry_manifest(
            tenant_id=tenant_id,
            project_id=project_id,
            actor_id=actor,
            asset_id=asset.asset_id,
            media_type="application/x-gaussian-splat",
            format="gaussian-splat",
            profile="splat-v1",
            format_version="1.0",
            coordinate_frame_id="frame-world",
            units="meter",
            bounds={"min": [0, 0, 0], "max": [1, 1, 1]},
            counts={"gaussians": 64},
            compression={"codec": "none"},
            source_run_id="fixture-run-missing-truth-label",
            quality={"schema_valid": True},
            visual_content_classes=["generated"],
            classification="internal",
        )

    manifest = context.spatial_data.register_geometry_manifest(
        tenant_id=tenant_id,
        project_id=project_id,
        actor_id=actor,
        asset_id=asset.asset_id,
        media_type="application/x-gaussian-splat",
        format="gaussian-splat",
        profile="splat-v1",
        format_version="1.0",
        coordinate_frame_id="frame-world",
        units="meter",
        bounds={"min": [0, 0, 0], "max": [1, 1, 1]},
        counts={"gaussians": 64},
        compression={"codec": "none"},
        source_run_id="fixture-splat-run-001",
        classification="internal",
        quality={"held_out_psnr_db": 28.0, "schema_valid": True},
        limitations=["not_metric_geometry"],
        visual_content_classes=["generated"],
        truth_label="generated_visual_non_metric",
        rebuild_recipe={"worker": "splat", "input_hashes": [asset.sha256]},
    )
    assert manifest["content_sha256"] == asset.sha256
    assert manifest["truth_label"] == "generated_visual_non_metric"
    retried_manifest = context.spatial_data.register_geometry_manifest(
        tenant_id=tenant_id,
        project_id=project_id,
        actor_id=actor,
        asset_id=asset.asset_id,
        media_type="application/x-gaussian-splat",
        format="gaussian-splat",
        profile="splat-v1",
        format_version="1.0",
        coordinate_frame_id="frame-world",
        units="meter",
        bounds={"min": [0, 0, 0], "max": [1, 1, 1]},
        counts={"gaussians": 64},
        compression={"codec": "none"},
        source_run_id="fixture-splat-run-001",
        classification="internal",
        quality={"held_out_psnr_db": 28.0, "schema_valid": True},
        limitations=["not_metric_geometry"],
        visual_content_classes=["generated"],
        truth_label="generated_visual_non_metric",
        rebuild_recipe={"worker": "splat", "input_hashes": [asset.sha256]},
    )
    assert retried_manifest["geometry_manifest_id"] == manifest["geometry_manifest_id"]
    assert retried_manifest["manifest_hash"] == manifest["manifest_hash"]
    with context.database.session() as session:
        manifests = list(session.scalars(select(GeometryAssetManifestRow).where(
            GeometryAssetManifestRow.tenant_id == tenant_id,
            GeometryAssetManifestRow.project_id == project_id,
            GeometryAssetManifestRow.manifest_hash == manifest["manifest_hash"],
        )))
        events = list(session.scalars(select(OutboxEventRow).where(
            OutboxEventRow.tenant_id == tenant_id,
            OutboxEventRow.project_id == project_id,
            OutboxEventRow.event_type == "geometry_manifest.registered",
        )))
        assert len(manifests) == 1
        assert len(events) == 1

    collected_at = datetime.now(UTC) - timedelta(minutes=5)
    evidence = context.spatial_data.record_evidence(
        tenant_id=tenant_id,
        project_id=project_id,
        asset_id=asset.asset_id,
        source_type="synthetic_direct_capture",
        collected_at=collected_at,
        collected_by="fixture-collector",
        device_or_tool="synthetic-rig-v1",
        location_context={"coordinate_frame_id": "frame-world", "region": "room-a"},
        relevant_region={"coordinate_frame_id": "frame-world", "region": "room-a"},
        relevant_time_start=collected_at,
        relevant_time_end=collected_at,
        retention_class="preservation",
        consent_scope={"basis": "synthetic_fixture"},
        access_policy={"allowed_audiences": ["project"]},
        actor_id=actor,
        policy={"allowed_audiences": ["project"]},
    )
    assertion = context.spatial_data.record_assertion(
        tenant_id=tenant_id,
        project_id=project_id,
        subject_id="room-a",
        predicate="has_visual_reconstruction",
        object_value={"geometry_manifest_id": manifest["geometry_manifest_id"]},
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.VISUAL,
        confidence=0.9,
        evidence_ids=[evidence["evidence_id"]],
        actor_id=actor,
    )
    disputed = context.spatial_data.record_assertion(
        tenant_id=tenant_id,
        project_id=project_id,
        subject_id="room-a",
        predicate="has_visual_reconstruction",
        object_value={"status": "disputed-quality"},
        source_class=SourceClass.DISPUTED,
        authority_class=AuthorityClass.HISTORICAL_ASSERTION,
        confidence=0.5,
        evidence_ids=[evidence["evidence_id"]],
        conflicts_with_assertion_ids=[assertion["assertion_id"]],
        actor_id=actor,
        state="disputed",
    )
    assert assertion["source_class"] == "generated"
    assert disputed["conflicts_with_assertion_ids"] == [assertion["assertion_id"]]

    now = datetime.now(UTC)
    kwargs = dict(
        activity_type="visual_reconstruction",
        input_ids=[asset.asset_id],
        input_hashes=[asset.sha256],
        algorithm_id="sip.synthetic.splat-normalizer",
        algorithm_version="1.0.0",
        parameters_hash="a" * 64,
        environment_hash="b" * 64,
        code_commit="fixture-commit",
        output_ids=[manifest["geometry_manifest_id"]],
        output_hashes=[manifest["manifest_hash"]],
        software={"name": "sip.synthetic.splat-normalizer", "version": "1.0.0"},
        started_at=now - timedelta(seconds=1),
        completed_at=now,
        quality={"schema_valid": True},
        validation={"status": "passed", "checks": ["schema", "truth_label", "hash"]},
        workload_identity="sip-worker:splat-normalizer",
    )
    first = context.spatial_data.record_derivation(tenant_id=tenant_id, project_id=project_id, **kwargs)
    retried = context.spatial_data.record_derivation(tenant_id=tenant_id, project_id=project_id, **kwargs)
    assert retried["derivation_id"] == first["derivation_id"]

    tenant_two = context.tenancy.create_tenant("Tenant Two", tenant_id="tenant-two", actor_id="system")
    project_two = context.tenancy.create_project(
        tenant_two,
        "Project Two",
        vertical="platform",
        classification="internal",
        project_id="project-two",
        actor_id="admin-two",
    )
    with pytest.raises(NotFoundError) as cross_tenant_reference:
        context.spatial_data.record_derivation(tenant_id=tenant_two, project_id=project_two, **kwargs)
    assert cross_tenant_reference.value.code == "NOT_FOUND"

    _frame(context, tenant_two, project_two, "admin-two", "frame-world-two")
    asset_two = _ingest(
        context,
        tenant_two,
        project_two,
        "admin-two",
        b"synthetic splat bytes",
        "scene.splat",
    )
    manifest_two = context.spatial_data.register_geometry_manifest(
        tenant_id=tenant_two,
        project_id=project_two,
        actor_id="admin-two",
        asset_id=asset_two.asset_id,
        media_type="application/x-gaussian-splat",
        format="gaussian-splat",
        profile="splat-v1",
        format_version="1.0",
        coordinate_frame_id="frame-world-two",
        units="meter",
        bounds={"min": [0, 0, 0], "max": [1, 1, 1]},
        counts={"gaussians": 64},
        compression={"codec": "none"},
        source_run_id="fixture-splat-run-001",
        classification="internal",
        quality={"held_out_psnr_db": 28.0, "schema_valid": True},
        limitations=["not_metric_geometry"],
        visual_content_classes=["generated"],
        truth_label="generated_visual_non_metric",
        rebuild_recipe={"worker": "splat", "input_hashes": [asset_two.sha256]},
    )
    isolated_kwargs = {
        **kwargs,
        "input_ids": [asset_two.asset_id],
        "input_hashes": [asset_two.sha256],
        "output_ids": [manifest_two["geometry_manifest_id"]],
        "output_hashes": [manifest_two["manifest_hash"]],
    }
    isolated = context.spatial_data.record_derivation(
        tenant_id=tenant_two,
        project_id=project_two,
        **isolated_kwargs,
    )
    assert isolated["derivation_id"] != first["derivation_id"]
    with context.database.session() as session:
        rows = list(session.scalars(select(DerivationEventRow).order_by(DerivationEventRow.tenant_id)))
        assert {(row.tenant_id, row.project_id) for row in rows} >= {
            (tenant_id, project_id),
            (tenant_two, project_two),
        }
        assertions = list(session.scalars(select(AssertionRow)))
        assert {row.state for row in assertions} == {"active", "disputed"}


@pytest.mark.integration
@pytest.mark.security
def test_datevid_derivation_references_are_scoped_hashed_unique_and_immutable(bootstrapped) -> None:
    """REQ: DATEVID-001, DATEVID-002, DATEVID-003 arbitrary, mismatched, ambiguous, and in-place lineage is denied."""
    context, tenant_id, project_id, actor = bootstrapped
    source = _ingest(context, tenant_id, project_id, actor, b"lineage source", "lineage-source.bin")
    output = _ingest(context, tenant_id, project_id, actor, b"lineage output", "lineage-output.bin")
    now = datetime.now(UTC)
    base = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "activity_type": "lineage_validation",
        "input_ids": [source.asset_id],
        "input_hashes": [source.sha256],
        "algorithm_id": "sip.synthetic.lineage",
        "algorithm_version": "1.0.0",
        "parameters_hash": "1" * 64,
        "environment_hash": "2" * 64,
        "code_commit": "3" * 40,
        "output_ids": [output.asset_id],
        "output_hashes": [output.sha256],
        "software": {"name": "sip.synthetic.lineage", "version": "1.0.0"},
        "validation": {"schema_valid": True, "hashes_verified": True},
        "started_at": now,
        "completed_at": now + timedelta(seconds=1),
        "quality": {"deterministic": True},
        "actor_id": actor,
    }
    with pytest.raises(ValidationError) as mismatch:
        context.spatial_data.record_derivation(**{**base, "input_hashes": ["0" * 64]})
    assert mismatch.value.code == "DERIVATION_REFERENCE_HASH_MISMATCH"

    with pytest.raises(NotFoundError):
        context.spatial_data.record_derivation(**{**base, "output_ids": ["missing-output"]})

    with pytest.raises(ValidationError) as mutation:
        context.spatial_data.record_derivation(
            **{
                **base,
                "output_ids": [source.asset_id],
                "output_hashes": [source.sha256],
            }
        )
    assert mutation.value.code == "DERIVATION_IN_PLACE_MUTATION_DENIED"

    evidence = context.spatial_data.record_evidence(
        tenant_id=tenant_id,
        project_id=project_id,
        asset_id=source.asset_id,
        source_type="synthetic_direct_capture",
        collected_at=now,
        collected_by=actor,
        device_or_tool="synthetic-fixture",
        location_context={"region": "lineage-test"},
        relevant_region={"region": "lineage-test"},
        relevant_time_start=now,
        relevant_time_end=now,
        retention_class="preservation",
        consent_scope={"basis": "synthetic_fixture"},
        access_policy={"allowed_audiences": ["project"]},
        actor_id=actor,
    )
    with context.database.session() as session:
        session.add(
            AssetRefRow(
                asset_id=evidence["evidence_id"],
                tenant_id=tenant_id,
                project_id=project_id,
                sha256=source.sha256,
                original_name="intentional-id-collision.bin",
                classification="internal",
                retention_class="preservation",
                source_class="direct_capture",
                authority_class="evidence",
                provenance_json={"source_ids": [source.asset_id]},
                created_by=actor,
            )
        )
    with pytest.raises(ValidationError) as ambiguous:
        context.spatial_data.record_derivation(
            **{
                **base,
                "input_ids": [evidence["evidence_id"]],
                "input_hashes": [source.sha256],
            }
        )
    assert ambiguous.value.code == "DERIVATION_REFERENCE_AMBIGUOUS"


@pytest.mark.integration
@pytest.mark.security
def test_pltmodel_datevid_model_derivation_has_signed_governance_receipt_and_historical_retry(bootstrapped) -> None:
    """REQ: PLTMODEL-001, PLTMODEL-004, DATEVID-001 model lineage is governed while exact historical retries remain stable."""
    context, tenant_id, project_id, actor = bootstrapped
    source = _ingest(context, tenant_id, project_id, actor, b"model source", "model-source.bin")
    output = _ingest(context, tenant_id, project_id, actor, b"model output", "model-output.bin")
    checkpoint_hash = canonical_sha256({"checkpoint": "synthetic-model-v1"})
    model_id = "synthetic-lineage-model-v1"
    registration = context.models.register(
        _approved_model_manifest(model_id=model_id, actor=actor, checkpoint_hash=checkpoint_hash),
        actor_id=actor,
    )
    now = datetime.now(UTC)
    request = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "activity_type": "model_inference",
        "input_ids": [source.asset_id],
        "input_hashes": [source.sha256],
        "algorithm_id": "sip.synthetic.model-inference",
        "algorithm_version": "1.0.0",
        "model_manifest_id": model_id,
        "parameters_hash": "4" * 64,
        "environment_hash": "5" * 64,
        "code_commit": "6" * 40,
        "output_ids": [output.asset_id],
        "output_hashes": [output.sha256],
        "software": {
            "name": "sip.synthetic.model-inference",
            "version": "1.0.0",
            "model_checkpoint_hash": checkpoint_hash,
        },
        "validation": {
            "schema_valid": True,
            "execution_context": {
                "purpose": "spatial-truth-test",
                "classification": "internal",
                "deployment": "test",
                "region": "local",
            },
        },
        "started_at": now,
        "completed_at": now + timedelta(seconds=1),
        "quality": {"deterministic": True},
        "workload_identity": "sip-worker:synthetic-model",
    }
    recorded = context.spatial_data.record_derivation(**request)
    receipt = recorded["validation"]["model_governance_receipt"]
    assert receipt["allowed"] is True
    assert receipt["manifest_hash"] == registration["manifest_hash"]
    assert recorded["software"]["model_manifest_hash"] == registration["manifest_hash"]
    assert len(recorded["request_hash"]) == 64 and len(recorded["derivation_hash"]) == 64

    revoked = _approved_model_manifest(model_id=model_id, actor=actor, checkpoint_hash=checkpoint_hash)
    revoked["approval_state"] = "revoked"
    revoked["revoked_at"] = datetime.now(UTC)
    context.models.register(revoked, actor_id=actor)

    historical_retry = context.spatial_data.record_derivation(**request)
    assert historical_retry["derivation_id"] == recorded["derivation_id"]
    assert historical_retry["validation"]["model_governance_receipt"] == receipt

    with pytest.raises(AuthorizationError) as denied:
        context.spatial_data.record_derivation(**{**request, "parameters_hash": "7" * 64})
    assert denied.value.code == "MODEL_EXECUTION_DENIED"


@pytest.mark.integration
def test_datanch_reprojectable_annotations_and_proxy_remap_report(bootstrapped) -> None:
    """REQ: DATANCH-001, DATANCH-002, DATHYB-006, DATHYB-010 durable annotations reject primitive identity and report remap failures."""
    context, tenant_id, project_id, actor = bootstrapped
    _frame(context, tenant_id, project_id, actor, "frame-world")
    _provider(context, actor, "local-annotation-provider")
    scene = context.scene.create_scene(tenant_id, project_id, name="Annotation scene", actor_id=actor)
    metric_source_asset = _ingest(
        context, tenant_id, project_id, actor, b"annotation metric source", "annotation-metric.bin"
    )
    source_proxy_asset = _ingest(
        context, tenant_id, project_id, actor, b"annotation source proxy", "annotation-source.glb"
    )
    target_proxy_asset = _ingest(
        context, tenant_id, project_id, actor, b"annotation target proxy", "annotation-target.glb"
    )
    entity_id = context.scene.create_entity(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        entity_type="room",
        name="Room A",
        attributes={},
        source_class=SourceClass.OBSERVED,
        authority_class=AuthorityClass.EVIDENCE,
        confidence=1.0,
        provenance=ProvenanceRef(source_ids=["fixture"]),
        policy={},
        stable_support={"frame_id": "frame-world", "point": [0.0, 0.0, 0.0]},
        actor_id=actor,
    )
    review_entity_id = context.scene.create_entity(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        entity_type="equipment",
        name="Anchor requiring review",
        attributes={},
        source_class=SourceClass.OBSERVED,
        authority_class=AuthorityClass.EVIDENCE,
        confidence=1.0,
        provenance=ProvenanceRef(source_ids=["fixture"]),
        policy={},
        stable_support={"frame_id": "frame-world", "point": [1.0, 1.0, 0.5]},
        actor_id=actor,
    )
    source_proxy = context.representations.create_candidate(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        asset_id=source_proxy_asset.asset_id,
        kind=RepresentationKind.INTERACTION,
        provider_id="local-annotation-provider",
        coordinate_frame_id="frame-world",
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        lossy=True,
        intended_uses=["picking"],
        prohibited_uses=["verified_measurement"],
        quality={},
        provenance={"source_ids": [metric_source_asset.asset_id]},
        support_map={},
        information_losses=["decimated_surface"],
        actor_id=actor,
    )
    target_proxy = context.representations.create_candidate(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        asset_id=target_proxy_asset.asset_id,
        kind=RepresentationKind.INTERACTION,
        provider_id="local-annotation-provider",
        coordinate_frame_id="frame-world",
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        lossy=True,
        intended_uses=["picking"],
        prohibited_uses=["verified_measurement"],
        quality={},
        provenance={"source_ids": [metric_source_asset.asset_id]},
        support_map={
            "semantic_entity_ids": [entity_id, review_entity_id],
            "anchors": [
                {"semantic_entity_id": entity_id, "position": [0.5, 1.0, 0.5], "confidence": 0.98},
                {"semantic_entity_id": review_entity_id, "position": [2.0, 1.0, 0.5], "confidence": 0.99},
                {"anchor_id": "duplicate-anchor", "position": [0.0, 0.0, 0.0], "confidence": 0.99},
                {"anchor_id": "duplicate-anchor", "position": [0.1, 0.0, 0.0], "confidence": 0.99},
            ],
        },
        information_losses=["decimated_surface"],
        actor_id=actor,
    )

    with pytest.raises(PydanticValidationError):
        context.spatial_data.create_annotation(
            tenant_id=tenant_id,
            project_id=project_id,
            scene_id=scene["scene_id"],
            entity_id=entity_id,
            coordinate_frame_id="frame-world",
            support_type="semantic_entity",
            support={"semantic_entity_id": entity_id, "triangle_id": 17},
            uncertainty_m=0.02,
            source_class=SourceClass.GENERATED,
            authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
            actor_id=actor,
            authored_from_representation_id=source_proxy,
        )
    with pytest.raises(ValidationError) as invalid_authority:
        context.spatial_data.create_annotation(
            tenant_id=tenant_id,
            project_id=project_id,
            scene_id=scene["scene_id"],
            entity_id=entity_id,
            coordinate_frame_id="frame-world",
            support_type="semantic_entity",
            support={"semantic_entity_id": entity_id},
            uncertainty_m=0.02,
            source_class=SourceClass.GENERATED,
            authority_class=AuthorityClass.METRIC,
            actor_id=actor,
            authored_from_representation_id=source_proxy,
        )
    assert invalid_authority.value.code == "PROXY_ANNOTATION_AUTHORITY_INVALID"

    resolved = context.spatial_data.create_annotation(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        entity_id=entity_id,
        coordinate_frame_id="frame-world",
        support_type="semantic_entity",
        support={"semantic_entity_id": entity_id},
        position=[0.5, 1.0, 0.5],
        uncertainty_m=0.02,
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        actor_id=actor,
        authored_from_representation_id=source_proxy,
    )
    unresolved = context.spatial_data.create_annotation(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        coordinate_frame_id="frame-world",
        support_type="semantic_entity",
        support={"semantic_entity_id": "missing-stable-entity"},
        position=[1.5, 1.0, 0.5],
        uncertainty_m=0.04,
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        actor_id=actor,
        authored_from_representation_id=source_proxy,
    )
    review_required = context.spatial_data.create_annotation(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        entity_id=review_entity_id,
        coordinate_frame_id="frame-world",
        support_type="semantic_entity",
        support={"semantic_entity_id": review_entity_id},
        position=[1.0, 1.0, 0.5],
        uncertainty_m=0.02,
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        actor_id=actor,
        authored_from_representation_id=source_proxy,
    )
    ambiguous = context.spatial_data.create_annotation(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        coordinate_frame_id="frame-world",
        support_type="semantic_entity",
        support={"semantic_entity_id": "duplicate-anchor"},
        position=[0.0, 0.0, 0.0],
        uncertainty_m=0.02,
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE,
        actor_id=actor,
        authored_from_representation_id=source_proxy,
    )
    report = context.spatial_data.remap_annotations(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        source_representation_id=source_proxy,
        target_representation_id=target_proxy,
        actor_id=actor,
    )
    assert report["resolved_annotation_ids"] == [resolved["annotation_id"]]
    assert report["unresolved_annotation_ids"] == sorted([
        unresolved["annotation_id"],
        review_required["annotation_id"],
        ambiguous["annotation_id"],
    ])
    assert report["metrics"]["resolved_fraction"] == pytest.approx(1 / 4)
    assert report["metrics"]["review_required"] == 2
    assert report["metrics"]["review_required_annotation_ids"] == sorted([
        review_required["annotation_id"],
        ambiguous["annotation_id"],
    ])
    resolved_metric = next(item for item in report["metrics"]["per_annotation"] if item["annotation_id"] == resolved["annotation_id"])
    assert resolved_metric["residual_m"] == 0.0
    assert resolved_metric["confidence"] == 0.98
    review_metric = next(item for item in report["metrics"]["per_annotation"] if item["annotation_id"] == review_required["annotation_id"])
    assert review_metric["decision"] == "review_required"
    assert review_metric["error"] == "residual_exceeds_threshold"
    assert review_metric["residual_m"] == pytest.approx(1.0)
    ambiguous_metric = next(item for item in report["metrics"]["per_annotation"] if item["annotation_id"] == ambiguous["annotation_id"])
    assert ambiguous_metric["decision"] == "review_required"
    assert ambiguous_metric["error"] == "ambiguous_target_support"
    assert ambiguous_metric["candidate_count"] == 2
    with context.database.session() as session:
        resolved_row = session.get(SpatialAnnotationRow, resolved["annotation_id"])
        unresolved_row = session.get(SpatialAnnotationRow, unresolved["annotation_id"])
        review_row = session.get(SpatialAnnotationRow, review_required["annotation_id"])
        ambiguous_row = session.get(SpatialAnnotationRow, ambiguous["annotation_id"])
        assert resolved_row is not None and resolved_row.authored_from_representation_id == target_proxy
        assert unresolved_row is not None and unresolved_row.lifecycle_state == "unresolved"
        assert review_row is not None and review_row.lifecycle_state == "unresolved"
        assert ambiguous_row is not None and ambiguous_row.lifecycle_state == "unresolved"
        history = resolved_row.support_json["remap_history"]
        assert history[-1]["source_representation_id"] == source_proxy
        assert history[-1]["target_representation_id"] == target_proxy
        assert history[-1]["prior_support"] == {"semantic_entity_id": entity_id}


@pytest.mark.integration
def test_datgit_dattwin_tags_as_of_change_evidence_and_protected_merge(bootstrapped) -> None:
    """REQ: DATGIT-001, DATGIT-003, DATGIT-004, DATTWIN-001, DATTWIN-002, DATTWIN-003 immutable commits support temporal queries and protected merges."""
    context, tenant_id, project_id, actor = bootstrapped
    asset = _ingest(context, tenant_id, project_id, actor, b"field visit evidence", "visit.bin")
    evidence = context.spatial_data.record_evidence(
        tenant_id=tenant_id,
        project_id=project_id,
        asset_id=asset.asset_id,
        source_type="field_visit",
        collected_at=datetime.now(UTC) - timedelta(days=1),
        collected_by=actor,
        device_or_tool="fixture",
        location_context={"site": "synthetic"},
        relevant_region={"site": "synthetic"},
        relevant_time_start=datetime.now(UTC) - timedelta(days=1),
        relevant_time_end=datetime.now(UTC) - timedelta(days=1),
        retention_class="preservation",
        consent_scope={"basis": "synthetic_fixture"},
        access_policy={"allowed_audiences": ["project"]},
        actor_id=actor,
    )
    scene = context.scene.create_scene(tenant_id, project_id, name="Temporal scene", actor_id=actor)
    _frame(context, tenant_id, project_id, actor, "world")
    context.scene.create_entity(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        entity_type="door",
        name="Door 101",
        attributes={"state": "observed", "verification": "unverified"},
        source_class=SourceClass.OBSERVED,
        authority_class=AuthorityClass.EVIDENCE,
        confidence=0.9,
        provenance=ProvenanceRef(source_ids=[asset.asset_id]),
        policy={},
        stable_support={"frame_id": "world", "point": [1, 0, 0]},
        actor_id=actor,
    )
    valid_from = datetime.now(UTC) - timedelta(days=2)
    commit = context.scene.commit(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        branch="main",
        expected_head=scene["commit_id"],
        message="Record late-arriving field evidence",
        actor_id=actor,
        field_visit_id="visit-2026-07-25",
        workflow_event_id="workflow-rfi-001",
        change_evidence_ids=[evidence["evidence_id"]],
        policy_checks={"authorization": "passed", "truth_labels": "passed"},
        review_state="reviewed",
        valid_from=valid_from,
    )
    tag = context.spatial_data.tag_commit(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        commit_id=commit["commit_id"],
        name="field-visit-2026-07-25",
        actor_id=actor,
        metadata={"kind": "field_visit"},
    )
    assert tag["commit_id"] == commit["commit_id"]
    by_tag = context.spatial_data.query_scene_as_of(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        tag="field-visit-2026-07-25",
    )
    by_valid_time = context.spatial_data.query_scene_as_of(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        valid_at=valid_from + timedelta(hours=1),
    )
    by_branch = context.spatial_data.query_scene_as_of(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        branch="main",
    )
    assert {by_tag["commit_id"], by_valid_time["commit_id"], by_branch["commit_id"]} == {commit["commit_id"]}
    assert by_tag["change_evidence_ids"] == [evidence["evidence_id"]]
    assert by_tag["recorded_at"] is not None
    assert by_tag["branch"] == "main"
    assert by_branch["branch"] == "main"

    with pytest.raises(ConflictError) as immutable:
        context.spatial_data.tag_commit(
            tenant_id=tenant_id,
            project_id=project_id,
            scene_id=scene["scene_id"],
            commit_id=scene["commit_id"],
            name="field-visit-2026-07-25",
            actor_id=actor,
        )
    assert immutable.value.code == "SCENE_TAG_IMMUTABLE"
    with pytest.raises(ValidationError):
        context.spatial_data.query_scene_as_of(
            tenant_id=tenant_id,
            project_id=project_id,
            scene_id=scene["scene_id"],
            commit_id=commit["commit_id"],
            branch="main",
        )

    left = {
        "entities": [{"entity_id": "door", "attributes": {"verification": "verified", "measurement": 1.0}}],
        "representations": [],
    }
    right = {
        "entities": [{"entity_id": "door", "attributes": {"verification": "disputed", "measurement": 1.2}}],
        "representations": [],
    }
    base = {
        "entities": [{"entity_id": "door", "attributes": {"verification": "unverified", "measurement": 1.1}}],
        "representations": [],
    }
    _, conflicts = context.spatial_data._semantic_merge(base, left, right)
    assert conflicts
    assert set(conflicts[0]["categories"]) >= {"measurement", "verification"}

    merge_scene = context.scene.create_scene(tenant_id, project_id, name="Protected merge scene", actor_id=actor)
    context.scene.create_branch(
        tenant_id,
        project_id,
        merge_scene["scene_id"],
        name="feature",
        from_commit_id=merge_scene["commit_id"],
    )
    base_snapshot = {"schema_version": "1.0.0", "scene_id": merge_scene["scene_id"], **base}
    left_snapshot = {"schema_version": "1.0.0", "scene_id": merge_scene["scene_id"], **left}
    right_snapshot = {"schema_version": "1.0.0", "scene_id": merge_scene["scene_id"], **right}
    base_id, left_id, right_id = new_uuid(), new_uuid(), new_uuid()
    with context.database.session() as session:
        for commit_id_value, branch_name, parents, snapshot, message in (
            (base_id, "main", [merge_scene["commit_id"]], base_snapshot, "merge base"),
            (left_id, "main", [base_id], left_snapshot, "target change"),
            (right_id, "feature", [base_id], right_snapshot, "source change"),
        ):
            digest = canonical_sha256(snapshot)
            session.add(SceneCommitRow(
                commit_id=commit_id_value,
                tenant_id=tenant_id,
                project_id=project_id,
                scene_id=merge_scene["scene_id"],
                branch=branch_name,
                parent_ids_json=parents,
                message=message,
                semantic_snapshot_json=snapshot,
                snapshot_hash=digest,
                root_manifest_hash=digest,
                policy_checks_json={"fixture": "passed"},
                signatures_json=[],
                review_state="reviewed",
                recorded_at=db_now(),
                created_by=actor,
            ))
        main_branch = session.scalar(select(SceneBranchRow).where(
            SceneBranchRow.scene_id == merge_scene["scene_id"],
            SceneBranchRow.name == "main",
        ))
        feature_branch = session.scalar(select(SceneBranchRow).where(
            SceneBranchRow.scene_id == merge_scene["scene_id"],
            SceneBranchRow.name == "feature",
        ))
        assert main_branch is not None and feature_branch is not None
        main_branch.head_commit_id = left_id
        feature_branch.head_commit_id = right_id

    review = context.spatial_data.merge_branches(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=merge_scene["scene_id"],
        target_branch="main",
        source_branch="feature",
        base_commit_id=base_id,
        actor_id=actor,
        message="protected merge",
    )
    assert review["status"] == "review_required"
    assert review["published"] is False
    assert review["target_head"] == left_id
    assert set(review["required_review_categories"]) >= {"measurement", "verification"}
    assert set(review["unapproved_review_categories"]) >= {"measurement", "verification"}
    with context.database.session() as session:
        main_branch = session.scalar(select(SceneBranchRow).where(
            SceneBranchRow.scene_id == merge_scene["scene_id"],
            SceneBranchRow.name == "main",
        ))
        assert main_branch is not None and main_branch.head_commit_id == left_id

    merged = context.spatial_data.merge_branches(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=merge_scene["scene_id"],
        target_branch="main",
        source_branch="feature",
        base_commit_id=base_id,
        actor_id=actor,
        message="approved protected merge",
        approved_review_categories=["measurement", "verification"],
    )
    assert merged["status"] == "merged"
    assert merged["branch"] == "main"
    assert merged["parent_ids"] == [left_id, right_id]
    assert merged["semantic_snapshot"] == left_snapshot
    assert merged["policy_checks"]["automatic_conflict_resolution"] is False
    with context.database.session() as session:
        main_branch = session.scalar(select(SceneBranchRow).where(
            SceneBranchRow.scene_id == merge_scene["scene_id"],
            SceneBranchRow.name == "main",
        ))
        assert main_branch is not None and main_branch.head_commit_id == merged["commit_id"]

    with context.database.session() as session:
        events = list(session.scalars(select(OutboxEventRow).where(OutboxEventRow.tenant_id == tenant_id)))
        event_types = {event.event_type for event in events}
        assert {"evidence.recorded", "scene.committed", "scene.tagged"} <= event_types


@pytest.mark.integration
@pytest.mark.privacy
def test_dathyb_dependency_invalidation_supersedes_bindings_and_view_falls_back(bootstrapped) -> None:
    """REQ: DATHYB-003, DATHYB-007, DATHYB-012, DATHYB-014 dependency changes invalidate published derivatives and preserve policy-aware fallbacks."""
    context, tenant_id, project_id, actor = bootstrapped
    _provider(context, actor, "local-hybrid-provider")
    _frame(context, tenant_id, project_id, actor, "world")
    scene = context.scene.create_scene(tenant_id, project_id, name="Hybrid policy scene", actor_id=actor)
    source_capture_asset = _ingest(
        context, tenant_id, project_id, actor, b"hybrid source capture", "hybrid-source.bin"
    )
    fallback_asset = _ingest(
        context, tenant_id, project_id, actor, b"hybrid fallback mesh", "hybrid-fallback.glb"
    )
    high_detail_asset = _ingest(
        context, tenant_id, project_id, actor, b"hybrid high detail splat", "hybrid-detail.splat"
    )
    consent_grant_id = context.liveforever.grant_consent(
        tenant_id=tenant_id,
        project_id=project_id,
        subject_id="hybrid-policy-subject",
        granted_by=actor,
        purposes=["display_visual"],
        audiences=[Audience.PROJECT],
        scopes=["representation:publish"],
        derivative_policy={"propagate_revocation": True},
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    fallback = context.representations.create_candidate(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        asset_id=fallback_asset.asset_id,
        kind=RepresentationKind.VISUAL,
        provider_id="local-hybrid-provider",
        coordinate_frame_id="world",
        source_class=SourceClass.OBSERVED,
        authority_class=AuthorityClass.VISUAL,
        lossy=False,
        intended_uses=["display_visual"],
        prohibited_uses=[],
        quality={},
        provenance={"source_ids": [source_capture_asset.asset_id]},
        support_map={},
        format_metadata={"format": "glb"},
        privacy_inheritance={"allowed_audiences": ["project"]},
        actor_id=actor,
    )
    context.representations.review_quality(
        fallback,
        reviewer_id="reviewer",
        approved_uses=["display_visual"],
        metrics={"schema_valid": True},
        passed=True,
    )
    context.publisher.publish(
        fallback,
        commit_id=scene["commit_id"],
        role="display_visual",
        intended_uses=["display_visual"],
        audience_policy={"allowed_audiences": ["project"]},
        publisher_id="publisher",
    )

    high_detail = context.representations.create_candidate(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        asset_id=high_detail_asset.asset_id,
        kind=RepresentationKind.VISUAL,
        provider_id="local-hybrid-provider",
        coordinate_frame_id="world",
        source_class=SourceClass.GENERATED,
        authority_class=AuthorityClass.VISUAL,
        lossy=True,
        intended_uses=["display_visual"],
        prohibited_uses=["metric_measurement"],
        quality={},
        provenance={"source_ids": [source_capture_asset.asset_id]},
        support_map={},
        format_metadata={"format": "gaussian-splat"},
        information_losses=["occluded_regions_unobserved"],
        privacy_inheritance={
            "consent_grant_ids": [consent_grant_id],
            "allowed_audiences": ["project"],
            "allowed_purposes": ["display_visual"],
            "required_scopes": ["representation:publish"],
        },
        dependencies=[consent_grant_id, "transform-1"],
        fallback_representation_id=fallback,
        metadata={"truth_label": "generated_visual_non_metric"},
        actor_id=actor,
    )
    context.representations.review_quality(
        high_detail,
        reviewer_id="reviewer",
        approved_uses=["display_visual"],
        metrics={"held_out_psnr_db": 30.0},
        passed=True,
    )
    binding = context.publisher.publish(
        high_detail,
        commit_id=scene["commit_id"],
        role="display_visual",
        intended_uses=["display_visual"],
        audience_policy={"allowed_audiences": ["project"], "purpose": "display_visual"},
        client_profile={"required_capabilities": ["gaussian_splat"]},
        publisher_id="publisher",
    )
    view = context.representations.select_for_view(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        intended_use="display_visual",
        audience="project",
        client_profile={"capabilities": []},
    )
    assert any(item["representation_id"] == fallback and item["used_fallback"] for item in view["selected"])

    result = context.representations.invalidate_dependencies(
        tenant_id=tenant_id,
        project_id=project_id,
        changed_resource_id=consent_grant_id,
        reason="consent revoked",
        actor_id=actor,
    )
    assert high_detail in result["invalidated_representation_ids"]
    assert binding in result["superseded_binding_ids"]
    with context.database.session() as session:
        row = session.get(RepresentationAssetRow, high_detail)
        binding_row = session.get(RepresentationBindingRow, binding)
        assert row is not None and row.state == "invalidated" and row.deprecated_at is not None
        assert binding_row is not None and binding_row.superseded_at is not None



@pytest.mark.integration
@pytest.mark.security
def test_conmeas_measurement_supersession_scope_tombstone_and_permitted_use_guards(bootstrapped) -> None:
    """REQ: CONMEAS-001, DATANCH-001, DATRET-001 measurements retain commit/use lineage and reject stale or unauthorized evidence."""
    context, tenant_id, project_id, actor = bootstrapped
    _frame(context, tenant_id, project_id, actor, "frame-measurement")
    scene = context.scene.create_scene(tenant_id, project_id, name="Measurement lifecycle", actor_id=actor)
    evidence = _ingest(context, tenant_id, project_id, actor, b"measurement evidence", "measurement.bin")

    common = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "scene_id": scene["scene_id"],
        "entity_id": None,
        "unit": "m",
        "uncertainty": 0.01,
        "source_asset_ids": [evidence.asset_id],
        "calibration": {"tool": "synthetic-laser", "certificate": "CAL-001"},
        "verifier_id": None,
        "verified": False,
        "actor_id": actor,
        "measurement_type": "distance",
        "geometry": {"type": "segment", "start": [0.0, 0.0, 0.0], "end": [1.0, 0.0, 0.0]},
        "source_method": "controlled_fixture",
        "coordinate_frame_id": "frame-measurement",
        "permitted_uses": ["reference", "facility_operations"],
    }
    original_id = context.scene.create_measurement(value=1.0, **common)
    original = context.scene.get_measurement(tenant_id, project_id, scene["scene_id"], original_id)
    assert original["source_commit_id"] == scene["commit_id"]
    assert original["permitted_uses"] == ["facility_operations", "reference"]

    replacement_id = context.scene.create_measurement(
        value=1.002,
        supersedes_measurement_id=original_id,
        **common,
    )
    replacement = context.scene.get_measurement(tenant_id, project_id, scene["scene_id"], replacement_id)
    assert replacement["supersedes_measurement_id"] == original_id
    with context.database.session() as session:
        original_row = session.get(MeasurementRow, original_id)
        replacement_row = session.get(MeasurementRow, replacement_id)
        assert original_row is not None and original_row.state == "superseded"
        assert replacement_row is not None and replacement_row.source_commit_id == scene["commit_id"]

    with pytest.raises(ConflictError) as already_superseded:
        context.scene.create_measurement(
            value=1.003,
            supersedes_measurement_id=original_id,
            **common,
        )
    assert already_superseded.value.code == "MEASUREMENT_ALREADY_SUPERSEDED"

    with pytest.raises(ValidationError) as prohibited_use:
        context.scene.create_measurement(
            value=1.0,
            permitted_uses=["reference", "survey"],
            **{key: value for key, value in common.items() if key != "permitted_uses"},
        )
    assert prohibited_use.value.code == "MEASUREMENT_PERMITTED_USE_INVALID"

    tombstoned = _ingest(context, tenant_id, project_id, actor, b"revoked evidence", "revoked.bin")
    context.assets.tombstone(tenant_id, project_id, tombstoned.asset_id, actor_id=actor, dry_run=False)
    with pytest.raises(ValidationError) as tombstone_error:
        context.scene.create_measurement(
            value=1.0,
            source_asset_ids=[tombstoned.asset_id],
            **{key: value for key, value in common.items() if key != "source_asset_ids"},
        )
    assert tombstone_error.value.code == "MEASUREMENT_EVIDENCE_OUT_OF_SCOPE"

    other_project_id = context.tenancy.create_project(
        tenant_id,
        "Other measurement project",
        vertical="platform",
        classification="internal",
        project_id="measurement-other-project",
        actor_id=actor,
    )
    foreign_asset = _ingest(context, tenant_id, other_project_id, actor, b"foreign evidence", "foreign.bin")
    with pytest.raises(ValidationError) as foreign_error:
        context.scene.create_measurement(
            value=1.0,
            source_asset_ids=[foreign_asset.asset_id],
            **{key: value for key, value in common.items() if key != "source_asset_ids"},
        )
    assert foreign_error.value.code == "MEASUREMENT_EVIDENCE_OUT_OF_SCOPE"

    other_scene = context.scene.create_scene(tenant_id, project_id, name="Other scene", actor_id=actor)
    with pytest.raises(NotFoundError):
        context.scene.create_measurement(
            value=1.0,
            source_commit_id=other_scene["commit_id"],
            **common,
        )


@pytest.mark.integration
def test_datevid_provenance_gate_corroboration_and_disputed_retrieval(bootstrapped) -> None:
    """REQ: DATEVID-004, DATEVID-005, DATEVID-006 incomplete provenance cannot become verified/corroborated and disputes remain inspectable."""
    context, tenant_id, project_id, actor = bootstrapped
    now = datetime.now(UTC)

    incomplete_payload = b"incomplete provenance fixture"
    incomplete_asset = context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=incomplete_payload,
        media_type="application/octet-stream",
        original_name="incomplete.bin",
        classification=Classification.INTERNAL,
        retention_class="preservation",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["fixture:incomplete"]),
        actor_id=actor,
    )
    incomplete_evidence = context.spatial_data.record_evidence(
        tenant_id=tenant_id,
        project_id=project_id,
        asset_id=incomplete_asset.asset_id,
        source_type="controlled_fixture",
        collected_at=now,
        collected_by="collector-incomplete",
        device_or_tool="fixture-rig",
        location_context={"region": "room-incomplete"},
        relevant_region={"region": "room-incomplete"},
        relevant_time_start=now,
        relevant_time_end=now,
        retention_class="preservation",
        consent_scope={"basis": "synthetic_fixture"},
        access_policy={"inherit_project_policy": True},
        actor_id=actor,
    )
    with pytest.raises(ValidationError) as incomplete:
        context.spatial_data.record_assertion(
            tenant_id=tenant_id,
            project_id=project_id,
            subject_id="room-incomplete",
            predicate="is_verified",
            object_value=True,
            source_class=SourceClass.VERIFIED,
            authority_class=AuthorityClass.EVIDENCE,
            confidence=1.0,
            evidence_ids=[incomplete_evidence["evidence_id"]],
            actor_id=actor,
        )
    assert incomplete.value.code == "ASSERTION_PROVENANCE_INCOMPLETE"
    gap_names = {
        gap
        for record in incomplete.value.details["evidence_gaps"]
        for gap in record["gaps"]
    }
    assert "provenance_output_hash_missing_or_mismatched" in gap_names
    assert "validation_result_missing" in gap_names

    evidence_records: list[dict[str, object]] = []
    for index in (1, 2):
        asset = _ingest(
            context,
            tenant_id,
            project_id,
            actor,
            f"independent evidence {index}".encode(),
            f"independent-{index}.bin",
        )
        evidence_records.append(context.spatial_data.record_evidence(
            tenant_id=tenant_id,
            project_id=project_id,
            asset_id=asset.asset_id,
            source_type=f"independent_fixture_{index}",
            collected_at=now + timedelta(seconds=index),
            collected_by=f"collector-{index}",
            device_or_tool=f"fixture-rig-{index}",
            location_context={"region": "room-a", "capture": index},
            relevant_region={"region": "room-a", "capture": index},
            relevant_time_start=now,
            relevant_time_end=now + timedelta(seconds=index),
            retention_class="preservation",
            consent_scope={"basis": "synthetic_fixture"},
            access_policy={"inherit_project_policy": True},
            actor_id=actor,
        ))

    with pytest.raises(ValidationError) as insufficient:
        context.spatial_data.record_assertion(
            tenant_id=tenant_id,
            project_id=project_id,
            subject_id="room-a",
            predicate="wall_finish",
            object_value="painted gypsum",
            source_class=SourceClass.CORROBORATED,
            authority_class=AuthorityClass.EVIDENCE,
            confidence=0.9,
            evidence_ids=[str(evidence_records[0]["evidence_id"])],
            actor_id=actor,
        )
    assert insufficient.value.code == "ASSERTION_CORROBORATION_INSUFFICIENT"

    corroborated = context.spatial_data.record_assertion(
        tenant_id=tenant_id,
        project_id=project_id,
        subject_id="room-a",
        predicate="wall_finish",
        object_value="painted gypsum",
        source_class=SourceClass.CORROBORATED,
        authority_class=AuthorityClass.EVIDENCE,
        confidence=0.9,
        evidence_ids=[
            str(evidence_records[0]["evidence_id"]),
            str(evidence_records[1]["evidence_id"]),
            str(evidence_records[0]["evidence_id"]),
        ],
        actor_id=actor,
    )
    assert corroborated["source_class"] == "corroborated"
    assert corroborated["evidence_ids"] == [
        evidence_records[0]["evidence_id"],
        evidence_records[1]["evidence_id"],
    ]

    unrelated = context.spatial_data.record_assertion(
        tenant_id=tenant_id,
        project_id=project_id,
        subject_id="room-b",
        predicate="wall_finish",
        object_value="unfinished",
        source_class=SourceClass.OBSERVED,
        authority_class=AuthorityClass.EVIDENCE,
        confidence=0.7,
        evidence_ids=[str(evidence_records[0]["evidence_id"])],
        actor_id=actor,
    )
    with pytest.raises(ValidationError) as mismatch:
        context.spatial_data.record_assertion(
            tenant_id=tenant_id,
            project_id=project_id,
            subject_id="room-a",
            predicate="wall_finish",
            object_value="tile",
            source_class=SourceClass.OBSERVED,
            authority_class=AuthorityClass.EVIDENCE,
            confidence=0.7,
            evidence_ids=[str(evidence_records[0]["evidence_id"])],
            actor_id=actor,
            supersedes_assertion_id=unrelated["assertion_id"],
        )
    assert mismatch.value.code == "ASSERTION_SUPERSESSION_SCOPE_MISMATCH"

    disputed = context.spatial_data.record_assertion(
        tenant_id=tenant_id,
        project_id=project_id,
        subject_id="room-a",
        predicate="wall_finish",
        object_value="possibly plaster",
        source_class=SourceClass.DISPUTED,
        authority_class=AuthorityClass.HISTORICAL_ASSERTION,
        confidence=0.4,
        evidence_ids=[str(evidence_records[0]["evidence_id"])],
        conflicts_with_assertion_ids=[corroborated["assertion_id"]],
        actor_id=actor,
        state="disputed",
    )
    principal = SignedPrincipal(
        subject_id=actor,
        tenant_id=tenant_id,
        project_ids=[project_id],
        roles=["tenant_admin"],
        purposes=["construction"],
        audience=Audience.PRIVATE,
    )
    retrieved = context.spatial_data.get_assertion(
        tenant_id=tenant_id,
        project_id=project_id,
        assertion_id=disputed["assertion_id"],
        principal=principal,
        purpose="construction",
        include_evidence=True,
    )
    assert retrieved["state"] == "disputed"
    assert retrieved["evidence"][0]["content_sha256"]
    listing = context.spatial_data.list_assertions(
        tenant_id=tenant_id,
        project_id=project_id,
        principal=principal,
        purpose="construction",
        subject_id="room-a",
    )
    assert disputed["assertion_id"] in {item["assertion_id"] for item in listing["items"]}
    assert corroborated["assertion_id"] in {item["assertion_id"] for item in listing["items"]}
    assert listing["withheld_count"] == 0


@pytest.mark.integration
def test_datevid_evidence_read_rechecks_referenced_consent_and_audits_revocation(bootstrapped) -> None:
    """REQ: DATEVID-002, DATEVID-004, OPSAUDIT-003 consent is re-evaluated server-side on every evidence read and revocation is audited."""
    context, tenant_id, project_id, actor = bootstrapped
    grant_id = context.liveforever.grant_consent(
        tenant_id=tenant_id,
        project_id=project_id,
        subject_id="person-consent-fixture",
        granted_by=actor,
        purposes=["construction"],
        audiences=[Audience.PROJECT],
        scopes=["evidence:read"],
        derivative_policy={"propagate_revocation": True},
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    asset = _ingest(context, tenant_id, project_id, actor, b"consent-bound evidence", "consent-evidence.bin")
    now = datetime.now(UTC)
    evidence = context.spatial_data.record_evidence(
        tenant_id=tenant_id,
        project_id=project_id,
        asset_id=asset.asset_id,
        source_type="consent_bound_fixture",
        collected_at=now,
        collected_by=actor,
        device_or_tool="fixture-recorder",
        location_context={"region_id": "consent-room"},
        relevant_region={"region_id": "consent-room"},
        relevant_time_start=now,
        relevant_time_end=now,
        retention_class="preservation",
        consent_scope={
            "consent_grant_ids": [grant_id],
            "required_scopes": ["evidence:read"],
        },
        access_policy={
            "allowed_audiences": ["project"],
            "allowed_purposes": ["construction"],
        },
        actor_id=actor,
    )
    principal = SignedPrincipal(
        subject_id="consent-viewer",
        tenant_id=tenant_id,
        project_ids=[project_id],
        roles=["viewer"],
        purposes=["construction"],
        audience=Audience.PROJECT,
        attributes={"spatial_region_ids": ["consent-room"]},
    )
    allowed = context.spatial_data.get_evidence(
        tenant_id=tenant_id,
        project_id=project_id,
        evidence_id=evidence["evidence_id"],
        principal=principal,
        purpose="construction",
    )
    assert allowed["evidence_id"] == evidence["evidence_id"]

    context.liveforever.revoke_consent(grant_id, tenant_id=tenant_id, project_id=project_id, actor_id=actor, reason="controlled revocation test")
    with pytest.raises(AuthorizationError) as denied:
        context.spatial_data.get_evidence(
            tenant_id=tenant_id,
            project_id=project_id,
            evidence_id=evidence["evidence_id"],
            principal=principal,
            purpose="construction",
        )
    assert denied.value.code == "EVIDENCE_CONSENT_GRANT_REVOKED"
    with context.database.session() as session:
        denied_events = list(session.scalars(select(AuditEventRow).where(
            AuditEventRow.tenant_id == tenant_id,
            AuditEventRow.project_id == project_id,
            AuditEventRow.action == "evidence:read",
            AuditEventRow.resource_id == evidence["evidence_id"],
            AuditEventRow.outcome == "denied",
        )))
    assert denied_events
    assert denied_events[-1].details_json["reason"] == "EVIDENCE_CONSENT_GRANT_REVOKED"
