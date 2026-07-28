from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import hmac
from typing import Any

from sqlalchemy import select

from .audit import AuditService
from .canonical import canonical_sha256, new_uuid
from .contracts import ProviderCapabilityDescriptorContract, ProviderPromotionContract
from .database import (
    AssetRefRow,
    ConsentGrantRow,
    CoordinateFrameRow,
    Database,
    IntendedUseValidationRow,
    OperationRow,
    ProviderManifestRevisionRow,
    ProviderManifestRow,
    ProviderPromotionRow,
    RepresentationAssetRow,
    RepresentationBindingRow,
    SceneCommitRow,
    SpatialConversionRow,
)
from .errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from .events import OutboxEventFactory
from .models import AuthorityClass, Classification, RepresentationKind, SourceClass
from .operations import OperationService
from .temporal import db_now


class ProviderRegistry:
    _events = OutboxEventFactory()

    def __init__(self, database: Database, audit: AuditService, signing_key: bytes | None = None) -> None:
        self.database = database
        self.audit = audit
        self.operations = OperationService(database, audit)
        self._signing_key = signing_key or audit.signing_key
        if len(self._signing_key) < 32:
            raise ValueError("provider registry signing key must contain at least 32 bytes")

    def register(self, manifest: dict[str, Any], *, actor_id: str) -> dict[str, Any]:
        """Register either the strict v1.1 capability descriptor or a preserved legacy manifest.

        Legacy manifests remain usable for historical/direct fixture registration, but they are
        never eligible for governed conversion admission because they lack a signed capability,
        security, coordinate, recovery, license-evidence, and benchmark descriptor.
        """
        if not isinstance(manifest, dict):
            raise ValidationError("PROVIDER_MANIFEST_INVALID", "provider manifest must be an object")
        if self._is_capability_descriptor(manifest):
            return self._register_capability_descriptor(manifest, actor_id=actor_id)
        return self._register_legacy_manifest(manifest, actor_id=actor_id)

    def _register_legacy_manifest(self, manifest: dict[str, Any], *, actor_id: str) -> dict[str, Any]:
        required = {
            "provider_id",
            "version",
            "source_url",
            "source_revision",
            "license_id",
            "approval_state",
            "allowed_classifications",
            "allowed_purposes",
            "allowed_regions",
        }
        missing = sorted(required - manifest.keys())
        if missing:
            raise ValidationError("PROVIDER_MANIFEST_INCOMPLETE", "provider manifest is incomplete", {"missing": missing})
        body = {key: manifest[key] for key in sorted(manifest) if key not in {"manifest_hash", "signature"}}
        digest = canonical_sha256(body)
        provider_id = str(manifest["provider_id"])
        now = db_now()
        with self.database.session() as session:
            row = session.get(ProviderManifestRow, provider_id)
            values = dict(
                provider_id=provider_id,
                version=str(manifest["version"]),
                provider_class=str(manifest.get("provider_class", "local_open_source")),
                source_url=str(manifest["source_url"]),
                source_revision=str(manifest["source_revision"]),
                image_digest=manifest.get("image_digest"),
                executable_digest=manifest.get("image_digest"),
                license_id=str(manifest["license_id"]),
                approval_state=str(manifest["approval_state"]),
                allowed_classifications_json=list(manifest["allowed_classifications"]),
                allowed_purposes_json=list(manifest["allowed_purposes"]),
                allowed_regions_json=list(manifest["allowed_regions"]),
                deployments_json=list(manifest.get("deployments", [])),
                retention_days=manifest.get("retention_days"),
                expires_at=_parse_datetime(manifest.get("expires_at")),
                manifest_hash=digest,
                manifest_signature=None,
                signed_by=manifest.get("signed_by", actor_id),
                descriptor_json={},
                registered_at=(row.registered_at if row else now),
                updated_at=now,
            )
            if row:
                for key, value in values.items():
                    setattr(row, key, value)
            else:
                session.add(ProviderManifestRow(**values))
        return {
            "provider_id": provider_id,
            "manifest_hash": digest,
            "approval_state": manifest["approval_state"],
            "descriptor_complete": False,
            "execution_eligible": False,
        }

    def _register_capability_descriptor(self, manifest: dict[str, Any], *, actor_id: str) -> dict[str, Any]:
        raw = dict(manifest)
        provided_hash = raw.pop("manifest_hash", None)
        provided_signature = raw.pop("manifest_signature", raw.pop("signature", None))
        raw.setdefault("schema", "sip.provider-capability/v1.1")
        raw.setdefault("schema_version", "1.1.0")
        raw.setdefault("signed_by", actor_id)
        try:
            provisional = ProviderCapabilityDescriptorContract.model_validate(
                {**raw, "manifest_hash": "0" * 64, "manifest_signature": "0" * 64}
            )
        except Exception as exc:
            errors = getattr(exc, "errors", lambda: [])()
            missing = sorted({str(item["loc"][0]) for item in errors if item.get("type") == "missing" and item.get("loc")})
            raise ValidationError(
                "PROVIDER_CAPABILITY_INCOMPLETE" if missing else "PROVIDER_CAPABILITY_INVALID",
                "provider capability descriptor is incomplete" if missing else "provider capability descriptor violates the canonical contract",
                {"missing": missing, "errors": _safe_pydantic_errors(errors)},
            ) from exc
        body = provisional.model_dump(mode="json", by_alias=True)
        body.pop("manifest_hash", None)
        body.pop("manifest_signature", None)
        digest = canonical_sha256(body)
        signature = self._signature(digest)
        if provided_hash is not None and not hmac.compare_digest(str(provided_hash), digest):
            raise ValidationError("PROVIDER_MANIFEST_HASH_MISMATCH", "provided provider manifest hash does not match canonical content")
        if provided_signature is not None and not hmac.compare_digest(str(provided_signature), signature):
            raise ValidationError("PROVIDER_MANIFEST_SIGNATURE_INVALID", "provided provider manifest signature is invalid")
        contract = ProviderCapabilityDescriptorContract.model_validate(
            {**body, "manifest_hash": digest, "manifest_signature": signature}
        )
        now = db_now()
        with self.database.session() as session:
            row = session.get(ProviderManifestRow, contract.provider_id)
            values = {
                "provider_id": contract.provider_id,
                "version": contract.provider_version,
                "provider_class": contract.provider_class,
                "source_url": contract.source_url,
                "source_revision": contract.source_revision,
                "image_digest": contract.executable_digest if "isolated_container" in set(contract.execution_modes) else None,
                "executable_digest": contract.executable_digest,
                "license_id": contract.license_manifest_id,
                "approval_state": contract.approval_state,
                "allowed_classifications_json": [item.value for item in contract.allowed_classifications],
                "allowed_purposes_json": list(contract.allowed_purposes),
                "allowed_regions_json": list(contract.allowed_regions),
                "deployments_json": list(contract.deployment_modes),
                "execution_modes_json": list(contract.execution_modes),
                "input_roles_json": list(contract.input_roles),
                "output_roles_json": list(contract.output_roles),
                "supported_formats_json": contract.supported_formats,
                "coordinate_contract_json": contract.coordinate_contract.model_dump(mode="json"),
                "reproducibility_json": contract.reproducibility,
                "security_contract_json": contract.security.model_dump(mode="json"),
                "recovery_contract_json": contract.recovery.model_dump(mode="json"),
                "model_manifest_ids_json": list(contract.model_manifest_ids),
                "dependency_inventory_json": list(contract.dependency_inventory),
                "license_evidence_json": [item.model_dump(mode="json") for item in contract.license_evidence],
                "benchmark_profile_ids_json": list(contract.benchmark_profile_ids),
                "descriptor_json": contract.model_dump(mode="json", by_alias=True),
                "retention_days": contract.retention_days,
                "expires_at": contract.expires_at,
                "manifest_hash": digest,
                "manifest_signature": signature,
                "signed_by": contract.signed_by,
                "registered_at": row.registered_at if row and row.registered_at else now,
                "updated_at": now,
            }
            revision = session.get(ProviderManifestRevisionRow, digest)
            descriptor_snapshot = contract.model_dump(mode="json", by_alias=True)
            if revision is None:
                session.add(ProviderManifestRevisionRow(
                    manifest_hash=digest,
                    provider_id=contract.provider_id,
                    provider_version=contract.provider_version,
                    descriptor_json=descriptor_snapshot,
                    manifest_signature=signature,
                    approval_state=contract.approval_state,
                    signed_by=contract.signed_by,
                    registered_by=actor_id,
                    registered_at=now,
                ))
            elif (
                revision.provider_id != contract.provider_id
                or revision.provider_version != contract.provider_version
                or revision.manifest_signature != signature
                or canonical_sha256(_descriptor_body(revision.descriptor_json)) != digest
            ):
                raise ConflictError(
                    "PROVIDER_REVISION_HASH_CONFLICT",
                    "provider manifest revision hash is already bound to different immutable content",
                )
            if row:
                for key, value in values.items():
                    setattr(row, key, value)
            else:
                session.add(ProviderManifestRow(**values))
            self.audit.append(
                tenant_id="system",
                project_id=None,
                actor_id=actor_id,
                action="provider:register_capability",
                resource_type="provider_manifest",
                resource_id=contract.provider_id,
                outcome="allowed",
                details={"manifest_hash": digest, "provider_version": contract.provider_version},
                session=session,
            )
        return {
            "provider_id": contract.provider_id,
            "provider_version": contract.provider_version,
            "manifest_hash": digest,
            "manifest_signature": signature,
            "approval_state": contract.approval_state,
            "descriptor_complete": True,
            "execution_eligible": contract.approval_state == "approved",
        }

    def promote(
        self,
        provider_id: str,
        *,
        state: str,
        data_classifications: list[str],
        scene_classes: list[str],
        output_roles: list[str],
        intended_uses: list[str],
        execution_zones: list[str],
        hardware_profiles: list[str],
        benchmark_evidence_hash: str,
        policy_snapshot_hash: str,
        valid_from: datetime | str | None,
        valid_until: datetime | str | None,
        actor_id: str,
        promotion_id: str | None = None,
    ) -> dict[str, Any]:
        promotion_id = promotion_id or new_uuid()
        now = db_now()
        with self.database.session() as session:
            provider = session.get(ProviderManifestRow, provider_id)
            if provider is None:
                raise NotFoundError("provider_manifest", provider_id)
            if not provider.descriptor_json or not provider.manifest_signature:
                raise ValidationError(
                    "PROVIDER_CAPABILITY_DESCRIPTOR_REQUIRED",
                    "provider promotion requires a complete signed capability descriptor",
                )
            if not self._provider_integrity_valid(provider):
                raise AuthorizationError(
                    "PROVIDER_MANIFEST_INTEGRITY_INVALID",
                    "provider promotion requires an intact signed capability descriptor",
                )
            revision = session.get(ProviderManifestRevisionRow, provider.manifest_hash)
            if revision is None or not self._revision_integrity_valid(revision):
                raise AuthorizationError(
                    "PROVIDER_REVISION_INTEGRITY_INVALID",
                    "provider promotion requires an intact immutable descriptor revision",
                )
            if state in {"active", "limited", "shadow", "research_isolated"} and provider.approval_state != "approved":
                raise AuthorizationError(
                    "PROVIDER_PROMOTION_STATE_DENIED",
                    "only approved provider descriptors may enter executable promotion states",
                )
            body = {
                "promotion_id": promotion_id,
                "provider_id": provider_id,
                "provider_version": provider.version,
                "provider_manifest_hash": provider.manifest_hash,
                "state": state,
                "data_classifications": sorted(set(data_classifications)),
                "scene_classes": sorted(set(scene_classes)),
                "output_roles": sorted(set(output_roles)),
                "intended_uses": sorted(set(intended_uses)),
                "execution_zones": sorted(set(execution_zones)),
                "hardware_profiles": sorted(set(hardware_profiles)),
                "benchmark_evidence_hash": benchmark_evidence_hash,
                "policy_snapshot_hash": policy_snapshot_hash,
                "valid_from": (_parse_datetime(valid_from) or now).isoformat(),
                "valid_until": _parse_datetime(valid_until).isoformat() if valid_until else None,
                "signed_by": actor_id,
            }
            digest = canonical_sha256(body)
            signature = self._signature(digest)
            contract = ProviderPromotionContract.model_validate(
                {**body, "promotion_hash": digest, "signature": signature}
            )
            existing = session.get(ProviderPromotionRow, promotion_id)
            if existing:
                if existing.promotion_hash != digest:
                    raise ConflictError("PROVIDER_PROMOTION_ID_CONFLICT", "promotion identifier is already bound to different scope")
                return self._promotion_dict(existing)
            if state in {"active", "limited", "shadow", "research_isolated"}:
                prior = list(session.scalars(select(ProviderPromotionRow).where(
                    ProviderPromotionRow.provider_id == provider_id,
                    ProviderPromotionRow.provider_version == provider.version,
                    ProviderPromotionRow.superseded_at.is_(None),
                )))
                for row in prior:
                    if _promotion_scope_overlaps(row, contract):
                        row.superseded_at = now
            row = ProviderPromotionRow(
                promotion_id=promotion_id,
                provider_id=provider_id,
                provider_version=provider.version,
                provider_manifest_hash=provider.manifest_hash,
                state=contract.state,
                data_classifications_json=[item.value for item in contract.data_classifications],
                scene_classes_json=contract.scene_classes,
                output_roles_json=contract.output_roles,
                intended_uses_json=contract.intended_uses,
                execution_zones_json=contract.execution_zones,
                hardware_profiles_json=contract.hardware_profiles,
                benchmark_evidence_hash=contract.benchmark_evidence_hash,
                policy_snapshot_hash=contract.policy_snapshot_hash,
                valid_from=contract.valid_from,
                valid_until=contract.valid_until,
                promotion_hash=digest,
                signed_by=actor_id,
                signature=signature,
            )
            session.add(row)
            session.add(self._events.create(
                session,
                event_type="provider.promotion_changed",
                schema_version="1.0.0",
                tenant_id="system",
                project_id=None,
                aggregate_type="provider_promotion",
                aggregate_id=promotion_id,
                payload={
                    "promotion_id": promotion_id,
                    "provider_id": provider_id,
                    "provider_version": provider.version,
                    "provider_manifest_hash": provider.manifest_hash,
                    "state": contract.state,
                    "promotion_hash": digest,
                },
                producer="provider-registry",
                actor_id=actor_id,
                workload_identity=None,
                causation_id=provider_id,
            ))
            self.audit.append(
                tenant_id="system",
                project_id=None,
                actor_id=actor_id,
                action="provider:promote",
                resource_type="provider_promotion",
                resource_id=promotion_id,
                outcome="allowed",
                details={"provider_id": provider_id, "state": state, "promotion_hash": digest},
                session=session,
            )
            return self._promotion_dict(row)

    def select(
        self,
        *,
        classification: str,
        purpose: str,
        region: str,
        deployment_mode: str,
        scene_class: str,
        output_roles: list[str],
        intended_uses: list[str],
        execution_zone: str,
        hardware_profile: str,
        required_capabilities: list[str],
        forbidden_capabilities: list[str] | None = None,
        preferred_provider_ids: list[str] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = now or db_now()
        forbidden = set(forbidden_capabilities or [])
        preferred = list(preferred_provider_ids or [])
        candidates: list[tuple[int, str, ProviderManifestRow, ProviderPromotionRow]] = []
        with self.database.session() as session:
            promotions = list(session.scalars(select(ProviderPromotionRow).where(
                ProviderPromotionRow.superseded_at.is_(None),
                ProviderPromotionRow.state.in_(["active", "limited", "shadow", "research_isolated"]),
                ProviderPromotionRow.valid_from <= now,
            )))
            for promotion in promotions:
                expiry = _aware(promotion.valid_until) if promotion.valid_until else None
                if expiry and expiry <= now:
                    continue
                provider = session.get(ProviderManifestRow, promotion.provider_id)
                if provider is None or not self._provider_integrity_valid(provider):
                    continue
                if (
                    promotion.provider_version != provider.version
                    or promotion.provider_manifest_hash != provider.manifest_hash
                    or not self._promotion_integrity_valid(promotion)
                ):
                    continue
                if provider.approval_state != "approved":
                    continue
                provider_expiry = _aware(provider.expires_at) if provider.expires_at else None
                if provider_expiry and provider_expiry <= now:
                    continue
                capabilities = set((provider.descriptor_json or {}).get("capabilities", []))
                if classification not in set(provider.allowed_classifications_json or []):
                    continue
                if purpose not in set(provider.allowed_purposes_json or []):
                    continue
                if region not in set(provider.allowed_regions_json or []):
                    continue
                if deployment_mode not in set(provider.deployments_json or []):
                    continue
                if not set(output_roles).issubset(set(provider.output_roles_json or [])):
                    continue
                if not set(required_capabilities).issubset(capabilities) or capabilities & forbidden:
                    continue
                if classification not in promotion.data_classifications_json:
                    continue
                if scene_class not in promotion.scene_classes_json:
                    continue
                if not set(output_roles).issubset(set(promotion.output_roles_json)):
                    continue
                if not set(intended_uses).issubset(set(promotion.intended_uses_json)):
                    continue
                if execution_zone not in promotion.execution_zones_json:
                    continue
                if hardware_profile not in promotion.hardware_profiles_json:
                    continue
                rank = preferred.index(provider.provider_id) if provider.provider_id in preferred else len(preferred)
                candidates.append((rank, provider.provider_id, provider, promotion))
            if not candidates:
                raise AuthorizationError(
                    "HYB_PROVIDER_NO_ELIGIBLE_MATCH",
                    "no approved provider meets the requested capability and policy envelope",
                    {"retryable": False, "remediation": "register or promote an eligible provider"},
                )
            _, _, provider, promotion = sorted(candidates, key=lambda item: (item[0], item[1], item[2].version))[0]
            revision = session.get(ProviderManifestRevisionRow, provider.manifest_hash)
            if revision is None or not self._revision_integrity_valid(revision):
                raise AuthorizationError(
                    "PROVIDER_REVISION_INTEGRITY_INVALID",
                    "selected provider has no intact immutable descriptor revision",
                )
            return {
                "provider_id": provider.provider_id,
                "provider_version": provider.version,
                "provider_class": provider.provider_class,
                "provider_manifest_hash": provider.manifest_hash,
                "provider_descriptor": dict(revision.descriptor_json),
                "provider_executable_digest": provider.executable_digest,
                "execution_modes": list(provider.execution_modes_json or []),
                "deployment_modes": list(provider.deployments_json or []),
                "input_roles": list(provider.input_roles_json or []),
                "output_roles": list(provider.output_roles_json or []),
                "license_evidence": list(provider.license_evidence_json or []),
                "dependency_inventory": list(provider.dependency_inventory_json or []),
                "benchmark_profile_ids": list(provider.benchmark_profile_ids_json or []),
                "promotion_id": promotion.promotion_id,
                "promotion_hash": promotion.promotion_hash,
                "promotion_state": promotion.state,
                "benchmark_evidence_hash": promotion.benchmark_evidence_hash,
                "policy_snapshot_hash": promotion.policy_snapshot_hash,
                "security": dict(provider.security_contract_json or {}),
                "coordinate_contract": dict(provider.coordinate_contract_json or {}),
                "recovery": dict(provider.recovery_contract_json or {}),
                "model_manifest_ids": list(provider.model_manifest_ids_json or []),
            }

    def get_descriptor(self, provider_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(ProviderManifestRow, provider_id)
            if row is None:
                raise NotFoundError("provider_manifest", provider_id)
            if not self._provider_integrity_valid(row):
                raise AuthorizationError("PROVIDER_MANIFEST_INTEGRITY_INVALID", "provider descriptor integrity verification failed")
            return dict(row.descriptor_json or {})

    def _provider_integrity_valid(self, row: ProviderManifestRow) -> bool:
        descriptor = dict(row.descriptor_json or {})
        if not descriptor or not row.manifest_signature:
            return False
        body = dict(descriptor)
        body.pop("manifest_hash", None)
        body.pop("manifest_signature", None)
        digest = canonical_sha256(body)
        return hmac.compare_digest(digest, row.manifest_hash) and hmac.compare_digest(row.manifest_signature, self._signature(digest))

    def _revision_integrity_valid(self, row: ProviderManifestRevisionRow) -> bool:
        body = _descriptor_body(row.descriptor_json)
        digest = canonical_sha256(body)
        return (
            hmac.compare_digest(digest, row.manifest_hash)
            and hmac.compare_digest(row.manifest_signature, self._signature(digest))
            and row.provider_id == str((row.descriptor_json or {}).get("provider_id"))
            and row.provider_version == str((row.descriptor_json or {}).get("provider_version"))
        )

    def _promotion_integrity_valid(self, row: ProviderPromotionRow) -> bool:
        body = {
            "promotion_id": row.promotion_id,
            "provider_id": row.provider_id,
            "provider_version": row.provider_version,
            "provider_manifest_hash": row.provider_manifest_hash,
            "state": row.state,
            "data_classifications": sorted(set(row.data_classifications_json or [])),
            "scene_classes": sorted(set(row.scene_classes_json or [])),
            "output_roles": sorted(set(row.output_roles_json or [])),
            "intended_uses": sorted(set(row.intended_uses_json or [])),
            "execution_zones": sorted(set(row.execution_zones_json or [])),
            "hardware_profiles": sorted(set(row.hardware_profiles_json or [])),
            "benchmark_evidence_hash": row.benchmark_evidence_hash,
            "policy_snapshot_hash": row.policy_snapshot_hash,
            "valid_from": _aware(row.valid_from).isoformat(),
            "valid_until": _aware(row.valid_until).isoformat() if row.valid_until else None,
            "signed_by": row.signed_by,
        }
        digest = canonical_sha256(body)
        return hmac.compare_digest(digest, row.promotion_hash) and hmac.compare_digest(
            row.signature, self._signature(digest)
        )

    def _signature(self, digest: str) -> str:
        return hmac.new(self._signing_key, digest.encode("ascii"), hashlib.sha256).hexdigest()

    @staticmethod
    def _is_capability_descriptor(manifest: dict[str, Any]) -> bool:
        return (
            manifest.get("schema") == "sip.provider-capability/v1.1"
            or "provider_version" in manifest
            or {"capabilities", "coordinate_contract", "security", "recovery"}.issubset(manifest)
        )

    @staticmethod
    def _promotion_dict(row: ProviderPromotionRow) -> dict[str, Any]:
        return {
            "promotion_id": row.promotion_id,
            "provider_id": row.provider_id,
            "provider_version": row.provider_version,
            "provider_manifest_hash": row.provider_manifest_hash,
            "state": row.state,
            "data_classifications": row.data_classifications_json,
            "scene_classes": row.scene_classes_json,
            "output_roles": row.output_roles_json,
            "intended_uses": row.intended_uses_json,
            "execution_zones": row.execution_zones_json,
            "hardware_profiles": row.hardware_profiles_json,
            "benchmark_evidence_hash": row.benchmark_evidence_hash,
            "policy_snapshot_hash": row.policy_snapshot_hash,
            "valid_from": row.valid_from,
            "valid_until": row.valid_until,
            "promotion_hash": row.promotion_hash,
            "signature": row.signature,
        }

    def authorize_execution(
        self,
        provider_id: str,
        *,
        classification: Classification,
        purpose: str,
        region: str,
        external: bool,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(ProviderManifestRow, provider_id)
            if not row:
                raise AuthorizationError("PROVIDER_NOT_REGISTERED", "provider execution is denied because no approved manifest exists")
            now = db_now()
            expiry = _aware(row.expires_at) if row.expires_at else None
            reasons: list[str] = []
            if row.approval_state != "approved":
                reasons.append("not_approved")
            if expiry and expiry <= now:
                reasons.append("approval_expired")
            if classification.value not in row.allowed_classifications_json:
                reasons.append("classification_not_allowed")
            if purpose not in row.allowed_purposes_json:
                reasons.append("purpose_not_allowed")
            if region not in row.allowed_regions_json:
                reasons.append("region_not_allowed")
            if external and classification in {Classification.CRITICAL_INFRASTRUCTURE, Classification.BIOMETRIC, Classification.MINOR}:
                reasons.append("sensitive_external_processing_denied")
            if reasons:
                raise AuthorizationError("PROVIDER_EXECUTION_DENIED", "provider manifest does not permit this execution", {"reasons": reasons})
            return {
                "allowed": True,
                "provider_id": provider_id,
                "provider_version": row.version,
                "source_revision": row.source_revision,
                "image_digest": row.image_digest,
                "manifest_hash": row.manifest_hash,
                "retention_days": row.retention_days,
            }


class RepresentationService:
    _events = OutboxEventFactory()

    def __init__(self, database: Database, audit: AuditService) -> None:
        self.database = database
        self.audit = audit

    def create_candidate(
        self,
        *,
        tenant_id: str,
        project_id: str,
        scene_id: str,
        asset_id: str,
        kind: RepresentationKind,
        provider_id: str,
        coordinate_frame_id: str,
        source_class: SourceClass,
        authority_class: AuthorityClass,
        lossy: bool,
        intended_uses: list[str],
        prohibited_uses: list[str],
        quality: dict[str, Any],
        provenance: dict[str, Any],
        support_map: dict[str, Any],
        actor_id: str,
        operation_id: str | None = None,
        representation_id: str | None = None,
        format_metadata: dict[str, Any] | None = None,
        derivation_policy: dict[str, Any] | None = None,
        limitations: list[str] | None = None,
        information_losses: list[str] | None = None,
        privacy_inheritance: dict[str, Any] | None = None,
        dependencies: list[str] | None = None,
        fallback_representation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if kind == RepresentationKind.INTERACTION and authority_class != AuthorityClass.DERIVED_NON_AUTHORITATIVE:
            raise ValidationError(
                "INTERACTION_AUTHORITY_INVALID",
                "interaction proxies must carry the exact derived_non_authoritative authority class",
            )
        if kind == RepresentationKind.VISUAL and authority_class in {AuthorityClass.METRIC, AuthorityClass.FIELD_VERIFIED}:
            raise ValidationError("VISUAL_AUTHORITY_INVALID", "visual representations cannot carry metric authority")
        if kind == RepresentationKind.METRIC and source_class == SourceClass.GENERATED and authority_class == AuthorityClass.FIELD_VERIFIED:
            raise ValidationError("GENERATED_VERIFICATION_INVALID", "generated geometry cannot be field verified by confidence alone")
        format_metadata = dict(format_metadata or {})
        derivation_policy = dict(derivation_policy or {})
        limitations = sorted(set(limitations or []))
        information_losses = sorted(set(information_losses or []))
        privacy_inheritance = dict(privacy_inheritance or {})
        dependencies = sorted(set(dependencies or []))
        metadata = dict(metadata or {})
        declared_format = str(format_metadata.get("format", "")).lower()
        if "splat" in declared_format and not metadata.get("truth_label"):
            raise ValidationError(
                "SPLAT_TRUTH_LABEL_REQUIRED",
                "Gaussian or splat representations require an explicit visual/non-metric truth label",
            )
        if lossy and not information_losses:
            information_losses = ["provider_declared_lossy_conversion"]
        representation_id = representation_id or new_uuid()
        if fallback_representation_id == representation_id:
            raise ValidationError("REPRESENTATION_FALLBACK_CYCLE", "representation cannot fall back to itself")
        if not isinstance(scene_id, str) or not scene_id.strip():
            raise ValidationError(
                "REPRESENTATION_SCENE_ID_INVALID",
                "representation candidates require a concrete scene identifier",
            )
        if not isinstance(asset_id, str) or not asset_id.strip():
            raise ValidationError(
                "REPRESENTATION_ASSET_ID_INVALID",
                "representation candidates require a concrete immutable asset identifier",
            )
        if not isinstance(coordinate_frame_id, str) or not coordinate_frame_id.strip():
            raise ValidationError(
                "REPRESENTATION_FRAME_ID_INVALID",
                "representation candidates require a concrete coordinate-frame identifier",
            )
        with self.database.session() as session:
            asset = session.get(AssetRefRow, asset_id)
            if (
                not asset
                or asset.tenant_id != tenant_id
                or asset.project_id != project_id
                or asset.tombstoned_at is not None
            ):
                raise NotFoundError("asset", asset_id)
            frame = session.get(CoordinateFrameRow, coordinate_frame_id)
            if (
                not frame
                or frame.tenant_id != tenant_id
                or frame.project_id != project_id
                or frame.deprecated_at is not None
            ):
                raise NotFoundError("coordinate_frame", coordinate_frame_id)
            scene_exists = session.scalar(
                select(SceneCommitRow.commit_id).where(
                    SceneCommitRow.tenant_id == tenant_id,
                    SceneCommitRow.project_id == project_id,
                    SceneCommitRow.scene_id == scene_id,
                ).limit(1)
            )
            if not scene_exists:
                raise NotFoundError("scene", scene_id)
            provider = session.get(ProviderManifestRow, provider_id)
            if not provider:
                raise NotFoundError("provider_manifest", provider_id)
            if provider.approval_state != "approved":
                raise AuthorizationError(
                    "REPRESENTATION_PROVIDER_NOT_APPROVED",
                    "new representation candidates require an approved provider manifest",
                    {"provider_id": provider_id, "approval_state": provider.approval_state},
                )
            if provider.expires_at and _aware(provider.expires_at) <= db_now():
                raise AuthorizationError(
                    "REPRESENTATION_PROVIDER_APPROVAL_EXPIRED",
                    "new representation candidates cannot use an expired provider approval",
                    {"provider_id": provider_id},
                )
            privacy_inheritance = self._effective_privacy_inheritance(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                output_asset_id=asset_id,
                provenance=provenance,
                dependencies=dependencies,
                requested=privacy_inheritance,
            )
            if fallback_representation_id:
                fallback = session.get(RepresentationAssetRow, fallback_representation_id)
                if not fallback or fallback.tenant_id != tenant_id or fallback.project_id != project_id or fallback.scene_id != scene_id:
                    raise NotFoundError("fallback_representation", fallback_representation_id)
            for dependency_id in dependencies:
                if dependency_id == representation_id:
                    raise ValidationError("REPRESENTATION_DEPENDENCY_CYCLE", "representation cannot depend on itself")
            if operation_id:
                existing = session.scalar(
                    select(RepresentationAssetRow).where(
                        RepresentationAssetRow.tenant_id == tenant_id,
                        RepresentationAssetRow.project_id == project_id,
                        RepresentationAssetRow.operation_id == operation_id,
                    )
                )
                if existing:
                    if (
                        existing.scene_id != scene_id
                        or existing.asset_id != asset_id
                        or existing.kind != kind.value
                        or existing.coordinate_frame_id != coordinate_frame_id
                        or existing.provider_id != provider_id
                        or existing.source_class != source_class.value
                        or existing.authority_class != authority_class.value
                        or existing.lossy != lossy
                        or existing.intended_uses_json != intended_uses
                        or existing.prohibited_uses_json != prohibited_uses
                        or canonical_sha256(existing.provenance_json) != canonical_sha256(provenance)
                        or canonical_sha256(existing.format_json) != canonical_sha256(format_metadata)
                        or canonical_sha256(existing.derivation_policy_json) != canonical_sha256(derivation_policy)
                        or existing.limitations_json != limitations
                        or existing.information_loss_json != information_losses
                        or canonical_sha256(existing.privacy_inheritance_json) != canonical_sha256(privacy_inheritance)
                        or existing.dependencies_json != dependencies
                        or existing.fallback_representation_id != fallback_representation_id
                    ):
                        raise ConflictError(
                            "REPRESENTATION_OPERATION_CONFLICT",
                            "operation is already bound to a different representation candidate",
                        )
                    if existing.representation_id != representation_id:
                        raise ConflictError(
                            "REPRESENTATION_IDEMPOTENCY_CONFLICT",
                            "operation candidate identifier does not match the durable candidate",
                        )
                    return existing.representation_id
            duplicate_id = session.get(RepresentationAssetRow, representation_id)
            if duplicate_id is not None:
                raise ConflictError(
                    "REPRESENTATION_ID_CONFLICT",
                    "representation identifier is already bound to another candidate",
                    {"representation_id": representation_id},
                )
            candidate_manifest = {
                "representation_id": representation_id,
                "tenant_id": tenant_id,
                "project_id": project_id,
                "scene_id": scene_id,
                "asset_id": asset_id,
                "operation_id": operation_id,
                "kind": kind.value,
                "provider_id": provider_id,
                "coordinate_frame_id": coordinate_frame_id,
                "source_class": source_class.value,
                "authority_class": authority_class.value,
                "authority_ceiling": (
                    AuthorityClass.DERIVED_NON_AUTHORITATIVE.value
                    if kind == RepresentationKind.INTERACTION
                    else authority_class.value
                ),
                "lossy": lossy,
                "intended_uses": intended_uses,
                "prohibited_uses": prohibited_uses,
                "format": format_metadata,
                "derivation_policy": derivation_policy,
                "limitations": limitations,
                "information_losses": information_losses,
                "privacy_inheritance": privacy_inheritance,
                "dependencies": dependencies,
                "fallback_representation_id": fallback_representation_id,
                "metadata": metadata,
                "provenance_hash": canonical_sha256(provenance),
                "support_map_hash": canonical_sha256(support_map),
            }
            manifest_hash = canonical_sha256(candidate_manifest)
            session.add(
                RepresentationAssetRow(
                    representation_id=representation_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    scene_id=scene_id,
                    asset_id=asset_id,
                    operation_id=operation_id,
                    kind=kind.value,
                    provider_id=provider_id,
                    coordinate_frame_id=coordinate_frame_id,
                    source_class=source_class.value,
                    authority_class=authority_class.value,
                    authority_ceiling=(
                        AuthorityClass.DERIVED_NON_AUTHORITATIVE.value
                        if kind == RepresentationKind.INTERACTION
                        else authority_class.value
                    ),
                    disposable=kind == RepresentationKind.INTERACTION,
                    lossy=lossy,
                    intended_uses_json=intended_uses,
                    prohibited_uses_json=prohibited_uses,
                    quality_json=quality,
                    provenance_json=provenance,
                    support_map_json=support_map,
                    format_json=format_metadata,
                    derivation_policy_json=derivation_policy,
                    limitations_json=limitations,
                    information_loss_json=information_losses,
                    privacy_inheritance_json=privacy_inheritance,
                    dependencies_json=dependencies,
                    fallback_representation_id=fallback_representation_id,
                    manifest_hash=manifest_hash,
                    metadata_json=metadata,
                    state="quarantined",
                )
            )
            event_payload = {
                "candidate_id": representation_id,
                "representation_id": representation_id,
                "operation_id": operation_id,
                "asset_id": asset_id,
                "kind": kind.value,
                "provider_id": provider_id,
                "state": "quarantined",
                "manifest_hash": manifest_hash,
                "authority_ceiling": candidate_manifest["authority_ceiling"],
            }
            session.add(
                self._events.create(
                    session,
                    event_type="representation.candidate_created",
                    schema_version="1.0.0",
                    tenant_id=tenant_id,
                    project_id=project_id,
                    aggregate_type="representation",
                    aggregate_id=representation_id,
                    payload=event_payload,
                    producer="representation-api",
                    actor_id=actor_id,
                    workload_identity=None,
                    correlation_id=operation_id or representation_id,
                    causation_id=operation_id,
                )
            )
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="representation:candidate_create",
                resource_type="representation",
                resource_id=representation_id,
                outcome="allowed",
                details={"kind": kind.value, "provider_id": provider_id, "state": "quarantined"},
                session=session,
            )
        return representation_id

    @staticmethod
    def _effective_privacy_inheritance(
        session: Any,
        *,
        tenant_id: str,
        project_id: str,
        output_asset_id: str,
        provenance: dict[str, Any],
        dependencies: list[str],
        requested: dict[str, Any],
    ) -> dict[str, Any]:
        """Compute derivative policy from every resolvable source; callers may only tighten it."""
        source_ids = sorted(set(provenance.get("source_ids", [])) | set(requested.get("source_ids", [])))
        asset_sources = list(session.scalars(select(AssetRefRow).where(
            AssetRefRow.tenant_id == tenant_id,
            AssetRefRow.project_id == project_id,
            AssetRefRow.asset_id.in_(source_ids or ["__none__"]),
        )))
        representation_sources = list(session.scalars(select(RepresentationAssetRow).where(
            RepresentationAssetRow.tenant_id == tenant_id,
            RepresentationAssetRow.project_id == project_id,
            RepresentationAssetRow.representation_id.in_(source_ids or ["__none__"]),
        )))
        matched_ids = {row.asset_id for row in asset_sources} | {row.representation_id for row in representation_sources}
        policies: list[dict[str, Any]] = []
        classifications: list[str] = []
        retention_classes: set[str] = set()
        legal_hold = False
        for row in asset_sources:
            classifications.append(row.classification)
            retention_classes.add(row.retention_class)
            legal_hold = legal_hold or bool(row.legal_hold)
            source_policy = (row.provenance_json or {}).get("policy", {})
            if isinstance(source_policy, dict):
                policies.append(source_policy)
        for row in representation_sources:
            policy = dict(row.privacy_inheritance_json or {})
            policies.append(policy)
            if policy.get("classification"):
                classifications.append(str(policy["classification"]))
            retention_classes.update(str(item) for item in policy.get("retention_classes", []))
            legal_hold = legal_hold or bool(policy.get("legal_hold", False))

        if requested.get("classification"):
            classifications.append(str(requested["classification"]))
        retention_classes.update(str(item) for item in requested.get("retention_classes", []))
        legal_hold = legal_hold or bool(requested.get("legal_hold", False))

        classification_order = {
            "public": 0,
            "internal": 1,
            "confidential": 2,
            "restricted": 3,
            "critical_infrastructure": 4,
            "biometric": 5,
            "minor": 5,
        }
        effective_classification = max(
            classifications or ["internal"],
            key=lambda value: classification_order.get(value, 99),
        )

        audience_sets = [
            set(str(item) for item in policy.get("allowed_audiences", []))
            for policy in [*policies, requested]
            if policy.get("allowed_audiences")
        ]
        allowed_audiences = sorted(set.intersection(*audience_sets)) if audience_sets else []
        if audience_sets and not allowed_audiences:
            raise ValidationError(
                "DERIVATIVE_AUDIENCE_POLICY_EMPTY",
                "source audience policies have no permitted intersection",
            )

        union_keys = ("consent_grant_ids", "export_dependencies", "deletion_dependencies", "legal_hold_ids")
        inherited_unions: dict[str, list[str]] = {}
        for key in union_keys:
            inherited_unions[key] = sorted({
                str(item)
                for policy in [*policies, requested]
                for item in policy.get(key, [])
            })

        output_asset = session.get(AssetRefRow, output_asset_id)
        policy_blockers: list[str] = []
        if output_asset and output_asset.tenant_id == tenant_id and output_asset.project_id == project_id:
            output_rank = classification_order.get(output_asset.classification, 99)
            inherited_rank = classification_order.get(effective_classification, 99)
            if output_rank < inherited_rank:
                raise ValidationError(
                    "DERIVATIVE_CLASSIFICATION_DOWNGRADE",
                    "derived asset classification is less restrictive than an input",
                    {
                        "output_asset_id": output_asset_id,
                        "output_classification": output_asset.classification,
                        "required_classification": effective_classification,
                    },
                )
            if legal_hold:
                output_asset.legal_hold = True
        else:
            policy_blockers.append("output_asset_reference_unresolved")

        unresolved = sorted(set(source_ids) - matched_ids)
        if unresolved:
            policy_blockers.append("source_policy_unresolved")
        effective = {
            **requested,
            "source_ids": source_ids,
            "resolved_source_ids": sorted(matched_ids),
            "unresolved_source_policy_ids": unresolved,
            "classification": effective_classification,
            "retention_classes": sorted(retention_classes),
            "legal_hold": legal_hold,
            "policy_blockers": sorted(set(policy_blockers)),
            **inherited_unions,
        }
        if allowed_audiences:
            effective["allowed_audiences"] = allowed_audiences
        effective["inheritance_hash"] = canonical_sha256({key: value for key, value in effective.items() if key != "inheritance_hash"})
        return effective


    def attach_worker_receipt(
        self,
        *,
        tenant_id: str,
        project_id: str,
        operation_id: str,
        worker_receipt_hash: str,
        candidate_core_hash: str,
        actor_id: str,
    ) -> dict[str, Any]:
        """Bind exact worker evidence to a still-quarantined candidate idempotently."""
        with self.database.session() as session:
            row = session.scalar(
                select(RepresentationAssetRow).where(
                    RepresentationAssetRow.tenant_id == tenant_id,
                    RepresentationAssetRow.project_id == project_id,
                    RepresentationAssetRow.operation_id == operation_id,
                )
            )
            if row is None:
                raise NotFoundError("representation_candidate_for_operation", operation_id)
            if row.state != "quarantined":
                raise ConflictError(
                    "REPRESENTATION_RECEIPT_STATE_CONFLICT",
                    "worker evidence can only be attached while a candidate is quarantined",
                    {"state": row.state},
                )
            provenance = dict(row.provenance_json or {})
            existing_core = provenance.get("candidate_core_hash")
            if existing_core and existing_core != candidate_core_hash:
                raise ConflictError(
                    "REPRESENTATION_RECEIPT_CONFLICT",
                    "candidate is already bound to a different immutable candidate core",
                )
            receipts = list(provenance.get("worker_receipts") or [])
            evidence = {
                "worker_receipt_hash": worker_receipt_hash,
                "candidate_core_hash": candidate_core_hash,
            }
            if evidence not in receipts:
                receipts.append(evidence)
            provenance.update(
                {
                    "worker_receipt_hash": worker_receipt_hash,
                    "candidate_core_hash": candidate_core_hash,
                    "worker_receipts": receipts,
                }
            )
            row.provenance_json = provenance
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="representation:worker_receipt_attach",
                resource_type="representation",
                resource_id=row.representation_id,
                outcome="allowed",
                details={
                    "operation_id": operation_id,
                    "worker_receipt_hash": worker_receipt_hash,
                    "candidate_core_hash": candidate_core_hash,
                },
                session=session,
            )
            return {
                "representation_id": row.representation_id,
                "worker_receipt_hash": worker_receipt_hash,
                "candidate_core_hash": candidate_core_hash,
            }


    def candidate_for_operation(self, *, tenant_id: str, project_id: str, operation_id: str) -> dict[str, Any] | None:
        """Return the idempotent candidate created by a durable operation, if any."""
        with self.database.session() as session:
            row = session.scalar(
                select(RepresentationAssetRow).where(
                    RepresentationAssetRow.tenant_id == tenant_id,
                    RepresentationAssetRow.project_id == project_id,
                    RepresentationAssetRow.operation_id == operation_id,
                )
            )
            if row is None:
                return None
            return {
                "representation_id": row.representation_id,
                "asset_id": row.asset_id,
                "state": row.state,
                "kind": row.kind,
                "operation_id": row.operation_id,
                "scene_id": row.scene_id,
                "provider_id": row.provider_id,
                "coordinate_frame_id": row.coordinate_frame_id,
                "source_class": row.source_class,
                "authority_class": row.authority_class,
                "authority_ceiling": row.authority_ceiling,
                "disposable": row.disposable,
                "lossy": row.lossy,
                "intended_uses": row.intended_uses_json,
                "prohibited_uses": row.prohibited_uses_json,
                "quality": row.quality_json,
                "provenance": row.provenance_json,
                "support_map": row.support_map_json,
                "format": row.format_json,
                "derivation_policy": row.derivation_policy_json,
                "limitations": row.limitations_json,
                "information_losses": row.information_loss_json,
                "privacy_inheritance": row.privacy_inheritance_json,
                "dependencies": row.dependencies_json,
                "fallback_representation_id": row.fallback_representation_id,
                "manifest_hash": row.manifest_hash,
                "metadata": row.metadata_json,
            }

    def review_quality(
        self,
        representation_id: str,
        *,
        reviewer_id: str,
        approved_uses: list[str],
        metrics: dict[str, Any],
        passed: bool,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(RepresentationAssetRow, representation_id)
            if not row:
                raise NotFoundError("representation", representation_id)
            if reviewer_id.startswith("sip-worker:"):
                raise AuthorizationError(
                    "WORKER_REVIEWER_NOT_INDEPENDENT",
                    "a representation-producing worker cannot independently approve its own output",
                )
            if row.state not in {"quarantined", "quality_failed", "approved"}:
                raise ConflictError("REPRESENTATION_REVIEW_STATE", "representation cannot be reviewed in its current state")
            provenance = dict(row.provenance_json or {})
            if row.operation_id and not (
                provenance.get("worker_receipt_hash") and provenance.get("candidate_core_hash")
            ):
                raise ConflictError(
                    "REPRESENTATION_WORKER_EVIDENCE_MISSING",
                    "worker-derived candidates require an immutable receipt before quality review",
                )
            unrequested = sorted(set(approved_uses) - set(row.intended_uses_json))
            if unrequested:
                raise ValidationError("REPRESENTATION_USE_NOT_REQUESTED", "review cannot approve unrequested use", {"uses": unrequested})
            if passed and (not approved_uses or not metrics):
                raise ValidationError(
                    "REPRESENTATION_REVIEW_EVIDENCE_INCOMPLETE",
                    "a passing independent review requires approved uses and retained quantitative metrics",
                )
            prior_quality = dict(row.quality_json or {})
            prior_review = dict(prior_quality.get("review", {}))
            prior_approved = set(str(item) for item in prior_review.get("approved_uses", []))
            newly_approved = set(approved_uses) if passed else set()
            merged_approved = sorted(prior_approved | newly_approved)
            validation_record = {
                "reviewer_id": reviewer_id,
                "passed": bool(passed),
                "approved_uses": sorted(newly_approved),
                "metrics": metrics,
                "metrics_hash": canonical_sha256(metrics),
                "reviewed_at": db_now().isoformat(),
                "independent_from_worker": True,
            }
            validations = list(prior_review.get("validations", []))
            validation_hash = canonical_sha256(validation_record)
            if not any(item.get("validation_hash") == validation_hash for item in validations):
                validations.append({**validation_record, "validation_hash": validation_hash})
            row.quality_json = {
                **prior_quality,
                "review": {
                    "reviewer_id": reviewer_id,
                    "approved_uses": merged_approved,
                    "metrics": metrics,
                    "reviewed_at": validation_record["reviewed_at"],
                    "independent_from_worker": True,
                    "validations": validations,
                },
            }
            row.state = "approved" if merged_approved else "quality_failed"
            self.audit.append(
                tenant_id=row.tenant_id,
                project_id=row.project_id,
                actor_id=reviewer_id,
                action="representation:quality_review",
                resource_type="representation",
                resource_id=row.representation_id,
                outcome="allowed",
                details={
                    "passed": passed,
                    "approved_uses": sorted(set(approved_uses)) if passed else [],
                    "metrics_hash": canonical_sha256(metrics),
                },
                session=session,
            )
            return {
                "representation_id": representation_id,
                "state": row.state,
                "approved_uses": sorted(set(approved_uses)) if passed else [],
            }

    def invalidate_dependencies(
        self,
        *,
        tenant_id: str,
        project_id: str,
        changed_resource_id: str,
        reason: str,
        actor_id: str,
        queue_regeneration: bool = True,
    ) -> dict[str, Any]:
        """Invalidate only dependent derivatives and produce durable, policy-aware rebuild operations."""
        if not reason:
            raise ValidationError("REPRESENTATION_INVALIDATION_REASON_REQUIRED", "dependency invalidation requires a reason")
        invalidated: list[str] = []
        superseded_bindings: list[str] = []
        regeneration_plans: list[dict[str, Any]] = []
        now = db_now()
        reason_lower = reason.lower()
        policy_revocation = any(token in reason_lower for token in ("consent", "revok", "delet", "legal hold", "privacy"))
        with self.database.session() as session:
            rows = list(session.scalars(select(RepresentationAssetRow).where(
                RepresentationAssetRow.tenant_id == tenant_id,
                RepresentationAssetRow.project_id == project_id,
                RepresentationAssetRow.deprecated_at.is_(None),
            )))
            for row in rows:
                references = set(row.dependencies_json or [])
                references.update((row.provenance_json or {}).get("source_ids", []))
                references.update((row.privacy_inheritance_json or {}).get("source_ids", []))
                references.update((row.privacy_inheritance_json or {}).get("consent_grant_ids", []))
                references.update((row.privacy_inheritance_json or {}).get("deletion_dependencies", []))
                if changed_resource_id not in references:
                    continue
                row.state = "invalidated"
                row.deprecated_at = now
                derivation_policy = dict(row.derivation_policy_json or {})
                rebuild_input = {
                    "schema": "sip.representation-regeneration/v1",
                    "invalidated_representation_id": row.representation_id,
                    "scene_id": row.scene_id,
                    "provider_id": row.provider_id,
                    "kind": row.kind,
                    "coordinate_frame_id": row.coordinate_frame_id,
                    "changed_resource_id": changed_resource_id,
                    "reason": reason,
                    "source_ids": sorted(set((row.provenance_json or {}).get("source_ids", []))),
                    "dependencies": sorted(set(row.dependencies_json or [])),
                    "derivation_policy": derivation_policy,
                    "prior_manifest_hash": row.manifest_hash,
                }
                blockers: list[str] = []
                operation_type = str(derivation_policy.get("operation_type", "")).strip()
                if not operation_type:
                    blockers.append("missing_operation_type")
                if policy_revocation:
                    blockers.append("policy_reauthorization_required")
                privacy_blockers = (row.privacy_inheritance_json or {}).get("policy_blockers", [])
                blockers.extend(str(item) for item in privacy_blockers)
                plan = {
                    "representation_id": row.representation_id,
                    "operation_type": operation_type or None,
                    "idempotency_key": f"regenerate:{row.representation_id}:{canonical_sha256(rebuild_input)[:16]}",
                    "input_manifest": rebuild_input,
                    "input_manifest_hash": canonical_sha256(rebuild_input),
                    "blocked_reasons": sorted(set(blockers)),
                    "queued": False,
                    "operation_id": None,
                }
                row.metadata_json = {
                    **(row.metadata_json or {}),
                    "invalidation": {"resource_id": changed_resource_id, "reason": reason, "at": now.isoformat()},
                    "regeneration_plan": plan,
                }
                invalidated.append(row.representation_id)
                regeneration_plans.append(plan)
                bindings = list(session.scalars(select(RepresentationBindingRow).where(
                    RepresentationBindingRow.tenant_id == tenant_id,
                    RepresentationBindingRow.project_id == project_id,
                    RepresentationBindingRow.representation_id == row.representation_id,
                    RepresentationBindingRow.superseded_at.is_(None),
                )))
                for binding in bindings:
                    binding.superseded_at = now
                    superseded_bindings.append(binding.binding_id)
                payload = {
                    "representation_id": row.representation_id,
                    "changed_resource_id": changed_resource_id,
                    "reason": reason,
                    "superseded_binding_count": len(bindings),
                    "regeneration_plan_hash": plan["input_manifest_hash"],
                    "regeneration_blocked_reasons": plan["blocked_reasons"],
                }
                session.add(self._events.create(
                    session,
                    event_type="representation.dependency_invalidated",
                    schema_version="1.0.0",
                    tenant_id=tenant_id,
                    project_id=project_id,
                    aggregate_type="representation",
                    aggregate_id=row.representation_id,
                    payload=payload,
                    producer="representation-api",
                    actor_id=actor_id,
                    workload_identity=None,
                    causation_id=changed_resource_id,
                ))
                self.audit.append(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    actor_id=actor_id,
                    action="representation:dependency_invalidate",
                    resource_type="representation",
                    resource_id=row.representation_id,
                    outcome="allowed",
                    details=payload,
                    session=session,
                )

        if queue_regeneration:
            for plan in regeneration_plans:
                if plan["blocked_reasons"]:
                    continue
                operation = self.operations.create(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    operation_type=str(plan["operation_type"]),
                    idempotency_key=str(plan["idempotency_key"]),
                    input_manifest=dict(plan["input_manifest"]),
                    actor_id=actor_id,
                )
                plan["queued"] = True
                plan["operation_id"] = operation["operation_id"]
        return {
            "invalidated_representation_ids": invalidated,
            "superseded_binding_ids": superseded_bindings,
            "regeneration_plans": regeneration_plans,
            "queued_operation_ids": [str(plan["operation_id"]) for plan in regeneration_plans if plan["operation_id"]],
        }

    def select_for_view(
        self,
        *,
        tenant_id: str,
        project_id: str,
        scene_id: str,
        intended_use: str,
        audience: str,
        role: str | None = None,
        client_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Select policy-compatible published layers with explicit deterministic fallbacks."""
        client_profile = client_profile or {}
        capabilities = set(client_profile.get("capabilities", []))
        selected: list[dict[str, Any]] = []
        rejected: list[dict[str, str]] = []
        with self.database.session() as session:
            bindings = list(session.scalars(select(RepresentationBindingRow).where(
                RepresentationBindingRow.tenant_id == tenant_id,
                RepresentationBindingRow.project_id == project_id,
                RepresentationBindingRow.scene_id == scene_id,
                RepresentationBindingRow.superseded_at.is_(None),
            ).order_by(RepresentationBindingRow.published_at.desc())))
            for binding in bindings:
                if role and binding.role != role:
                    continue
                if intended_use not in set(binding.intended_uses_json or []):
                    rejected.append({"binding_id": binding.binding_id, "reason": "intended_use_not_bound"})
                    continue
                allowed_audiences = set((binding.audience_policy_json or {}).get("allowed_audiences", [audience]))
                if audience not in allowed_audiences:
                    rejected.append({"binding_id": binding.binding_id, "reason": "audience_denied"})
                    continue
                representation = session.get(RepresentationAssetRow, binding.representation_id)
                if not representation or representation.state != "published" or representation.deprecated_at is not None:
                    rejected.append({"binding_id": binding.binding_id, "reason": "representation_unavailable"})
                    continue
                required = set((binding.client_profile_json or {}).get("required_capabilities", []))
                used_fallback = False
                if not required.issubset(capabilities):
                    fallback = session.get(RepresentationAssetRow, representation.fallback_representation_id) if representation.fallback_representation_id else None
                    if not fallback or fallback.state != "published" or fallback.deprecated_at is not None:
                        rejected.append({"binding_id": binding.binding_id, "reason": "client_incompatible_no_fallback"})
                        continue
                    representation = fallback
                    used_fallback = True
                selected.append({
                    "binding_id": binding.binding_id,
                    "representation_id": representation.representation_id,
                    "kind": representation.kind,
                    "role": binding.role,
                    "coordinate_frame_id": binding.coordinate_frame_id,
                    "transform": binding.transform_json,
                    "authority_class": binding.authority_class,
                    "authority_ceiling": binding.authority_ceiling,
                    "intended_uses": binding.intended_uses_json,
                    "used_fallback": used_fallback,
                })
        by_kind: dict[str, list[dict[str, Any]]] = {}
        for item in selected:
            by_kind.setdefault(item["kind"], []).append(item)
        return {"scene_id": scene_id, "intended_use": intended_use, "selected": selected, "by_kind": by_kind, "rejected": rejected}

    def replace_proxy(self, old_representation_id: str, new_representation_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            old = session.get(RepresentationAssetRow, old_representation_id)
            new = session.get(RepresentationAssetRow, new_representation_id)
            if not old or not new or old.kind != "interaction" or new.kind != "interaction":
                raise ValidationError("PROXY_REPLACEMENT_INVALID", "both representations must be interaction proxies")
            if old.scene_id != new.scene_id or old.coordinate_frame_id != new.coordinate_frame_id:
                raise ValidationError("PROXY_REPLACEMENT_FRAME_MISMATCH", "proxy replacement must remain in the same scene and coordinate frame")
            anchors = old.support_map_json.get("anchors", [])
            supported = set(new.support_map_json.get("semantic_support_ids", []))
            reprojected = [anchor for anchor in anchors if anchor.get("semantic_support_id") in supported]
            unresolved = [anchor for anchor in anchors if anchor.get("semantic_support_id") not in supported]
            new.support_map_json = {**new.support_map_json, "anchors": reprojected, "replaces": old_representation_id}
            old.state = "superseded"
            return {
                "old_representation_id": old_representation_id,
                "new_representation_id": new_representation_id,
                "reprojected": len(reprojected),
                "unresolved": len(unresolved),
                "reprojected_anchor_ids": [item.get("anchor_id") for item in reprojected],
                "unresolved_anchors": unresolved,
            }


class RepresentationPublisher:
    """The only service allowed to attach a reviewed representation to a scene commit."""

    _events = OutboxEventFactory()

    def __init__(
        self,
        database: Database,
        audit: AuditService,
        providers: ProviderRegistry | None = None,
    ) -> None:
        self.database = database
        self.audit = audit
        self.providers = providers or ProviderRegistry(database, audit)

    def publish(
        self,
        representation_id: str,
        *,
        commit_id: str,
        role: str,
        publisher_id: str,
        transform: list[list[float]] | None = None,
        intended_uses: list[str] | None = None,
        review_decision: dict[str, Any] | None = None,
        audience_policy: dict[str, Any] | None = None,
        client_profile: dict[str, Any] | None = None,
    ) -> str:
        if publisher_id.startswith("sip-worker:"):
            raise AuthorizationError(
                "WORKER_PUBLICATION_DENIED",
                "worker workload identities have no representation publication permission",
            )
        transform = transform or [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
        if len(transform) != 4 or any(len(row) != 4 for row in transform):
            raise ValidationError("REPRESENTATION_BINDING_TRANSFORM_INVALID", "binding transform must be 4x4")
        with self.database.session() as session:
            rep = session.get(RepresentationAssetRow, representation_id)
            commit = session.get(SceneCommitRow, commit_id)
            if not rep:
                raise NotFoundError("representation", representation_id)
            if not commit or commit.tenant_id != rep.tenant_id or commit.project_id != rep.project_id or commit.scene_id != rep.scene_id:
                raise ValidationError("REPRESENTATION_COMMIT_SCOPE_MISMATCH", "representation and commit do not share scope")
            if rep.state != "approved":
                raise ConflictError("REPRESENTATION_NOT_APPROVED", "only quality-approved candidates may be published")
            provider = session.get(ProviderManifestRow, rep.provider_id)
            provider_expiry = _aware(provider.expires_at) if provider and provider.expires_at else None
            if provider is None or provider.approval_state != "approved" or (provider_expiry and provider_expiry <= db_now()):
                raise AuthorizationError(
                    "PROVIDER_PUBLICATION_DENIED",
                    "representation publication is denied because its provider is not currently approved",
                )
            admitted_manifest_hash = (rep.provenance_json or {}).get("provider_manifest_hash")
            if admitted_manifest_hash and admitted_manifest_hash != provider.manifest_hash:
                raise AuthorizationError(
                    "PROVIDER_MANIFEST_CHANGED",
                    "provider policy changed after computation; the candidate must be re-admitted and reviewed",
                )
            if role in set(rep.prohibited_uses_json):
                raise AuthorizationError("REPRESENTATION_USE_PROHIBITED", "requested publication role is prohibited")

            conversion = session.scalar(
                select(SpatialConversionRow).where(SpatialConversionRow.operation_id == rep.operation_id)
            ) if rep.operation_id else None
            if conversion is not None:
                bound_uses, governed_review = self._authorize_governed_publication(
                    session,
                    rep=rep,
                    commit=commit,
                    conversion=conversion,
                    role=role,
                    intended_uses=intended_uses,
                )
                review_decision = review_decision or governed_review
            else:
                reviewed = set(rep.quality_json.get("review", {}).get("approved_uses", []))
                if role not in reviewed:
                    raise AuthorizationError("REPRESENTATION_USE_NOT_APPROVED", "requested publication role was not independently approved")
                bound_uses = sorted(set(intended_uses or [role]))
                unauthorized_uses = sorted(set(bound_uses) - reviewed)
                if unauthorized_uses:
                    raise AuthorizationError("REPRESENTATION_USE_NOT_APPROVED", "binding includes uses not independently approved", {"uses": unauthorized_uses})
                review_decision = review_decision or dict(rep.quality_json.get("review", {}))
            inherited_policy = dict(rep.privacy_inheritance_json or {})
            policy_blockers = sorted(set(str(item) for item in inherited_policy.get("policy_blockers", [])))
            if policy_blockers:
                raise AuthorizationError(
                    "REPRESENTATION_POLICY_BLOCKED",
                    "representation publication is blocked until every inherited source policy resolves",
                    {"policy_blockers": policy_blockers},
                )
            requested_policy = dict(audience_policy or inherited_policy)
            inherited_audiences = set(str(item) for item in inherited_policy.get("allowed_audiences", []))
            requested_audiences = set(str(item) for item in requested_policy.get("allowed_audiences", []))
            if inherited_audiences and not requested_audiences:
                requested_audiences = set(inherited_audiences)
                requested_policy["allowed_audiences"] = sorted(requested_audiences)
            if inherited_audiences and not requested_audiences.issubset(inherited_audiences):
                raise AuthorizationError(
                    "REPRESENTATION_AUDIENCE_WIDENING_DENIED",
                    "publication audience cannot be broader than inherited source policy",
                    {
                        "inherited_audiences": sorted(inherited_audiences),
                        "requested_audiences": sorted(requested_audiences),
                    },
                )
            purpose = str(
                requested_policy.get("purpose")
                or inherited_policy.get("purpose")
                or role
            )
            inherited_purposes = set(str(item) for item in inherited_policy.get("allowed_purposes", []))
            if inherited_purposes and purpose not in inherited_purposes:
                raise AuthorizationError(
                    "REPRESENTATION_PURPOSE_DENIED",
                    "publication purpose is not permitted by inherited source policy",
                    {"purpose": purpose, "allowed_purposes": sorted(inherited_purposes)},
                )
            required_scopes = set(str(item) for item in inherited_policy.get("required_scopes", []))
            for grant_id in sorted(set(str(item) for item in inherited_policy.get("consent_grant_ids", []))):
                grant = session.get(ConsentGrantRow, grant_id)
                grant_expiry = _aware(grant.expires_at) if grant and grant.expires_at else None
                if (
                    grant is None
                    or grant.tenant_id != rep.tenant_id
                    or grant.project_id != rep.project_id
                    or grant.state != "active"
                    or grant.revoked_at is not None
                    or (grant_expiry and grant_expiry <= db_now())
                ):
                    raise AuthorizationError(
                        "REPRESENTATION_CONSENT_INVALID",
                        "representation publication requires a current in-scope consent grant",
                        {"grant_id": grant_id},
                    )
                if purpose not in set(str(item) for item in grant.purposes_json):
                    raise AuthorizationError(
                        "REPRESENTATION_CONSENT_PURPOSE_DENIED",
                        "consent grant does not permit the publication purpose",
                        {"grant_id": grant_id, "purpose": purpose},
                    )
                grant_audiences = set(str(item) for item in grant.audiences_json)
                if requested_audiences and not requested_audiences.issubset(grant_audiences):
                    raise AuthorizationError(
                        "REPRESENTATION_CONSENT_AUDIENCE_DENIED",
                        "consent grant does not permit every requested audience",
                        {"grant_id": grant_id, "requested_audiences": sorted(requested_audiences)},
                    )
                if required_scopes and not required_scopes.issubset(set(str(item) for item in grant.scopes_json)):
                    raise AuthorizationError(
                        "REPRESENTATION_CONSENT_SCOPE_DENIED",
                        "consent grant does not include every required derivative scope",
                        {"grant_id": grant_id, "required_scopes": sorted(required_scopes)},
                    )
            requested_policy["purpose"] = purpose
            audience_policy = requested_policy
            client_profile = client_profile or {}
            prior = list(
                session.scalars(
                    select(RepresentationBindingRow).where(
                        RepresentationBindingRow.tenant_id == rep.tenant_id,
                        RepresentationBindingRow.project_id == rep.project_id,
                        RepresentationBindingRow.scene_id == rep.scene_id,
                        RepresentationBindingRow.role == role,
                        RepresentationBindingRow.superseded_at.is_(None),
                    )
                )
            )
            now = db_now()
            for binding in prior:
                binding.superseded_at = now
            binding_id = new_uuid()
            session.add(
                RepresentationBindingRow(
                    binding_id=binding_id,
                    tenant_id=rep.tenant_id,
                    project_id=rep.project_id,
                    scene_id=rep.scene_id,
                    commit_id=commit_id,
                    representation_id=representation_id,
                    role=role,
                    coordinate_frame_id=rep.coordinate_frame_id,
                    transform_json=transform,
                    authority_class=rep.authority_class,
                    authority_ceiling=rep.authority_ceiling,
                    intended_uses_json=bound_uses,
                    review_decision_json=review_decision,
                    audience_policy_json=audience_policy,
                    client_profile_json=client_profile,
                    published_by=publisher_id,
                )
            )
            rep.state = "published"
            event_payload = {
                "binding_id": binding_id,
                "representation_id": representation_id,
                "commit_id": commit_id,
                "role": role,
                "coordinate_frame_id": rep.coordinate_frame_id,
                "authority_ceiling": rep.authority_ceiling,
                "intended_uses": bound_uses,
            }
            session.add(self._events.create(
                session,
                event_type="representation.published",
                schema_version="1.0.0",
                tenant_id=rep.tenant_id,
                project_id=rep.project_id,
                aggregate_type="representation_binding",
                aggregate_id=binding_id,
                payload=event_payload,
                producer="representation-publisher",
                actor_id=publisher_id,
                workload_identity=None,
                causation_id=representation_id,
            ))
            self.audit.append(
                tenant_id=rep.tenant_id,
                project_id=rep.project_id,
                actor_id=publisher_id,
                action="representation:publish",
                resource_type="representation_binding",
                resource_id=binding_id,
                outcome="allowed",
                details={"representation_id": representation_id, "commit_id": commit_id, "role": role},
                session=session,
            )
            return binding_id


    def _authorize_governed_publication(
        self,
        session: Any,
        *,
        rep: RepresentationAssetRow,
        commit: SceneCommitRow,
        conversion: SpatialConversionRow,
        role: str,
        intended_uses: list[str] | None,
    ) -> tuple[list[str], dict[str, Any]]:
        if conversion.candidate_representation_id != rep.representation_id:
            raise AuthorizationError(
                "HYB_PUBLICATION_CANDIDATE_MISMATCH",
                "conversion does not identify this representation as its quarantined candidate",
            )
        if conversion.state != "validated":
            raise AuthorizationError(
                "HYB_PUBLICATION_CONVERSION_NOT_VALIDATED",
                "governed conversion must be in validated state before publication",
                {"state": conversion.state},
            )
        if commit.commit_id != conversion.scene_revision_id:
            raise AuthorizationError(
                "HYB_PUBLICATION_SCENE_SNAPSHOT_STALE",
                "candidate may only bind to the exact scene revision admitted for conversion",
            )
        if role not in set(conversion.output_roles_json):
            raise AuthorizationError("HYB_PUBLICATION_ROLE_UNADMITTED", "publication role was not admitted for this conversion")
        if str((rep.metadata_json or {}).get("output_role", role)) != role:
            raise AuthorizationError("HYB_PUBLICATION_OUTPUT_ROLE_MISMATCH", "candidate output role differs from requested binding role")
        provenance = dict(rep.provenance_json or {})
        expected_provenance = {
            "conversion_id": conversion.conversion_id,
            "operation_id": conversion.operation_id,
            "request_hash": conversion.request_hash,
            "admission_decision_hash": conversion.admission_decision_hash,
            "provider_id": conversion.provider_id,
            "provider_version": conversion.provider_version,
            "provider_manifest_hash": conversion.provider_manifest_hash,
            "promotion_id": conversion.promotion_id,
        }
        provenance_mismatches = sorted(
            key for key, value in expected_provenance.items() if provenance.get(key) != value
        )
        if provenance_mismatches:
            raise AuthorizationError(
                "HYB_PUBLICATION_PROVENANCE_MISMATCH",
                "candidate provenance differs from immutable conversion admission",
                {"fields": provenance_mismatches},
            )
        if not rep.manifest_hash:
            raise AuthorizationError("HYB_PUBLICATION_CANDIDATE_HASH_MISSING", "candidate manifest hash is missing")

        provider = session.get(ProviderManifestRow, conversion.provider_id)
        revision = session.get(ProviderManifestRevisionRow, conversion.provider_manifest_hash)
        if (
            provider is None
            or provider.version != conversion.provider_version
            or provider.manifest_hash != conversion.provider_manifest_hash
            or not self.providers._provider_integrity_valid(provider)
            or revision is None
            or not self.providers._revision_integrity_valid(revision)
        ):
            raise AuthorizationError(
                "HYB_PUBLICATION_PROVIDER_SNAPSHOT_STALE",
                "provider descriptor no longer matches the admitted immutable revision",
            )
        admission_provider = dict((conversion.admission_decision_json or {}).get("provider", {}))
        descriptor_snapshot = dict(admission_provider.get("descriptor_snapshot", {}))
        if (
            admission_provider.get("descriptor_snapshot_hash") != conversion.provider_manifest_hash
            or canonical_sha256(_descriptor_body(descriptor_snapshot)) != conversion.provider_manifest_hash
            or descriptor_snapshot != revision.descriptor_json
        ):
            raise AuthorizationError(
                "HYB_PUBLICATION_DESCRIPTOR_SNAPSHOT_INVALID",
                "retained admission descriptor snapshot is missing or no longer integrity-valid",
            )

        promotion = session.get(ProviderPromotionRow, conversion.promotion_id)
        now = db_now()
        if (
            promotion is None
            or promotion.superseded_at is not None
            or promotion.state not in {"active", "limited"}
            or promotion.provider_id != conversion.provider_id
            or promotion.provider_version != conversion.provider_version
            or promotion.provider_manifest_hash != conversion.provider_manifest_hash
            or _aware(promotion.valid_from) > now
            or (promotion.valid_until is not None and _aware(promotion.valid_until) <= now)
            or not self.providers._promotion_integrity_valid(promotion)
        ):
            raise AuthorizationError(
                "HYB_PUBLICATION_PROMOTION_STALE",
                "provider promotion is no longer active, current, or integrity-valid",
            )
        if admission_provider.get("promotion_hash") != promotion.promotion_hash:
            raise AuthorizationError(
                "HYB_PUBLICATION_PROMOTION_SNAPSHOT_MISMATCH",
                "publication promotion differs from the admitted promotion snapshot",
            )

        bound_uses = sorted(set(intended_uses or conversion.intended_uses_json))
        if not bound_uses:
            raise ValidationError("HYB_PUBLICATION_USE_REQUIRED", "governed publication requires at least one intended use")
        if not set(bound_uses).issubset(set(conversion.intended_uses_json)):
            raise AuthorizationError("HYB_PUBLICATION_USE_UNADMITTED", "binding contains an intended use not admitted for conversion")
        if not set(bound_uses).issubset(set(promotion.intended_uses_json)):
            raise AuthorizationError("HYB_PUBLICATION_USE_PROMOTION_DENIED", "binding use is outside the current provider promotion")

        rows = list(session.scalars(select(IntendedUseValidationRow).where(
            IntendedUseValidationRow.conversion_id == conversion.conversion_id,
            IntendedUseValidationRow.representation_id == rep.representation_id,
            IntendedUseValidationRow.intended_use.in_(bound_uses),
            IntendedUseValidationRow.passed.is_(True),
            IntendedUseValidationRow.candidate_snapshot_hash == rep.manifest_hash,
            IntendedUseValidationRow.policy_snapshot_hash == conversion.admission_decision_hash,
        )))
        valid_by_use = {row.intended_use: row for row in rows}
        missing = sorted(set(bound_uses) - set(valid_by_use))
        if missing:
            raise AuthorizationError(
                "HYB_PUBLICATION_VALIDATION_MISSING",
                "every bound intended use requires a current independent passing validation",
                {"uses": missing},
            )
        if any(
            row.validator_id.startswith(("sip-worker:", "sip-provider:"))
            or row.validator_id in {conversion.provider_id, conversion.requested_by}
            for row in rows
        ):
            raise AuthorizationError("HYB_PUBLICATION_VALIDATOR_NOT_INDEPENDENT", "validation is not independent from provider or requester")
        reviewed = set((rep.quality_json or {}).get("review", {}).get("approved_uses", []))
        if not set(bound_uses).issubset(reviewed):
            raise AuthorizationError(
                "HYB_PUBLICATION_REVIEW_SNAPSHOT_MISMATCH",
                "representation review does not retain every passing intended-use validation",
            )
        return bound_uses, {
            "mode": "governed_conversion",
            "conversion_id": conversion.conversion_id,
            "request_hash": conversion.request_hash,
            "admission_decision_hash": conversion.admission_decision_hash,
            "provider_manifest_hash": conversion.provider_manifest_hash,
            "promotion_id": promotion.promotion_id,
            "promotion_hash": promotion.promotion_hash,
            "candidate_snapshot_hash": rep.manifest_hash,
            "validation_ids": sorted(row.validation_id for row in rows),
            "validation_hashes": sorted(row.validation_hash for row in rows),
            "approved_uses": bound_uses,
            "independent_validation": True,
        }


def _safe_pydantic_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe: list[dict[str, Any]] = []
    for item in errors[:25]:
        safe.append({
            "loc": [str(value) for value in item.get("loc", [])],
            "type": str(item.get("type", "invalid")),
            "msg": str(item.get("msg", "invalid value"))[:256],
        })
    return safe


def _descriptor_body(descriptor: dict[str, Any] | None) -> dict[str, Any]:
    body = dict(descriptor or {})
    body.pop("manifest_hash", None)
    body.pop("manifest_signature", None)
    return body


def _promotion_scope_overlaps(row: ProviderPromotionRow, candidate: ProviderPromotionContract) -> bool:
    return all([
        bool(set(row.data_classifications_json) & {item.value for item in candidate.data_classifications}),
        bool(set(row.scene_classes_json) & set(candidate.scene_classes)),
        bool(set(row.output_roles_json) & set(candidate.output_roles)),
        bool(set(row.intended_uses_json) & set(candidate.intended_uses)),
        bool(set(row.execution_zones_json) & set(candidate.execution_zones)),
        bool(set(row.hardware_profiles_json) & set(candidate.hardware_profiles)),
    ])


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
