from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from sip.canonical import canonical_json, merkle_root, sha256_bytes
from sip.database import SupportAccessGrantRow, SupportBundleRow
from sip.errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from tests.progress08_helpers import bootstrap, telemetry


def _grant(context, tenant: str, project: str, *, resource_ids: list[str], requester: str = "customer-admin", engineer: str = "support-engineer") -> dict:
    requested = context.operations_intelligence.request_support_access(
        tenant_id=tenant,
        project_id=project,
        resource_scope={
            "resource_ids": resource_ids,
            "telemetry_types": ["log", "metric", "trace", "quality"],
            "include_logs": True,
            "include_metrics": True,
            "include_traces": True,
            "classification": "internal",
            "audience": "private",
        },
        purpose="support",
        personnel=[engineer],
        requested_by=requester,
        duration_seconds=3600,
    )
    return context.operations_intelligence.approve_support_access(
        tenant_id=tenant, project_id=project, grant_id=requested["grant_id"], approved_by="customer-approver"
    )


def _crafted_support_zip(*, extra: dict[str, bytes] | None = None, omit_checksum_for: str | None = None) -> bytes:
    files = {
        "support-bundle.json": canonical_json({
            "schema": "sip.support-bundle/v1",
            "raw_media_included": False,
            "unrestricted_signed_urls_included": False,
        }),
        "versions.json": canonical_json({"platform_release": "test"}),
        "manifests.json": canonical_json({"references": []}),
        "metrics.json": canonical_json({"records": []}),
        "errors.json": canonical_json({"records": []}),
        "logs.ndjson": b"",
        "hardware-profile.json": canonical_json({"device_tier": "test"}),
    }
    files.update(extra or {})
    checksums = {name: sha256_bytes(data) for name, data in sorted(files.items()) if name != omit_checksum_for}
    checksums_body = canonical_json({"algorithm": "sha256", "files": checksums, "root_hash": merkle_root(checksums.items())})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
        archive.writestr("checksums.json", checksums_body)
    return buffer.getvalue()


def test_progress08_telemetry_scrubs_secrets_and_resists_injection_cardinality_and_trace_spoofing(tmp_path: Path) -> None:
    """REQ: ARCOBS-001, ARCOBS-002, ARCOBS-003 telemetry rejects sensitive content, free-form injection, high-cardinality labels, and conflicting trace context."""
    context, tenant, project = bootstrap(tmp_path, name="p08-telemetry-security")
    base = dict(
        tenant_id=tenant, project_id=project, telemetry_type="log", service="api", release="progress08",
        correlation_id="safe-correlation", trace_id="a" * 32, traceparent="00-" + "a" * 32 + "-" + "b" * 16 + "-01",
        operation_id=None, route_template="/v1/projects/{project_id}/scene", stage="request", model_id=None,
        checkpoint_hash=None, capture_profile=None, hardware_profile=None, execution_profile="local", queue_class=None,
        vertical="platform", severity="info", outcome="success", stable_error_code=None, actor_id="ops-agent",
    )
    with pytest.raises(ValidationError):
        context.operations_intelligence.record_telemetry(**base, payload={"password": "SUPERSECRET"}, labels={})
    with pytest.raises(ValidationError):
        context.operations_intelligence.record_telemetry(**base, payload={"message_code": "password=SUPERSECRET"}, labels={})
    with pytest.raises(ValidationError):
        context.operations_intelligence.record_telemetry(**base, payload={"count": 1}, labels={"asset_id": "asset-123"})
    conflicting = {**base, "traceparent": "00-" + "c" * 32 + "-" + "d" * 16 + "-01"}
    with pytest.raises(ValidationError, match="different traces"):
        context.operations_intelligence.record_telemetry(**conflicting, payload={"count": 1}, labels={})
    query_in_route = {**base, "route_template": "/v1/search?secret=1"}
    with pytest.raises(ValidationError, match="parameterized"):
        context.operations_intelligence.record_telemetry(**query_in_route, payload={"count": 1}, labels={})


def test_progress08_support_scope_approval_expiration_revocation_and_cross_tenant_isolation(tmp_path: Path) -> None:
    """REQ: OPSSUP-002, OPSSUP-003, OPSSUP-006 support access requires independent scoped approval, expires/revokes, and cannot cross tenant or create unrestricted links."""
    context, tenant, project = bootstrap(tmp_path, name="p08-support-security")
    first = telemetry(context, tenant, project, telemetry_type="log", correlation_id="support-1", payload={"message_code": "controlled_error", "duration_ms": 5})
    second = telemetry(context, tenant, project, telemetry_type="metric", correlation_id="support-2", payload={"count": 2})
    requested = context.operations_intelligence.request_support_access(
        tenant_id=tenant,
        project_id=project,
        resource_scope={"resource_ids": [first["telemetry_id"]], "telemetry_types": ["log"], "include_logs": True, "include_metrics": False, "include_traces": False},
        purpose="support",
        personnel=["support-engineer"],
        requested_by="customer-admin",
        duration_seconds=3600,
    )
    with pytest.raises(AuthorizationError, match="independent"):
        context.operations_intelligence.approve_support_access(
            tenant_id=tenant, project_id=project, grant_id=requested["grant_id"], approved_by="customer-admin"
        )
    grant = context.operations_intelligence.approve_support_access(
        tenant_id=tenant, project_id=project, grant_id=requested["grant_id"], approved_by="customer-approver"
    )
    with pytest.raises(AuthorizationError, match="outside"):
        context.operations_intelligence.create_support_bundle(
            tenant_id=tenant, project_id=project, grant_id=grant["grant_id"], telemetry_ids=[second["telemetry_id"]],
            hardware_profile={"device_tier": "desktop"}, manifest_references=[], actor_id="support-engineer",
        )
    with pytest.raises(AuthorizationError, match="not named"):
        context.operations_intelligence.create_support_bundle(
            tenant_id=tenant, project_id=project, grant_id=grant["grant_id"], telemetry_ids=[first["telemetry_id"]],
            hardware_profile={"device_tier": "desktop"}, manifest_references=[], actor_id="other-engineer",
        )
    with pytest.raises(ValidationError, match="non-approved field"):
        context.operations_intelligence.create_support_bundle(
            tenant_id=tenant, project_id=project, grant_id=grant["grant_id"], telemetry_ids=[first["telemetry_id"]],
            hardware_profile={"device_tier": "desktop", "operator_notes": "private family transcript"},
            manifest_references=[], actor_id="support-engineer",
        )
    with pytest.raises(ValidationError, match="invalid controlled value|credential-like content"):
        context.operations_intelligence.create_support_bundle(
            tenant_id=tenant, project_id=project, grant_id=grant["grant_id"], telemetry_ids=[first["telemetry_id"]],
            hardware_profile={"device_tier": "password=SUPERSECRET"},
            manifest_references=[], actor_id="support-engineer",
        )
    bundle = context.operations_intelligence.create_support_bundle(
        tenant_id=tenant, project_id=project, grant_id=grant["grant_id"], telemetry_ids=[first["telemetry_id"]],
        hardware_profile={"device_tier": "desktop"}, manifest_references=[{"kind": "release", "sha256": "1" * 64}], actor_id="support-engineer",
    )
    assert bundle["manifest"]["raw_media_included"] is False
    assert bundle["manifest"]["unrestricted_signed_urls_included"] is False

    other_tenant = context.tenancy.create_tenant("Other", tenant_id="support-other-tenant", actor_id="bootstrap")
    other_project = context.tenancy.create_project(other_tenant, "Other", vertical="platform", classification="internal", project_id="support-other-project", actor_id="bootstrap")
    with pytest.raises(NotFoundError):
        context.operations_intelligence.verify_support_bundle(
            tenant_id=other_tenant, project_id=other_project, bundle_id=bundle["bundle_id"], actor_id="support-engineer"
        )

    revoked = context.operations_intelligence.revoke_support_access(
        tenant_id=tenant, project_id=project, grant_id=grant["grant_id"], actor_id="customer-approver"
    )
    assert revoked["state"] == "revoked"
    with pytest.raises(AuthorizationError, match="expired or revoked"):
        context.operations_intelligence.verify_support_bundle(
            tenant_id=tenant, project_id=project, bundle_id=bundle["bundle_id"], actor_id="support-engineer"
        )


def test_progress08_support_bundle_rejects_unchecked_unexpected_symlink_and_changed_replay(tmp_path: Path) -> None:
    """REQ: OPSSUP-001, OPSSUP-003, OPSSUP-006 support bundle verification rejects traversal, symlinks, unchecked members, partial manifests, and changed replay bytes."""
    context, tenant, project = bootstrap(tmp_path, name="p08-support-archive")
    record = telemetry(context, tenant, project, telemetry_type="log", correlation_id="bundle-1", payload={"message_code": "controlled_error"})
    grant = _grant(context, tenant, project, resource_ids=[record["telemetry_id"]])
    bundle = context.operations_intelligence.create_support_bundle(
        tenant_id=tenant, project_id=project, grant_id=grant["grant_id"], telemetry_ids=[record["telemetry_id"]],
        hardware_profile={"device_tier": "desktop"}, manifest_references=[], actor_id="support-engineer",
    )
    valid_path: Path
    with context.database.session() as session:
        row = session.get(SupportBundleRow, bundle["bundle_id"])
        assert row is not None
        valid_path = Path(row.bundle_path)
    assert valid_path.is_file()

    unexpected = context.operations_intelligence.verify_support_bundle_bytes(_crafted_support_zip(extra={"evil.js": b"alert(1)"}))
    assert unexpected["valid"] is False
    partial = context.operations_intelligence.verify_support_bundle_bytes(_crafted_support_zip(omit_checksum_for="logs.ndjson"))
    assert partial["valid"] is False

    traversal_buffer = io.BytesIO()
    with zipfile.ZipFile(traversal_buffer, "w") as archive:
        archive.writestr("../escape", b"bad")
    with pytest.raises(ValidationError):
        context.operations_intelligence.verify_support_bundle_bytes(traversal_buffer.getvalue())

    symlink_buffer = io.BytesIO()
    with zipfile.ZipFile(symlink_buffer, "w") as archive:
        info = zipfile.ZipInfo("support-bundle.json")
        info.create_system = 3
        info.external_attr = (0o120777 & 0xFFFF) << 16
        archive.writestr(info, b"target")
    with pytest.raises(ValidationError):
        context.operations_intelligence.verify_support_bundle_bytes(symlink_buffer.getvalue())

    valid_path.write_bytes(valid_path.read_bytes() + b"tampered")
    with pytest.raises(ConflictError, match="no longer verifies"):
        context.operations_intelligence.create_support_bundle(
            tenant_id=tenant, project_id=project, grant_id=grant["grant_id"], telemetry_ids=[record["telemetry_id"]],
            hardware_profile={"device_tier": "desktop"}, manifest_references=[], actor_id="support-engineer",
        )


def test_progress08_high_risk_support_routes_and_retains_no_raw_customer_data(tmp_path: Path) -> None:
    """REQ: OPSSUP-004, OPSSUP-005 high-risk issues route to specialized personnel and resolutions retain remediation without unnecessary customer data."""
    context, tenant, project = bootstrap(tmp_path, name="p08-ticket")
    ticket = context.operations_intelligence.create_support_ticket(
        tenant_id=tenant, project_id=project, risk_class="critical_infrastructure", issue_type="security_system",
        summary="Synthetic restricted-system diagnostic", stable_error_codes=["RESTRICTED_READ_DENIED"], actor_id="customer-admin",
    )
    assert ticket["routed_role"] == "specialized_support"
    resolved = context.operations_intelligence.resolve_support_ticket(
        tenant_id=tenant, project_id=project, ticket_id=ticket["ticket_id"],
        remediation_reference="release:1.1.0-progress08", affected_release="1.1.0-progress08", actor_id="specialized-support",
    )
    assert resolved["retention"] == {"stable_error_codes": ["RESTRICTED_READ_DENIED"], "raw_customer_data_retained": False}
