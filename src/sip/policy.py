from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from .audit import AuditService
from .database import ConsentGrantRow, Database, IdentityRow, ProjectRow, RoleBindingRow
from .errors import AuthorizationError, NotFoundError, ValidationError
from .models import Audience, Classification, SignedPrincipal
from .temporal import db_now


ROLE_ACTIONS: dict[str, set[str]] = {
    "tenant_admin": {"*"},
    "project_admin": {"project:*", "asset:*", "scene:*", "construction:*", "liveforever:*", "representation:*", "export:*", "ops:support_request", "ops:cost_read"},
    "restricted_export_approver": {"construction:restricted_export", "construction:read", "asset:read"},
    "restricted_reader": {"construction:restricted_read", "construction:read", "asset:read"},
    "construction_verifier": {"construction:verify", "construction:read", "asset:read"},
    "liveforever_reviewer": {"liveforever:review", "liveforever:read", "asset:read"},
    "capture_operator": {"asset:create", "capture:*", "scene:read"},
    "reviewer": {"asset:read", "scene:read", "scene:review", "measurement:review", "construction:read", "liveforever:read"},
    "publisher": {"representation:publish", "scene:commit", "scene:read", "asset:read"},
    "privacy_officer": {"consent:*", "deletion:*", "liveforever:*", "asset:read", "security:privacy_manage", "security:incident_manage", "security:cache_invalidate"},
    "security_admin": {"security:threat_manage", "security:privileged_access", "security:workload_identity", "security:key_manage", "security:privacy_manage", "security:audit_verify", "security:provider_governance", "security:cache_invalidate", "security:release_manage", "security:transport_verify", "security:capture_finalize", "security:immersive_safety", "security:incident_manage", "asset:read"},
    "key_custodian": {"security:key_manage", "asset:read"},
    "release_manager": {"security:release_manage", "security:audit_verify", "qa:campaign_manage", "qa:waiver_approve", "qa:candidate_sign", "qa:production_admit", "qa:read", "asset:read"},
    "qa_operator": {"qa:evidence_record", "qa:read", "asset:read"},
    "qa_reviewer": {"qa:evidence_record", "qa:read", "security:audit_verify", "asset:read"},
    "ops_admin": {"ops:observe", "ops:slo_manage", "ops:cost_manage", "ops:quota_manage", "ops:incident_manage", "ops:support_request", "deployment:read", "asset:read"},
    "deployment_admin": {"deployment:profile_manage", "deployment:project_assign", "deployment:residency_manage", "deployment:transfer_manage", "deployment:edge_manage", "deployment:update_manage", "deployment:migrate", "deployment:autoscale_manage", "deployment:aws_manage", "deployment:admit", "deployment:drift_check", "deployment:read", "asset:read"},
    "recovery_admin": {"recovery:objective_manage", "recovery:backup_manage", "recovery:restore", "recovery:key_recover", "recovery:game_day", "recovery:production_admit", "retention:manage", "deletion:plan", "deletion:approve", "deletion:execute", "tenant:offboard", "migration:exercise", "asset:read", "export:read"},
    "recovery_operator": {"recovery:backup_manage", "recovery:restore", "recovery:game_day", "retention:manage", "deletion:plan", "asset:read", "export:read"},
    "deletion_approver": {"deletion:approve", "asset:read"},
    "deletion_executor": {"deletion:execute", "asset:read"},
    "residency_officer": {"deployment:residency_manage", "deployment:transfer_manage", "deployment:admit", "deployment:read", "asset:read"},
    "edge_operator": {"deployment:edge_manage", "deployment:update_manage", "deployment:read", "asset:read"},
    "budget_approver": {"ops:budget_override", "ops:cost_read", "asset:read"},
    "support_approver": {"ops:support_approve", "ops:support_read", "asset:read"},
    "support_engineer": {"ops:support_access", "ops:support_read", "ops:observe", "asset:read"},
    "specialized_support": {"ops:support_access", "ops:support_read", "ops:observe", "construction:restricted_read", "liveforever:read", "asset:read"},
    "viewer": {"asset:read", "scene:read", "construction:read", "liveforever:read", "ops:cost_read"},
    "service_worker": {"operation:lease", "operation:checkpoint", "operation:complete", "asset:read", "asset:create"},
}

# Namespace wildcards are intentionally insufficient for these higher-order
# approvals. They require an exact grant (or tenant-wide superuser authority)
# so a routine project administrator cannot self-authorize a restricted export.
EXACT_GRANT_ACTIONS = {
    "construction:restricted_export",
    "construction:restricted_read",
    "construction:verify",
    "liveforever:review",
    "security:threat_manage",
    "security:privileged_access",
    "security:workload_identity",
    "security:key_manage",
    "security:privacy_manage",
    "security:audit_verify",
    "security:provider_governance",
    "security:cache_invalidate",
    "security:release_manage",
    "security:transport_verify",
    "security:capture_finalize",
    "security:immersive_safety",
    "security:incident_manage",
    "qa:campaign_manage",
    "qa:evidence_record",
    "qa:waiver_approve",
    "qa:candidate_sign",
    "qa:production_admit",
    "ops:slo_manage",
    "ops:cost_manage",
    "ops:quota_manage",
    "ops:budget_override",
    "ops:support_approve",
    "ops:support_access",
    "ops:incident_manage",
    "deployment:profile_manage",
    "deployment:project_assign",
    "deployment:residency_manage",
    "deployment:transfer_manage",
    "deployment:edge_manage",
    "deployment:update_manage",
    "deployment:migrate",
    "deployment:autoscale_manage",
    "deployment:aws_manage",
    "deployment:admit",
    "deployment:drift_check",
    "recovery:objective_manage",
    "recovery:backup_manage",
    "recovery:restore",
    "recovery:key_recover",
    "recovery:game_day",
    "recovery:production_admit",
    "retention:manage",
    "deletion:plan",
    "deletion:approve",
    "deletion:execute",
    "tenant:offboard",
    "migration:exercise",
}

CLASSIFICATION_ORDER = {
    Classification.PUBLIC.value: 0,
    Classification.INTERNAL.value: 1,
    Classification.CONFIDENTIAL.value: 2,
    Classification.RESTRICTED.value: 3,
    Classification.CRITICAL_INFRASTRUCTURE.value: 4,
    Classification.BIOMETRIC.value: 4,
    Classification.MINOR.value: 4,
}


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason_code: str
    obligations: list[str]
    evaluated_policy_version: str = "sip-policy-1.1.0"


class PolicyService:
    def __init__(self, database: Database, audit: AuditService) -> None:
        self.database = database
        self.audit = audit

    @staticmethod
    def _role_allows(role: str, action: str) -> bool:
        grants = ROLE_ACTIONS.get(role, set())
        if "*" in grants or action in grants:
            return True
        if action in EXACT_GRANT_ACTIONS:
            return False
        namespace = action.split(":", 1)[0] + ":*"
        return namespace in grants

    def authorize(
        self,
        principal: SignedPrincipal,
        *,
        action: str,
        tenant_id: str,
        project_id: str | None,
        purpose: str | None = None,
        classification: str = Classification.INTERNAL.value,
        required_audience: Audience | None = None,
        spatial_region_id: str | None = None,
        audit_denial: bool = True,
    ) -> PolicyDecision:
        obligations: list[str] = []
        reason = "ALLOW"
        allowed = True
        if principal.tenant_id != tenant_id:
            allowed, reason = False, "TENANT_MISMATCH"
        elif project_id and project_id not in principal.project_ids and "tenant_admin" not in principal.roles:
            allowed, reason = False, "PROJECT_SCOPE_DENIED"
        elif not any(self._role_allows(role, action) for role in principal.roles):
            allowed, reason = False, "ACTION_DENIED"
        elif purpose and purpose not in principal.purposes and "tenant_admin" not in principal.roles:
            allowed, reason = False, "PURPOSE_DENIED"
        elif required_audience and principal.audience not in {required_audience, Audience.PRIVATE} and "tenant_admin" not in principal.roles:
            allowed, reason = False, "AUDIENCE_DENIED"
        if classification in {Classification.CRITICAL_INFRASTRUCTURE.value, Classification.BIOMETRIC.value, Classification.MINOR.value}:
            obligations.extend(["no_external_provider", "watermark_sensitive", "audit_every_read"])
            if not set(principal.roles).intersection({"tenant_admin", "project_admin", "privacy_officer", "reviewer"}):
                allowed, reason = False, "SENSITIVE_CLASSIFICATION_DENIED"
        if spatial_region_id:
            allowed_regions = set(principal.attributes.get("spatial_region_ids", []))
            if allowed_regions and spatial_region_id not in allowed_regions:
                allowed, reason = False, "SPATIAL_REGION_DENIED"
        if not allowed and audit_denial:
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=principal.subject_id,
                action=f"authorize:{action}",
                resource_type="policy_decision",
                resource_id=project_id or tenant_id,
                outcome="denied",
                details={"reason": reason, "purpose": purpose, "classification": classification, "spatial_region_id": spatial_region_id},
            )
        return PolicyDecision(allowed=allowed, reason_code=reason, obligations=obligations)

    def require(self, principal: SignedPrincipal, **kwargs: Any) -> PolicyDecision:
        decision = self.authorize(principal, **kwargs)
        if not decision.allowed:
            raise AuthorizationError(decision.reason_code, "access denied by server-side policy", {"obligations": decision.obligations})
        return decision

    def create_identity(self, tenant_id: str, identity_id: str, display_name: str, identity_type: str = "user") -> None:
        with self.database.session() as session:
            if session.get(IdentityRow, identity_id):
                raise ValidationError("IDENTITY_EXISTS", "identity already exists")
            session.add(IdentityRow(identity_id=identity_id, tenant_id=tenant_id, display_name=display_name, identity_type=identity_type))

    def bind_role(
        self,
        *,
        binding_id: str,
        tenant_id: str,
        project_id: str | None,
        identity_id: str,
        role: str,
        purposes: list[str],
        spatial_restrictions: list[dict[str, Any]] | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        if role not in ROLE_ACTIONS:
            raise ValidationError("ROLE_UNKNOWN", "role is not defined")
        with self.database.session() as session:
            identity = session.get(IdentityRow, identity_id)
            if not identity or identity.tenant_id != tenant_id:
                raise NotFoundError("identity", identity_id)
            if project_id:
                project = session.get(ProjectRow, project_id)
                if not project or project.tenant_id != tenant_id:
                    raise NotFoundError("project", project_id)
            session.add(
                RoleBindingRow(
                    binding_id=binding_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    identity_id=identity_id,
                    role=role,
                    purposes_json=purposes,
                    spatial_restrictions_json=spatial_restrictions or [],
                    expires_at=expires_at,
                )
            )

    def principal_for(self, tenant_id: str, identity_id: str, *, project_id: str | None = None, audience: Audience = Audience.PRIVATE) -> SignedPrincipal:
        now = db_now()
        with self.database.session() as session:
            identity = session.get(IdentityRow, identity_id)
            if not identity or identity.tenant_id != tenant_id or identity.disabled:
                raise NotFoundError("identity", identity_id)
            rows = list(
                session.scalars(
                    select(RoleBindingRow).where(
                        RoleBindingRow.tenant_id == tenant_id,
                        RoleBindingRow.identity_id == identity_id,
                        (RoleBindingRow.project_id == project_id) | (RoleBindingRow.project_id.is_(None)),
                    )
                )
            )
        active = [row for row in rows if row.expires_at is None or _aware(row.expires_at) > now]
        return SignedPrincipal(
            subject_id=identity_id,
            tenant_id=tenant_id,
            project_ids=[project_id] if project_id else [],
            roles=sorted({row.role for row in active}),
            purposes=sorted({purpose for row in active for purpose in row.purposes_json}),
            audience=audience,
            attributes={
                "spatial_region_ids": sorted(
                    {
                        restriction["region_id"]
                        for row in active
                        for restriction in row.spatial_restrictions_json
                        if restriction.get("effect") == "allow" and restriction.get("region_id")
                    }
                )
            },
        )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
