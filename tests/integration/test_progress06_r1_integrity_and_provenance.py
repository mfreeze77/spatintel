from __future__ import annotations

import json
from pathlib import Path
import stat
import zipfile

import pytest

from sip.canonical import merkle_root, sha256_bytes
from sip.errors import ConflictError, ValidationError
from sip.models import Audience, AuthorityClass, Classification, ProvenanceRef, SourceClass


def _rewrite_with_valid_manifest(path: Path, *, member: str, payload: bytes) -> None:
    with zipfile.ZipFile(path) as archive:
        members = {name: archive.read(name) for name in archive.namelist() if name != "checksums.json"}
    members[member] = payload
    checks = {name: sha256_bytes(data) for name, data in sorted(members.items())}
    manifest = json.dumps(
        {"algorithm": "sha256", "files": checks, "root_hash": merkle_root(sorted(checks.items()))},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in sorted({**members, "checksums.json": manifest}.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)


def _asset(context, tenant: str, project: str, *, name: str, content: bytes):
    return context.assets.ingest_bytes(
        tenant_id=tenant,
        project_id=project,
        data=content,
        media_type="application/octet-stream",
        original_name=name,
        classification=Classification.INTERNAL,
        retention_class="records",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=[f"synthetic:{name}"], output_hash=sha256_bytes(content)),
        actor_id="r1-provenance-test",
    )


def _document_kwargs(asset_id: str, digest: str, *, revision: str) -> dict:
    return {
        "stable_document_id": None,
        "document_type": "drawing",
        "title": f"Synthetic drawing {revision}",
        "revision": revision,
        "issue_date": "2026-07-29",
        "issuer": "Synthetic issuer",
        "status": "reviewed",
        "asset_id": asset_id,
        "source_sha256": digest,
        "page_count": 1,
        "permissions": {"audience": "project"},
        "page_regions": [],
        "spatial_links": [],
        "extraction": {},
        "review": {"state": "reviewed"},
        "actor_id": "r1-provenance-test",
    }


def _interchange_kwargs(asset_id: str, digest: str, *, key: str) -> dict:
    return {
        "format": "IFC",
        "direction": "import",
        "source_asset_id": asset_id,
        "source_sha256": digest,
        "schema_version": "IFC4",
        "units": "meter",
        "crs": {"type": "local"},
        "owner_history": {},
        "global_ids": [],
        "classifications": {},
        "properties": {},
        "relationships": [],
        "geometry_conversion_report": {},
        "unsupported_constructs": [],
        "alignment": {},
        "mappings": [],
        "issues": [],
        "truth_labels": {"source": "design"},
        "actor_id": "r1-provenance-test",
        "idempotency_key": key,
    }


@pytest.mark.integration
def test_progress06_r1_document_and_interchange_sources_are_scoped_immutable_assets(context) -> None:
    """REQ: CONDOC-001, DATBIM-001, DATEVID-002 missing, tombstoned, foreign, and hash-mismatched provenance assets fail closed."""
    tenant_a = context.tenancy.create_tenant("R1 provenance A", tenant_id="r1-prov-tenant-a")
    tenant_b = context.tenancy.create_tenant("R1 provenance B", tenant_id="r1-prov-tenant-b")
    project_a = context.tenancy.create_project(
        tenant_a, "A", vertical="construction", classification="internal",
        project_id="r1-prov-project-a", actor_id="bootstrap-a",
    )
    project_b = context.tenancy.create_project(
        tenant_b, "B", vertical="construction", classification="internal",
        project_id="r1-prov-project-b", actor_id="bootstrap-b",
    )
    project_a_other = context.tenancy.create_project(
        tenant_a, "A other", vertical="construction", classification="internal",
        project_id="r1-prov-project-a-other", actor_id="bootstrap-a",
    )
    valid = _asset(context, tenant_a, project_a, name="valid.ifc", content=b"valid IFC source")
    cross_project = _asset(context, tenant_a, project_a_other, name="cross-project.ifc", content=b"cross project IFC source")
    foreign = _asset(context, tenant_b, project_b, name="foreign.ifc", content=b"foreign IFC source")
    tombstoned = _asset(context, tenant_a, project_a, name="tombstoned.ifc", content=b"tombstoned IFC source")
    context.assets.tombstone(tenant_a, project_a, tombstoned.asset_id, actor_id="r1-provenance-test", dry_run=False)

    invalid_documents = [
        ("missing-asset", "0" * 64),
        (cross_project.asset_id, cross_project.sha256),
        (foreign.asset_id, foreign.sha256),
        (tombstoned.asset_id, tombstoned.sha256),
        (valid.asset_id, "f" * 64),
    ]
    for index, (asset_id, digest) in enumerate(invalid_documents):
        with pytest.raises(ValidationError) as exc:
            context.construction.create_document_revision(
                tenant_id=tenant_a,
                project_id=project_a,
                **_document_kwargs(asset_id, digest, revision=f"invalid-{index}"),
            )
        assert exc.value.code == "DOCUMENT_ASSET_SCOPE"

    valid_document = context.construction.create_document_revision(
        tenant_id=tenant_a,
        project_id=project_a,
        **_document_kwargs(valid.asset_id, valid.sha256, revision="valid"),
    )
    assert valid_document["idempotent_replay"] is False

    invalid_interchanges = [
        ("", valid.sha256, "missing"),
        ("missing-asset", "0" * 64, "unknown"),
        (cross_project.asset_id, cross_project.sha256, "cross-project"),
        (foreign.asset_id, foreign.sha256, "foreign"),
        (tombstoned.asset_id, tombstoned.sha256, "tombstoned"),
        (valid.asset_id, "e" * 64, "mismatch"),
    ]
    for asset_id, digest, key in invalid_interchanges:
        with pytest.raises(ValidationError) as exc:
            context.construction.record_interchange(
                tenant_id=tenant_a,
                project_id=project_a,
                **_interchange_kwargs(asset_id, digest, key=f"invalid-{key}"),
            )
        assert exc.value.code in {"INTERCHANGE_ASSET_REQUIRED", "INTERCHANGE_ASSET_SCOPE"}

    valid_interchange = context.construction.record_interchange(
        tenant_id=tenant_a,
        project_id=project_a,
        **_interchange_kwargs(valid.asset_id, valid.sha256, key="valid-interchange"),
    )
    assert valid_interchange["status"] == "validated"


@pytest.mark.integration
def test_progress06_r1_owner_handoff_replay_revalidates_current_package_bytes(context, tmp_path: Path) -> None:
    """REQ: CONHAND-006 idempotent owner-handoff replay revalidates current bytes and detects a validly rechecksummed replacement."""
    tenant = context.tenancy.create_tenant("R1 handoff replay", tenant_id="r1-handoff-tenant")
    project = context.tenancy.create_project(
        tenant, "R1 handoff", vertical="construction", classification="internal",
        project_id="r1-handoff-project", actor_id="bootstrap",
    )
    scene = context.scene.create_scene(tenant, project, name="R1 handoff scene", actor_id="bootstrap")
    destination = tmp_path / "owner-handoff.zip"
    request = dict(
        tenant_id=tenant,
        project_id=project,
        destination=destination,
        scope={"systems": [], "include_restricted_annex": False},
        accepted_scene_commit_id=scene["commit_id"],
        warranties=[],
        training=[],
        exclusions=[],
        audience_profiles={"owner": {"read_only": True}},
        actor_id="handoff-author",
        idempotency_key="r1-handoff-replay",
    )
    created = context.construction.create_owner_handoff(**request)
    assert created["status"] == "verified"
    _rewrite_with_valid_manifest(destination, member="README.txt", payload=b"replacement owner handoff\n")
    assert context.construction.verify_owner_handoff(destination)["valid"] is True
    with pytest.raises(ConflictError) as exc:
        context.construction.create_owner_handoff(**request)
    assert exc.value.code == "HANDOFF_REPLAY_PACKAGE_CHANGED"


@pytest.mark.integration
def test_progress06_r1_preservation_replay_revalidates_current_package_bytes(context, tmp_path: Path) -> None:
    """REQ: LIFPRESV-001 idempotent preservation replay revalidates current bytes and detects a validly rechecksummed replacement."""
    tenant = context.tenancy.create_tenant("R1 preservation replay", tenant_id="r1-preservation-tenant")
    project = context.tenancy.create_project(
        tenant, "R1 preservation", vertical="liveforever", classification="internal",
        project_id="r1-preservation-project", actor_id="bootstrap",
    )
    edition = context.liveforever.create_edition(
        tenant_id=tenant,
        project_id=project,
        name="Synthetic private preservation",
        audience=Audience.PRIVATE,
        purpose="preservation",
        presentation_choices={"quiet_mode": True},
        scene_commit_id=None,
        narrative_path=[],
        policy_snapshot={"synthetic": True},
        actor_id="preservation-author",
        idempotency_key="r1-edition",
        publish=True,
    )
    destination = tmp_path / "preservation.zip"
    request = dict(
        tenant_id=tenant,
        project_id=project,
        edition_id=edition["edition_id"],
        destination=destination,
        originals=[{"asset_id": "synthetic-original", "sha256": "0" * 64}],
        technical_metadata={"format": "synthetic"},
        rights_consent=[],
        memory_graph={"records": []},
        scene_manifests=[],
        open_assets=[],
        human_guide={"title": "Synthetic guide"},
        offline_fallback={"viewer": "viewer/index.html", "network_required": False},
        replicas=[],
        format_migrations=[],
        succession={"owner": "synthetic"},
        shutdown={"export_before_shutdown": True},
        actor_id="preservation-author",
        idempotency_key="r1-preservation-replay",
    )
    created = context.liveforever.create_preservation_release(**request)
    assert created["status"] == "verified"
    _rewrite_with_valid_manifest(destination, member="README.txt", payload=b"replacement preservation package\n")
    assert context.liveforever.verify_preservation_release(destination)["valid"] is True
    with pytest.raises(ConflictError) as exc:
        context.liveforever.create_preservation_release(**request)
    assert exc.value.code == "PRESERVATION_REPLAY_PACKAGE_CHANGED"
