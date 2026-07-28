from __future__ import annotations

import pytest

from sip.canonical import sha256_bytes
from sip.context import PlatformContext
from sip.errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from sip.database import AuditEventRow, MultipartChunkRow, MultipartUploadRow
from sip.models import Audience, AuthorityClass, Classification, ProvenanceRef, SignedPrincipal, SourceClass
from sqlalchemy import select


@pytest.mark.unit
def test_datasasset_001_content_addressed_encrypted_immutable_ingest(bootstrapped) -> None:
    """REQ: DATASSET-001 immutable hash identity and encrypted local bytes."""
    context, tenant_id, project_id, actor = bootstrapped
    payload = b"original immutable capture bytes"
    asset = context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=payload,
        media_type="application/octet-stream",
        original_name="capture.bin",
        classification=Classification.CONFIDENTIAL,
        retention_class="source_evidence",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["fixture"], output_hash=sha256_bytes(payload)),
        actor_id=actor,
    )
    assert asset.sha256 == sha256_bytes(payload)
    assert context.store.path_for(asset.sha256).read_bytes() != payload
    assert context.assets.read(tenant_id, project_id, asset.asset_id, actor_id=actor) == payload


@pytest.mark.unit
def test_datasasset_002_multipart_chunks_are_hash_verified_idempotent_and_resumable(bootstrapped) -> None:
    """REQ: DATASSET-002 persisted chunk hashes allow restart-safe resume without retransmission."""
    context, tenant_id, project_id, actor = bootstrapped
    parts = [b"durable first chunk", b" and independently verified second chunk"]
    payload = b"".join(parts)
    upload_id = context.assets.begin_multipart(
        tenant_id=tenant_id,
        project_id=project_id,
        expected_sha256=sha256_bytes(payload),
        expected_bytes=len(payload),
        media_type="application/octet-stream",
        metadata={"fixture": "restart-resume"},
        actor_id=actor,
    )
    first = context.assets.put_part(
        upload_id,
        1,
        parts[0],
        sha256_bytes(parts[0]),
        tenant_id=tenant_id,
        project_id=project_id,
    )
    assert first["already_verified"] is False

    # A fresh service instance reconstructs resume state from durable database
    # metadata and verifies the persisted chunk bytes before advertising them.
    restarted = PlatformContext.create(context.settings)
    status = restarted.assets.multipart_status(upload_id, tenant_id=tenant_id, project_id=project_id)
    assert status["verified_parts"] == [
        {"part_number": 1, "sha256": sha256_bytes(parts[0]), "bytes": len(parts[0])}
    ]
    assert status["next_part_number"] == 2
    duplicate = restarted.assets.put_part(
        upload_id,
        1,
        parts[0],
        sha256_bytes(parts[0]),
        tenant_id=tenant_id,
        project_id=project_id,
    )
    assert duplicate["already_verified"] is True
    with pytest.raises(ConflictError):
        restarted.assets.put_part(
            upload_id,
            1,
            b"different",
            sha256_bytes(b"different"),
            tenant_id=tenant_id,
            project_id=project_id,
        )
    with pytest.raises(NotFoundError):
        restarted.assets.multipart_status(upload_id, tenant_id="another-tenant")

    restarted.assets.put_part(
        upload_id,
        2,
        parts[1],
        sha256_bytes(parts[1]),
        tenant_id=tenant_id,
        project_id=project_id,
    )
    asset = restarted.assets.complete_multipart(
        upload_id,
        original_name="resumed.bin",
        classification=Classification.CONFIDENTIAL,
        retention_class="source_evidence",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["multipart-fixture"], output_hash=sha256_bytes(payload)),
        actor_id=actor,
        tenant_id=tenant_id,
        project_id=project_id,
    )
    assert asset.sha256 == sha256_bytes(payload)
    assert restarted.assets.read(tenant_id, project_id, asset.asset_id, actor_id=actor) == payload


@pytest.mark.unit
@pytest.mark.security
def test_arciam_001_server_side_tenant_project_purpose_and_sensitive_policy(bootstrapped) -> None:
    """ARCIAM-001: client hiding is not authorization; tenant/project/purpose enforced server-side."""
    context, tenant_id, project_id, _ = bootstrapped
    principal = SignedPrincipal(
        subject_id="reviewer",
        tenant_id=tenant_id,
        project_ids=[project_id],
        roles=["reviewer"],
        purposes=["quality_review"],
        audience=Audience.PROJECT,
    )
    assert context.policy.require(
        principal,
        action="asset:read",
        tenant_id=tenant_id,
        project_id=project_id,
        purpose="quality_review",
        classification=Classification.INTERNAL.value,
    ).allowed
    with pytest.raises(AuthorizationError) as error:
        context.policy.require(
            principal,
            action="asset:read",
            tenant_id="another-tenant",
            project_id=project_id,
            purpose="quality_review",
        )
    assert error.value.code == "TENANT_MISMATCH"
    with pytest.raises(AuthorizationError):
        context.policy.require(
            principal,
            action="asset:read",
            tenant_id=tenant_id,
            project_id=project_id,
            purpose="marketing",
        )


@pytest.mark.unit
@pytest.mark.security
def test_opssec_signed_asset_token_is_scoped_and_temporary(bootstrapped) -> None:
    """REQ: PLTREST-004 signed asset access is exact-scope, short-lived, and audited."""
    context, tenant_id, project_id, actor = bootstrapped
    payload = b"token fixture"
    asset = context.assets.ingest_bytes(
        tenant_id=tenant_id,
        project_id=project_id,
        data=payload,
        media_type="text/plain",
        original_name="token.txt",
        classification=Classification.INTERNAL,
        retention_class="project_record",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["fixture"]),
        actor_id=actor,
    )
    token = context.assets.issue_read_token(tenant_id, project_id, asset.asset_id, subject_id="reviewer", ttl_seconds=60)
    assert context.assets.read_with_token(token) == payload
    with pytest.raises(ValidationError):
        context.assets.issue_read_token(tenant_id, project_id, asset.asset_id, subject_id="reviewer", ttl_seconds=7200)
    with context.database.session() as session:
        issuance = session.scalar(
            select(AuditEventRow).where(
                AuditEventRow.action == "asset:read_token_issue",
                AuditEventRow.resource_id == asset.asset_id,
            )
        )
        access = session.scalar(
            select(AuditEventRow).where(
                AuditEventRow.action == "asset:read",
                AuditEventRow.resource_id == asset.asset_id,
                AuditEventRow.actor_id == "reviewer",
            )
        )
    assert issuance is not None
    assert issuance.details_json == {"action": "asset:read", "ttl_seconds": 60, "classification": "internal"}
    assert access is not None


@pytest.mark.unit
def test_multipart_upload_records_verified_chunks_resumes_and_blocks_unverified_publication(bootstrapped) -> None:
    """REQ: DATASSET-002, DATASSET-003, ARCSYNC-002 verified chunks resume without retransmission and final integrity gates publication."""
    context, tenant_id, project_id, actor = bootstrapped
    payload = b"first verified chunk" + b"second verified chunk"
    expected = sha256_bytes(payload)
    upload_id = context.assets.begin_multipart(
        tenant_id=tenant_id,
        project_id=project_id,
        expected_sha256=expected,
        expected_bytes=len(payload),
        media_type="application/octet-stream",
        metadata={"source": "unit-fixture"},
        actor_id=actor,
    )
    parts = [b"first verified chunk", b"second verified chunk"]
    for number, part in enumerate(parts, 1):
        result = context.assets.put_part(upload_id, number, part, sha256_bytes(part), tenant_id=tenant_id, project_id=project_id)
        assert result["sha256"] == sha256_bytes(part)
    # Re-sending a verified chunk is an idempotent resume, not a duplicate row.
    repeated = context.assets.put_part(upload_id, 1, parts[0], sha256_bytes(parts[0]), tenant_id=tenant_id, project_id=project_id)
    assert repeated["sha256"] == sha256_bytes(parts[0])
    with context.database.session() as session:
        upload = session.get(MultipartUploadRow, upload_id)
        chunks = list(session.scalars(select(MultipartChunkRow).where(MultipartChunkRow.upload_id == upload_id)))
        assert upload is not None and upload.state == "open"
        assert len(chunks) == 2
        assert {row.part_number: row.sha256 for row in chunks} == {1: sha256_bytes(parts[0]), 2: sha256_bytes(parts[1])}

    status = context.assets.multipart_status(upload_id, tenant_id=tenant_id, project_id=project_id)
    assert status["verified_bytes"] == len(payload)
    assert status["next_part_number"] == 3

    # A manifest mismatch fails before an AssetRef can be created.
    with context.database.session() as session:
        row = session.get(MultipartUploadRow, upload_id)
        assert row is not None
        row.expected_sha256 = "0" * 64
    with pytest.raises(ValidationError) as error:
        context.assets.complete_multipart(
            upload_id,
            original_name="multipart.bin",
            classification=Classification.INTERNAL,
            retention_class="project_record",
            source_class=SourceClass.DIRECT_CAPTURE,
            authority_class=AuthorityClass.EVIDENCE,
            provenance=ProvenanceRef(source_ids=["multipart-fixture"]),
            actor_id=actor,
            tenant_id=tenant_id,
            project_id=project_id,
        )
    assert error.value.code == "UPLOAD_FINAL_INTEGRITY_FAILED"
    with context.database.session() as session:
        row = session.get(MultipartUploadRow, upload_id)
        assert row is not None
        row.expected_sha256 = expected
    completed = context.assets.complete_multipart(
        upload_id,
        original_name="multipart.bin",
        classification=Classification.INTERNAL,
        retention_class="project_record",
        source_class=SourceClass.DIRECT_CAPTURE,
        authority_class=AuthorityClass.EVIDENCE,
        provenance=ProvenanceRef(source_ids=["multipart-fixture"]),
        actor_id=actor,
        tenant_id=tenant_id,
        project_id=project_id,
    )
    assert completed.sha256 == expected
    assert context.assets.read(tenant_id, project_id, completed.asset_id, actor_id=actor) == payload
