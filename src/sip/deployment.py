from __future__ import annotations

import base64
import hmac
import json
import re
import threading
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .audit import AuditService
from .canonical import canonical_json, canonical_sha256, new_uuid, sha256_file
from .database import (
    AssetRefRow,
    AutoscalingAdmissionRow,
    AutoscalingPolicyRow,
    AwsEnvironmentManifestRow,
    ConsentGrantRow,
    Database,
    DeploymentAdmissionRow,
    DeploymentDriftReportRow,
    DeploymentProfileRow,
    EdgeNodeRow,
    EdgeUpdateApplicationRow,
    ExportRow,
    GracefulShutdownEvidenceRow,
    HybridTransferPolicyRow,
    LocalUpgradeRehearsalRow,
    ModelManifestRow,
    OfflineUpdatePackageRow,
    OperationRow,
    ProjectDeploymentBindingRow,
    ProjectDeploymentMigrationRow,
    ProjectRow,
    ProviderReplacementPathRow,
    ResidencyPolicyRow,
    RoleBindingRow,
    CdnDerivativeDeliveryRow,
    SceneCommitRow,
    TenantRow,
)
from .errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from .events import OutboxEventFactory
from .temporal import db_now

if TYPE_CHECKING:
    from .security_ops import SecurityOperationsService

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,127}$")
_REGION = re.compile(r"^[a-z]{2}(?:-gov)?-[a-z]+-\d$|^[a-z][a-z0-9-]{1,31}$")
_IMAGE = re.compile(r"^[a-z0-9][a-z0-9./_-]*:[A-Za-z0-9_.-]+@sha256:[0-9a-f]{64}$")
_SECRET_REF = re.compile(r"^(?:secret|vault|aws-sm|k8s-secret)://[A-Za-z0-9_./:@-]{1,240}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")

MODES = {"local_only", "edge", "hybrid", "single_tenant_cloud", "multi_tenant_cloud", "aws_reference"}
ADMISSION_TYPES = {"asset_upload", "worker_schedule", "asset_transfer", "autoscale", "gpu_queue", "production_promotion"}
TRANSFER_STAGES = {"raw", "normalized", "redacted_derivative", "approved_derivative", "published_derivative"}
TRANSFER_STAGE_ORDER = {name: index for index, name in enumerate(("raw", "normalized", "redacted_derivative", "approved_derivative", "published_derivative"))}
SENSITIVE_ASSET_CLASSES = {"raw_capture", "private_media", "biometric", "critical_infrastructure", "restricted_construction", "liveforever_private"}


class DeploymentService:
    """Governed deployment profiles, residency, edge enrollment, and portability.

    This service is deliberately provider-neutral.  It records immutable intent and
    verification evidence, but it does not claim that a cloud, cluster, or physical
    edge node exists merely because its structural manifest passed local validation.
    """

    def __init__(
        self,
        database: Database,
        audit: AuditService,
        signing_key: bytes,
        *,
        root: Path | None = None,
        environment: str = "development",
        security_ops: "SecurityOperationsService | None" = None,
    ) -> None:
        if len(signing_key) < 32:
            raise ValueError("deployment signing key must be at least 32 bytes")
        self.database = database
        self.audit = audit
        self.signing_key = signing_key
        self.root = (root or Path(__file__).resolve().parents[2]).resolve()
        self.environment = environment
        self.security_ops = security_ops
        self.events = OutboxEventFactory()
        self._autoscaling_lock = threading.RLock()

    # ---------- canonical contracts and profile manifests ----------

    def canonical_contracts(self) -> dict[str, Any]:
        contract_files = {
            "package": "capture-root.schema.json",
            "scene": "scene-entity.schema.json",
            "evidence": "evidence-record.schema.json",
            "export": "preservation-manifest.schema.json",
        }
        values: dict[str, Any] = {}
        for role, filename in contract_files.items():
            path = self.root / "schemas" / "jsonschema" / filename
            if not path.is_file():
                raise ValidationError("DEPLOYMENT_CONTRACT_MISSING", "canonical contract is missing", {"role": role, "path": str(path)})
            document = json.loads(path.read_text(encoding="utf-8"))
            values[role] = {
                "schema_id": document.get("$id"),
                "schema_version": "1.1.0",
                "sha256": sha256_file(path),
            }
        return values

    def register_profile(
        self,
        *,
        name: str,
        revision: str,
        mode: str,
        features: dict[str, Any],
        service_images: dict[str, str],
        infrastructure_versions: dict[str, str],
        secret_references: dict[str, str],
        network_policy: dict[str, Any],
        resource_limits: dict[str, Any],
        supported_regions: list[str],
        degraded_modes: dict[str, Any],
        provider_replacements: dict[str, Any],
        production_approved: bool,
        actor_id: str,
        supersedes_profile_id: str | None = None,
    ) -> dict[str, Any]:
        self._validate_identifier(name, "DEPLOYMENT_PROFILE_NAME_INVALID")
        self._validate_version(revision)
        if mode not in MODES:
            raise ValidationError("DEPLOYMENT_MODE_INVALID", "deployment mode is not supported", {"mode": mode})
        self._validate_features(features)
        self._validate_pins(service_images, infrastructure_versions, secret_references, network_policy, resource_limits)
        regions = self._validate_regions(supported_regions)
        if not isinstance(degraded_modes, dict) or not degraded_modes:
            raise ValidationError("DEPLOYMENT_DEGRADED_MODES_REQUIRED", "deployment profile must declare degraded behavior")
        if not isinstance(provider_replacements, dict) or not provider_replacements:
            raise ValidationError("DEPLOYMENT_REPLACEMENT_PATHS_REQUIRED", "provider replacement and export paths are required")
        if production_approved:
            raise AuthorizationError(
                "DEPLOYMENT_PRODUCTION_APPROVAL_EXTERNAL",
                "local profile registration cannot grant production approval",
                {"required": "independent deployed infrastructure evidence"},
            )
        contracts = self.canonical_contracts()
        contracts_hash = canonical_sha256(contracts)
        body = {
            "schema_version": "1.1.0",
            "name": name,
            "revision": revision,
            "mode": mode,
            "canonical_contracts": contracts,
            "features": features,
            "service_images": dict(sorted(service_images.items())),
            "infrastructure_versions": dict(sorted(infrastructure_versions.items())),
            "secret_references": dict(sorted(secret_references.items())),
            "network_policy": network_policy,
            "resource_limits": resource_limits,
            "supported_regions": regions,
            "degraded_modes": degraded_modes,
            "provider_replacements": provider_replacements,
            "production_approved": False,
            "supersedes_profile_id": supersedes_profile_id,
        }
        digest = canonical_sha256(body)
        with self.database.session() as session:
            existing = session.scalar(select(DeploymentProfileRow).where(DeploymentProfileRow.profile_hash == digest))
            if existing:
                return self._profile(existing, idempotent_replay=True)
            if supersedes_profile_id:
                prior = session.get(DeploymentProfileRow, supersedes_profile_id)
                if prior is None:
                    raise NotFoundError("deployment_profile", supersedes_profile_id)
            identifier = new_uuid()
            row = DeploymentProfileRow(
                deployment_profile_id=identifier,
                name=name,
                revision=revision,
                mode=mode,
                canonical_contracts_json=contracts,
                canonical_contracts_hash=contracts_hash,
                features_json=features,
                service_images_json=dict(sorted(service_images.items())),
                infrastructure_versions_json=dict(sorted(infrastructure_versions.items())),
                secret_references_json=dict(sorted(secret_references.items())),
                network_policy_json=network_policy,
                resource_limits_json=resource_limits,
                supported_regions_json=regions,
                degraded_modes_json=degraded_modes,
                provider_replacements_json=provider_replacements,
                production_approved=False,
                state="active",
                profile_hash=digest,
                supersedes_profile_id=supersedes_profile_id,
                created_by=actor_id,
            )
            session.add(row)
            session.add(self._event(session, event_type="deployment.profile.registered", tenant_id="platform", project_id=None, aggregate_type="deployment_profile", aggregate_id=identifier, actor_id=actor_id, payload={"profile_hash": digest, "mode": mode, "revision": revision}))
            self.audit.append(tenant_id="platform", project_id=None, actor_id=actor_id, action="deployment.profile.register", resource_type="deployment_profile", resource_id=identifier, outcome="allowed", details={"profile_hash": digest, "mode": mode}, session=session)
            return self._profile(row, idempotent_replay=False)

    def get_profile(self, profile_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(DeploymentProfileRow, profile_id)
            if row is None:
                raise NotFoundError("deployment_profile", profile_id)
            return self._profile(row, idempotent_replay=False)

    def feature_availability(self, *, profile_id: str, feature: str) -> dict[str, Any]:
        row = self._require_profile(profile_id)
        details = row.features_json.get(feature)
        if not isinstance(details, dict):
            raise NotFoundError("deployment_feature", feature)
        return {
            "deployment_profile_id": profile_id,
            "feature": feature,
            "enabled": bool(details.get("enabled", False)),
            "requires_cloud_connectivity": bool(details.get("requires_cloud_connectivity", False)),
            "when_unavailable": details.get("when_unavailable"),
            "administrator_notice": details.get("administrator_notice"),
            "mode": row.mode,
        }

    def assign_project_profile(
        self,
        *,
        tenant_id: str,
        project_id: str,
        deployment_profile_id: str,
        residency_policy_id: str | None,
        transfer_policy_id: str | None,
        revision: str,
        feature_overrides: dict[str, Any],
        cloud_dependencies_acknowledged: bool,
        actor_id: str,
    ) -> dict[str, Any]:
        self._validate_version(revision)
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            profile = session.get(DeploymentProfileRow, deployment_profile_id)
            if profile is None or profile.state != "active":
                raise NotFoundError("deployment_profile", deployment_profile_id)
            if residency_policy_id:
                policy = session.get(ResidencyPolicyRow, residency_policy_id)
                if policy is None or policy.tenant_id != tenant_id or policy.project_id != project_id or policy.state != "active":
                    raise AuthorizationError("DEPLOYMENT_RESIDENCY_SCOPE_MISMATCH", "residency policy is not active in project scope")
            if transfer_policy_id:
                policy = session.get(HybridTransferPolicyRow, transfer_policy_id)
                if policy is None or policy.tenant_id != tenant_id or policy.project_id != project_id or policy.state != "active":
                    raise AuthorizationError("DEPLOYMENT_TRANSFER_SCOPE_MISMATCH", "transfer policy is not active in project scope")
            cloud_required = any(isinstance(value, dict) and value.get("enabled") is True and value.get("requires_cloud_connectivity") is True for value in profile.features_json.values())
            if cloud_required and not cloud_dependencies_acknowledged:
                raise AuthorizationError("DEPLOYMENT_CLOUD_DEPENDENCY_ACK_REQUIRED", "cloud-dependent features require explicit administrator acknowledgement")
            current = session.scalar(select(ProjectDeploymentBindingRow).where(ProjectDeploymentBindingRow.tenant_id == tenant_id, ProjectDeploymentBindingRow.project_id == project_id, ProjectDeploymentBindingRow.state == "active"))
            if current and current.deployment_profile_id == deployment_profile_id and current.residency_policy_id == residency_policy_id and current.transfer_policy_id == transfer_policy_id and current.revision == revision and current.feature_overrides_json == feature_overrides and current.cloud_dependencies_acknowledged == cloud_dependencies_acknowledged:
                return self._binding(current, idempotent_replay=True)
            if current:
                current.state = "superseded"
                current.superseded_at = db_now()
            body = {"tenant_id": tenant_id, "project_id": project_id, "deployment_profile_id": deployment_profile_id, "residency_policy_id": residency_policy_id, "transfer_policy_id": transfer_policy_id, "revision": revision, "feature_overrides": feature_overrides, "cloud_dependencies_acknowledged": cloud_dependencies_acknowledged}
            identifier = new_uuid()
            row = ProjectDeploymentBindingRow(binding_id=identifier, tenant_id=tenant_id, project_id=project_id, deployment_profile_id=deployment_profile_id, residency_policy_id=residency_policy_id, transfer_policy_id=transfer_policy_id, revision=revision, feature_overrides_json=feature_overrides, cloud_dependencies_acknowledged=cloud_dependencies_acknowledged, state="active", binding_hash=canonical_sha256(body), created_by=actor_id)
            session.add(row)
            session.add(self._event(session, event_type="deployment.project.assigned", tenant_id=tenant_id, project_id=project_id, aggregate_type="project_deployment", aggregate_id=identifier, actor_id=actor_id, payload={"profile_id": deployment_profile_id, "binding_hash": row.binding_hash}))
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="deployment.project.assign", resource_type="project_deployment", resource_id=identifier, outcome="allowed", details={"profile_id": deployment_profile_id}, session=session)
            return self._binding(row, idempotent_replay=False)

    # ---------- residency and hybrid transfer ----------

    def register_residency_policy(self, *, tenant_id: str, project_id: str, revision: str, home_region: str, allowed_regions: list[str], allowed_modes: list[str], asset_rules: dict[str, Any], worker_rules: dict[str, Any], provider_rules: dict[str, Any], default_action: str, actor_id: str) -> dict[str, Any]:
        self._validate_version(revision)
        regions = self._validate_regions(allowed_regions)
        home_region = self._validate_regions([home_region])[0]
        if home_region not in regions:
            raise ValidationError("RESIDENCY_HOME_REGION_DENIED", "home region must be included in allowed regions")
        modes = sorted(set(allowed_modes))
        if not modes or any(mode not in MODES for mode in modes):
            raise ValidationError("RESIDENCY_MODES_INVALID", "residency policy contains unsupported deployment modes")
        if default_action != "deny":
            raise ValidationError("RESIDENCY_DEFAULT_MUST_DENY", "residency policy must fail closed")
        if not isinstance(asset_rules, dict) or not asset_rules or not isinstance(worker_rules, dict) or not worker_rules or not isinstance(provider_rules, dict) or not provider_rules:
            raise ValidationError("RESIDENCY_RULES_REQUIRED", "asset, worker, and provider residency rules are required")
        body = {"tenant_id": tenant_id, "project_id": project_id, "revision": revision, "home_region": home_region, "allowed_regions": regions, "allowed_modes": modes, "asset_rules": asset_rules, "worker_rules": worker_rules, "provider_rules": provider_rules, "default_action": default_action}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            existing = session.scalar(select(ResidencyPolicyRow).where(ResidencyPolicyRow.policy_hash == digest))
            if existing:
                return self._residency(existing, True)
            identifier = new_uuid()
            row = ResidencyPolicyRow(residency_policy_id=identifier, tenant_id=tenant_id, project_id=project_id, revision=revision, home_region=home_region, allowed_regions_json=regions, allowed_modes_json=modes, asset_rules_json=asset_rules, worker_rules_json=worker_rules, provider_rules_json=provider_rules, default_action="deny", policy_hash=digest, state="active", created_by=actor_id)
            session.add(row)
            session.add(self._event(session, event_type="deployment.residency.registered", tenant_id=tenant_id, project_id=project_id, aggregate_type="residency_policy", aggregate_id=identifier, actor_id=actor_id, payload={"policy_hash": digest, "regions": regions, "modes": modes}))
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="deployment.residency.register", resource_type="residency_policy", resource_id=identifier, outcome="allowed", details={"policy_hash": digest}, session=session)
            return self._residency(row, False)

    def register_transfer_policy(self, *, tenant_id: str, project_id: str, revision: str, source_profile_id: str, destination_profile_id: str, rules: list[dict[str, Any]], purpose: str, actor_id: str) -> dict[str, Any]:
        self._validate_version(revision)
        self._validate_identifier(purpose, "TRANSFER_PURPOSE_INVALID")
        if not rules:
            raise ValidationError("TRANSFER_RULES_REQUIRED", "hybrid transfer policy requires explicit rules")
        normalized: list[dict[str, Any]] = []
        for rule in rules:
            asset_class = str(rule.get("asset_class", ""))
            minimum_stage = str(rule.get("minimum_stage", ""))
            if not asset_class or minimum_stage not in TRANSFER_STAGES:
                raise ValidationError("TRANSFER_RULE_INVALID", "transfer rule requires asset_class and valid minimum_stage")
            destinations = self._validate_regions(list(rule.get("allowed_regions", [])))
            if not destinations:
                raise ValidationError("TRANSFER_REGIONS_REQUIRED", "transfer rule must declare destination regions")
            if asset_class in SENSITIVE_ASSET_CLASSES and TRANSFER_STAGE_ORDER[minimum_stage] < TRANSFER_STAGE_ORDER["redacted_derivative"]:
                raise ValidationError("TRANSFER_SENSITIVE_STAGE_TOO_EARLY", "sensitive assets cannot leave before redaction")
            normalized.append({"asset_class": asset_class, "minimum_stage": minimum_stage, "allowed_regions": destinations, "allowed_purposes": sorted(set(rule.get("allowed_purposes", [purpose]))), "requires_approval": bool(rule.get("requires_approval", True))})
        normalized.sort(key=lambda item: item["asset_class"])
        body = {"tenant_id": tenant_id, "project_id": project_id, "revision": revision, "source_profile_id": source_profile_id, "destination_profile_id": destination_profile_id, "rules": normalized, "purpose": purpose}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            for profile_id in (source_profile_id, destination_profile_id):
                if session.get(DeploymentProfileRow, profile_id) is None:
                    raise NotFoundError("deployment_profile", profile_id)
            existing = session.scalar(select(HybridTransferPolicyRow).where(HybridTransferPolicyRow.policy_hash == digest))
            if existing:
                return self._transfer(existing, True)
            identifier = new_uuid()
            row = HybridTransferPolicyRow(transfer_policy_id=identifier, tenant_id=tenant_id, project_id=project_id, revision=revision, source_profile_id=source_profile_id, destination_profile_id=destination_profile_id, rules_json=normalized, purpose=purpose, policy_hash=digest, state="active", created_by=actor_id)
            session.add(row)
            session.add(self._event(session, event_type="deployment.transfer.registered", tenant_id=tenant_id, project_id=project_id, aggregate_type="transfer_policy", aggregate_id=identifier, actor_id=actor_id, payload={"policy_hash": digest, "rule_count": len(normalized)}))
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="deployment.transfer.register", resource_type="transfer_policy", resource_id=identifier, outcome="allowed", details={"policy_hash": digest}, session=session)
            return self._transfer(row, False)

    def authorize_admission(self, *, tenant_id: str, project_id: str | None, admission_type: str, deployment_profile_id: str | None, region: str | None, request: dict[str, Any], actor_id: str) -> dict[str, Any]:
        if admission_type not in ADMISSION_TYPES:
            raise ValidationError("DEPLOYMENT_ADMISSION_TYPE_INVALID", "unsupported deployment admission type")
        if any(str(key).startswith("precomputed_") for key in request):
            raise ValidationError("DEPLOYMENT_ADMISSION_PRECOMPUTED_PROHIBITED", "callers may not submit precomputed admission decisions")
        decision, reason, obligations = self._evaluate_admission(tenant_id=tenant_id, project_id=project_id, admission_type=admission_type, deployment_profile_id=deployment_profile_id, region=region, request=request)
        return self._record_admission(tenant_id=tenant_id, project_id=project_id, admission_type=admission_type, deployment_profile_id=deployment_profile_id, region=region, request=request, decision=decision, reason=reason, obligations=obligations, actor_id=actor_id, raise_on_denial=True)

    def sign_manifest(self, manifest: dict[str, Any]) -> str:
        digest = canonical_sha256(manifest)
        return base64.b64encode(hmac.new(self.signing_key, digest.encode("ascii"), sha256).digest()).decode("ascii")

    def enroll_edge_node(self, *, tenant_id: str, project_id: str | None, deployment_profile_id: str, node_identity: str, identity_public_key_hash: str, software_manifest: dict[str, Any], software_signature: str, signing_key_id: str, disk_encryption: dict[str, Any], region: str, capabilities: dict[str, Any], actor_id: str) -> dict[str, Any]:
        self._validate_identifier(node_identity, "EDGE_IDENTITY_INVALID")
        self._require_sha256(identity_public_key_hash, "EDGE_PUBLIC_KEY_HASH_INVALID")
        self._validate_regions([region])
        profile = self._require_profile(deployment_profile_id)
        if profile.mode not in {"edge", "hybrid", "local_only"}:
            raise ValidationError("EDGE_PROFILE_MODE_INVALID", "edge enrollment requires an edge-capable profile")
        if disk_encryption.get("enabled") is not True or disk_encryption.get("attested") is not True or not _SHA256.fullmatch(str(disk_encryption.get("attestation_hash", ""))):
            raise ValidationError("EDGE_DISK_ENCRYPTION_REQUIRED", "edge disk encryption must be enabled and attested")
        manifest_hash = canonical_sha256(software_manifest)
        if not self._verify_signature(manifest_hash, software_signature):
            raise AuthorizationError("EDGE_SOFTWARE_SIGNATURE_INVALID", "edge software signature is invalid")
        if not _IMAGE.fullmatch(str(software_manifest.get("image", ""))) or not _GIT_SHA.fullmatch(str(software_manifest.get("source_commit", ""))) or not str(software_manifest.get("release", "")).strip():
            raise ValidationError("EDGE_SOFTWARE_MANIFEST_INVALID", "edge software manifest must pin image digest, full source commit, and release")
        body = {"tenant_id": tenant_id, "project_id": project_id, "deployment_profile_id": deployment_profile_id, "node_identity": node_identity, "identity_public_key_hash": identity_public_key_hash, "software_manifest_hash": manifest_hash, "disk_encryption": disk_encryption, "region": region, "capabilities": capabilities}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            self._require_tenant(session, tenant_id)
            if project_id:
                self._require_project(session, tenant_id, project_id)
            existing = session.scalar(select(EdgeNodeRow).where(EdgeNodeRow.enrollment_hash == digest))
            if existing:
                return self._edge(existing, True)
        if self.security_ops is None:
            raise AuthorizationError("EDGE_WORKLOAD_IDENTITY_UNAVAILABLE", "edge enrollment requires the security workload-identity service")
        workload = self.security_ops.issue_workload_identity(tenant_id=tenant_id, project_id=project_id, workload_id=f"edge:{node_identity}", audience="sip-edge-runtime", scopes=["deployment:edge_runtime"], purpose="edge_runtime", ttl_seconds=900, actor_id=actor_id)
        with self.database.session() as session:
            existing = session.scalar(select(EdgeNodeRow).where(EdgeNodeRow.enrollment_hash == digest))
            if existing:
                return self._edge(existing, True)
            identifier = new_uuid()
            row = EdgeNodeRow(edge_node_id=identifier, tenant_id=tenant_id, project_id=project_id, deployment_profile_id=deployment_profile_id, node_identity=node_identity, identity_public_key_hash=identity_public_key_hash, workload_identity_grant_id=str(workload["grant_id"]), software_release=str(software_manifest.get("release", "unknown")), software_manifest_hash=manifest_hash, software_signature=software_signature, signing_key_id=signing_key_id, disk_encryption_json=disk_encryption, region=region, capabilities_json=capabilities, health_json={"status": "enrolled", "workload_identity_expires_at": workload["expires_at"]}, state="enrolled", enrollment_hash=digest, enrolled_by=actor_id)
            session.add(row)
            session.add(self._event(session, event_type="deployment.edge.enrolled", tenant_id=tenant_id, project_id=project_id, aggregate_type="edge_node", aggregate_id=identifier, actor_id=actor_id, payload={"region": region, "profile_id": deployment_profile_id, "software_manifest_hash": manifest_hash}))
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="deployment.edge.enroll", resource_type="edge_node", resource_id=identifier, outcome="allowed", details={"enrollment_hash": digest}, session=session)
            return self._edge(row, False)

    def report_edge_health(self, *, tenant_id: str, edge_node_id: str, health: dict[str, Any], actor_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(EdgeNodeRow, edge_node_id)
            if row is None or row.tenant_id != tenant_id:
                raise NotFoundError("edge_node", edge_node_id)
            if row.state == "revoked":
                raise AuthorizationError("EDGE_NODE_REVOKED", "revoked edge node cannot report health")
            if str(health.get("software_manifest_hash")) != row.software_manifest_hash:
                raise ConflictError("EDGE_SOFTWARE_DRIFT", "edge health report software hash differs from enrolled manifest")
            status = str(health.get("status", ""))
            if status not in {"healthy", "degraded", "offline", "quarantined"}:
                raise ValidationError("EDGE_HEALTH_STATUS_INVALID", "edge health status is invalid")
            row.health_json = dict(health)
            row.last_seen_at = db_now()
            row.state = "healthy" if status == "healthy" else status
            session.add(self._event(session, event_type="deployment.edge.health_reported", tenant_id=tenant_id, project_id=row.project_id, aggregate_type="edge_node", aggregate_id=edge_node_id, actor_id=actor_id, payload={"status": status, "software_manifest_hash": row.software_manifest_hash}))
            return self._edge(row, False)

    def revoke_edge_node(self, *, tenant_id: str, edge_node_id: str, reason: str, actor_id: str) -> dict[str, Any]:
        if not reason.strip():
            raise ValidationError("EDGE_REVOCATION_REASON_REQUIRED", "edge revocation requires a reason")
        with self.database.session() as session:
            row = session.get(EdgeNodeRow, edge_node_id)
            if row is None or row.tenant_id != tenant_id:
                raise NotFoundError("edge_node", edge_node_id)
            if row.state == "revoked":
                return self._edge(row, True)
            row.state = "revoked"
            row.revoked_by = actor_id
            row.revoked_at = db_now()
            row.revocation_reason = reason.strip()
            session.add(self._event(session, event_type="deployment.edge.revoked", tenant_id=tenant_id, project_id=row.project_id, aggregate_type="edge_node", aggregate_id=edge_node_id, actor_id=actor_id, payload={"reason_code": "EDGE_ADMINISTRATIVE_REVOCATION"}))
            self.audit.append(tenant_id=tenant_id, project_id=row.project_id, actor_id=actor_id, action="deployment.edge.revoke", resource_type="edge_node", resource_id=edge_node_id, outcome="allowed", details={"reason": reason.strip()}, session=session)
            result = self._edge(row, False)
            grant_id = row.workload_identity_grant_id
        if self.security_ops is not None:
            self.security_ops.revoke_workload_identity(grant_id=grant_id, tenant_id=tenant_id, actor_id=actor_id)
        return result

    def register_offline_update(self, *, deployment_profile_id: str, manifest: dict[str, Any], signature: str, signing_key_id: str, actor_id: str) -> dict[str, Any]:
        profile = self._require_profile(deployment_profile_id)
        required = {"from_release", "to_release", "bundle_hash", "rollback_bundle_hash", "rollback_signature", "service_images", "migration_head", "compatible_export_versions", "source_commit"}
        if not required.issubset(manifest):
            raise ValidationError("OFFLINE_UPDATE_MANIFEST_INCOMPLETE", "offline update manifest is incomplete", {"missing": sorted(required - set(manifest))})
        for key in ("bundle_hash", "rollback_bundle_hash"):
            self._require_sha256(str(manifest[key]), "OFFLINE_UPDATE_HASH_INVALID")
        if _GIT_SHA.fullmatch(str(manifest["source_commit"])) is None:
            raise ValidationError("OFFLINE_UPDATE_SOURCE_COMMIT_INVALID", "offline update source_commit must be a full Git SHA")
        if not manifest.get("compatible_export_versions"):
            raise ValidationError("OFFLINE_UPDATE_EXPORT_COMPATIBILITY_REQUIRED", "offline update must preserve compatible export paths")
        self._validate_image_map(dict(manifest.get("service_images", {})))
        manifest_hash = canonical_sha256(manifest)
        if not self._verify_signature(manifest_hash, signature):
            raise AuthorizationError("OFFLINE_UPDATE_SIGNATURE_INVALID", "offline update signature is invalid")
        rollback_signature = str(manifest["rollback_signature"])
        if not self._verify_signature(str(manifest["rollback_bundle_hash"]), rollback_signature):
            raise AuthorizationError("OFFLINE_ROLLBACK_SIGNATURE_INVALID", "offline rollback signature is invalid")
        with self.database.session() as session:
            existing = session.scalar(select(OfflineUpdatePackageRow).where(OfflineUpdatePackageRow.manifest_hash == manifest_hash))
            if existing:
                return self._update(existing, True)
            identifier = new_uuid()
            row = OfflineUpdatePackageRow(update_id=identifier, deployment_profile_id=profile.deployment_profile_id, from_release=str(manifest["from_release"]), to_release=str(manifest["to_release"]), bundle_hash=str(manifest["bundle_hash"]), manifest_json=manifest, manifest_hash=manifest_hash, signature=signature, signing_key_id=signing_key_id, rollback_bundle_hash=str(manifest["rollback_bundle_hash"]), rollback_signature=rollback_signature, compatible_export_versions_json=list(manifest["compatible_export_versions"]), state="verified", created_by=actor_id)
            session.add(row)
            session.add(self._event(session, event_type="deployment.update.registered", tenant_id="platform", project_id=None, aggregate_type="offline_update", aggregate_id=identifier, actor_id=actor_id, payload={"profile_id": deployment_profile_id, "from_release": row.from_release, "to_release": row.to_release, "manifest_hash": manifest_hash}))
            return self._update(row, False)

    def apply_offline_update(self, *, tenant_id: str, edge_node_id: str, update_id: str, current_release: str, actor_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            node = session.get(EdgeNodeRow, edge_node_id)
            update = session.get(OfflineUpdatePackageRow, update_id)
            if node is None or node.tenant_id != tenant_id:
                raise NotFoundError("edge_node", edge_node_id)
            if update is None:
                raise NotFoundError("offline_update", update_id)
            if node.state == "revoked":
                raise AuthorizationError("EDGE_NODE_REVOKED", "revoked node cannot apply updates")
            if update.deployment_profile_id != node.deployment_profile_id or update.from_release != current_release:
                raise ConflictError("OFFLINE_UPDATE_BASE_MISMATCH", "offline update does not match node profile or current release")
            if not self._verify_signature(update.manifest_hash, update.signature):
                raise AuthorizationError("OFFLINE_UPDATE_SIGNATURE_INVALID", "stored offline update signature is invalid")
            existing_application = session.scalar(select(EdgeUpdateApplicationRow).where(EdgeUpdateApplicationRow.edge_node_id == edge_node_id, EdgeUpdateApplicationRow.update_id == update_id))
            if existing_application:
                return {"edge_node_id": edge_node_id, "update_id": update_id, "release": existing_application.target_release, "rollback_bundle_hash": update.rollback_bundle_hash, "state": existing_application.state, "idempotent_replay": True}
            prior = node.software_manifest_hash
            node.software_manifest_hash = update.manifest_hash
            node.software_release = update.to_release
            node.health_json = {**node.health_json, "release": update.to_release, "previous_software_manifest_hash": prior, "rollback_bundle_hash": update.rollback_bundle_hash}
            node.state = "enrolled"
            application_body = {"edge_node_id": edge_node_id, "update_id": update_id, "previous_release": current_release, "target_release": update.to_release}
            session.add(EdgeUpdateApplicationRow(application_id=new_uuid(), edge_node_id=edge_node_id, update_id=update_id, previous_release=current_release, target_release=update.to_release, state="applied", application_hash=canonical_sha256(application_body), applied_by=actor_id))
            session.add(self._event(session, event_type="deployment.update.applied", tenant_id=tenant_id, project_id=node.project_id, aggregate_type="edge_node", aggregate_id=edge_node_id, actor_id=actor_id, payload={"update_id": update_id, "from_release": update.from_release, "to_release": update.to_release, "rollback_available": True}))
            return {"edge_node_id": edge_node_id, "update_id": update_id, "release": update.to_release, "rollback_bundle_hash": update.rollback_bundle_hash, "state": "applied", "idempotent_replay": False}

    # ---------- portability and scaling ----------

    def create_project_migration(self, *, tenant_id: str, project_id: str, source_profile_id: str, target_profile_id: str, idempotency_key: str, actor_id: str) -> dict[str, Any]:
        if not idempotency_key.strip():
            raise ValidationError("DEPLOYMENT_MIGRATION_IDEMPOTENCY_REQUIRED", "project migration requires an idempotency key")
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            for profile_id in (source_profile_id, target_profile_id):
                if session.get(DeploymentProfileRow, profile_id) is None:
                    raise NotFoundError("deployment_profile", profile_id)
            existing = session.scalar(select(ProjectDeploymentMigrationRow).where(ProjectDeploymentMigrationRow.tenant_id == tenant_id, ProjectDeploymentMigrationRow.project_id == project_id, ProjectDeploymentMigrationRow.idempotency_key == idempotency_key))
            if existing:
                if existing.source_profile_id != source_profile_id or existing.target_profile_id != target_profile_id:
                    raise ConflictError("DEPLOYMENT_MIGRATION_IDEMPOTENCY_CONFLICT", "idempotency key was reused for a different migration")
                return self._migration(existing, True)
            source_snapshot = self._project_snapshot(session, tenant_id, project_id)
            source_hash = canonical_sha256(source_snapshot)
            body = {"tenant_id": tenant_id, "project_id": project_id, "source_profile_id": source_profile_id, "target_profile_id": target_profile_id, "idempotency_key": idempotency_key, "source_snapshot_hash": source_hash}
            identifier = new_uuid()
            row = ProjectDeploymentMigrationRow(migration_id=identifier, tenant_id=tenant_id, project_id=project_id, source_profile_id=source_profile_id, target_profile_id=target_profile_id, idempotency_key=idempotency_key, source_snapshot_json=source_snapshot, source_snapshot_hash=source_hash, target_snapshot_json={}, target_snapshot_hash=None, validation_json={"state": "pending"}, state="planned", migration_hash=canonical_sha256(body), created_by=actor_id)
            session.add(row)
            session.add(self._event(session, event_type="deployment.migration.created", tenant_id=tenant_id, project_id=project_id, aggregate_type="deployment_migration", aggregate_id=identifier, actor_id=actor_id, payload={"source_profile_id": source_profile_id, "target_profile_id": target_profile_id, "source_snapshot_hash": source_hash}))
            return self._migration(row, False)

    def complete_project_migration(self, *, tenant_id: str, project_id: str, migration_id: str, actor_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(ProjectDeploymentMigrationRow, migration_id)
            if row is None or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("deployment_migration", migration_id)
            if row.state == "completed":
                return self._migration(row, True)
            current = session.scalar(select(ProjectDeploymentBindingRow).where(ProjectDeploymentBindingRow.tenant_id == tenant_id, ProjectDeploymentBindingRow.project_id == project_id, ProjectDeploymentBindingRow.state == "active"))
            if current and current.deployment_profile_id != row.source_profile_id:
                raise ConflictError("DEPLOYMENT_MIGRATION_SOURCE_DRIFT", "project deployment binding no longer matches the migration source profile")
            if current:
                current.state = "superseded"
                current.superseded_at = db_now()
            binding_body = {"tenant_id": tenant_id, "project_id": project_id, "deployment_profile_id": row.target_profile_id, "migration_id": migration_id}
            session.add(ProjectDeploymentBindingRow(binding_id=new_uuid(), tenant_id=tenant_id, project_id=project_id, deployment_profile_id=row.target_profile_id, residency_policy_id=current.residency_policy_id if current else None, transfer_policy_id=current.transfer_policy_id if current else None, revision=f"migration-{migration_id}", feature_overrides_json=current.feature_overrides_json if current else {}, cloud_dependencies_acknowledged=current.cloud_dependencies_acknowledged if current else False, state="active", binding_hash=canonical_sha256(binding_body), created_by=actor_id))
            target_snapshot = self._project_snapshot(session, tenant_id, project_id)
            target_hash = canonical_sha256(target_snapshot)
            preserved = target_snapshot == row.source_snapshot_json
            validation = {"preserved": preserved, "source_snapshot_hash": row.source_snapshot_hash, "target_snapshot_hash": target_hash, "checked_categories": sorted(target_snapshot.keys())}
            if not preserved:
                raise ConflictError("DEPLOYMENT_MIGRATION_SEMANTIC_DRIFT", "project migration would change stable identity, history, permissions, consent, hashes, or manifests", validation)
            row.target_snapshot_json = target_snapshot
            row.target_snapshot_hash = target_hash
            row.validation_json = validation
            row.state = "completed"
            row.completed_at = db_now()
            session.add(self._event(session, event_type="deployment.migration.completed", tenant_id=tenant_id, project_id=project_id, aggregate_type="deployment_migration", aggregate_id=migration_id, actor_id=actor_id, payload={"source_profile_id": row.source_profile_id, "target_profile_id": row.target_profile_id, "snapshot_hash": target_hash, "preserved": True}))
            self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="deployment.migration.complete", resource_type="deployment_migration", resource_id=migration_id, outcome="allowed", details=validation, session=session)
            return self._migration(row, False)

    def register_autoscaling_policy(self, *, tenant_id: str, project_id: str | None, queue_class: str, revision: str, min_replicas: int, max_replicas: int, tenant_concurrency_limit: int, profile_quotas: dict[str, int], global_budget_limit: float, currency: str, dead_letter: dict[str, Any], restricted_egress: bool, actor_id: str) -> dict[str, Any]:
        self._validate_version(revision)
        self._validate_identifier(queue_class, "AUTOSCALING_QUEUE_CLASS_INVALID")
        if min_replicas < 0 or max_replicas < 1 or max_replicas < min_replicas or tenant_concurrency_limit < 1:
            raise ValidationError("AUTOSCALING_LIMITS_INVALID", "autoscaling replica and concurrency limits are invalid")
        if global_budget_limit <= 0 or len(currency) != 3:
            raise ValidationError("AUTOSCALING_BUDGET_INVALID", "autoscaling requires a positive global budget and currency")
        if not profile_quotas or any(value < 0 for value in profile_quotas.values()):
            raise ValidationError("AUTOSCALING_PROFILE_QUOTAS_INVALID", "autoscaling profile quotas are required")
        if not dead_letter.get("enabled") or not dead_letter.get("queue") or int(dead_letter.get("max_attempts", 0)) < 1:
            raise ValidationError("AUTOSCALING_DEAD_LETTER_REQUIRED", "GPU and worker queues require dead-letter handling")
        if restricted_egress is not True:
            raise ValidationError("AUTOSCALING_EGRESS_MUST_BE_RESTRICTED", "compute queue egress must be restricted")
        body = {"tenant_id": tenant_id, "project_id": project_id, "queue_class": queue_class, "revision": revision, "min_replicas": min_replicas, "max_replicas": max_replicas, "tenant_concurrency_limit": tenant_concurrency_limit, "profile_quotas": dict(sorted(profile_quotas.items())), "global_budget_limit": global_budget_limit, "currency": currency.upper(), "dead_letter": dead_letter, "restricted_egress": True}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            self._require_tenant(session, tenant_id)
            if project_id:
                self._require_project(session, tenant_id, project_id)
            existing = session.scalar(select(AutoscalingPolicyRow).where(AutoscalingPolicyRow.policy_hash == digest))
            if existing:
                return self._autoscaling(existing, True)
            identifier = new_uuid()
            row = AutoscalingPolicyRow(autoscaling_policy_id=identifier, tenant_id=tenant_id, project_id=project_id, queue_class=queue_class, revision=revision, min_replicas=min_replicas, max_replicas=max_replicas, tenant_concurrency_limit=tenant_concurrency_limit, profile_quotas_json=dict(sorted(profile_quotas.items())), global_budget_limit=global_budget_limit, currency=currency.upper(), dead_letter_json=dead_letter, restricted_egress=True, policy_hash=digest, state="active", created_by=actor_id)
            session.add(row)
            session.add(self._event(session, event_type="deployment.autoscaling.registered", tenant_id=tenant_id, project_id=project_id, aggregate_type="autoscaling_policy", aggregate_id=identifier, actor_id=actor_id, payload={"queue_class": queue_class, "max_replicas": max_replicas, "budget_limit": global_budget_limit}))
            return self._autoscaling(row, False)

    def admit_autoscaling(self, *, tenant_id: str, project_id: str | None, autoscaling_policy_id: str, compute_profile: str, requested_replicas: int, current_tenant_jobs: int, projected_cost: float, actor_id: str, current_replicas: int = 0) -> dict[str, Any]:
        """Admit autoscaling with uniqueness-backed concurrent idempotency.

        Two schedulers can evaluate the same immutable request concurrently.  The
        database uniqueness constraint is the final arbiter; the losing transaction
        is rolled back and resolves the committed decision in a fresh transaction.
        A raw database exception is never exposed as an ambiguous scheduling result.
        """
        try:
            return self._admit_autoscaling_once(
                tenant_id=tenant_id,
                project_id=project_id,
                autoscaling_policy_id=autoscaling_policy_id,
                compute_profile=compute_profile,
                requested_replicas=requested_replicas,
                current_tenant_jobs=current_tenant_jobs,
                projected_cost=projected_cost,
                actor_id=actor_id,
                current_replicas=current_replicas,
            )
        except IntegrityError as exc:
            text = str(exc).lower()
            if "autoscaling_admissions.decision_hash" not in text and "decision_hash" not in text:
                raise
            return self._resolve_concurrent_autoscaling(
                tenant_id=tenant_id,
                project_id=project_id,
                autoscaling_policy_id=autoscaling_policy_id,
                compute_profile=compute_profile,
                requested_replicas=requested_replicas,
                current_tenant_jobs=current_tenant_jobs,
                projected_cost=projected_cost,
                actor_id=actor_id,
                current_replicas=current_replicas,
            )

    def _autoscaling_decision(
        self,
        *,
        policy: AutoscalingPolicyRow,
        tenant_id: str,
        project_id: str | None,
        autoscaling_policy_id: str,
        compute_profile: str,
        requested_replicas: int,
        current_tenant_jobs: int,
        projected_cost: float,
        current_replicas: int,
    ) -> tuple[bool, str, dict[str, Any], str]:
        quota = int(policy.profile_quotas_json.get(compute_profile, 0))
        allowed, reason = True, "ALLOW"
        if requested_replicas < policy.min_replicas or requested_replicas > policy.max_replicas:
            allowed, reason = False, "AUTOSCALING_REPLICA_LIMIT"
        elif requested_replicas > quota:
            allowed, reason = False, "AUTOSCALING_PROFILE_QUOTA"
        elif current_tenant_jobs + requested_replicas > policy.tenant_concurrency_limit:
            allowed, reason = False, "AUTOSCALING_TENANT_QUOTA"
        elif projected_cost > policy.global_budget_limit:
            allowed, reason = False, "AUTOSCALING_GLOBAL_BUDGET"
        elif not policy.restricted_egress:
            allowed, reason = False, "AUTOSCALING_EGRESS_POLICY"
        body = {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "autoscaling_policy_id": autoscaling_policy_id,
            "queue_class": policy.queue_class,
            "capability_profile": compute_profile,
            "current_replicas": current_replicas,
            "requested_replicas": requested_replicas,
            "active_jobs": current_tenant_jobs,
            "estimated_incremental_cost": projected_cost,
            "global_cost_after": projected_cost,
            "decision": "allow" if allowed else "deny",
            "reason_code": reason,
        }
        return allowed, reason, body, canonical_sha256(body)

    def _admit_autoscaling_once(self, *, tenant_id: str, project_id: str | None, autoscaling_policy_id: str, compute_profile: str, requested_replicas: int, current_tenant_jobs: int, projected_cost: float, actor_id: str, current_replicas: int = 0) -> dict[str, Any]:
        with self.database.session() as session:
            policy = session.get(AutoscalingPolicyRow, autoscaling_policy_id)
            if policy is None or policy.tenant_id != tenant_id or policy.project_id != project_id or policy.state != "active":
                raise NotFoundError("autoscaling_policy", autoscaling_policy_id)
            allowed, reason, body, digest = self._autoscaling_decision(
                policy=policy, tenant_id=tenant_id, project_id=project_id,
                autoscaling_policy_id=autoscaling_policy_id, compute_profile=compute_profile,
                requested_replicas=requested_replicas, current_tenant_jobs=current_tenant_jobs,
                projected_cost=projected_cost, current_replicas=current_replicas,
            )
            existing = session.scalar(select(AutoscalingAdmissionRow).where(AutoscalingAdmissionRow.decision_hash == digest))
            if existing:
                result = {"autoscaling_admission_id": existing.admission_id, **body, "admitted_replicas": existing.admitted_replicas, "idempotent_replay": True}
            else:
                row = AutoscalingAdmissionRow(
                    admission_id=new_uuid(), tenant_id=tenant_id, project_id=project_id,
                    autoscaling_policy_id=autoscaling_policy_id, queue_class=policy.queue_class,
                    capability_profile=compute_profile, current_replicas=current_replicas,
                    requested_replicas=requested_replicas,
                    admitted_replicas=requested_replicas if allowed else current_replicas,
                    active_jobs=current_tenant_jobs, estimated_incremental_cost=projected_cost,
                    global_cost_after=projected_cost, decision="allow" if allowed else "deny",
                    reason_code=reason, decision_hash=digest, requested_by=actor_id,
                )
                session.add(row)
                session.flush()
                session.add(self._event(session, event_type="deployment.autoscaling.decided", tenant_id=tenant_id, project_id=project_id, aggregate_type="autoscaling_admission", aggregate_id=row.admission_id, actor_id=actor_id, payload={"decision": row.decision, "reason_code": reason, "requested_replicas": requested_replicas, "admitted_replicas": row.admitted_replicas}))
                self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action="deployment.autoscaling.admit", resource_type="autoscaling_admission", resource_id=row.admission_id, outcome="allowed" if allowed else "denied", details={"reason_code": reason, "decision_hash": digest}, session=session)
                result = {"autoscaling_admission_id": row.admission_id, **body, "admitted_replicas": row.admitted_replicas, "idempotent_replay": False}
        if not allowed:
            raise AuthorizationError(reason, "autoscaling admission denied", {"autoscaling_admission_id": result["autoscaling_admission_id"]})
        return result

    def _resolve_concurrent_autoscaling(self, *, tenant_id: str, project_id: str | None, autoscaling_policy_id: str, compute_profile: str, requested_replicas: int, current_tenant_jobs: int, projected_cost: float, actor_id: str, current_replicas: int = 0) -> dict[str, Any]:
        del actor_id
        with self.database.session() as session:
            policy = session.get(AutoscalingPolicyRow, autoscaling_policy_id)
            if policy is None or policy.tenant_id != tenant_id or policy.project_id != project_id or policy.state != "active":
                raise ConflictError("AUTOSCALING_CONCURRENT_STATE_CONFLICT", "concurrent autoscaling policy state is inconsistent")
            allowed, reason, body, digest = self._autoscaling_decision(
                policy=policy, tenant_id=tenant_id, project_id=project_id,
                autoscaling_policy_id=autoscaling_policy_id, compute_profile=compute_profile,
                requested_replicas=requested_replicas, current_tenant_jobs=current_tenant_jobs,
                projected_cost=projected_cost, current_replicas=current_replicas,
            )
            existing = session.scalar(select(AutoscalingAdmissionRow).where(AutoscalingAdmissionRow.decision_hash == digest))
            if existing is None:
                raise ConflictError("AUTOSCALING_CONCURRENT_STATE_CONFLICT", "concurrent autoscaling decision is missing after uniqueness conflict")
            equivalent = (
                existing.tenant_id == tenant_id
                and existing.project_id == project_id
                and existing.autoscaling_policy_id == autoscaling_policy_id
                and existing.queue_class == policy.queue_class
                and existing.capability_profile == compute_profile
                and existing.current_replicas == current_replicas
                and existing.requested_replicas == requested_replicas
                and existing.active_jobs == current_tenant_jobs
                and float(existing.estimated_incremental_cost) == float(projected_cost)
                and existing.decision == body["decision"]
                and existing.reason_code == reason
            )
            if not equivalent:
                raise ConflictError("AUTOSCALING_CONCURRENT_STATE_CONFLICT", "concurrent autoscaling decision is not equivalent to the requested operation")
            result = {"autoscaling_admission_id": existing.admission_id, **body, "admitted_replicas": existing.admitted_replicas, "idempotent_replay": True}
        if not allowed:
            raise AuthorizationError(reason, "autoscaling admission denied", {"autoscaling_admission_id": result["autoscaling_admission_id"]})
        return result

    def register_aws_environment(self, *, environment: str, account_boundary: str, region: str, infrastructure_versions: dict[str, str], network: dict[str, Any], database: dict[str, Any], object_store: dict[str, Any], queue: dict[str, Any], kms: dict[str, Any], secrets: dict[str, Any], cdn: dict[str, Any], gpu: dict[str, Any], export_replacement_paths: dict[str, Any], actor_id: str) -> dict[str, Any]:
        self._validate_identifier(environment, "AWS_ENVIRONMENT_INVALID")
        self._validate_identifier(account_boundary, "AWS_ACCOUNT_BOUNDARY_INVALID")
        self._validate_regions([region])
        if not infrastructure_versions or any(not _VERSION.fullmatch(str(value)) for value in infrastructure_versions.values()):
            raise ValidationError("AWS_INFRASTRUCTURE_VERSIONS_INVALID", "AWS manifest must pin infrastructure versions")
        self._validate_no_embedded_secrets({
            "network": network,
            "database": database,
            "object_store": object_store,
            "queue": queue,
            "kms": kms,
            "secrets": secrets,
            "cdn": cdn,
            "gpu": gpu,
        })
        if network.get("private_subnets") is not True or network.get("default_deny_egress") is not True or network.get("separate_environment_boundary") is not True:
            raise ValidationError("AWS_NETWORK_BOUNDARY_INVALID", "AWS network must use private subnets, default-deny egress, and strong environment boundaries")
        for label, value in (("database", database), ("object_store", object_store)):
            if value.get("private") is not True or value.get("encrypted") is not True or value.get("backup_enabled") is not True or value.get("approved_identity_only") is not True or value.get("public_access") is not False:
                raise ValidationError("AWS_PRIVATE_DATA_PLANE_REQUIRED", f"AWS {label} must be private, encrypted, backed up, and identity-scoped")
        if not queue.get("dead_letter_enabled") or not queue.get("tenant_quota_enforced") or not queue.get("budget_enforced"):
            raise ValidationError("AWS_QUEUE_CONTROLS_REQUIRED", "AWS queues require quotas, budgets, and dead-letter handling")
        if kms.get("least_privilege") is not True or kms.get("audit_enabled") is not True or secrets.get("least_privilege") is not True or secrets.get("audit_enabled") is not True or secrets.get("references_only") is not True:
            raise ValidationError("AWS_KMS_SECRETS_GOVERNANCE_REQUIRED", "AWS KMS and secrets require least privilege, audit, and reference-only storage")
        for label, value in (("database", database), ("object_store", object_store), ("queue", queue)):
            reference = value.get("secret_reference")
            if reference is not None and _SECRET_REF.fullmatch(str(reference)) is None:
                raise ValidationError("AWS_SECRET_REFERENCE_INVALID", f"AWS {label} secret reference is invalid")
        for label, value, key in (("kms", kms, "key_reference"), ("secrets", secrets, "store_reference")):
            reference = value.get(key)
            if reference is not None and _SECRET_REF.fullmatch(str(reference)) is None:
                raise ValidationError("AWS_SECRET_REFERENCE_INVALID", f"AWS {label} reference is invalid")
        if cdn.get("signed_authorization") is not True or cdn.get("redacted_derivatives_only") is not True or cdn.get("raw_asset_origin") is not False or cdn.get("immutable_derivatives") is not True:
            raise ValidationError("AWS_CDN_POLICY_INVALID", "CDN must use signed authorization and immutable redacted derivatives without raw origins")
        if gpu.get("isolated_subnets") is not True or gpu.get("restricted_egress") is not True or gpu.get("prebaked_approved_models") is not True:
            raise ValidationError("AWS_GPU_ISOLATION_INVALID", "GPU pools require isolated subnets, restricted egress, and pre-baked approved models")
        required_replacements = {"database", "object_store", "queue", "workflow", "kms", "secrets", "cdn", "gpu"}
        if not required_replacements.issubset(export_replacement_paths) or any(not export_replacement_paths[key] for key in required_replacements):
            raise ValidationError("AWS_REPLACEMENT_PATHS_INCOMPLETE", "provider-specific services require documented export/replacement paths")
        body = {"environment": environment, "account_boundary": account_boundary, "region": region, "infrastructure_versions": dict(sorted(infrastructure_versions.items())), "network": network, "database": database, "object_store": object_store, "queue": queue, "kms": kms, "secrets": secrets, "cdn": cdn, "gpu": gpu, "export_replacement_paths": export_replacement_paths, "evidence_class": "synthetic_structural", "production_approved": False}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            existing = session.scalar(select(AwsEnvironmentManifestRow).where(AwsEnvironmentManifestRow.manifest_hash == digest))
            if existing:
                return self._aws(existing, True)
            identifier = new_uuid()
            row = AwsEnvironmentManifestRow(aws_environment_id=identifier, environment=environment, account_boundary=account_boundary, region=region, infrastructure_versions_json=dict(sorted(infrastructure_versions.items())), network_json=network, database_json=database, object_store_json=object_store, queue_json=queue, kms_json=kms, secrets_json=secrets, cdn_json=cdn, gpu_json=gpu, export_replacement_paths_json=export_replacement_paths, evidence_class="synthetic_structural", production_approved=False, manifest_hash=digest, created_by=actor_id)
            session.add(row)
            session.add(self._event(session, event_type="deployment.aws.registered", tenant_id="platform", project_id=None, aggregate_type="aws_environment", aggregate_id=identifier, actor_id=actor_id, payload={"environment": environment, "region": region, "manifest_hash": digest, "production_approved": False}))
            return self._aws(row, False)

    def detect_drift(self, *, deployment_profile_id: str, observed_manifest: dict[str, Any], actor_id: str) -> dict[str, Any]:
        expected = self._profile(self._require_profile(deployment_profile_id), False)
        expected_control = {key: expected[key] for key in ("mode", "canonical_contracts_hash", "service_images", "infrastructure_versions", "secret_references", "network_policy", "resource_limits", "supported_regions")}
        observed_control = {key: observed_manifest.get(key) for key in expected_control}
        findings: list[dict[str, Any]] = []
        for key in sorted(expected_control):
            if observed_control.get(key) != expected_control[key]:
                findings.append({"field": key, "code": "DEPLOYMENT_CONFIGURATION_DRIFT", "expected_hash": canonical_sha256(expected_control[key]), "observed_hash": canonical_sha256(observed_control.get(key))})
        expected_hash = canonical_sha256(expected_control)
        observed_hash = canonical_sha256(observed_control)
        status = "passed" if not findings else "drift_detected"
        body = {"deployment_profile_id": deployment_profile_id, "expected_hash": expected_hash, "observed_hash": observed_hash, "findings": findings, "status": status}
        with self.database.session() as session:
            identifier = new_uuid()
            row = DeploymentDriftReportRow(drift_report_id=identifier, deployment_profile_id=deployment_profile_id, expected_hash=expected_hash, observed_hash=observed_hash, findings_json=findings, status=status, report_hash=canonical_sha256(body), observed_by=actor_id)
            session.add(row)
            session.add(self._event(session, event_type="deployment.drift.detected", tenant_id="platform", project_id=None, aggregate_type="deployment_drift", aggregate_id=identifier, actor_id=actor_id, payload={"status": status, "finding_count": len(findings), "profile_id": deployment_profile_id}))
            return {"drift_report_id": identifier, **body, "report_hash": row.report_hash}

    def production_admission(self, *, deployment_profile_id: str, aws_environment_id: str | None, evidence: dict[str, Any], actor_id: str) -> dict[str, Any]:
        profile = self._require_profile(deployment_profile_id)
        required = (
            "executed_compose", "executed_kubernetes", "executed_terraform",
            "cross_tenant_isolation", "default_deny_network", "secrets_scan",
            "image_signature", "migration_rehearsal", "rollback_rehearsal",
            "object_store_continuity", "queue_continuity", "graceful_shutdown_recovery",
        )
        missing = [key for key in required if evidence.get(key) is not True]
        if aws_environment_id:
            with self.database.session() as session:
                aws = session.get(AwsEnvironmentManifestRow, aws_environment_id)
                if aws is None:
                    raise NotFoundError("aws_environment", aws_environment_id)
                if aws.production_approved is not True:
                    missing.append("aws_external_approval")
        else:
            missing.append("aws_environment_evidence")
        if profile.production_approved is not True:
            missing.append("profile_external_approval")
        request = {"aws_environment_id": aws_environment_id, "evidence_hash": canonical_sha256(evidence), "missing_evidence": sorted(set(missing))}
        return self._record_admission(tenant_id="platform", project_id=None, admission_type="production_promotion", deployment_profile_id=deployment_profile_id, region=None, request=request, decision="deny" if missing else "allow", reason="DEPLOYMENT_PRODUCTION_EVIDENCE_INCOMPLETE" if missing else "ALLOW", obligations=sorted(set(missing)), actor_id=actor_id, raise_on_denial=True)

    def rollback_offline_update(self, *, tenant_id: str, edge_node_id: str, update_id: str, reason: str, actor_id: str) -> dict[str, Any]:
        if not reason.strip():
            raise ValidationError("OFFLINE_ROLLBACK_REASON_REQUIRED", "rollback requires a reason")
        with self.database.session() as session:
            node = session.get(EdgeNodeRow, edge_node_id)
            update = session.get(OfflineUpdatePackageRow, update_id)
            if node is None or node.tenant_id != tenant_id:
                raise NotFoundError("edge_node", edge_node_id)
            if update is None:
                raise NotFoundError("offline_update", update_id)
            application = session.scalar(select(EdgeUpdateApplicationRow).where(EdgeUpdateApplicationRow.edge_node_id == edge_node_id, EdgeUpdateApplicationRow.update_id == update_id))
            if application is None:
                raise NotFoundError("edge_update_application", f"{edge_node_id}:{update_id}")
            if application.state == "rolled_back":
                return {"edge_node_id": edge_node_id, "update_id": update_id, "release": application.previous_release, "state": "rolled_back", "idempotent_replay": True}
            if not self._verify_signature(update.rollback_bundle_hash, update.rollback_signature):
                raise AuthorizationError("OFFLINE_ROLLBACK_SIGNATURE_INVALID", "stored rollback signature is invalid")
            application.state = "rolled_back"
            application.rolled_back_at = db_now()
            application.rollback_reason = reason.strip()
            node.software_release = application.previous_release
            node.software_manifest_hash = str(node.health_json.get("previous_software_manifest_hash", node.software_manifest_hash))
            node.health_json = {**node.health_json, "release": application.previous_release, "rollback_reason": reason.strip()}
            node.state = "enrolled"
            session.add(self._event(session, event_type="deployment.update.rolled_back", tenant_id=tenant_id, project_id=node.project_id, aggregate_type="edge_node", aggregate_id=edge_node_id, actor_id=actor_id, payload={"update_id": update_id, "release": application.previous_release, "reason_code": "OPERATOR_ROLLBACK"}))
            self.audit.append(tenant_id=tenant_id, project_id=node.project_id, actor_id=actor_id, action="deployment.update.rollback", resource_type="edge_node", resource_id=edge_node_id, outcome="allowed", details={"update_id": update_id, "target_release": application.previous_release}, session=session)
            return {"edge_node_id": edge_node_id, "update_id": update_id, "release": application.previous_release, "state": "rolled_back", "idempotent_replay": False}

    def record_local_upgrade_rehearsal(self, *, deployment_profile_id: str, from_release: str, to_release: str, from_schema: str, to_schema: str, pre_export_root: str, post_upgrade_export_root: str, rollback_export_root: str, object_store_root: str, queue_root: str, job_recovery: dict[str, Any], evidence: dict[str, Any], actor_id: str) -> dict[str, Any]:
        profile = self._require_profile(deployment_profile_id)
        if profile.mode not in {"local_only", "edge", "hybrid"}:
            raise ValidationError("LOCAL_UPGRADE_PROFILE_INVALID", "local upgrade rehearsal requires a local-capable deployment profile")
        for value in (pre_export_root, post_upgrade_export_root, rollback_export_root, object_store_root, queue_root):
            self._require_sha256(value, "LOCAL_UPGRADE_ROOT_INVALID")
        if pre_export_root != post_upgrade_export_root or pre_export_root != rollback_export_root:
            raise ConflictError("LOCAL_UPGRADE_EXPORT_IDENTITY_DRIFT", "upgrade and rollback must preserve open-export semantic identity")
        if not job_recovery.get("graceful_shutdown") or not job_recovery.get("checkpoint_resume") or not job_recovery.get("idempotent_replay"):
            raise ValidationError("LOCAL_UPGRADE_JOB_RECOVERY_INCOMPLETE", "upgrade rehearsal must prove graceful shutdown, checkpoint resume, and idempotent replay")
        body = {"deployment_profile_id": deployment_profile_id, "from_release": from_release, "to_release": to_release, "from_schema": from_schema, "to_schema": to_schema, "pre_export_root": pre_export_root, "post_upgrade_export_root": post_upgrade_export_root, "rollback_export_root": rollback_export_root, "object_store_root": object_store_root, "queue_root": queue_root, "job_recovery": job_recovery, "evidence": evidence}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            existing = session.scalar(select(LocalUpgradeRehearsalRow).where(LocalUpgradeRehearsalRow.rehearsal_hash == digest))
            if existing:
                return {"rehearsal_id": existing.rehearsal_id, "rehearsal_hash": digest, "state": existing.state, "idempotent_replay": True}
            identifier = new_uuid()
            row = LocalUpgradeRehearsalRow(rehearsal_id=identifier, deployment_profile_id=deployment_profile_id, from_release=from_release, to_release=to_release, from_schema=from_schema, to_schema=to_schema, pre_export_root=pre_export_root, post_upgrade_export_root=post_upgrade_export_root, rollback_export_root=rollback_export_root, object_store_root=object_store_root, queue_root=queue_root, job_recovery_json=job_recovery, evidence_json=evidence, rehearsal_hash=digest, state="verified", actor_id=actor_id)
            session.add(row)
            session.add(self._event(session, event_type="deployment.upgrade.rehearsed", tenant_id="platform", project_id=None, aggregate_type="local_upgrade_rehearsal", aggregate_id=identifier, actor_id=actor_id, payload={"profile_id": deployment_profile_id, "from_release": from_release, "to_release": to_release, "semantic_identity_preserved": True}))
            return {"rehearsal_id": identifier, "rehearsal_hash": digest, "state": "verified", "idempotent_replay": False}

    def record_graceful_shutdown(self, *, worker_id: str, deployment_profile_id: str, operation_ids: list[str], checkpoint_hashes: dict[str, str], queue_before: dict[str, Any], queue_after: dict[str, Any], recovery: dict[str, Any], actor_id: str) -> dict[str, Any]:
        self._validate_identifier(worker_id, "SHUTDOWN_WORKER_ID_INVALID")
        self._require_profile(deployment_profile_id)
        if not operation_ids or set(checkpoint_hashes) != set(operation_ids):
            raise ValidationError("SHUTDOWN_CHECKPOINT_COVERAGE_INVALID", "every active operation requires a checkpoint hash")
        for digest in checkpoint_hashes.values():
            self._require_sha256(digest, "SHUTDOWN_CHECKPOINT_HASH_INVALID")
        if queue_after.get("leased_jobs", 1) != 0 or recovery.get("resumable") is not True or recovery.get("duplicate_side_effects") not in {0, False}:
            raise ValidationError("SHUTDOWN_RECOVERY_UNVERIFIED", "graceful shutdown must release leases and prove resumable, duplicate-free recovery")
        body = {"worker_id": worker_id, "deployment_profile_id": deployment_profile_id, "operation_ids": sorted(operation_ids), "checkpoint_hashes": dict(sorted(checkpoint_hashes.items())), "queue_before": queue_before, "queue_after": queue_after, "recovery": recovery}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            existing = session.scalar(select(GracefulShutdownEvidenceRow).where(GracefulShutdownEvidenceRow.shutdown_hash == digest))
            if existing:
                return {"shutdown_id": existing.shutdown_id, "shutdown_hash": digest, "state": existing.state, "idempotent_replay": True}
            identifier = new_uuid()
            session.add(GracefulShutdownEvidenceRow(shutdown_id=identifier, worker_id=worker_id, deployment_profile_id=deployment_profile_id, operation_ids_json=sorted(operation_ids), checkpoint_hashes_json=dict(sorted(checkpoint_hashes.items())), queue_before_json=queue_before, queue_after_json=queue_after, recovery_json=recovery, shutdown_hash=digest, state="verified", recorded_by=actor_id))
            session.add(self._event(session, event_type="deployment.worker.shutdown_verified", tenant_id="platform", project_id=None, aggregate_type="graceful_shutdown", aggregate_id=identifier, actor_id=actor_id, payload={"worker_id": worker_id, "operation_count": len(operation_ids), "resumable": True}))
            return {"shutdown_id": identifier, "shutdown_hash": digest, "state": "verified", "idempotent_replay": False}

    def register_cdn_derivative(self, *, tenant_id: str, project_id: str, asset_id: str, immutable_sha256: str, redaction_profile: str, redaction_hash: str, authorization_token: str, expires_at: datetime, actor_id: str) -> dict[str, Any]:
        self._require_sha256(immutable_sha256, "CDN_ASSET_HASH_INVALID")
        self._require_sha256(redaction_hash, "CDN_REDACTION_HASH_INVALID")
        if expires_at <= db_now():
            raise ValidationError("CDN_AUTHORIZATION_EXPIRED", "CDN authorization must expire in the future")
        token_hash = sha256(authorization_token.encode("utf-8")).hexdigest()
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            asset = session.get(AssetRefRow, asset_id)
            if asset is None or asset.tenant_id != tenant_id or asset.project_id != project_id or asset.tombstoned_at is not None:
                raise NotFoundError("asset", asset_id)
            if asset.sha256 != immutable_sha256:
                raise ConflictError("CDN_ASSET_HASH_MISMATCH", "CDN derivative hash does not match immutable asset identity")
            if asset.source_class in {"direct_capture", "source_document"} or asset.classification in {"restricted", "secret"}:
                raise AuthorizationError("CDN_RAW_OR_RESTRICTED_ASSET_DENIED", "raw or restricted assets cannot use the CDN delivery path")
            body = {"tenant_id": tenant_id, "project_id": project_id, "asset_id": asset_id, "immutable_sha256": immutable_sha256, "redaction_profile": redaction_profile, "redaction_hash": redaction_hash, "token_hash": token_hash, "expires_at": expires_at.isoformat(), "raw_origin": False}
            digest = canonical_sha256(body)
            existing = session.scalar(select(CdnDerivativeDeliveryRow).where(CdnDerivativeDeliveryRow.delivery_hash == digest))
            if existing:
                return {"delivery_id": existing.delivery_id, "delivery_hash": existing.delivery_hash, "state": existing.state, "expires_at": existing.expires_at.isoformat(), "idempotent_replay": True}
            identifier = new_uuid()
            session.add(CdnDerivativeDeliveryRow(delivery_id=identifier, tenant_id=tenant_id, project_id=project_id, asset_id=asset_id, immutable_sha256=immutable_sha256, redaction_profile=redaction_profile, redaction_hash=redaction_hash, signed_authorization_required=True, raw_origin=False, token_hash=token_hash, expires_at=expires_at, state="active", delivery_hash=digest, created_by=actor_id))
            session.add(self._event(session, event_type="deployment.cdn.derivative_registered", tenant_id=tenant_id, project_id=project_id, aggregate_type="cdn_derivative", aggregate_id=identifier, actor_id=actor_id, payload={"asset_id": asset_id, "redaction_profile": redaction_profile, "expires_at": expires_at.isoformat()}))
            return {"delivery_id": identifier, "delivery_hash": digest, "state": "active", "expires_at": expires_at.isoformat(), "idempotent_replay": False}

    def register_provider_replacement_path(self, *, provider_name: str, service_class: str, export_format: str, adapter_contract: str, replacement_steps: list[dict[str, Any]], data_exit: dict[str, Any], limitations: list[str], actor_id: str) -> dict[str, Any]:
        for value, code in ((provider_name, "PROVIDER_NAME_INVALID"), (service_class, "PROVIDER_SERVICE_CLASS_INVALID"), (export_format, "PROVIDER_EXPORT_FORMAT_INVALID")):
            self._validate_identifier(value, code)
        if not adapter_contract.startswith("schemas/") or not replacement_steps or data_exit.get("complete_export") is not True or data_exit.get("deletion_attestation") is not True:
            raise ValidationError("PROVIDER_REPLACEMENT_INCOMPLETE", "replacement path requires a public SIP contract, complete export, steps, and deletion attestation")
        body = {"provider_name": provider_name, "service_class": service_class, "export_format": export_format, "adapter_contract": adapter_contract, "replacement_steps": replacement_steps, "data_exit": data_exit, "limitations": limitations}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            existing = session.scalar(select(ProviderReplacementPathRow).where(ProviderReplacementPathRow.replacement_hash == digest))
            if existing:
                return {"replacement_id": existing.replacement_id, "replacement_hash": digest, "state": existing.state, "idempotent_replay": True}
            identifier = new_uuid()
            session.add(ProviderReplacementPathRow(replacement_id=identifier, provider_name=provider_name, service_class=service_class, export_format=export_format, adapter_contract=adapter_contract, replacement_steps_json=replacement_steps, data_exit_json=data_exit, limitations_json=limitations, replacement_hash=digest, state="approved", created_by=actor_id))
            session.add(self._event(session, event_type="deployment.provider.replacement_registered", tenant_id="platform", project_id=None, aggregate_type="provider_replacement", aggregate_id=identifier, actor_id=actor_id, payload={"provider_name": provider_name, "service_class": service_class, "export_format": export_format}))
            return {"replacement_id": identifier, "replacement_hash": digest, "state": "approved", "idempotent_replay": False}

    def active_binding(self, *, tenant_id: str, project_id: str) -> dict[str, Any] | None:
        with self.database.session() as session:
            row = session.scalar(select(ProjectDeploymentBindingRow).where(ProjectDeploymentBindingRow.tenant_id == tenant_id, ProjectDeploymentBindingRow.project_id == project_id, ProjectDeploymentBindingRow.state == "active"))
            return self._binding(row, False) if row else None

    def authorize_if_configured(self, *, tenant_id: str, project_id: str, admission_type: str, region: str | None, request: dict[str, Any], actor_id: str) -> dict[str, Any] | None:
        binding = self.active_binding(tenant_id=tenant_id, project_id=project_id)
        if binding is None:
            return None
        if not region:
            return self._record_admission(tenant_id=tenant_id, project_id=project_id, admission_type=admission_type, deployment_profile_id=binding["deployment_profile_id"], region=region, request=request, decision="deny", reason="DEPLOYMENT_REGION_REQUIRED", obligations=["deployment_region"], actor_id=actor_id, raise_on_denial=True)
        return self.authorize_admission(tenant_id=tenant_id, project_id=project_id, admission_type=admission_type, deployment_profile_id=binding["deployment_profile_id"], region=region, request=request, actor_id=actor_id)

    def _record_admission(self, *, tenant_id: str, project_id: str | None, admission_type: str, deployment_profile_id: str | None, region: str | None, request: dict[str, Any], decision: str, reason: str, obligations: list[str], actor_id: str, raise_on_denial: bool) -> dict[str, Any]:
        body = {"tenant_id": tenant_id, "project_id": project_id, "admission_type": admission_type, "deployment_profile_id": deployment_profile_id, "region": region, "request": request, "decision": decision, "reason_code": reason, "obligations": obligations}
        digest = canonical_sha256(body)
        with self.database.session() as session:
            row = session.scalar(select(DeploymentAdmissionRow).where(DeploymentAdmissionRow.evidence_hash == digest))
            if row is None:
                row = DeploymentAdmissionRow(admission_id=new_uuid(), tenant_id=tenant_id, project_id=project_id, admission_type=admission_type, deployment_profile_id=deployment_profile_id, region=region, request_json=request, decision=decision, reason_code=reason, obligations_json=obligations, evidence_hash=digest, decided_by=actor_id)
                session.add(row)
                session.add(self._event(session, event_type="deployment.admission.decided", tenant_id=tenant_id, project_id=project_id, aggregate_type="deployment_admission", aggregate_id=row.admission_id, actor_id=actor_id, payload={"decision": decision, "reason_code": reason, "admission_type": admission_type}))
                self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action=f"deployment.admission.{admission_type}", resource_type="deployment_admission", resource_id=row.admission_id, outcome="allowed" if decision == "allow" else "denied", details={"reason_code": reason, "evidence_hash": digest}, session=session)
            result = self._admission(row)
        if decision != "allow" and raise_on_denial:
            raise AuthorizationError(reason, "deployment admission denied", {"admission_id": result["admission_id"], "obligations": obligations})
        return result

    # ---------- internals ----------

    def _evaluate_admission(self, *, tenant_id: str, project_id: str | None, admission_type: str, deployment_profile_id: str | None, region: str | None, request: dict[str, Any]) -> tuple[str, str, list[str]]:
        if project_id is None:
            return "deny", "DEPLOYMENT_PROJECT_SCOPE_REQUIRED", []
        with self.database.session() as session:
            self._require_project(session, tenant_id, project_id)
            binding = session.scalar(select(ProjectDeploymentBindingRow).where(ProjectDeploymentBindingRow.tenant_id == tenant_id, ProjectDeploymentBindingRow.project_id == project_id, ProjectDeploymentBindingRow.state == "active"))
            if binding is None:
                return "deny", "DEPLOYMENT_PROFILE_NOT_ASSIGNED", []
            if deployment_profile_id and binding.deployment_profile_id != deployment_profile_id:
                return "deny", "DEPLOYMENT_PROFILE_SCOPE_MISMATCH", []
            profile = session.get(DeploymentProfileRow, binding.deployment_profile_id)
            if profile is None or profile.state != "active":
                return "deny", "DEPLOYMENT_PROFILE_INACTIVE", []
            if region and region not in profile.supported_regions_json:
                return "deny", "DEPLOYMENT_REGION_DENIED", []
            policy = session.get(ResidencyPolicyRow, binding.residency_policy_id) if binding.residency_policy_id else None
            if policy is None or policy.state != "active":
                return "deny", "DEPLOYMENT_RESIDENCY_POLICY_REQUIRED", []
            if profile.mode not in policy.allowed_modes_json or (region and region not in policy.allowed_regions_json):
                return "deny", "DEPLOYMENT_RESIDENCY_DENIED", []
            if admission_type in {"asset_upload", "worker_schedule"}:
                rules = policy.asset_rules_json if admission_type == "asset_upload" else policy.worker_rules_json
                class_key = str(request.get("asset_class") or request.get("worker_class") or "")
                rule = rules.get(class_key)
                if not isinstance(rule, dict):
                    return "deny", "DEPLOYMENT_RESIDENCY_RULE_MISSING", []
                if region and region not in rule.get("allowed_regions", []):
                    return "deny", "DEPLOYMENT_RESIDENCY_REGION_DENIED", []
                if profile.mode not in rule.get("allowed_modes", []):
                    return "deny", "DEPLOYMENT_RESIDENCY_MODE_DENIED", []
            if admission_type == "asset_transfer":
                transfer = session.get(HybridTransferPolicyRow, binding.transfer_policy_id) if binding.transfer_policy_id else None
                if transfer is None or transfer.state != "active":
                    return "deny", "DEPLOYMENT_TRANSFER_POLICY_REQUIRED", []
                asset_class = str(request.get("asset_class", ""))
                stage = str(request.get("processing_stage", ""))
                purpose = str(request.get("purpose", ""))
                rule = next((item for item in transfer.rules_json if item.get("asset_class") == asset_class), None)
                if not rule:
                    return "deny", "DEPLOYMENT_TRANSFER_ASSET_CLASS_DENIED", []
                if stage not in TRANSFER_STAGES or TRANSFER_STAGE_ORDER[stage] < TRANSFER_STAGE_ORDER[rule["minimum_stage"]]:
                    return "deny", "DEPLOYMENT_TRANSFER_STAGE_DENIED", []
                if region not in rule.get("allowed_regions", []) or purpose not in rule.get("allowed_purposes", []):
                    return "deny", "DEPLOYMENT_TRANSFER_SCOPE_DENIED", []
                if rule.get("requires_approval") and request.get("approval_receipt_valid") is not True:
                    return "deny", "DEPLOYMENT_TRANSFER_APPROVAL_REQUIRED", ["approved_transfer_receipt"]
            return "allow", "ALLOW", []

    def _project_snapshot(self, session: Session, tenant_id: str, project_id: str) -> dict[str, Any]:
        project = self._require_project(session, tenant_id, project_id)
        roles = list(session.scalars(select(RoleBindingRow).where(RoleBindingRow.tenant_id == tenant_id, RoleBindingRow.project_id == project_id)))
        consents = list(session.scalars(select(ConsentGrantRow).where(ConsentGrantRow.tenant_id == tenant_id, ConsentGrantRow.project_id == project_id)))
        assets = list(session.scalars(select(AssetRefRow).where(AssetRefRow.tenant_id == tenant_id, AssetRefRow.project_id == project_id)))
        scenes = list(session.scalars(select(SceneCommitRow).where(SceneCommitRow.tenant_id == tenant_id, SceneCommitRow.project_id == project_id)))
        operations = list(session.scalars(select(OperationRow).where(OperationRow.tenant_id == tenant_id, OperationRow.project_id == project_id)))
        exports = list(session.scalars(select(ExportRow).where(ExportRow.tenant_id == tenant_id, ExportRow.project_id == project_id)))
        models = list(session.scalars(select(ModelManifestRow)))
        return {
            "project": {"project_id": project.project_id, "tenant_id": project.tenant_id, "vertical": project.vertical, "classification": project.classification, "created_at": project.created_at.isoformat()},
            "permissions": [list(item) for item in sorted({(row.binding_id, row.identity_id, row.role, canonical_sha256(row.purposes_json), canonical_sha256(row.spatial_restrictions_json)) for row in roles})],
            "consent": [list(item) for item in sorted({(row.grant_id, row.subject_id, canonical_sha256(row.purposes_json), canonical_sha256(row.audiences_json), canonical_sha256(row.scopes_json), row.state, row.created_at.isoformat()) for row in consents})],
            "asset_hashes": [list(item) for item in sorted({(row.asset_id, row.sha256, row.classification, row.source_class, row.authority_class) for row in assets})],
            "scene_history": [list(item) for item in sorted({(row.commit_id, row.scene_id, canonical_sha256(row.parent_ids_json), row.snapshot_hash, row.root_manifest_hash) for row in scenes})],
            "run_manifests": [list(item) for item in sorted({(row.operation_id, row.operation_type, row.input_manifest_hash, row.output_hash or "") for row in operations})],
            "exports": [list(item) for item in sorted({(row.export_id, row.root_hash, row.manifest_json.get("schema_version", "")) for row in exports})],
            "model_manifests": [list(item) for item in sorted({(row.model_id, row.version, row.checkpoint_hash, row.manifest_hash) for row in models})],
        }

    def _validate_features(self, features: dict[str, Any]) -> None:
        if not isinstance(features, dict) or not features:
            raise ValidationError("DEPLOYMENT_FEATURES_REQUIRED", "deployment profile must declare feature availability")
        for name, value in features.items():
            self._validate_identifier(name, "DEPLOYMENT_FEATURE_NAME_INVALID")
            if not isinstance(value, dict) or not {"enabled", "requires_cloud_connectivity", "when_unavailable", "administrator_notice"}.issubset(value):
                raise ValidationError("DEPLOYMENT_FEATURE_DECLARATION_INCOMPLETE", "every feature must declare cloud dependence and unavailable behavior", {"feature": name})
            if not str(value["when_unavailable"]).strip() or not str(value["administrator_notice"]).strip():
                raise ValidationError("DEPLOYMENT_FEATURE_DECLARATION_INCOMPLETE", "feature degraded behavior and administrator notice cannot be blank", {"feature": name})

    @staticmethod
    def _validate_no_embedded_secrets(value: Any) -> None:
        """Reject raw secret material from deployment/cloud manifests."""
        forbidden_exact = {
            "password", "passwd", "passcode", "pin", "private_key", "privatekey",
            "client_secret", "api_secret", "api_token", "access_token", "refresh_token",
            "secret_value", "access_key", "secret_access_key", "credential_secret",
        }
        forbidden_parts = (
            "password", "passcode", "private_key", "privatekey", "client_secret",
            "access_token", "refresh_token", "secret_value", "secret_access_key",
            "credential_secret",
        )
        reference_keys = {"secret_reference", "store_reference", "key_reference"}
        findings: list[str] = []
        invalid_references: list[str] = []

        def walk(item: Any, path: str) -> None:
            if isinstance(item, dict):
                for raw_key, child in item.items():
                    key = str(raw_key).strip().lower()
                    child_path = f"{path}.{raw_key}"
                    if key in reference_keys:
                        if not isinstance(child, str) or _SECRET_REF.fullmatch(child.strip()) is None:
                            invalid_references.append(child_path)
                        continue
                    if key in forbidden_exact or any(part in key for part in forbidden_parts):
                        if child not in (None, "", [], {}):
                            findings.append(child_path)
                        continue
                    walk(child, child_path)
            elif isinstance(item, list):
                for index, child in enumerate(item):
                    walk(child, f"{path}[{index}]")
            elif isinstance(item, str) and "BEGIN PRIVATE KEY" in item:
                findings.append(path)

        walk(value, "$")
        if findings:
            raise ValidationError(
                "DEPLOYMENT_RAW_SECRET_PROHIBITED",
                "deployment manifests may contain only opaque secret references, never raw credentials or private material",
                {"paths": sorted(set(findings))},
            )
        if invalid_references:
            raise ValidationError(
                "AWS_SECRET_REFERENCE_INVALID",
                "deployment secret references must use an approved opaque secret URI",
                {"paths": sorted(set(invalid_references))},
            )

    def _validate_pins(self, images: dict[str, str], versions: dict[str, str], secrets: dict[str, str], network: dict[str, Any], resources: dict[str, Any]) -> None:
        self._validate_image_map(images)
        if not versions or any(not _VERSION.fullmatch(str(value)) for value in versions.values()):
            raise ValidationError("DEPLOYMENT_INFRASTRUCTURE_VERSION_UNPINNED", "infrastructure versions must be explicit and pinned")
        if not secrets or any(not _SECRET_REF.fullmatch(str(value)) for value in secrets.values()):
            raise ValidationError("DEPLOYMENT_SECRET_REFERENCE_INVALID", "secrets must be external references rather than embedded values")
        if network.get("default_deny_ingress") is not True or network.get("default_deny_egress") is not True or not network.get("allowed_egress"):
            raise ValidationError("DEPLOYMENT_NETWORK_POLICY_INVALID", "network policy must default deny ingress and egress with an explicit allowlist")
        if not resources or any(not isinstance(value, dict) or float(value.get("cpu", 0)) <= 0 or int(value.get("memory_mb", 0)) <= 0 for value in resources.values()):
            raise ValidationError("DEPLOYMENT_RESOURCE_LIMITS_INVALID", "every workload requires positive CPU and memory limits")

    def _validate_image_map(self, images: dict[str, str]) -> None:
        if not images or any(not _IMAGE.fullmatch(str(value)) for value in images.values()):
            raise ValidationError("DEPLOYMENT_IMAGE_UNPINNED", "service images must use immutable sha256 digests")

    @staticmethod
    def _validate_identifier(value: str, code: str) -> None:
        if not isinstance(value, str) or _SAFE_ID.fullmatch(value.strip()) is None:
            raise ValidationError(code, "identifier contains invalid characters")

    @staticmethod
    def _validate_version(value: str) -> None:
        if _VERSION.fullmatch(value) is None:
            raise ValidationError("DEPLOYMENT_VERSION_INVALID", "version is invalid")

    @staticmethod
    def _validate_regions(values: Iterable[str]) -> list[str]:
        result = sorted(set(str(value) for value in values))
        if not result or any(_REGION.fullmatch(value) is None for value in result):
            raise ValidationError("DEPLOYMENT_REGION_INVALID", "region list is empty or invalid")
        return result

    @staticmethod
    def _require_sha256(value: str, code: str) -> None:
        if _SHA256.fullmatch(value) is None:
            raise ValidationError(code, "value must be a lowercase SHA-256 digest")

    def _verify_signature(self, digest: str, signature: str) -> bool:
        try:
            actual = base64.b64decode(signature, validate=True)
        except Exception:
            return False
        expected = hmac.new(self.signing_key, digest.encode("ascii"), sha256).digest()
        return hmac.compare_digest(actual, expected)

    def _require_profile(self, profile_id: str) -> DeploymentProfileRow:
        with self.database.session() as session:
            row = session.get(DeploymentProfileRow, profile_id)
            if row is None:
                raise NotFoundError("deployment_profile", profile_id)
            return row

    @staticmethod
    def _require_tenant(session: Session, tenant_id: str) -> TenantRow:
        row = session.get(TenantRow, tenant_id)
        if row is None:
            raise NotFoundError("tenant", tenant_id)
        return row

    @staticmethod
    def _require_project(session: Session, tenant_id: str, project_id: str) -> ProjectRow:
        row = session.get(ProjectRow, project_id)
        if row is None or row.tenant_id != tenant_id:
            raise NotFoundError("project", project_id)
        return row

    def _event(self, session: Session, *, event_type: str, tenant_id: str, project_id: str | None, aggregate_type: str, aggregate_id: str, actor_id: str, payload: dict[str, Any]):
        return self.events.create(session, event_type=event_type, schema_version="1.0.0", tenant_id=tenant_id, project_id=project_id, aggregate_type=aggregate_type, aggregate_id=aggregate_id, payload=payload, producer="deployment-control", actor_id=actor_id, workload_identity=None)

    @staticmethod
    def _profile(row: DeploymentProfileRow, idempotent_replay: bool) -> dict[str, Any]:
        return {"deployment_profile_id": row.deployment_profile_id, "name": row.name, "revision": row.revision, "mode": row.mode, "canonical_contracts": row.canonical_contracts_json, "canonical_contracts_hash": row.canonical_contracts_hash, "features": row.features_json, "service_images": row.service_images_json, "infrastructure_versions": row.infrastructure_versions_json, "secret_references": row.secret_references_json, "network_policy": row.network_policy_json, "resource_limits": row.resource_limits_json, "supported_regions": row.supported_regions_json, "degraded_modes": row.degraded_modes_json, "provider_replacements": row.provider_replacements_json, "production_approved": row.production_approved, "state": row.state, "profile_hash": row.profile_hash, "created_by": row.created_by, "created_at": row.created_at.isoformat(), "idempotent_replay": idempotent_replay}

    @staticmethod
    def _binding(row: ProjectDeploymentBindingRow, idempotent_replay: bool) -> dict[str, Any]:
        return {"binding_id": row.binding_id, "tenant_id": row.tenant_id, "project_id": row.project_id, "deployment_profile_id": row.deployment_profile_id, "residency_policy_id": row.residency_policy_id, "transfer_policy_id": row.transfer_policy_id, "revision": row.revision, "feature_overrides": row.feature_overrides_json, "cloud_dependencies_acknowledged": row.cloud_dependencies_acknowledged, "state": row.state, "binding_hash": row.binding_hash, "idempotent_replay": idempotent_replay}

    @staticmethod
    def _residency(row: ResidencyPolicyRow, replay: bool) -> dict[str, Any]:
        return {"residency_policy_id": row.residency_policy_id, "tenant_id": row.tenant_id, "project_id": row.project_id, "revision": row.revision, "home_region": row.home_region, "allowed_regions": row.allowed_regions_json, "allowed_modes": row.allowed_modes_json, "asset_rules": row.asset_rules_json, "worker_rules": row.worker_rules_json, "provider_rules": row.provider_rules_json, "default_action": row.default_action, "policy_hash": row.policy_hash, "state": row.state, "idempotent_replay": replay}

    @staticmethod
    def _transfer(row: HybridTransferPolicyRow, replay: bool) -> dict[str, Any]:
        return {"transfer_policy_id": row.transfer_policy_id, "tenant_id": row.tenant_id, "project_id": row.project_id, "revision": row.revision, "source_profile_id": row.source_profile_id, "destination_profile_id": row.destination_profile_id, "rules": row.rules_json, "purpose": row.purpose, "policy_hash": row.policy_hash, "state": row.state, "idempotent_replay": replay}

    @staticmethod
    def _edge(row: EdgeNodeRow, replay: bool) -> dict[str, Any]:
        return {"edge_node_id": row.edge_node_id, "tenant_id": row.tenant_id, "project_id": row.project_id, "deployment_profile_id": row.deployment_profile_id, "node_identity": row.node_identity, "identity_public_key_hash": row.identity_public_key_hash, "workload_identity_grant_id": row.workload_identity_grant_id, "software_release": row.software_release, "software_manifest_hash": row.software_manifest_hash, "signing_key_id": row.signing_key_id, "disk_encryption": row.disk_encryption_json, "region": row.region, "capabilities": row.capabilities_json, "health": row.health_json, "state": row.state, "enrollment_hash": row.enrollment_hash, "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None, "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None, "idempotent_replay": replay}

    @staticmethod
    def _update(row: OfflineUpdatePackageRow, replay: bool) -> dict[str, Any]:
        return {"update_id": row.update_id, "deployment_profile_id": row.deployment_profile_id, "from_release": row.from_release, "to_release": row.to_release, "bundle_hash": row.bundle_hash, "manifest_hash": row.manifest_hash, "signing_key_id": row.signing_key_id, "rollback_bundle_hash": row.rollback_bundle_hash, "compatible_export_versions": row.compatible_export_versions_json, "state": row.state, "idempotent_replay": replay}

    @staticmethod
    def _migration(row: ProjectDeploymentMigrationRow, replay: bool) -> dict[str, Any]:
        return {"migration_id": row.migration_id, "tenant_id": row.tenant_id, "project_id": row.project_id, "source_profile_id": row.source_profile_id, "target_profile_id": row.target_profile_id, "source_snapshot_hash": row.source_snapshot_hash, "target_snapshot_hash": row.target_snapshot_hash, "validation": row.validation_json, "state": row.state, "migration_hash": row.migration_hash, "idempotent_replay": replay}

    @staticmethod
    def _autoscaling(row: AutoscalingPolicyRow, replay: bool) -> dict[str, Any]:
        return {"autoscaling_policy_id": row.autoscaling_policy_id, "tenant_id": row.tenant_id, "project_id": row.project_id, "queue_class": row.queue_class, "revision": row.revision, "min_replicas": row.min_replicas, "max_replicas": row.max_replicas, "tenant_concurrency_limit": row.tenant_concurrency_limit, "profile_quotas": row.profile_quotas_json, "global_budget_limit": row.global_budget_limit, "currency": row.currency, "dead_letter": row.dead_letter_json, "restricted_egress": row.restricted_egress, "policy_hash": row.policy_hash, "state": row.state, "idempotent_replay": replay}

    @staticmethod
    def _aws(row: AwsEnvironmentManifestRow, replay: bool) -> dict[str, Any]:
        return {"aws_environment_id": row.aws_environment_id, "environment": row.environment, "account_boundary": row.account_boundary, "region": row.region, "infrastructure_versions": row.infrastructure_versions_json, "network": row.network_json, "database": row.database_json, "object_store": row.object_store_json, "queue": row.queue_json, "kms": row.kms_json, "secrets": row.secrets_json, "cdn": row.cdn_json, "gpu": row.gpu_json, "export_replacement_paths": row.export_replacement_paths_json, "evidence_class": row.evidence_class, "production_approved": row.production_approved, "manifest_hash": row.manifest_hash, "idempotent_replay": replay}

    @staticmethod
    def _admission(row: DeploymentAdmissionRow) -> dict[str, Any]:
        return {"admission_id": row.admission_id, "tenant_id": row.tenant_id, "project_id": row.project_id, "admission_type": row.admission_type, "deployment_profile_id": row.deployment_profile_id, "region": row.region, "decision": row.decision, "reason_code": row.reason_code, "obligations": row.obligations_json, "evidence_hash": row.evidence_hash, "decided_at": row.decided_at.isoformat()}
