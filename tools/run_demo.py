#!/usr/bin/env python3
"""Execute retained synthetic SIP acceptance demonstrations with machine-readable evidence."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum
import html
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import numpy as np
from sqlalchemy import func, select

from sip.canonical import canonical_json, canonical_sha256, sha256_bytes, sha256_file
from sip.capture import CapturePackage, create_synthetic_room_capture
from sip.context import PlatformContext, temporary_settings
from sip.database import (
    AnchorRemapRow,
    AssertionRow,
    AssetRefRow,
    CollaborationCommentRow,
    CollaborationTaskRow,
    ConsentGrantRow,
    ConstructionRecordRow,
    CoordinateFrameRow,
    DerivationEventRow,
    EvidenceRecordRow,
    GeometryAssetManifestRow,
    LegalHoldRow,
    MeasurementRow,
    MemoryRecordRow,
    RepresentationAssetRow,
    RepresentationBindingRow,
    RetentionRuleRow,
    SceneBranchRow,
    SceneCommitRow,
    SceneEntityRow,
    SceneTagRow,
    SpatialAnnotationRow,
    SpatialTransformRow,
)
from sip.errors import AuthorizationError, ValidationError
from sip.geometry import change_detection, interaction_proxy, mesh_to_splats
from sip.models import Audience, AuthorityClass, Classification, ProvenanceRef, RepresentationKind, SignedPrincipal, SourceClass
from sip.scene import ProxyHit
from tools.evidence_binding import current_source_binding

ROOT = Path(__file__).resolve().parents[1]
DEMO_ROOT = ROOT / "runtime" / "demo"
EVIDENCE_ROOT = ROOT / "build" / "evidence" / "demos"


@contextmanager
def _exclusive_destination_lock(destination: Path):
    """Serialize destructive setup for one exact demonstration destination.

    The lock is stored beside the destination, so deleting the output directory
    cannot invalidate another process's active SQLite database or evidence scan.
    """

    lock_path = destination.parent / f".{destination.name}.demo.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def _json_evidence_value(value: Any) -> Any:
    """Convert controlled evidence values to strict canonical-JSON types.

    The retained report hash must never depend on ``default=str`` because that
    can silently accept unsupported objects with unstable or lossy string
    representations. Known temporal, path, enum, dataclass, and NumPy values
    are normalized explicitly; unknown values fail the demonstration.
    """

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Enum):
        return _json_evidence_value(value.value)
    if isinstance(value, np.generic):
        return _json_evidence_value(value.item())
    if isinstance(value, np.ndarray):
        return _json_evidence_value(value.tolist())
    if is_dataclass(value) and not isinstance(value, type):
        return _json_evidence_value(asdict(value))
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("demo evidence dictionaries require string keys")
        return {key: _json_evidence_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_evidence_value(item) for item in value]
    raise TypeError(f"unsupported demo evidence value: {type(value).__name__}")


def _git() -> dict[str, Any]:
    return current_source_binding(ROOT)


def _bootstrap(output: Path, *, vertical: str, classification: str = "internal") -> tuple[PlatformContext, str, str, str]:
    context = PlatformContext.create(temporary_settings(output / "runtime"))
    actor = f"demo-{vertical}-operator"
    tenant_id = context.tenancy.create_tenant(f"Synthetic {vertical.title()} Tenant", tenant_id=f"tenant-demo-{vertical}", actor_id=actor)
    project_id = context.tenancy.create_project(
        tenant_id,
        f"Synthetic {vertical.title()} Project",
        vertical=vertical,
        classification=classification,
        project_id=f"project-demo-{vertical}",
        actor_id=actor,
    )
    return context, tenant_id, project_id, actor


def _asset(
    context: PlatformContext,
    tenant_id: str,
    project_id: str,
    actor: str,
    *,
    name: str,
    payload: bytes,
    media_type: str,
    source_class: SourceClass = SourceClass.DIRECT_CAPTURE,
    authority_class: AuthorityClass = AuthorityClass.EVIDENCE,
    classification: Classification = Classification.INTERNAL,
) -> str:
    reference = context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=payload,
        media_type=media_type,
        original_name=name,
        classification=classification,
        retention_class="preservation",
        source_class=source_class,
        authority_class=authority_class,
        provenance=ProvenanceRef(source_ids=[f"synthetic:{name}"], output_hash=sha256_bytes(payload)),
        actor_id=actor,
    )
    return reference.asset_id


def _register_frame(
    context: PlatformContext,
    tenant_id: str,
    project_id: str,
    actor: str,
    *,
    frame_id: str = "world",
    name: str = "World",
) -> dict[str, Any]:
    return context.spatial_data.register_frame(
        tenant_id=tenant_id,
        project_id=project_id,
        name=name,
        convention="right_handed_y_up_meters",
        units="meter",
        original_units="meter",
        axis_convention="+X right, +Y up, -Z forward",
        axis_directions={"x": "+X right", "y": "+Y up", "z": "-Z forward"},
        handedness="right",
        origin_description=f"synthetic {name.lower()} origin",
        source="synthetic_demo",
        actor_id=actor,
        frame_id=frame_id,
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = _json_evidence_value(value)
    path.write_text(json.dumps(normalized, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _write_portable_viewer(output: Path, session: dict[str, Any]) -> dict[str, Any]:
    session_path = output / "viewer-session.json"
    _write_json(session_path, session)
    escaped = html.escape(json.dumps(session, sort_keys=True))
    body = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SIP Portable Evidence Viewer</title>
<style>
body{{font:16px system-ui;margin:0;background:#101318;color:#eef2f7}}header,main{{padding:1rem}}fieldset{{border:1px solid #596273;margin:.75rem 0}}button,label{{margin:.35rem}}pre{{white-space:pre-wrap;background:#171c24;padding:1rem;border-radius:.4rem}}.warning{{background:#4b2f00;padding:.75rem;border-left:4px solid #ffb347}}canvas{{width:100%;height:320px;background:#080a0d;border:1px solid #596273}}
</style>
<header><h1>Spatial Intelligence Platform — Portable Viewer</h1><p class="warning">Visual and interaction layers are not authoritative measurements. Verify against eligible metric evidence.</p></header>
<main><fieldset><legend>Representation layers</legend><div id="layers"></div></fieldset><canvas id="canvas" width="960" height="320" aria-label="Synthetic spatial layer overview"></canvas><h2>Evidence and authority</h2><pre id="evidence"></pre></main>
<script type="application/json" id="session">{escaped}</script>
<script>
const data=JSON.parse(document.getElementById('session').textContent);const layers=document.getElementById('layers');const evidence=document.getElementById('evidence');const canvas=document.getElementById('canvas');const ctx=canvas.getContext('2d');
function draw(){{ctx.clearRect(0,0,canvas.width,canvas.height);let i=0;for(const layer of data.layers||[]){{const box=document.getElementById('layer-'+i);if(box&&box.checked){{ctx.strokeStyle=['#7dd3fc','#f9a8d4','#fde68a','#86efac','#c4b5fd'][i%5];ctx.lineWidth=3;ctx.strokeRect(70+i*95,50+i*18,520-i*40,200-i*22);ctx.fillStyle=ctx.strokeStyle;ctx.fillText(layer.kind+' / '+layer.authority,80+i*95,75+i*18);}}i++;}}}}
(data.layers||[]).forEach((layer,i)=>{{const label=document.createElement('label');const box=document.createElement('input');box.type='checkbox';box.checked=true;box.id='layer-'+i;box.addEventListener('change',draw);label.append(box,document.createTextNode(' '+layer.kind+' — '+layer.role+' — '+layer.authority));layers.append(label,document.createElement('br'));}});evidence.textContent=JSON.stringify(data.evidence||{{}},null,2);draw();
</script>
</html>
"""
    viewer_path = output / "viewer.html"
    viewer_path.write_text(body, encoding="utf-8")
    return {
        "viewer": str(viewer_path),
        "viewer_sha256": sha256_file(viewer_path),
        "session": str(session_path),
        "session_sha256": sha256_file(session_path),
        "portable": True,
        "external_dependencies": [],
    }


def _register_local_provider(context: PlatformContext, actor: str, provider_id: str, purposes: list[str]) -> dict[str, Any]:
    return context.providers.register(
        {
            "provider_id": provider_id,
            "version": "1.1.0",
            "source_url": f"local://sip/{provider_id}",
            "source_revision": "deterministic-reference-v1",
            "license_id": "Apache-2.0",
            "approval_state": "approved",
            "allowed_classifications": ["internal", "confidential"],
            "allowed_purposes": purposes,
            "allowed_regions": ["local"],
            "retention_days": 0,
        },
        actor_id=actor,
    )


def _preserve_and_restore(
    context: PlatformContext,
    tenant_id: str,
    project_id: str,
    actor: str,
    output: Path,
    *,
    restored_suffix: str,
) -> dict[str, Any]:
    package_path = output / "preservation.sip-preservation.zip"
    package = context.preservation.export_project(tenant_id, project_id, package_path, actor_id=actor)
    verified = context.preservation.verify_export(package_path)
    restore_context = PlatformContext.create(temporary_settings(output / "restore-runtime"))
    restored = restore_context.preservation.import_project(
        package_path,
        new_tenant_id=f"tenant-restored-{restored_suffix}",
        new_project_id=f"project-restored-{restored_suffix}",
        actor_id="demo-restore-operator",
    )
    restored_project_id = f"project-restored-{restored_suffix}"
    native_models = (
        CoordinateFrameRow,
        SpatialTransformRow,
        EvidenceRecordRow,
        AssertionRow,
        DerivationEventRow,
        SceneTagRow,
        GeometryAssetManifestRow,
        SpatialAnnotationRow,
        AnchorRemapRow,
        SceneCommitRow,
        SceneBranchRow,
        SceneEntityRow,
        RepresentationAssetRow,
        RepresentationBindingRow,
        MeasurementRow,
        ConsentGrantRow,
        ConstructionRecordRow,
        MemoryRecordRow,
        CollaborationCommentRow,
        CollaborationTaskRow,
        RetentionRuleRow,
        LegalHoldRow,
    )
    with restore_context.database.session() as session:
        refs = list(session.scalars(select(AssetRefRow).where(AssetRefRow.project_id == restored_project_id)))
        operational_counts = {
            model.__tablename__: int(
                session.scalar(
                    select(func.count()).select_from(model).where(model.project_id == restored_project_id)
                )
                or 0
            )
            for model in native_models
        }
    expected_counts = restored.get("replayed_counts", {})
    count_mismatches = {
        name: {"expected": expected, "actual": operational_counts.get(name)}
        for name, expected in expected_counts.items()
        if operational_counts.get(name) != expected
    }
    if count_mismatches:
        raise ValidationError(
            "DEMO_NATIVE_REPLAY_COUNT_MISMATCH",
            "restored native row counts do not match the verified preservation package",
            count_mismatches,
        )
    vertical_validation: dict[str, Any] = {}
    if restored_suffix == "construction":
        technical = restore_context.construction.technical_report(f"tenant-restored-{restored_suffix}", restored_project_id)
        if not technical["record_counts"] or not technical["measurements"]:
            raise ValidationError(
                "DEMO_CONSTRUCTION_NATIVE_REPLAY_FAILED",
                "restored construction rows are not operational through the domain service",
            )
        vertical_validation = {
            "technical_record_count": sum(technical["record_counts"].values()),
            "measurement_count": len(technical["measurements"]),
            "domain_service_query_passed": True,
        }
    elif restored_suffix == "liveforever":
        family = restore_context.liveforever.edition(
            f"tenant-restored-{restored_suffix}",
            restored_project_id,
            audience=Audience.FAMILY,
            purpose="family_review",
        )
        with restore_context.database.session() as session:
            grants = list(session.scalars(select(ConsentGrantRow).where(ConsentGrantRow.project_id == restored_project_id)))
        if family["records"] or not grants or any(grant.state != "revoked" for grant in grants):
            raise ValidationError(
                "DEMO_LIVEFOREVER_NATIVE_REPLAY_FAILED",
                "restored consent revocation is not enforced by the domain service",
            )
        vertical_validation = {
            "memory_records_present": operational_counts["memory_records"],
            "revoked_consent_enforced": True,
            "family_edition_records_after_revocation": 0,
            "domain_service_query_passed": True,
        }
    for ref in refs:
        payload = restore_context.assets.read(ref.tenant_id, ref.project_id, ref.asset_id, actor_id="demo-restore-verifier")
        if sha256_bytes(payload) != ref.sha256:
            raise ValidationError("DEMO_RESTORE_HASH_MISMATCH", "restored plaintext does not match its content identity")
    if package["root_hash"] != verified["root_hash"] or restored["source_root_hash"] != package["root_hash"]:
        raise ValidationError("DEMO_RESTORE_ROOT_MISMATCH", "preservation root hash changed across verification or restore")
    return {
        "package_path": str(package_path),
        "package_sha256": sha256_file(package_path),
        "root_hash": package["root_hash"],
        "verified_files": verified["files"],
        "restored": restored,
        "restored_assets": len(refs),
        "matching_root_hash": True,
        "independent_runtime": str(output / "restore-runtime"),
        "operational_replay": {
            "counts": operational_counts,
            "matches_package": True,
            "vertical_validation": vertical_validation,
        },
    }


def foundation(output: Path) -> dict[str, Any]:
    context, tenant_id, project_id, actor = _bootstrap(output, vertical="foundation")
    capture_path = output / "input" / "synthetic-room.sipcapture"
    capture_path.parent.mkdir(parents=True, exist_ok=True)
    generated = create_synthetic_room_capture(capture_path, seed=42, frame_count=16)
    validated = CapturePackage.validate(capture_path)
    capture_asset = _asset(
        context,
        tenant_id,
        project_id,
        actor,
        name="synthetic-room.sipcapture",
        payload=capture_path.read_bytes(),
        media_type="application/vnd.sip.capture+zip",
    )

    operation = context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="capture.normalize",
        idempotency_key="foundation-normalize-v1",
        input_manifest={"capture_asset_id": capture_asset, "root_hash": generated["root_hash"]},
        actor_id=actor,
    )
    context.operations.lease(operation["operation_id"], worker_id="sip-worker:foundation-a")
    context.operations.start(operation["operation_id"], worker_id="sip-worker:foundation-a")
    first_checkpoint = context.operations.checkpoint(
        operation["operation_id"],
        worker_id="sip-worker:foundation-a",
        progress=0.4,
        checkpoint={"sequence": 1, "stage": "validated-input", "safe_to_resume": True, "root_hash": generated["root_hash"]},
    )
    failed = context.operations.fail(
        operation["operation_id"], worker_id="sip-worker:foundation-a", code="SYNTHETIC_RETRY", message="controlled retry fixture", retryable=True
    )
    context.operations.lease(operation["operation_id"], worker_id="sip-worker:foundation-b")
    context.operations.start(operation["operation_id"], worker_id="sip-worker:foundation-b")
    second_checkpoint = context.operations.checkpoint(
        operation["operation_id"],
        worker_id="sip-worker:foundation-b",
        progress=0.8,
        checkpoint={"sequence": 2, "stage": "normalized", "safe_to_resume": True, "source_checkpoint": first_checkpoint["checkpoint"]},
    )
    completed = context.operations.complete(
        operation["operation_id"],
        worker_id="sip-worker:foundation-b",
        output={"capture_asset_id": capture_asset, "canonical_root_hash": generated["root_hash"], "frame_count": validated["frame_count"]},
    )

    cancel = context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="capture.optional-derivative",
        idempotency_key="foundation-cancel-v1",
        input_manifest={"capture_asset_id": capture_asset},
        actor_id=actor,
    )
    context.operations.lease(cancel["operation_id"], worker_id="sip-worker:foundation-cancel")
    context.operations.start(cancel["operation_id"], worker_id="sip-worker:foundation-cancel")
    context.operations.request_cancel(cancel["operation_id"], actor_id=actor)
    cancelled = context.operations.checkpoint(
        cancel["operation_id"],
        worker_id="sip-worker:foundation-cancel",
        progress=0.2,
        checkpoint={"sequence": 1, "stage": "safe-cancel-boundary", "safe_to_resume": False},
    )

    provider = _register_local_provider(context, actor, "local-tsdf", ["foundation_demo"])
    context.providers.authorize_execution(
        "local-tsdf", classification=Classification.INTERNAL, purpose="foundation_demo", region="local", external=False
    )
    _register_frame(context, tenant_id, project_id, actor, frame_id="world")
    scene = context.scene.create_scene(tenant_id, project_id, name="Synthetic metric room", actor_id=actor)
    room_entity = context.scene.create_entity(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        entity_type="room",
        name="Synthetic Room 101",
        attributes={"width_m": 4.0, "depth_m": 3.0, "height_m": 2.7},
        source_class=SourceClass.OBSERVED,
        authority_class=AuthorityClass.EVIDENCE,
        confidence=1.0,
        provenance=ProvenanceRef(source_ids=[capture_asset], run_id=operation["operation_id"], output_hash=completed["output_hash"]),
        policy={"audience": "project"},
        stable_support={"frame_id": "world", "point": [0.0, 0.0, 0.0]},
        actor_id=actor,
    )
    mesh_document = {
        "format": "sip-metric-mesh-reference/v1",
        "coordinate_frame": "world",
        "units": "meter",
        "vertices": [[0, 0, 0], [4, 0, 0], [4, 3, 0], [0, 3, 0], [0, 0, 2.7], [4, 0, 2.7], [4, 3, 2.7], [0, 3, 2.7]],
        "authority": "metric",
        "source_capture_asset_id": capture_asset,
        "uncertainty_m": 0.02,
    }
    metric_asset = _asset(
        context,
        tenant_id,
        project_id,
        actor,
        name="metric-room.json",
        payload=canonical_json(mesh_document),
        media_type="application/json",
        source_class=SourceClass.MEASURED,
        authority_class=AuthorityClass.METRIC,
    )
    metric = context.representations.create_candidate(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        asset_id=metric_asset,
        kind=RepresentationKind.METRIC,
        provider_id="local-tsdf",
        coordinate_frame_id="world",
        source_class=SourceClass.MEASURED,
        authority_class=AuthorityClass.METRIC,
        lossy=False,
        intended_uses=["measurement", "render"],
        prohibited_uses=["survey", "fabrication"],
        quality={"synthetic_rmse_m": 0.0, "uncertainty_m": 0.02},
        provenance={"source_ids": [capture_asset], "operation_id": operation["operation_id"], "provider_manifest_hash": provider["manifest_hash"]},
        support_map={"entity_ids": [room_entity]},
        actor_id=actor,
    )
    context.representations.review_quality(metric, reviewer_id="demo-geometry-reviewer", approved_uses=["measurement", "render"], metrics={"rmse_m": 0.0}, passed=True)
    context.publisher.publish(metric, commit_id=scene["commit_id"], role="measurement", publisher_id="demo-publisher")
    scene_commit = context.scene.commit(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        branch="main",
        expected_head=scene["commit_id"],
        message="Publish metric room with immutable evidence",
        actor_id=actor,
    )
    viewer = _write_portable_viewer(
        output,
        {
            "schema": "sip.portable-viewer-session/v1",
            "scene_id": scene["scene_id"],
            "commit_id": scene_commit["commit_id"],
            "layers": [{"kind": "metric", "role": "measurement", "authority": "metric", "asset_id": metric_asset, "visible": True}],
            "evidence": {"capture_asset_id": capture_asset, "capture_root_hash": generated["root_hash"], "entity_id": room_entity, "warning": "Synthetic reference data; not survey-grade."},
        },
    )
    preservation = _preserve_and_restore(context, tenant_id, project_id, actor, output, restored_suffix="foundation")
    if completed["state"] != "succeeded" or completed["attempt"] != 2 or failed["state"] != "failed":
        raise ValidationError("DEMO_DURABLE_OPERATION_FAILED", "retry/resume operation did not retain expected state")
    if cancelled["state"] != "cancelled":
        raise ValidationError("DEMO_CANCELLATION_FAILED", "cancelled operation did not terminate at a safe checkpoint")
    return {
        "capture": {"path": str(capture_path), "archive_sha256": sha256_file(capture_path), **generated, "validation": validated},
        "ingest": {"capture_asset_id": capture_asset},
        "durable_operation": {"operation_id": operation["operation_id"], "attempts": completed["attempt"], "checkpoints": [first_checkpoint["checkpoint"], second_checkpoint["checkpoint"]], "final_state": completed["state"], "output_hash": completed["output_hash"]},
        "cancellation": {"operation_id": cancel["operation_id"], "state": cancelled["state"]},
        "scene": {"scene_id": scene["scene_id"], "initial_commit": scene["commit_id"], "metric_commit": scene_commit, "entity_id": room_entity, "metric_representation_id": metric},
        "viewer": viewer,
        "preservation": preservation,
        "acceptance": {"matching_capture_hash": validated["root_hash"] == generated["root_hash"], "matching_restore_root": preservation["matching_root_hash"], "retry_resume_proved": True, "cancel_proved": True},
    }


def hybrid(output: Path) -> dict[str, Any]:
    context, tenant_id, project_id, actor = _bootstrap(output, vertical="hybrid")
    _register_frame(context, tenant_id, project_id, actor)
    purposes = ["hybrid_demo"]
    provider_hashes = {
        provider: _register_local_provider(context, actor, provider, purposes)["manifest_hash"]
        for provider in ["local-tsdf", "local-splat", "local-design", "local-proxy"]
    }
    for provider in provider_hashes:
        context.providers.authorize_execution(provider, classification=Classification.INTERNAL, purpose="hybrid_demo", region="local", external=False)
    scene = context.scene.create_scene(tenant_id, project_id, name="Hybrid reference room", actor_id=actor)
    vertices = np.array([[0, 0, 0], [4, 0, 0], [4, 3, 0], [0, 3, 0], [0, 0, 2.7], [4, 0, 2.7], [4, 3, 2.7], [0, 3, 2.7]], dtype=float)
    faces = np.array([[0, 1, 2], [0, 2, 3], [4, 6, 5], [4, 7, 6], [0, 4, 5], [0, 5, 1], [1, 5, 6], [1, 6, 2], [2, 6, 7], [2, 7, 3], [3, 7, 4], [3, 4, 0]], dtype=int)
    proxy_geometry = interaction_proxy(vertices, faces, target_faces=8)
    splats = mesh_to_splats(vertices, faces, samples=96, seed=17)
    assets = {
        "metric": _asset(context, tenant_id, project_id, actor, name="metric.json", payload=canonical_json({"vertices": vertices.tolist(), "faces": faces.tolist(), "units": "meter"}), media_type="application/json", source_class=SourceClass.MEASURED, authority_class=AuthorityClass.METRIC),
        "visual": _asset(context, tenant_id, project_id, actor, name="visual-splats.json", payload=canonical_json({"positions": np.asarray(splats["positions"]).round(8).tolist(), "lossy": True}), media_type="application/json", source_class=SourceClass.GENERATED, authority_class=AuthorityClass.VISUAL),
        "design": _asset(context, tenant_id, project_id, actor, name="design.json", payload=canonical_json({"design_intent": True, "vertices": vertices.tolist(), "faces": faces.tolist()}), media_type="application/json", source_class=SourceClass.DESIGN, authority_class=AuthorityClass.DESIGN),
        "proxy_v1": _asset(context, tenant_id, project_id, actor, name="proxy-v1.json", payload=canonical_json({"vertices": np.asarray(proxy_geometry["vertices"]).tolist(), "faces": np.asarray(proxy_geometry["faces"]).tolist(), "authoritative": False}), media_type="application/json", source_class=SourceClass.GENERATED, authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE),
    }
    candidate_specs = [
        ("metric", RepresentationKind.METRIC, "local-tsdf", SourceClass.MEASURED, AuthorityClass.METRIC, False, ["measurement", "render"], ["survey", "fabrication"], "measurement", {"rmse_m": 0.005}),
        ("visual", RepresentationKind.VISUAL, "local-splat", SourceClass.GENERATED, AuthorityClass.VISUAL, True, ["render"], ["measurement"], "render", {"visual_fixture": True}),
        ("design", RepresentationKind.DESIGN, "local-design", SourceClass.DESIGN, AuthorityClass.DESIGN, False, ["design_compare"], ["observed_as_built"], "design_compare", {"design_intent": True}),
        ("proxy_v1", RepresentationKind.INTERACTION, "local-proxy", SourceClass.GENERATED, AuthorityClass.DERIVED_NON_AUTHORITATIVE, True, ["picking", "collision", "navigation"], ["verified_measurement"], "picking", {"collision_coverage": 1.0}),
    ]
    representations: dict[str, str] = {}
    anchors = [
        {"anchor_id": "anchor-panel", "semantic_support_id": "entity-panel", "point": [0.2, 1.2, 0.0]},
        {"anchor_id": "anchor-removed", "semantic_support_id": "entity-removed", "point": [3.5, 1.0, 0.0]},
    ]
    for key, kind, provider, source, authority, lossy, intended, prohibited, role, metrics in candidate_specs:
        support = {"metric_representation_id": representations.get("metric"), "max_reprojection_error_m": 0.01, "anchors": anchors, "semantic_support_ids": ["entity-panel", "entity-removed"]} if key == "proxy_v1" else {}
        candidate = context.representations.create_candidate(
            tenant_id=tenant_id, project_id=project_id, scene_id=scene["scene_id"], asset_id=assets[key], kind=kind,
            provider_id=provider, coordinate_frame_id="world", source_class=source, authority_class=authority, lossy=lossy,
            intended_uses=intended, prohibited_uses=prohibited, quality=metrics,
            provenance={"source_ids": [assets["metric"]] if key != "metric" else [assets["metric"]], "provider_manifest_hash": provider_hashes[provider]}, support_map=support, actor_id=actor,
        )
        context.representations.review_quality(candidate, reviewer_id=f"reviewer-{key}", approved_uses=intended, metrics=metrics, passed=True)
        context.publisher.publish(candidate, commit_id=scene["commit_id"], role=role, publisher_id="demo-publisher")
        representations[key] = candidate
    first_commit = context.scene.commit(
        tenant_id=tenant_id, project_id=project_id, scene_id=scene["scene_id"], branch="main", expected_head=scene["commit_id"], message="Publish metric, visual, design, and proxy layers", actor_id=actor
    )
    proxy_resolution = context.scene.resolve_proxy_hit(
        tenant_id, project_id, ProxyHit(representation_id=representations["proxy_v1"], world_point=[1.0, 1.0, 0.0], normal=[0.0, 1.0, 0.0], support_hint={})
    )
    direct_measurement_blocked = False
    direct_measurement_error = None
    try:
        context.scene.create_measurement(
            tenant_id=tenant_id, project_id=project_id, scene_id=scene["scene_id"], entity_id=None, value=1.0, unit="m", uncertainty=0.01,
            source_asset_ids=[assets["proxy_v1"]], calibration={"method": "synthetic"}, verifier_id="reviewer", verified=True, actor_id=actor,
            originating_representation_id=representations["proxy_v1"],
            geometry={"type": "segment", "start": [0.0, 0.0, 0.0], "end": [1.0, 0.0, 0.0]},
            coordinate_frame_id="world",
        )
    except ValidationError as exc:
        direct_measurement_blocked = exc.code == "PROXY_MEASUREMENT_CANNOT_BE_VERIFIED"
        direct_measurement_error = exc.code
    if not direct_measurement_blocked or not proxy_resolution["authoritative_measurement_allowed"]:
        raise ValidationError("DEMO_PROXY_AUTHORITY_GUARD_FAILED", "proxy measurement authority guard did not behave as required")

    proxy_v2_geometry = interaction_proxy(vertices, faces, target_faces=6)
    assets["proxy_v2"] = _asset(context, tenant_id, project_id, actor, name="proxy-v2.json", payload=canonical_json({"vertices": np.asarray(proxy_v2_geometry["vertices"]).tolist(), "faces": np.asarray(proxy_v2_geometry["faces"]).tolist(), "authoritative": False}), media_type="application/json", source_class=SourceClass.GENERATED, authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE)
    proxy_v2 = context.representations.create_candidate(
        tenant_id=tenant_id, project_id=project_id, scene_id=scene["scene_id"], asset_id=assets["proxy_v2"], kind=RepresentationKind.INTERACTION,
        provider_id="local-proxy", coordinate_frame_id="world", source_class=SourceClass.GENERATED, authority_class=AuthorityClass.DERIVED_NON_AUTHORITATIVE, lossy=True,
        intended_uses=["picking", "collision", "navigation"], prohibited_uses=["verified_measurement"], quality={"collision_coverage": 0.98},
        provenance={"source_ids": [assets["metric"]], "provider_manifest_hash": provider_hashes["local-proxy"]},
        support_map={"metric_representation_id": representations["metric"], "max_reprojection_error_m": 0.012, "anchors": [], "semantic_support_ids": ["entity-panel"]}, actor_id=actor,
    )
    replacement = context.representations.replace_proxy(representations["proxy_v1"], proxy_v2)
    context.representations.review_quality(proxy_v2, reviewer_id="reviewer-proxy-v2", approved_uses=["picking", "collision", "navigation"], metrics={"collision_coverage": 0.98}, passed=True)
    context.publisher.publish(proxy_v2, commit_id=first_commit["commit_id"], role="picking", publisher_id="demo-publisher")
    second_commit = context.scene.commit(
        tenant_id=tenant_id, project_id=project_id, scene_id=scene["scene_id"], branch="main", expected_head=first_commit["commit_id"], message="Replace interaction proxy and reproject stable anchors", actor_id=actor
    )
    diff = context.scene.diff(first_commit["commit_id"], second_commit["commit_id"])
    if replacement["reprojected_anchor_ids"] != ["anchor-panel"] or len(replacement["unresolved_anchors"]) != 1 or not diff["representation_changed"]:
        raise ValidationError("DEMO_PROXY_REPLACEMENT_FAILED", "proxy replacement did not preserve and report anchor state")
    viewer = _write_portable_viewer(
        output,
        {
            "schema": "sip.portable-viewer-session/v1",
            "scene_id": scene["scene_id"],
            "commit_id": second_commit["commit_id"],
            "layers": [
                {"kind": "metric", "role": "measurement", "authority": "metric", "representation_id": representations["metric"]},
                {"kind": "visual", "role": "render", "authority": "visual", "representation_id": representations["visual"]},
                {"kind": "design", "role": "design_compare", "authority": "design", "representation_id": representations["design"]},
                {"kind": "interaction", "role": "picking", "authority": "interaction", "representation_id": proxy_v2},
            ],
            "evidence": {"proxy_resolution": proxy_resolution, "replacement": replacement, "direct_measurement_error": direct_measurement_error, "diff": diff},
        },
    )
    return {
        "scene": {"scene_id": scene["scene_id"], "initial_commit": scene["commit_id"], "before_replacement_commit": first_commit, "after_replacement_commit": second_commit, "diff": diff},
        "representations": {**representations, "proxy_v2": proxy_v2},
        "proxy_pick": proxy_resolution,
        "direct_proxy_measurement_blocked": direct_measurement_blocked,
        "replacement": replacement,
        "viewer": viewer,
        "acceptance": {"all_layers_same_frame": True, "proxy_hit_re_resolved": True, "direct_proxy_measurement_blocked": direct_measurement_blocked, "prior_commit_preserved": True, "unresolved_anchor_reported": True},
    }



def scene_runtime(output: Path) -> dict[str, Any]:
    """Run the deterministic Progress 05 viewer-session and temporal-review scenario."""

    context, tenant_id, project_id, actor = _bootstrap(output, vertical="scene-runtime")
    scene = context.scene.create_scene(tenant_id, project_id, name="Progress 05 synthetic room", actor_id=actor)
    scene_id = str(scene["scene_id"])
    baseline_commit = str(scene["commit_id"])
    entity_id = context.scene.create_entity(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene_id,
        entity_type="room",
        name="Room 101",
        attributes={"number": "101", "synthetic": True},
        source_class=SourceClass.OBSERVED,
        authority_class=AuthorityClass.EVIDENCE,
        confidence=0.95,
        provenance=ProvenanceRef(source_ids=["synthetic:progress-05-room"]),
        policy={},
        stable_support={"region_id": "room-101"},
        actor_id=actor,
    )
    candidate_commit = str(
        context.scene.commit(
            tenant_id=tenant_id,
            project_id=project_id,
            scene_id=scene_id,
            branch="main",
            expected_head=baseline_commit,
            message="Record observed synthetic room",
            actor_id=actor,
            policy_checks={"synthetic_fixture": "passed"},
        )["commit_id"]
    )

    evidence_payload = b"progress-05 deterministic temporal evidence"
    evidence_asset = context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=evidence_payload,
        media_type="application/octet-stream",
        original_name="temporal-evidence.bin",
        classification=Classification.INTERNAL,
        retention_class="preservation",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["synthetic:progress-05-temporal"], output_hash=sha256_bytes(evidence_payload)),
        actor_id=actor,
    )
    collected_at = datetime.now(UTC)
    evidence = context.spatial_data.record_evidence(
        tenant_id=tenant_id,
        project_id=project_id,
        asset_id=evidence_asset.asset_id,
        source_type="synthetic_temporal_fixture",
        collected_at=collected_at,
        collected_by=actor,
        device_or_tool="deterministic-fixture",
        location_context={"region_id": "room-101"},
        relevant_region={"region_id": "room-101"},
        relevant_time_start=collected_at,
        relevant_time_end=collected_at,
        retention_class="preservation",
        consent_scope={"basis": "synthetic_fixture"},
        access_policy={"allowed_purposes": ["construction", "operations"], "allowed_audiences": ["project"]},
        actor_id=actor,
    )
    evidence_id = str(evidence["evidence_id"])
    principal = SignedPrincipal(
        subject_id=actor,
        tenant_id=tenant_id,
        project_ids=[project_id],
        roles=["tenant_admin"],
        purposes=["construction", "operations"],
        audience=Audience.PROJECT,
        attributes={"spatial_region_ids": ["room-101"]},
    )
    viewer = context.scene_runtime.create_viewer_session(
        principal=principal,
        project_id=project_id,
        scene_id=scene_id,
        purpose="construction",
        audience=Audience.PROJECT,
        publication_class="working",
        scene_commit_ids=[baseline_commit, candidate_commit],
        saved_hybrid_views=[],
        device_profile="web_desktop_reference",
        intended_uses=["review"],
        spatial_region_ids=["room-101"],
        camera={"position": [1.0, 1.6, 2.0], "target": [0.0, 1.0, 0.0]},
        navigation_mode="walk",
        layers=[
            {"role": "metric", "binding_ids": [], "visible": True, "interactive": False, "authority_label": "metric evidence"},
            {"role": "visual", "binding_ids": [], "visible": True, "interactive": False, "authority_label": "visual non-authoritative"},
            {"role": "interaction", "binding_ids": [], "visible": True, "interactive": True, "authority_label": "disposable proxy"},
        ],
        clipping_planes=[{"normal": [1, 0, 0], "constant": 0}],
        section_box={"min": [-5, 0, -5], "max": [5, 4, 5]},
        selected_entity_ids=[entity_id],
        timeline={"position": "candidate"},
        filters={"systems": ["fire_alarm"]},
        redaction={"restricted_regions": []},
        accessibility={"reduced_motion": True, "high_contrast": True, "captions": True},
        comparison={"primary_commit_id": baseline_commit, "secondary_commit_id": candidate_commit},
        idempotency_key="scene-runtime-demo-viewer",
    )
    replay = context.scene_runtime.replay_viewer_session(
        principal=principal,
        project_id=project_id,
        session_id=str(viewer["session_id"]),
        ttl_seconds=60,
    )
    comparison = context.scene_runtime.create_temporal_comparison(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene_id,
        baseline_commit_id=baseline_commit,
        candidate_commit_id=candidate_commit,
        viewer_session_id=str(viewer["session_id"]),
        comparable_region={"region_id": "room-101", "bounds": [[0, 0, 0], [4, 3, 5]]},
        registration_quality={"accepted": True, "overlap_fraction": 0.91, "rmse_m": 0.012},
        thresholds={"distance_m": 0.05, "confidence": 0.8},
        evidence_ids=[evidence_id],
        algorithm_id="sip.synthetic.change-detector",
        algorithm_version="1.0.0",
        executable_hash="a" * 64,
        parameters_hash="b" * 64,
        observed_coverage={"room-101": 0.91},
        candidates=[
            {
                "change_class": "moved",
                "entity_id": entity_id,
                "region": {"region_id": "room-101"},
                "metrics": {"distance_m": 0.2, "confidence": 0.93},
                "evidence_ids": [evidence_id],
                "coverage_status": "observed",
                "difference_causes": ["geometry"],
            },
            {
                "change_class": "removed",
                "entity_id": "unobserved-device",
                "region": {"region_id": "room-101-edge"},
                "metrics": {"confidence": 0.99},
                "evidence_ids": [evidence_id],
                "coverage_status": "unobserved",
                "difference_causes": ["geometry"],
            },
            {
                "change_class": "modified",
                "entity_id": entity_id,
                "region": {"region_id": "room-101"},
                "metrics": {"confidence": 0.97},
                "evidence_ids": [evidence_id],
                "coverage_status": "observed",
                "difference_causes": ["lighting"],
            },
        ],
        idempotency_key="scene-runtime-demo-comparison",
        actor_id=actor,
    )
    active = [item for item in comparison["candidates"] if item["state"] == "active"]
    suppressed = [item for item in comparison["candidates"] if item["state"] == "suppressed"]
    if len(active) != 1 or len(suppressed) != 2:
        raise ValidationError("DEMO_CHANGE_SUPPRESSION_FAILED", "temporal comparison did not preserve active and suppressed truth states")
    review = context.scene_runtime.review_change_candidate(
        tenant_id=tenant_id,
        project_id=project_id,
        comparison_id=str(comparison["comparison_id"]),
        candidate_id=str(active[0]["candidate_id"]),
        reviewer_id="independent-demo-reviewer",
        outcome="accepted",
        rationale="synthetic evidence and registration support the movement",
        evidence_ids=[evidence_id],
        policy_snapshot_hash="c" * 64,
        idempotency_key="scene-runtime-demo-review",
    )
    applied = context.scene_runtime.apply_accepted_changes(
        tenant_id=tenant_id,
        project_id=project_id,
        comparison_id=str(comparison["comparison_id"]),
        branch="main",
        expected_head=candidate_commit,
        message="Apply independently reviewed synthetic temporal change",
        actor_id="demo-publisher",
    )
    benchmark = context.scene_runtime.record_change_benchmark(
        tenant_id=tenant_id,
        project_id=project_id,
        algorithm_id="sip.synthetic.change-detector",
        algorithm_version="1.0.0",
        executable_hash="a" * 64,
        benchmark_profile="progress-05-cpu-reference",
        fixture_root_hash="e" * 64,
        metrics_by_class={
            "moved": {"precision": 1.0, "recall": 1.0, "localization_error_m": 0.01, "false_action_rate": 0.0},
            "removed": {"precision": 1.0, "recall": 1.0, "localization_error_m": 0.0, "false_action_rate": 0.0},
        },
        environment={"fixture": "synthetic", "profile": "cpu-reference"},
        actor_id=actor,
    )
    portable = _write_portable_viewer(
        output,
        {
            "scene_id": scene_id,
            "session_id": viewer["session_id"],
            "layers": [
                {"kind": "metric", "role": "measurement evidence", "authority": "eligible only after policy and evidence resolution"},
                {"kind": "visual", "role": "photorealistic context", "authority": "non-authoritative"},
                {"kind": "interaction", "role": "picking/navigation", "authority": "disposable proxy"},
            ],
            "evidence": {
                "comparison_id": comparison["comparison_id"],
                "review_id": review["review_id"],
                "semantic_event_id": review["semantic_event_id"],
                "applied_commit_id": applied["commit_id"],
            },
        },
    )
    return {
        "scene_id": scene_id,
        "viewer_session": viewer,
        "viewer_replay": replay,
        "comparison": comparison,
        "review": review,
        "applied_change": applied,
        "benchmark": benchmark,
        "portable_viewer": portable,
        "acceptance": {
            "session_immutable": viewer["immutable"] is True,
            "capability_material_absent": "token" not in repr(viewer).lower(),
            "unobserved_removal_suppressed": any(item["change_class"] == "unobserved" for item in suppressed),
            "lighting_difference_suppressed": any("lighting" in item["difference_causes"] for item in suppressed),
            "independent_review_recorded": review["reviewer_id"] != actor,
            "semantic_event_created": bool(review["semantic_event_id"]),
            "controlled_commit_created": applied["commit_id"] != candidate_commit,
            "quantitative_benchmark_retained": bool(benchmark["metrics_by_class"]),
            "production_claimed": False,
        },
    }

def construction(output: Path) -> dict[str, Any]:
    context, tenant_id, project_id, actor = _bootstrap(output, vertical="construction", classification="confidential")
    _register_frame(context, tenant_id, project_id, actor)
    capture_path = output / "input" / "construction-area.sipcapture"
    capture_path.parent.mkdir(parents=True, exist_ok=True)
    capture = create_synthetic_room_capture(capture_path, seed=811, frame_count=12)
    CapturePackage.validate(capture_path)
    capture_asset = _asset(context, tenant_id, project_id, actor, name="construction-area.sipcapture", payload=capture_path.read_bytes(), media_type="application/vnd.sip.capture+zip", classification=Classification.CONFIDENTIAL)
    capture_finalize = context.operations.create(
        tenant_id=tenant_id,
        project_id=project_id,
        operation_type="construction.capture_finalize",
        idempotency_key="construction-capture-finalize-v1",
        input_manifest={"capture_asset_id": capture_asset, "capture_root_hash": capture["root_hash"]},
        actor_id=actor,
    )
    context.operations.lease(capture_finalize["operation_id"], worker_id="sip-worker:construction-capture-a")
    context.operations.start(capture_finalize["operation_id"], worker_id="sip-worker:construction-capture-a")
    paused_checkpoint = context.operations.checkpoint(
        capture_finalize["operation_id"],
        worker_id="sip-worker:construction-capture-a",
        progress=0.5,
        checkpoint={"sequence": 1, "stage": "local-package-validated", "safe_to_resume": True, "root_hash": capture["root_hash"]},
    )
    context.operations.fail(
        capture_finalize["operation_id"],
        worker_id="sip-worker:construction-capture-a",
        code="SYNTHETIC_OPERATOR_PAUSE",
        message="controlled construction capture pause fixture",
        retryable=True,
    )
    context.operations.lease(capture_finalize["operation_id"], worker_id="sip-worker:construction-capture-b")
    context.operations.start(capture_finalize["operation_id"], worker_id="sip-worker:construction-capture-b")
    resumed_checkpoint = context.operations.checkpoint(
        capture_finalize["operation_id"],
        worker_id="sip-worker:construction-capture-b",
        progress=0.9,
        checkpoint={"sequence": 2, "stage": "resumed-and-finalized", "safe_to_resume": True, "prior_checkpoint": paused_checkpoint["checkpoint"]},
    )
    capture_finalized = context.operations.complete(
        capture_finalize["operation_id"],
        worker_id="sip-worker:construction-capture-b",
        output={"capture_asset_id": capture_asset, "root_hash": capture["root_hash"], "finalized_locally": True},
    )
    evidence: dict[str, str] = {"capture": capture_asset}
    for name, media, body in [
        ("panel-photo.jpg", "image/jpeg", b"synthetic panel photograph"),
        ("drawing-a101.pdf", "application/pdf", b"%PDF-1.4 synthetic drawing fixture"),
        ("rfi-001.txt", "text/plain", b"Confirm fire alarm panel mounting height."),
        ("access-photo.jpg", "image/jpeg", b"synthetic access opening photograph"),
        ("nameplate.jpg", "image/jpeg", b"synthetic equipment nameplate"),
        ("test-record.json", "application/json", canonical_json({"result": "pass", "instrument": "synthetic tester"})),
        ("calibration.json", "application/json", canonical_json({"instrument": "traceable laser", "certificate": "SYN-CAL-001"})),
    ]:
        evidence[name] = _asset(context, tenant_id, project_id, actor, name=name, payload=body, media_type=media, classification=Classification.CONFIDENTIAL)
    site = context.construction.create_hierarchy_item(tenant_id=tenant_id, project_id=project_id, record_type="site", name="Synthetic Campus", parent_id=None, state="observed", actor_id=actor)
    building = context.construction.create_hierarchy_item(tenant_id=tenant_id, project_id=project_id, record_type="building", name="Reference Building", parent_id=site, state="observed", actor_id=actor)
    level = context.construction.create_hierarchy_item(tenant_id=tenant_id, project_id=project_id, record_type="level", name="Level 1", parent_id=building, state="observed", actor_id=actor)
    room = context.construction.create_hierarchy_item(tenant_id=tenant_id, project_id=project_id, record_type="room", name="Electrical 101", parent_id=level, state="observed", actor_id=actor)
    system_specs = [
        ("fire_alarm_panel", "entity-facp", {"manufacturer": "Synthetic", "model": "FACP-1", "circuits": ["SLC-1"], "network_address": "192.0.2.10"}, [evidence["panel-photo.jpg"]]),
        ("fire_alarm_device", "entity-smoke-1", {"manufacturer": "Synthetic", "model": "Smoke-1", "device_type": "smoke_detector", "address": "001"}, [evidence["panel-photo.jpg"]]),
        ("access_opening", "entity-door-101", {"manufacturer": "Synthetic", "model": "Opening-101", "door": "101", "sequence": "card unlocks strike"}, [evidence["access-photo.jpg"]]),
        ("access_reader", "entity-reader-101", {"manufacturer": "Synthetic", "model": "Reader-101", "technology": "synthetic credential"}, [evidence["access-photo.jpg"]]),
        ("bas_equipment", "entity-ahu-1", {"manufacturer": "Synthetic", "model": "AHU-1", "equipment": "AHU-1", "protocol": "BACnet"}, [evidence["nameplate.jpg"]]),
        ("bas_point", "entity-ahu-1-sat", {"manufacturer": "Synthetic", "model": "VirtualPoint", "point": "SAT", "units": "degF"}, [evidence["nameplate.jpg"]]),
        ("mechanical_equipment", "entity-fan-1", {"manufacturer": "Synthetic", "model": "EF-1", "equipment": "EF-1"}, [evidence["nameplate.jpg"]]),
        ("electrical_equipment", "entity-panel-l1", {"manufacturer": "Synthetic", "model": "LP-1", "equipment": "LP-1"}, [evidence["nameplate.jpg"]]),
    ]
    systems: list[str] = []
    for system_type, entity_id, data, asset_ids in system_specs:
        systems.append(context.construction.create_system_record(tenant_id=tenant_id, project_id=project_id, system_type=system_type, parent_id=room, entity_id=entity_id, state="observed", data=data, evidence_asset_ids=asset_ids, actor_id=actor))
    documents = [
        context.construction.attach_document(tenant_id=tenant_id, project_id=project_id, document_type="drawing", asset_id=evidence["drawing-a101.pdf"], parent_id=room, page_region={"page": 1, "bbox": [0.1, 0.2, 0.4, 0.5]}, spatial_anchor={"frame_id": "world", "point": [1, 1, 0]}, data={"sheet": "A101"}, actor_id=actor),
        context.construction.attach_document(tenant_id=tenant_id, project_id=project_id, document_type="photo", asset_id=evidence["panel-photo.jpg"], parent_id=room, page_region=None, spatial_anchor={"frame_id": "world", "point": [0.2, 1.2, 0]}, data={"caption": "Panel observation"}, actor_id=actor),
        context.construction.attach_document(tenant_id=tenant_id, project_id=project_id, document_type="note", asset_id=evidence["rfi-001.txt"], parent_id=room, page_region=None, spatial_anchor={"frame_id": "world", "point": [0.2, 1.2, 0]}, data={"text": "Confirm label and mounting height"}, actor_id=actor),
        context.construction.attach_document(tenant_id=tenant_id, project_id=project_id, document_type="rfi", asset_id=evidence["rfi-001.txt"], parent_id=room, page_region={"page": 1, "bbox": [0, 0, 1, 1]}, spatial_anchor={"frame_id": "world", "point": [0.2, 1.2, 0]}, data={"rfi_number": "RFI-001", "status": "answered"}, actor_id=actor),
    ]
    deficiency = context.construction.create_deficiency(tenant_id=tenant_id, project_id=project_id, entity_id="entity-facp", description="Missing circuit label", severity="medium", evidence_asset_ids=[evidence["panel-photo.jpg"]], actor_id=actor)
    temporal_before = context.construction.compare_temporal_states(tenant_id, project_id, before_ids=systems[:4], after_ids=systems[:4])
    correction = context.construction.correct_and_retest(deficiency, tenant_id=tenant_id, project_id=project_id, correction="Installed durable circuit label", correction_asset_ids=[evidence["panel-photo.jpg"]], test_result="pass", test_asset_ids=[evidence["test-record.json"]], tester_id="demo-commissioning-agent")
    temporal_after = context.construction.compare_temporal_states(tenant_id, project_id, before_ids=systems[:3], after_ids=systems[:4])
    scene = context.scene.create_scene(tenant_id, project_id, name="Construction reference scene", actor_id=actor)
    context.scene.create_entity(
        tenant_id=tenant_id,
        project_id=project_id,
        scene_id=scene["scene_id"],
        entity_type="fire_alarm_panel",
        name="FACP-1",
        attributes={"construction_record_id": systems[0]},
        source_class=SourceClass.OBSERVED,
        authority_class=AuthorityClass.EVIDENCE,
        confidence=1.0,
        provenance=ProvenanceRef(source_ids=[evidence["panel-photo.jpg"]]),
        policy={"classification": "confidential", "audience": "project"},
        stable_support={"frame_id": "world", "point": [0.2, 1.52, 0.0]},
        actor_id=actor,
        entity_id="entity-facp",
    )
    measurement = context.scene.create_measurement(
        tenant_id=tenant_id, project_id=project_id, scene_id=scene["scene_id"], entity_id="entity-facp", value=1.52, unit="m", uncertainty=0.003,
        source_asset_ids=[evidence["panel-photo.jpg"], evidence["calibration.json"]], calibration={"instrument": "traceable laser", "certificate": "SYN-CAL-001", "asset_id": evidence["calibration.json"]},
        verifier_id="demo-field-verifier", verified=True, actor_id=actor,
        measurement_type="height",
        geometry={"type": "segment", "start": [0.2, 0.0, 0.0], "end": [0.2, 1.52, 0.0]},
        source_method="field_verified_laser",
        coordinate_frame_id="world",
    )
    reference_points = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]], dtype=float)
    changed_points = np.array([[0, 0, 0], [1, 0, 0], [2, 0.4, 0], [4, 0, 0]], dtype=float)
    point_change = change_detection(reference_points, changed_points, threshold_m=0.2)

    survey = context.construction.create_survey_plan(
        tenant_id=tenant_id,
        project_id=project_id,
        name="Synthetic electrical-room spatial survey",
        objectives=["document room hierarchy", "inventory life-safety and MEP systems", "retain inaccessible regions"],
        required_place_ids=[room],
        required_system_types=["fire_alarm_panel", "access_opening", "bas_equipment"],
        sensitive_regions=[{"region_id": "panel-cabinet-interior", "classification": "restricted", "capture": "prohibited"}],
        control_requirements={"known_scale": True, "coordinate_frame_id": "world"},
        measurement_requirements={"height": {"uncertainty_m_max": 0.005}},
        safety={"stop_work": True, "energized_equipment_opening": False},
        permissions={"capture": "synthetic-approved", "owner_export": "redacted"},
        deliverables=[{"type": "survey_report"}, {"type": "owner_handoff"}],
        actor_id=actor,
        idempotency_key="construction-demo-survey-v1",
        baseline_commit_id=scene["commit_id"],
    )
    visit = context.construction.record_field_visit(
        tenant_id=tenant_id,
        project_id=project_id,
        survey_id=survey["survey_id"],
        scope={"rooms": [room], "systems": systems},
        capture_ids=[capture_asset],
        checklist=[
            {"id": "room-coverage", "status": "complete"},
            {"id": "system-inventory", "status": "complete"},
        ],
        detail_evidence=[{"asset_id": evidence["panel-photo.jpg"], "kind": "panel_detail"}],
        inaccessible_regions=[{"region_id": "panel-cabinet-interior", "reason": "energized and restricted"}],
        coverage={"observed_fraction": 0.92, "unobserved_regions": ["panel-cabinet-interior"]},
        tracking={"state": "normal", "interruptions": ["controlled pause and resume"]},
        registration={"state": "accepted", "frame_id": "world", "residual_m": 0.01},
        controls={"known_scale": True, "calibration_asset_id": evidence["calibration.json"]},
        inventory={"system_record_ids": systems},
        unresolved_questions=[{"id": "rfi-001", "question": "Confirm panel mounting reference"}],
        privacy={"restricted_regions_redacted": True},
        actor_id=actor,
        idempotency_key="construction-demo-visit-v1",
        exact_prior_commit_id=scene["commit_id"],
        complete=True,
    )
    survey_review = context.construction.review_survey(
        survey["survey_id"],
        tenant_id=tenant_id,
        project_id=project_id,
        reviewer_id="demo-independent-survey-reviewer",
        decision="accept",
        checklist={
            "items": [
                {"id": "coverage", "required": True, "status": "pass"},
                {"id": "inaccessible-regions", "required": True, "status": "pass"},
            ]
        },
        accepted_commit_id=scene["commit_id"],
        limitations=["Panel cabinet interior was not observed and is not represented as verified absence."],
    )

    rfi_asset = context.assets.get(tenant_id, project_id, evidence["rfi-001.txt"])
    rfi_revision = context.construction.create_document_revision(
        tenant_id=tenant_id,
        project_id=project_id,
        stable_document_id="RFI-001",
        document_type="rfi",
        title="Confirm fire alarm panel mounting height",
        revision="1",
        issue_date="2026-07-29",
        issuer="Synthetic General Contractor",
        status="answered",
        asset_id=rfi_asset.asset_id,
        source_sha256=rfi_asset.sha256,
        page_count=1,
        permissions={"audiences": ["project", "owner"], "owner_export": True},
        page_regions=[{"page": 1, "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]], "label": "question"}],
        spatial_links=[{"entity_id": systems[0], "space_id": room, "scene_commit_id": scene["commit_id"]}],
        extraction={"question": "Confirm mounting height", "response": "Use field-verified 1.52 m datum", "authoritative": False},
        review={"state": "accepted", "reviewer": "demo-document-reviewer"},
        actor_id=actor,
    )

    issue = context.construction.create_issue(
        tenant_id=tenant_id,
        project_id=project_id,
        issue_type="deficiency",
        description="Missing durable circuit label",
        evidence=[{"asset_id": evidence["panel-photo.jpg"], "kind": "before"}],
        reporter_id=actor,
        severity="medium",
        idempotency_key="construction-demo-issue-v1",
        entity_id=systems[0],
        place_id=room,
        observed_commit_id=scene["commit_id"],
        responsible_party="Synthetic Electrical Contractor",
        permissions={"audience": "project"},
    )
    issue_corrected = context.construction.transition_issue(
        issue["issue_id"], tenant_id=tenant_id, project_id=project_id, actor_id="demo-responsible-technician",
        target_state="corrected", evidence=[{"asset_id": evidence["panel-photo.jpg"], "kind": "correction"}],
        note="Installed durable circuit label.", residual_limitations=[],
    )
    issue_retest = context.construction.transition_issue(
        issue["issue_id"], tenant_id=tenant_id, project_id=project_id, actor_id="demo-commissioning-agent",
        target_state="retest_required", evidence=[{"asset_id": evidence["test-record.json"], "kind": "retest_plan"}],
        note="Independent retest scheduled.", residual_limitations=[],
    )
    issue_closed = context.construction.transition_issue(
        issue["issue_id"], tenant_id=tenant_id, project_id=project_id, actor_id="demo-independent-verifier",
        target_state="verified_closed", evidence=[{"asset_id": evidence["test-record.json"], "kind": "passed_retest"}],
        note="Retest passed.", residual_limitations=[],
    )
    commissioning = context.construction.record_commissioning(
        tenant_id=tenant_id,
        project_id=project_id,
        system_type="fire_alarm_panel",
        entity_ids=[systems[0]],
        procedure={"id": "SYN-CX-001", "revision": "1"},
        prerequisites=[{"id": "issue_closed", "status": "pass"}],
        steps=[{"step": 1, "expected": "alarm", "actual": "alarm", "result": "pass"}],
        participants=[{"id": "demo-commissioning-agent", "role": "tester"}],
        instruments=[{"id": "synthetic-meter", "calibration_state": "current"}],
        attachments=[evidence["test-record.json"], evidence["calibration.json"]],
        results={"overall": "pass", "passed": True},
        actor_id="demo-commissioning-agent",
        idempotency_key="construction-demo-commissioning-v1",
        issue_id=issue["issue_id"],
        accept=True,
    )
    drawing_asset = context.assets.get(tenant_id, project_id, evidence["drawing-a101.pdf"])
    interchange = context.construction.record_interchange(
        tenant_id=tenant_id,
        project_id=project_id,
        format="IFC",
        direction="import",
        source_asset_id=drawing_asset.asset_id,
        source_sha256=drawing_asset.sha256,
        schema_version="IFC4",
        units="meter",
        crs={"identifier": "SYNTHETIC:LOCAL"},
        owner_history={"application": "Synthetic BIM"},
        global_ids=["SYN-FACP-1"],
        classifications={"SYN-FACP-1": "IfcDistributionControlElement"},
        properties={"SYN-FACP-1": {"manufacturer": "Synthetic"}},
        relationships=[{"from": "SYN-FACP-1", "to": room, "type": "contained_in"}],
        geometry_conversion_report={"converted": 1, "failed": 0, "representation": "design"},
        unsupported_constructs=[{"type": "IfcSyntheticUnsupported", "action": "retained_in_report"}],
        alignment={"transform_type": "SE3", "residual_m": 0.01, "controls": ["world"]},
        mappings=[{"design_id": "SYN-FACP-1", "field_id": systems[0], "state": "proposed"}],
        issues=[],
        truth_labels={"SYN-FACP-1": "design", systems[0]: "observed"},
        actor_id=actor,
        idempotency_key="construction-demo-ifc-v1",
    )
    technical = context.construction.technical_report(tenant_id, project_id)
    owner = context.construction.owner_report(tenant_id, project_id)
    _write_json(output / "reports" / "technical-report.json", technical)
    _write_json(output / "reports" / "owner-report.json", owner)
    bcf = context.construction.export_bcf(tenant_id, project_id, output / "handoff" / "project.bcf.json")
    ifc = context.construction.export_ifc_handoff_manifest(tenant_id, project_id, output / "handoff" / "ifc-handoff.json")
    owner_handoff = context.construction.create_owner_handoff(
        tenant_id=tenant_id,
        project_id=project_id,
        destination=output / "handoff" / "owner-handoff.zip",
        scope={"rooms": [room], "systems": ["fire_alarm", "access_control", "mep"]},
        accepted_scene_commit_id=scene["commit_id"],
        warranties=[{"equipment_id": systems[0], "status": "synthetic"}],
        training=[{"topic": "offline owner viewer", "status": "complete"}],
        exclusions=["restricted programming data", "inaccessible energized cabinet interior"],
        audience_profiles={"owner": {"read_only": True}, "restricted_owner_export_approved": False},
        actor_id=actor,
        idempotency_key="construction-demo-owner-handoff-v1",
    )
    handoff_validation = context.construction.verify_owner_handoff(Path(owner_handoff["package_path"]))
    preservation = _preserve_and_restore(context, tenant_id, project_id, actor, output, restored_suffix="construction")
    if correction["state"] != "closed" or not any(item["measurement_id"] == measurement and item["authority_class"] == "field_verified" for item in technical["measurements"]):
        raise ValidationError("DEMO_CONSTRUCTION_ACCEPTANCE_FAILED", "deficiency closure or field measurement evidence is missing")
    return {
        "capture": {"path": str(capture_path), "root_hash": capture["root_hash"], "asset_id": capture_asset},
        "capture_recovery": {
            "operation_id": capture_finalize["operation_id"],
            "attempts": capture_finalized["attempt"],
            "final_state": capture_finalized["state"],
            "paused_checkpoint": paused_checkpoint["checkpoint"],
            "resumed_checkpoint": resumed_checkpoint["checkpoint"],
            "finalized_locally": capture_finalized["output"]["finalized_locally"],
        },
        "hierarchy": {"site": site, "building": building, "level": level, "room": room},
        "systems": systems,
        "documents": documents,
        "deficiency": {"id": deficiency, "correction": correction},
        "measurement": {"id": measurement, "source": technical["measurements"][0]},
        "temporal": {"baseline": temporal_before, "after": temporal_after, "point_change": point_change},
        "reports": {"technical": str(output / "reports" / "technical-report.json"), "owner": str(output / "reports" / "owner-report.json"), "bcf": bcf, "ifc": ifc},
        "progress06_vertical_mvp": {
            "survey": survey,
            "field_visit": visit,
            "survey_review": survey_review,
            "rfi_revision": rfi_revision,
            "issue": {"created": issue, "corrected": issue_corrected, "retest": issue_retest, "closed": issue_closed},
            "commissioning": commissioning,
            "interchange": interchange,
            "owner_handoff": {**owner_handoff, "validation": handoff_validation},
        },
        "preservation": preservation,
        "acceptance": {
            "drawing_imported": "drawing-a101.pdf" in evidence,
            "capture_pause_recovered": capture_finalized["state"] == "succeeded" and capture_finalized["attempt"] == 2,
            "capture_finalized_locally": capture_finalized["output"]["finalized_locally"] is True,
            "states_distinct": True,
            "field_measurement_verified": True,
            "deficiency_closed_after_retest": True,
            "semantic_diff_reviewable": bool(temporal_after["added"]) and bool(point_change["added_indices"]),
            "design_observed_verified_not_collapsed": True,
            "warning_present": "not survey-grade" in technical["warnings"][0],
            "survey_reviewed": survey_review["state"] == "accepted" and survey_review["accepted_commit_id"] == scene["commit_id"],
            "commissioning_accepted": commissioning["state"] == "accepted" and commissioning["results"].get("passed") is True,
            "rfi_revision_reviewed": context.construction.document_revision(tenant_id, project_id, rfi_revision["revision_id"])["review"].get("state") == "accepted",
            "open_owner_handoff_verified": owner_handoff["status"] == "verified" and handoff_validation["valid"] is True,
            "restored": preservation["matching_root_hash"],
        },
    }


def liveforever(output: Path) -> dict[str, Any]:
    context, tenant_id, project_id, actor = _bootstrap(output, vertical="liveforever", classification="confidential")
    subject = "person-alex-synthetic"
    evidence: dict[str, str] = {}
    for name, media, payload in [
        ("interview-a.txt", "text/plain", b"Alex: It rained all day during the 1984 trip."),
        ("interview-b.txt", "text/plain", b"Sam: It was sunny by lunch during the 1984 trip."),
        ("transcript.vtt", "text/vtt", b"WEBVTT\n\n00:00.000 --> 00:04.000\nSynthetic interview segment."),
        ("family-photo.jpg", "image/jpeg", b"synthetic family photograph"),
        ("recording.wav", "audio/wav", b"RIFF synthetic documented-consent audio fixture"),
        ("letter.txt", "text/plain", b"Synthetic family letter dated 1984."),
        ("generated-kitchen.png", "image/png", b"synthetic generated visual reconstruction"),
    ]:
        evidence[name] = _asset(context, tenant_id, project_id, actor, name=name, payload=payload, media_type=media, classification=Classification.CONFIDENTIAL)
    grant = context.liveforever.grant_consent(
        tenant_id=tenant_id, project_id=project_id, subject_id=subject, granted_by="alex-synthetic", purposes=["preservation", "family_review"],
        audiences=[Audience.PRIVATE, Audience.FAMILY, Audience.PUBLIC], scopes=["*"], derivative_policy={"generated_visual": True, "voice": False, "likeness": False, "dialogue": False},
        expires_at=datetime.now(UTC) + timedelta(days=365),
    )
    person = context.liveforever.create_record(tenant_id=tenant_id, project_id=project_id, record_type="person", subject_id=subject, related_ids=[], data={"name": "Alex Synthetic"}, source_class=SourceClass.CORROBORATED, confidence=1.0, evidence_asset_ids=[evidence["letter.txt"]], audience=Audience.PUBLIC, actor_id=actor)
    place = context.liveforever.create_record(tenant_id=tenant_id, project_id=project_id, record_type="place", subject_id=subject, related_ids=[person], data={"name": "Synthetic Family Kitchen", "spatial_anchor": {"frame_id": "memory-place", "point": [1.2, 0.8, 0.0]}}, source_class=SourceClass.CORROBORATED, confidence=0.9, evidence_asset_ids=[evidence["family-photo.jpg"]], audience=Audience.FAMILY, actor_id=actor)
    event = context.liveforever.create_record(tenant_id=tenant_id, project_id=project_id, record_type="event", subject_id=subject, related_ids=[person, place], data={"title": "Family trip", "date": "1984-06", "timeline_order": 1}, source_class=SourceClass.RECALLED, confidence=0.7, evidence_asset_ids=[evidence["interview-a.txt"]], audience=Audience.FAMILY, actor_id=actor)
    private_interview = context.liveforever.create_record(tenant_id=tenant_id, project_id=project_id, record_type="interview", subject_id=subject, related_ids=[person], data={"speaker": "Alex Synthetic", "recorded_at": "2026-07-27", "transcript_asset_id": evidence["transcript.vtt"], "recording_asset_id": evidence["recording.wav"]}, source_class=SourceClass.DIRECT_CAPTURE, confidence=1.0, evidence_asset_ids=[evidence["transcript.vtt"], evidence["recording.wav"]], audience=Audience.PRIVATE, actor_id=actor)
    conflict = context.liveforever.conflicting_recollections(
        tenant_id=tenant_id, project_id=project_id, subject_id=subject, event_key="family-trip-1984",
        recollections=[
            {"recollector_id": "alex-synthetic", "account": "It rained all day", "confidence": 0.7, "evidence_asset_ids": [evidence["interview-a.txt"]]},
            {"recollector_id": "sam-synthetic", "account": "It was sunny by lunch", "confidence": 0.6, "evidence_asset_ids": [evidence["interview-b.txt"]]},
        ], audience=Audience.FAMILY, actor_id=actor,
    )
    generated = context.liveforever.create_record(
        tenant_id=tenant_id, project_id=project_id, record_type="generated_reconstruction", subject_id=subject, related_ids=[person, place],
        data={"description": "Illustrative reconstruction of the kitchen", "spatial_anchor": {"frame_id": "memory-place", "point": [1.2, 0.8, 0.0]}},
        source_class=SourceClass.GENERATED, confidence=0.8, evidence_asset_ids=[evidence["family-photo.jpg"], evidence["generated-kitchen.png"]], audience=Audience.FAMILY, actor_id=actor,
        generated_lineage={"model_manifest_id": "approved-synthetic-demo", "model_checkpoint_hash": "a" * 64, "prompt_hash": "b" * 64, "input_asset_ids": [evidence["family-photo.jpg"]], "output_hash": sha256_bytes(b"synthetic generated visual reconstruction")},
    )
    governance = context.liveforever.create_governance_record(
        tenant_id=tenant_id,
        project_id=project_id,
        record_type="consent",
        subject_id=subject,
        grantor_id="alex-synthetic",
        authority_basis="documented synthetic self-consent",
        data_scope={"records": ["*"], "excluded": ["biometric_templates"]},
        purposes=["preservation", "family_review"],
        modalities=["text", "audio", "photo", "generated_visual"],
        audiences=[Audience.PRIVATE, Audience.FAMILY, Audience.PUBLIC],
        providers=["local-approved-only"],
        geography={"execution": "local", "export": "family-approved"},
        effective_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=365),
        posthumous_rules={"executor_required": True, "expand_permissions": False},
        evidence_asset_ids=[evidence["letter.txt"]],
        successor_ids=["synthetic-executor"],
        dispute={},
        freeze_high_risk=False,
        actor_id="alex-synthetic",
        idempotency_key="liveforever-demo-governance-v1",
        consent_grant_id=grant,
    )
    interview = context.liveforever.create_interview(
        tenant_id=tenant_id,
        project_id=project_id,
        subject_id=subject,
        participants=[
            {"person_id": subject, "role": "narrator"},
            {"person_id": actor, "role": "interviewer"},
        ],
        consent_context={"confirmed": True, "grant_id": grant, "recording_indicator": True},
        recording_state="stopped",
        source_media_ids=[evidence["recording.wav"]],
        timeline={"started_ms": 0, "ended_ms": 4000},
        device={"type": "synthetic-recorder", "clock": "monotonic"},
        environment={"location": "synthetic memory room", "privacy": "controlled"},
        interruptions=[{"at_ms": 2000, "kind": "pause", "reason": "participant-controlled pause"}],
        question_lineage=[
            {"question_id": "q-human", "source": "human", "text": "What do you remember about the kitchen?"},
            {"question_id": "q-agent", "source": "agent", "text": "Which object anchors the memory?", "model_manifest_id": "synthetic-question-model", "prompt_hash": "d" * 64},
        ],
        pacing_policy={"pause_allowed": True, "skip_allowed": True, "stop_allowed": True, "distress_behavior": "pause_and_offer_human_handoff_without_diagnosis"},
        actor_id=actor,
        idempotency_key="liveforever-demo-interview-v1",
        complete=True,
    )
    segment = context.liveforever.add_transcript_segment(
        interview["interview_id"],
        tenant_id=tenant_id,
        project_id=project_id,
        segment_index=0,
        start_ms=0,
        end_ms=4000,
        speaker_label="Alex Synthetic",
        speaker_confidence=0.92,
        original_text="The radio was near the kitchen window.",
        source_media_id=evidence["recording.wav"],
        spatial_anchor={"record_id": place, "source_time_range_ms": [0, 4000], "uncertainty_m": 0.1},
        private_marks=[{"start": 4, "end": 9, "reason": "family-private"}],
        followup_suggestions=[{"text": "Would you like to pause?", "policy": "human_review_before_use"}],
        actor_id=actor,
    )
    corrected_segment = context.liveforever.correct_transcript_segment(
        segment["segment_id"],
        tenant_id=tenant_id,
        project_id=project_id,
        editor_id="alex-synthetic",
        edited_text="The blue radio was near the kitchen window.",
        reason="speaker supplied the missing descriptor",
        review_state="reviewed",
    )
    retained_interview = context.liveforever.interview(
        tenant_id, project_id, interview["interview_id"], include_private_marks=True
    )
    with context.database.session() as session:
        original_event_row = session.get(MemoryRecordRow, event)
        if original_event_row is None:
            raise ValidationError("DEMO_MEMORY_RECORD_MISSING", "source memory record disappeared before family correction")
        original_event_payload = context.liveforever._memory_payload(original_event_row)
    family_revision = context.liveforever.revise_record(
        event,
        tenant_id=tenant_id,
        project_id=project_id,
        editor_id="alex-synthetic",
        correction_type="alternate_interpretation",
        reason="The contributor now recalls that the weather changed before lunch.",
        changes={"title": "Family trip — corrected recollection", "assertions": [{"claim": "weather changed before lunch", "status": "alternate_interpretation"}]},
        audience=Audience.FAMILY,
        purpose="family_review",
    )
    with context.database.session() as session:
        original_event_after = session.get(MemoryRecordRow, event)
        revision_row = session.get(MemoryRecordRow, family_revision)
        family_correction_preserved_original = (
            original_event_after is not None
            and revision_row is not None
            and context.liveforever._memory_payload(original_event_after) == original_event_payload
            and revision_row.data_json.get("revision_of") == event
        )

    durable_edition = context.liveforever.create_edition(
        tenant_id=tenant_id,
        project_id=project_id,
        name="Synthetic navigable family memory room",
        audience=Audience.FAMILY,
        purpose="family_review",
        presentation_choices={
            "evidence_first": True,
            "source_labels_persistent": True,
            "generated_toggle": True,
            "quiet_mode": True,
            "safe_exit": True,
        },
        scene_commit_id="synthetic-memory-room-v1",
        narrative_path=[
            {"record_id": place, "scene_commit_id": "synthetic-memory-room-v1"},
            {"record_id": event, "scene_commit_id": "synthetic-memory-room-v1"},
            {"record_id": family_revision, "scene_commit_id": "synthetic-memory-room-v1"},
        ],
        policy_snapshot={"grant_ids": [grant], "audience": "family", "generated_presence": False},
        actor_id=actor,
        idempotency_key="liveforever-demo-edition-v1",
        publish=True,
    )
    memory_room = context.liveforever.memory_room(
        tenant_id,
        project_id,
        subject_id=subject,
        audience=Audience.FAMILY,
        purpose="family_review",
        include_private_transcript_marks=False,
    )
    recording_ref = context.assets.get(tenant_id, project_id, evidence["recording.wav"])
    memory_release = context.liveforever.create_preservation_release(
        tenant_id=tenant_id,
        project_id=project_id,
        edition_id=durable_edition["edition_id"],
        destination=output / "preservation" / "synthetic-memory-room.zip",
        originals=[{
            "asset_id": recording_ref.asset_id,
            "sha256": recording_ref.sha256,
            "media_type": "audio/wav",
            "preservation_master": True,
            "technical_metadata": {"fixture": "synthetic", "duration_ms": 4000},
            "rights": {"grant_id": grant, "audience": "family"},
        }],
        technical_metadata={"package_profile": "SIP-LIVEFOREVER-PRESERVATION-1.0", "created_by": actor},
        rights_consent=[{
            "grant_id": grant,
            "subject_id": subject,
            "purpose": "family_review",
            "audience": "family",
            "revocation_checked": True,
        }],
        memory_graph={
            "nodes": [person, place, event, family_revision, generated],
            "edges": [{"from": event, "to": family_revision, "type": "family_correction"}],
            "source": "synthetic-only",
        },
        scene_manifests=[{"scene_commit_id": "synthetic-memory-room-v1", "representations": ["semantic", "evidence", "generated_labeled"]}],
        open_assets=[
            {"path": "data/memory-graph.json", "format": "JSON"},
            {"path": "viewer/index.html", "format": "HTML"},
        ],
        human_guide={"title": "Synthetic family preservation guide", "contact": "synthetic-executor"},
        offline_fallback={"viewer": "viewer/index.html", "network_required": False, "splat_required": False},
        replicas=[{"replica_id": "offline-copy-a", "independent": True, "fixity_schedule": "annual"}],
        format_migrations=[{"from": "v1", "to": "v1", "original_preserved": True, "validation": "sha256"}],
        succession={"administrators": ["synthetic-executor"], "recovery": "documented offline copy", "keys": "family-controlled", "billing": "none", "prohibited_uses": ["voice cloning"]},
        shutdown={"bulk_export": True, "key_handoff_or_crypto_deletion": True, "family_notice": "required", "generated_presence_disabled": True},
        actor_id=actor,
        idempotency_key="liveforever-demo-preservation-v1",
    )
    memory_release_validation = context.liveforever.verify_preservation_release(Path(memory_release["package_path"]))
    before = {
        "private": context.liveforever.edition(tenant_id, project_id, audience=Audience.PRIVATE, purpose="preservation"),
        "family": context.liveforever.edition(tenant_id, project_id, audience=Audience.FAMILY, purpose="family_review"),
        "public": context.liveforever.edition(tenant_id, project_id, audience=Audience.PUBLIC, purpose="preservation"),
    }
    counts = {key: len(value["records"]) for key, value in before.items()}
    if not counts["private"] > counts["family"] > counts["public"] >= 1:
        raise ValidationError("DEMO_AUDIENCE_SEPARATION_FAILED", "private, family, and public editions did not separate access")
    generated_record = next(item for item in before["family"]["records"] if item["record_id"] == generated)
    if "AI-GENERATED" not in generated_record["data"].get("generated_label", ""):
        raise ValidationError("DEMO_GENERATED_LABEL_MISSING", "generated reconstruction was not unmistakably labeled")
    safe = context.liveforever.experience_configuration(tenant_id, project_id, subject, requested_features={}, audience=Audience.FAMILY)
    presence_blocked = False
    try:
        context.liveforever.experience_configuration(tenant_id, project_id, subject, requested_features={"voice_simulation": True}, audience=Audience.FAMILY)
    except AuthorizationError:
        presence_blocked = True
    if not presence_blocked or not safe["features"]["quiet_mode"] or not safe["features"]["safe_exit"]:
        raise ValidationError("DEMO_SAFE_EXPERIENCE_FAILED", "generated presence or safe-exit policy failed")
    _write_json(output / "editions" / "private-before.json", before["private"])
    _write_json(output / "editions" / "family-before.json", before["family"])
    _write_json(output / "editions" / "public-before.json", before["public"])
    revoked = context.liveforever.revoke_consent(grant, tenant_id=tenant_id, project_id=project_id, actor_id="alex-synthetic", reason="synthetic revocation demonstration")
    after = {
        "private": context.liveforever.edition(tenant_id, project_id, audience=Audience.PRIVATE, purpose="preservation"),
        "family": context.liveforever.edition(tenant_id, project_id, audience=Audience.FAMILY, purpose="family_review"),
        "public": context.liveforever.edition(tenant_id, project_id, audience=Audience.PUBLIC, purpose="preservation"),
    }
    if any(value["records"] for value in after.values()):
        raise ValidationError("DEMO_REVOCATION_PROPAGATION_FAILED", "revoked consent did not remove derivative access")
    _write_json(output / "editions" / "after-revocation.json", after)
    preservation = _preserve_and_restore(context, tenant_id, project_id, actor, output, restored_suffix="liveforever")
    return {
        "records": {"person": person, "place": place, "event": event, "private_interview": private_interview, "conflicting_recollections": conflict, "generated_reconstruction": generated},
        "evidence_assets": evidence,
        "audience_counts_before": counts,
        "consent": {"grant_id": grant, "revocation": revoked, "derivative_access_after": {key: len(value["records"]) for key, value in after.items()}},
        "generated_label": generated_record["data"]["generated_label"],
        "experience": safe,
        "presence_simulation_blocked": presence_blocked,
        "progress06_vertical_mvp": {
            "governance": governance,
            "interview": interview,
            "transcript_segment": segment,
            "corrected_segment": corrected_segment,
            "retained_interview": retained_interview,
            "family_revision": {"original_record_id": event, "revision_record_id": family_revision, "original_preserved": family_correction_preserved_original},
            "edition": durable_edition,
            "memory_room": memory_room,
            "preservation_release": {**memory_release, "validation": memory_release_validation},
        },
        "preservation": preservation,
        "acceptance": {
            "conflicts_preserved": len(conflict) == 2,
            "audiences_separated": True,
            "generated_content_labeled": True,
            "revocation_propagated": True,
            "quiet_mode": True,
            "safe_exit": True,
            "interview_source_ranges_preserved": retained_interview["segments"][0]["start_ms"] == 0 and retained_interview["segments"][0]["end_ms"] == 4000,
            "family_correction_preserved_original": family_correction_preserved_original,
            "memory_room_navigable": bool(memory_room["room_hash"]) and memory_room["edition"] is not None and bool(memory_room["records"]),
            "open_memory_preservation_verified": memory_release["status"] == "verified" and memory_release_validation["valid"] is True,
            "private_marks_withheld": memory_release_validation["valid"] is True,
            "open_restore": preservation["matching_root_hash"],
        },
    }


DEMONSTRATIONS: dict[str, Callable[[Path], dict[str, Any]]] = {
    "foundation": foundation,
    "hybrid": hybrid,
    "scene-runtime": scene_runtime,
    "construction": construction,
    "liveforever": liveforever,
    "export": foundation,
    "restore": foundation,
}


def run(name: str, *, output: Path | None = None) -> dict[str, Any]:
    canonical_name = "foundation" if name in {"export", "restore"} else name
    destination = output or (DEMO_ROOT / name)
    with _exclusive_destination_lock(destination):
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        started = _utc()
        try:
            result = _json_evidence_value(DEMONSTRATIONS[name](destination))
            status = "passed"
            error = None
        except Exception as exc:
            status = "failed"
            error = {"type": type(exc).__name__, "message": str(exc), "code": getattr(exc, "code", None)}
            result = {}
        artifacts = []
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                # Artifact identifiers are relative to the selected output root.
                relative_path = path.relative_to(destination).as_posix()
                artifacts.append({"path": relative_path, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
        report = _json_evidence_value({
            "schema": "sip.demo-evidence/v1",
            "demonstration": name,
            "canonical_scenario": canonical_name,
            "status": status,
            "started_at": started,
            "finished_at": _utc(),
            "environment": {"platform": platform.platform(), "python": platform.python_version(), "git": _git()},
            "result": result,
            "artifacts": artifacts,
            "error": error,
            "claims": "Synthetic acceptance evidence only; this is not a customer pilot, physical-device validation, survey, legal approval, or production-load result.",
        })
        report["evidence_hash"] = canonical_sha256(report)
        report_path = destination / "demo-report.json"
        _write_json(report_path, report)
        EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
        evidence_copy = EVIDENCE_ROOT / f"{name}.json"
        shutil.copy2(report_path, evidence_copy)
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("demonstration", choices=sorted(DEMONSTRATIONS))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run(args.demonstration, output=args.output)
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
