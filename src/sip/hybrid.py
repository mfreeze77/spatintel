from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select

from .audit import AuditService
from .canonical import canonical_sha256, new_uuid
from .contracts import (
    HybridSceneViewManifestContract,
    IntendedUseValidationContract,
    ManualExternalReceiptContract,
    ProviderProgressContract,
    SpatialConversionRequestContract,
)
from .database import (
    AssetRefRow,
    AssetRow,
    ConsentGrantRow,
    CoordinateFrameRow,
    Database,
    HybridSceneViewRow,
    IntendedUseValidationRow,
    InteractionProfileRow,
    ManualProviderTransferRow,
    ModelManifestRow,
    OperationRow,
    ProjectRow,
    ProviderManifestRow,
    ProviderProgressRow,
    ProviderPromotionRow,
    RepresentationAssetRow,
    RepresentationBindingRow,
    RepresentationFamilyRow,
    SceneCommitRow,
    SpatialConversionRow,
)
from .errors import AuthenticationError, AuthorizationError, ConflictError, NotFoundError, ValidationError
from .events import OutboxEventFactory
from .lifecycle import AdmissionController
from .model_governance import ModelRegistry
from .models import Audience, AuthorityClass, Classification, RepresentationKind, SignedPrincipal, SourceClass
from .operations import OperationService
from .policy import PolicyService
from .representations import ProviderRegistry, RepresentationService
from .security import SignedTokenCodec
from .temporal import db_now


_CLASSIFICATION_RANK = {
    Classification.PUBLIC.value: 0,
    Classification.INTERNAL.value: 1,
    Classification.CONFIDENTIAL.value: 2,
    Classification.RESTRICTED.value: 3,
    Classification.CRITICAL_INFRASTRUCTURE.value: 4,
    Classification.BIOMETRIC.value: 4,
    Classification.MINOR.value: 4,
}
_HARD_EXTERNAL_DENY = {
    Classification.CRITICAL_INFRASTRUCTURE.value,
    Classification.BIOMETRIC.value,
    Classification.MINOR.value,
}
_SPATIAL_SENSITIVITY_FLOORS: dict[str, str] = {
    "public_fixture": Classification.PUBLIC.value,
    "public_cleared_landmark_geometry": Classification.PUBLIC.value,
    "geometry_or_layout": Classification.INTERNAL.value,
    "relationship_graph": Classification.CONFIDENTIAL.value,
    "private_residential_layout": Classification.RESTRICTED.value,
    "restricted_building_system": Classification.RESTRICTED.value,
    "inferred_occupancy_or_security": Classification.RESTRICTED.value,
    "precise_private_location": Classification.RESTRICTED.value,
    "intimate_place": Classification.RESTRICTED.value,
    "liveforever_sensitive_relationships": Classification.RESTRICTED.value,
    "security_system_topology": Classification.CRITICAL_INFRASTRUCTURE.value,
    "critical_infrastructure_layout": Classification.CRITICAL_INFRASTRUCTURE.value,
    "biometric_geometry": Classification.BIOMETRIC.value,
    "minor_relationship_graph": Classification.MINOR.value,
}
_EXTERNAL_DENY_SENSITIVITY_SIGNALS = {
    "private_residential_layout",
    "restricted_building_system",
    "inferred_occupancy_or_security",
    "precise_private_location",
    "intimate_place",
    "liveforever_sensitive_relationships",
    "security_system_topology",
    "critical_infrastructure_layout",
    "biometric_geometry",
    "minor_relationship_graph",
}
_INTERACTION_USES = {"picking", "collision", "navigation", "occlusion", "spatial_audio"}
_FORBIDDEN_SAFETY_CLAIMS = {
    "egress_compliance",
    "life_safety",
    "accessibility_compliance",
    "robotics_safety",
    "survey_grade",
    "fabrication_ready",
}
_OUTPUT_ROLE_KIND_COMPATIBILITY: dict[str, set[RepresentationKind]] = {
    "metric_mesh": {RepresentationKind.METRIC},
    "metric_surface": {RepresentationKind.METRIC},
    "metric_volume": {RepresentationKind.METRIC},
    "visual_mesh": {RepresentationKind.VISUAL},
    "gaussian_splat": {RepresentationKind.VISUAL},
    "visual_splat": {RepresentationKind.VISUAL},
    "photorealistic_scene": {RepresentationKind.VISUAL},
    "interaction_proxy": {RepresentationKind.INTERACTION},
    "collision_proxy": {RepresentationKind.INTERACTION},
    "collision_geometry": {RepresentationKind.INTERACTION},
    "navigation_surface": {RepresentationKind.INTERACTION},
    "occlusion_hull": {RepresentationKind.INTERACTION},
    "spatial_audio_geometry": {RepresentationKind.INTERACTION},
    "design_mesh": {RepresentationKind.DESIGN},
    "bim_design": {RepresentationKind.DESIGN},
    "evidence_mesh": {RepresentationKind.EVIDENCE},
    "evidence_geometry": {RepresentationKind.EVIDENCE},
}
_FAILURE_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")



class HybridControlService:
    """Governed control plane for provider-neutral hybrid representation conversion.

    The service deliberately separates admission, execution, quarantine, independent
    intended-use validation, publication, and view authorization. Provider workers receive
    only exact immutable input references and a write-only quarantine scope; no worker
    credential carries publication authority.
    """

    _events = OutboxEventFactory()

    def __init__(
        self,
        database: Database,
        audit: AuditService,
        operations: OperationService,
        providers: ProviderRegistry,
        representations: RepresentationService,
        models: ModelRegistry,
        admission: AdmissionController,
        token_codec: SignedTokenCodec,
        policy: PolicyService,
        *,
        environment: str = "production",
    ) -> None:
        self.database = database
        self.audit = audit
        self.operations = operations
        self.providers = providers
        self.representations = representations
        self.models = models
        self.admission = admission
        self.token_codec = token_codec
        self.policy = policy
        self.environment = environment

    def create_conversion(
        self,
        request: dict[str, Any] | SpatialConversionRequestContract,
        *,
        actor_id: str,
        traceparent: str | None = None,
        worker_lease_ttl_seconds: int = 900,
    ) -> dict[str, Any]:
        """Admit an immutable conversion request before any source may be decrypted."""
        if not 30 <= worker_lease_ttl_seconds <= 900:
            raise ValidationError("HYB_WORKER_LEASE_TTL_INVALID", "worker lease TTL must be between 30 and 900 seconds")
        try:
            contract = request if isinstance(request, SpatialConversionRequestContract) else SpatialConversionRequestContract.model_validate(request)
        except PydanticValidationError as exc:
            raise ValidationError("HYB_CONVERSION_REQUEST_INVALID", "spatial conversion request violates the canonical contract", _safe_errors(exc)) from exc
        if contract.requested_by != actor_id:
            raise AuthorizationError("HYB_REQUESTER_MISMATCH", "conversion requester must match the authenticated actor")

        request_body = contract.model_dump(mode="json", by_alias=True)
        request_body.pop("request_hash", None)
        request_body.pop("operation_id", None)
        request_hash = canonical_sha256(request_body)
        if contract.request_hash and not hmac.compare_digest(contract.request_hash, request_hash):
            raise ValidationError("HYB_REQUEST_HASH_MISMATCH", "conversion request hash does not match canonical content")

        with self.database.session() as session:
            prior = session.scalar(
                select(SpatialConversionRow).where(
                    SpatialConversionRow.tenant_id == contract.tenant_id,
                    SpatialConversionRow.project_id == contract.project_id,
                    SpatialConversionRow.idempotency_key == contract.idempotency_key,
                )
            )
            if prior:
                if prior.request_hash != request_hash:
                    raise ConflictError("HYB_IDEMPOTENCY_PAYLOAD_CONFLICT", "conversion idempotency key was reused with different immutable input")
                return {**self._conversion_dict(prior), "worker_token": None, "idempotent_replay": True}

        try:
            policy_context = dict(contract.policy_context)
            validated = self._validate_conversion_sources(contract, policy_context=policy_context)
            effective_classification = validated["effective_classification"]
            scene_class = _required_text(policy_context, "scene_class")
            execution_zone = _required_text(policy_context, "execution_zone")
            hardware_profile = _required_text(policy_context, "hardware_profile")
            region = _required_text(policy_context, "region")
            deployment_mode = str(policy_context.get("deployment_mode") or "local_only")
            required_capabilities = _string_list(contract.provider_selector.get("required_capabilities", []), "required_capabilities")
            forbidden_capabilities = _string_list(contract.provider_selector.get("forbidden_capabilities", []), "forbidden_capabilities")
            preferred = _string_list(contract.provider_selector.get("preferred_provider_ids", []), "preferred_provider_ids")

            selected = self.providers.select(
                classification=effective_classification,
                purpose=contract.purpose,
                region=region,
                deployment_mode=deployment_mode,
                scene_class=scene_class,
                output_roles=contract.output_roles,
                intended_uses=contract.intended_uses,
                execution_zone=execution_zone,
                hardware_profile=hardware_profile,
                required_capabilities=required_capabilities,
                forbidden_capabilities=forbidden_capabilities,
                preferred_provider_ids=preferred,
            )
            promotion_state = str(selected.get("promotion_state", ""))
            if promotion_state in {"shadow", "research_isolated"} and not (
                self.environment in {"development", "test"}
                and bool(policy_context.get("research_isolated", False))
            ):
                raise AuthorizationError(
                    "HYB_PROVIDER_PROMOTION_NOT_PRODUCTION_ELIGIBLE",
                    "shadow or research-isolated promotions require an explicit isolated test context",
                )
            external = bool(selected["security"].get("external_processing", False))
            # Platform-wide data-transfer prohibitions are evaluated before provider-specific
            # admission so denial evidence retains the most precise, policy-owned reason.
            self._validate_provider_for_request(
                selected=selected,
                contract=contract,
                effective_classification=effective_classification,
                policy_context=policy_context,
                classification_context=validated["classification_context"],
            )
            self.providers.authorize_execution(
                selected["provider_id"],
                classification=Classification(effective_classification),
                purpose=contract.purpose,
                region=region,
                external=external,
            )
            consent_receipts = self._validate_consents(
                tenant_id=contract.tenant_id,
                project_id=contract.project_id,
                purpose=contract.purpose,
                intended_uses=contract.intended_uses,
                audience=str(policy_context.get("audience") or "project"),
                classification=effective_classification,
                policy_context=policy_context,
            )
            model_receipts = self._authorize_models(
                selected=selected,
                purpose=contract.purpose,
                classification=effective_classification,
                deployment_mode=deployment_mode,
                region=region,
                tenant_id=contract.tenant_id,
            )

        except Exception as exc:
            self._record_pre_admission_rejection(contract, request_hash, actor_id, exc)
            raise

        immutable_input = {
            **request_body,
            "request_hash": request_hash,
            "effective_classification": effective_classification,
            "classification_context": validated["classification_context"],
            "validated_sources": validated["source_snapshots"],
            "validated_references": validated["reference_snapshots"],
        }
        operation = self.operations.create(
            tenant_id=contract.tenant_id,
            project_id=contract.project_id,
            operation_type="spatial.conversion",
            idempotency_key=contract.idempotency_key,
            input_manifest=immutable_input,
            actor_id=actor_id,
            max_attempts=int(policy_context.get("max_attempts", 3)),
            traceparent=traceparent,
        )
        estimate = self._resource_estimate(validated, contract)
        try:
            quota_receipt = self.admission.admit_and_record(
                tenant_id=contract.tenant_id,
                project_id=contract.project_id,
                operation_id=operation["operation_id"],
                resource_type="hybrid_provider_input_bytes",
                quantity=float(estimate["input_bytes"]),
                unit="bytes",
                unit_cost=float(policy_context.get("unit_cost_per_byte", 0.0)),
                currency=str(policy_context.get("currency", "USD")),
                price_source_version=str(policy_context.get("price_source_version", "local-reference-v1")),
                estimated=True,
                actor_id=actor_id,
                metadata={"provider_id": selected["provider_id"], "request_hash": request_hash},
            )
        except Exception as exc:
            self._mark_operation_rejected(operation["operation_id"], exc)
            raise

        admission_decision = {
            "allowed": True,
            "request_hash": request_hash,
            "provider": {
                "provider_id": selected["provider_id"],
                "provider_version": selected["provider_version"],
                "provider_manifest_hash": selected["provider_manifest_hash"],
                "promotion_id": selected["promotion_id"],
                "promotion_hash": selected["promotion_hash"],
                "benchmark_evidence_hash": selected["benchmark_evidence_hash"],
                "descriptor_snapshot": selected["provider_descriptor"],
                "descriptor_snapshot_hash": selected["provider_manifest_hash"],
            },
            "policy_snapshot_hash": canonical_sha256(policy_context),
            "source_snapshot_hash": canonical_sha256(validated["source_snapshots"]),
            "reference_snapshot_hash": canonical_sha256(validated["reference_snapshots"]),
            "consent_receipts": consent_receipts,
            "model_authorization_receipts": model_receipts,
            "quota_receipt": quota_receipt,
            "classification": effective_classification,
            "classification_context": validated["classification_context"],
            "external_processing": external,
            "execution_zone": execution_zone,
            "region": region,
            "deployment_mode": deployment_mode,
        }
        admission_hash = canonical_sha256(admission_decision)
        conversion_id = new_uuid()
        worker_identity = f"sip-provider:{selected['provider_id']}:{conversion_id}"
        worker_lease_generation = 1
        credential_claims = {
            "type": "hybrid-worker-lease",
            "credential_id": new_uuid(),
            "credential_generation": 1,
            "conversion_id": conversion_id,
            "operation_id": operation["operation_id"],
            "tenant_id": contract.tenant_id,
            "project_id": contract.project_id,
            "scene_id": contract.scene_id,
            "scene_revision_id": contract.scene_revision_id,
            "provider_id": selected["provider_id"],
            "provider_version": selected["provider_version"],
            "provider_manifest_hash": selected["provider_manifest_hash"],
            "promotion_id": selected["promotion_id"],
            "promotion_hash": selected["promotion_hash"],
            "workload_identity": worker_identity,
            "worker_lease_generation": worker_lease_generation,
            "lease_ttl_seconds": worker_lease_ttl_seconds,
            "permissions": ["asset:read_exact", "quarantine:write", "operation:checkpoint", "operation:complete"],
            "input_assets": [
                {"asset_id": item["asset_id"], "sha256": item["sha256"], "role": item["role"]}
                for item in validated["source_snapshots"] + validated["reference_snapshots"]
            ],
            "output_staging_scope": {
                "mode": "write_only_quarantine",
                "namespace": f"quarantine/{contract.tenant_id}/{contract.project_id}/{conversion_id}",
                "maximum_bytes": int(estimate["max_output_bytes"]),
            },
            "publication_permission": False,
            "admission_decision_hash": admission_hash,
        }
        worker_token = self.token_codec.encode(credential_claims, ttl_seconds=worker_lease_ttl_seconds)
        token_claims = self.token_codec.decode(worker_token)
        worker_token_hash = hashlib.sha256(worker_token.encode("utf-8")).hexdigest()
        worker_token_expires_at = datetime.fromtimestamp(int(token_claims["exp"]), UTC)

        with self.database.session() as session:
            row = SpatialConversionRow(
                conversion_id=conversion_id,
                operation_id=operation["operation_id"],
                tenant_id=contract.tenant_id,
                project_id=contract.project_id,
                scene_id=contract.scene_id,
                scene_revision_id=contract.scene_revision_id,
                purpose=contract.purpose,
                intended_uses_json=contract.intended_uses,
                output_roles_json=contract.output_roles,
                source_assets_json=validated["source_snapshots"],
                reference_assets_json=validated["reference_snapshots"],
                constraints_json=contract.constraints,
                policy_context_json=policy_context,
                provider_selector_json=contract.provider_selector,
                provider_id=selected["provider_id"],
                provider_version=selected["provider_version"],
                provider_manifest_hash=selected["provider_manifest_hash"],
                promotion_id=selected["promotion_id"],
                request_hash=request_hash,
                admission_state="allowed",
                admission_decision_json=admission_decision,
                admission_decision_hash=admission_hash,
                resource_estimate_json=estimate,
                credential_claims_json=credential_claims,
                worker_lease_generation=worker_lease_generation,
                worker_token_hash=worker_token_hash,
                worker_token_expires_at=worker_token_expires_at,
                state="admitted",
                idempotency_key=contract.idempotency_key,
                requested_by=actor_id,
            )
            session.add(row)
            session.add(self._event(
                session,
                event_type="representation.operation.requested",
                aggregate_type="spatial_conversion",
                aggregate_id=conversion_id,
                tenant_id=contract.tenant_id,
                project_id=contract.project_id,
                actor_id=actor_id,
                payload={"conversion_id": conversion_id, "operation_id": operation["operation_id"], "request_hash": request_hash},
            ))
            session.add(self._event(
                session,
                event_type="representation.operation.admitted",
                aggregate_type="spatial_conversion",
                aggregate_id=conversion_id,
                tenant_id=contract.tenant_id,
                project_id=contract.project_id,
                actor_id=actor_id,
                payload={
                    "conversion_id": conversion_id,
                    "provider_id": selected["provider_id"],
                    "provider_manifest_hash": selected["provider_manifest_hash"],
                    "promotion_id": selected["promotion_id"],
                    "admission_decision_hash": admission_hash,
                },
            ))
            self.audit.append(
                tenant_id=contract.tenant_id,
                project_id=contract.project_id,
                actor_id=actor_id,
                action="hybrid_conversion:admit",
                resource_type="spatial_conversion",
                resource_id=conversion_id,
                outcome="allowed",
                details={"request_hash": request_hash, "admission_decision_hash": admission_hash, "provider_id": selected["provider_id"]},
                session=session,
            )
            result = self._conversion_dict(row)
        return {**result, "worker_token": worker_token, "idempotent_replay": False}

    def get_conversion(self, conversion_id: str, *, tenant_id: str, project_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = self._scoped_conversion(session, conversion_id, tenant_id, project_id)
            result = self._conversion_dict(row)
            progress = list(session.scalars(select(ProviderProgressRow).where(ProviderProgressRow.conversion_id == conversion_id).order_by(ProviderProgressRow.sequence)))
            result["progress"] = [self._progress_dict(item) for item in progress]
            return result

    def renew_worker_lease(
        self,
        worker_token: str,
        *,
        lease_ttl_seconds: int = 900,
    ) -> dict[str, Any]:
        """Rotate a worker credential after fail-closed policy reauthorization.

        Renewal preserves the immutable conversion request and admitted provider revision,
        invalidates every earlier token generation, and bounds any durable operation lease
        to the remaining lifetime of the newly signed worker token. A retryable conversion
        may resume only after verified cleanup evidence has been retained.
        """
        if not 30 <= lease_ttl_seconds <= 900:
            raise ValidationError(
                "HYB_WORKER_LEASE_TTL_INVALID",
                "worker lease TTL must be between 30 and 900 seconds",
            )
        claims = self._verify_worker_token(
            worker_token,
            allowed_inactive_states={"failed_retryable"},
        )
        now = db_now()
        with self.database.session() as session:
            row = self._scoped_conversion(
                session, claims["conversion_id"], claims["tenant_id"], claims["project_id"]
            )
            if row.state not in {"admitted", "running", "failed_retryable"}:
                raise ConflictError(
                    "HYB_WORKER_LEASE_RENEWAL_STATE_INVALID",
                    "worker credentials may be renewed only for active or safely retryable work",
                    {"state": row.state},
                )
            resuming = row.state == "failed_retryable"
            retained_failure = dict(row.failure_json or {})
            if resuming and retained_failure.get("cleanup_verified") is not True:
                raise AuthorizationError(
                    "HYB_WORKER_RESUME_CLEANUP_UNVERIFIED",
                    "retryable work cannot resume until governed cleanup evidence is verified",
                )

            durable_claims = dict(row.credential_claims_json or {})
            if durable_claims.get("credential_id") != claims.get("credential_id"):
                raise AuthenticationError(
                    "HYB_WORKER_CREDENTIAL_SUPERSEDED",
                    "worker credential has already been rotated",
                )
            if int(durable_claims.get("credential_generation", 0)) != int(
                claims.get("credential_generation", 0)
            ):
                raise AuthenticationError(
                    "HYB_WORKER_CREDENTIAL_SUPERSEDED",
                    "worker credential generation is no longer current",
                )
            current_worker_generation = int(row.worker_lease_generation or 1)
            if int(claims.get("worker_lease_generation", 0)) != current_worker_generation:
                raise AuthenticationError(
                    "HYB_WORKER_TOKEN_SUPERSEDED",
                    "worker lease generation is no longer current",
                )

            provider = session.get(ProviderManifestRow, row.provider_id)
            promotion = session.get(ProviderPromotionRow, row.promotion_id)
            if (
                provider is None
                or provider.manifest_hash != row.provider_manifest_hash
                or not self.providers._provider_integrity_valid(provider)
            ):
                raise AuthorizationError(
                    "HYB_PROVIDER_SNAPSHOT_STALE",
                    "provider descriptor is no longer the admitted immutable revision",
                )
            promotion_expiry = _aware(promotion.valid_until) if promotion and promotion.valid_until else None
            if (
                promotion is None
                or promotion.provider_manifest_hash != row.provider_manifest_hash
                or promotion.provider_version != row.provider_version
                or promotion.superseded_at is not None
                or promotion.state not in {"active", "limited"}
                or _aware(promotion.valid_from) > now
                or (promotion_expiry is not None and promotion_expiry <= now)
                or not self.providers._promotion_integrity_valid(promotion)
            ):
                raise AuthorizationError(
                    "HYB_PROVIDER_PROMOTION_STALE",
                    "provider promotion is no longer eligible for execution",
                )
            if durable_claims.get("promotion_hash") != promotion.promotion_hash:
                raise AuthorizationError(
                    "HYB_PROVIDER_PROMOTION_STALE",
                    "worker credential promotion snapshot no longer matches the governed promotion",
                )

            classification = str(row.admission_decision_json.get("classification", "internal"))
            policy_context = dict(row.policy_context_json or {})
            provider_snapshot = {
                "provider_id": row.provider_id,
                "provider_version": row.provider_version,
                "provider_manifest_hash": row.provider_manifest_hash,
                "model_manifest_ids": list(provider.model_manifest_ids_json or []),
            }
            provider_security = dict(provider.security_contract_json or {})
            immutable_snapshot = {
                "operation_id": row.operation_id,
                "purpose": row.purpose,
                "intended_uses": list(row.intended_uses_json or []),
                "source_assets": list(row.source_assets_json or []),
                "reference_assets": list(row.reference_assets_json or []),
                "admission_decision_hash": row.admission_decision_hash,
                "resource_estimate": dict(row.resource_estimate_json or {}),
                "current_state": row.state,
                "current_worker_generation": current_worker_generation,
                "current_credential_id": durable_claims.get("credential_id"),
                "current_credential_generation": int(durable_claims.get("credential_generation", 1)),
            }

        region = _required_text(policy_context, "region")
        deployment_mode = str(policy_context.get("deployment_mode") or "local_only")
        self.providers.authorize_execution(
            provider_snapshot["provider_id"],
            classification=Classification(classification),
            purpose=immutable_snapshot["purpose"],
            region=region,
            external=bool(provider_security.get("external_processing", False)),
        )
        consent_receipts = self._validate_consents(
            tenant_id=claims["tenant_id"],
            project_id=claims["project_id"],
            purpose=immutable_snapshot["purpose"],
            intended_uses=immutable_snapshot["intended_uses"],
            audience=str(policy_context.get("audience") or "project"),
            classification=classification,
            policy_context=policy_context,
        )
        model_receipts = self._authorize_models(
            selected=provider_snapshot,
            purpose=immutable_snapshot["purpose"],
            classification=classification,
            deployment_mode=deployment_mode,
            region=region,
            tenant_id=claims["tenant_id"],
        )

        next_worker_generation = immutable_snapshot["current_worker_generation"] + 1
        next_claims = {
            **claims,
            "credential_id": new_uuid(),
            "credential_generation": immutable_snapshot["current_credential_generation"] + 1,
            "renewed_from_credential_id": immutable_snapshot["current_credential_id"],
            "worker_lease_generation": next_worker_generation,
            "lease_ttl_seconds": lease_ttl_seconds,
            "renewal": {
                "consent_receipt_hash": canonical_sha256(consent_receipts),
                "model_receipt_hash": canonical_sha256(model_receipts),
                "resuming_retryable_failure": resuming,
                "retained_failure_hash": retained_failure.get("failure_hash") if resuming else None,
            },
        }
        # Expiry is always freshly supplied by the token codec; stale temporal claims from
        # the prior token are intentionally removed before signing.
        next_claims.pop("iat", None)
        next_claims.pop("exp", None)
        next_claims.pop("jti", None)
        new_token = self.token_codec.encode(next_claims, ttl_seconds=lease_ttl_seconds)
        token_claims = self.token_codec.decode(new_token)
        token_hash = hashlib.sha256(new_token.encode("utf-8")).hexdigest()
        expires_at = datetime.fromtimestamp(int(token_claims["exp"]), UTC)
        remaining_seconds = max(1, int(token_claims["exp"]) - int(datetime.now(UTC).timestamp()))
        bounded_lease_seconds = max(1, min(900, lease_ttl_seconds, remaining_seconds))

        operation = self.operations.get(immutable_snapshot["operation_id"])
        if operation["state"] in {"leased", "running"}:
            if operation["lease_owner"] != claims["workload_identity"]:
                raise ConflictError(
                    "HYB_OPERATION_LEASE_OWNER_MISMATCH",
                    "conversion operation is leased to another workload",
                )
            self.operations.heartbeat(
                immutable_snapshot["operation_id"],
                worker_id=claims["workload_identity"],
                lease_seconds=bounded_lease_seconds,
            )
        elif operation["state"] == "pending":
            pass
        elif operation["state"] == "failed" and resuming:
            # The next progress/checkpoint call leases and starts the failed operation.
            pass
        else:
            raise ConflictError(
                "HYB_WORKER_LEASE_RENEWAL_OPERATION_INVALID",
                "worker credential cannot be renewed for the current durable operation state",
                {"state": operation["state"]},
            )

        with self.database.session() as session:
            row = self._scoped_conversion(
                session, claims["conversion_id"], claims["tenant_id"], claims["project_id"]
            )
            current = dict(row.credential_claims_json or {})
            if (
                current.get("credential_id") != immutable_snapshot["current_credential_id"]
                or int(current.get("credential_generation", 0))
                != immutable_snapshot["current_credential_generation"]
                or int(row.worker_lease_generation or 1)
                != immutable_snapshot["current_worker_generation"]
                or row.state != immutable_snapshot["current_state"]
            ):
                raise ConflictError(
                    "HYB_WORKER_CREDENTIAL_ROTATION_RACE",
                    "worker credential or conversion state changed during lease renewal",
                )
            row.credential_claims_json = {
                key: value for key, value in token_claims.items() if key not in {"iat", "exp", "jti"}
            }
            row.worker_lease_generation = next_worker_generation
            row.worker_token_hash = token_hash
            row.worker_token_expires_at = expires_at
            if resuming:
                row.state = "admitted"
            row.updated_at = db_now()
            session.add(self._event(
                session,
                event_type="representation.worker_lease.renewed",
                aggregate_type="spatial_conversion",
                aggregate_id=row.conversion_id,
                tenant_id=row.tenant_id,
                project_id=row.project_id,
                actor_id=None,
                workload_identity=claims["workload_identity"],
                payload={
                    "conversion_id": row.conversion_id,
                    "operation_id": row.operation_id,
                    "credential_id": next_claims["credential_id"],
                    "credential_generation": next_claims["credential_generation"],
                    "worker_lease_generation": next_worker_generation,
                    "lease_ttl_seconds": lease_ttl_seconds,
                    "bounded_operation_lease_seconds": bounded_lease_seconds,
                    "expires_at": expires_at.isoformat(),
                    "resumed_retryable_failure": resuming,
                },
            ))
            self.audit.append(
                tenant_id=row.tenant_id,
                project_id=row.project_id,
                actor_id=claims["workload_identity"],
                action="hybrid_worker_lease:renew",
                resource_type="spatial_conversion",
                resource_id=row.conversion_id,
                outcome="allowed",
                details={
                    "operation_id": row.operation_id,
                    "credential_generation": next_claims["credential_generation"],
                    "worker_lease_generation": next_worker_generation,
                    "lease_ttl_seconds": lease_ttl_seconds,
                    "resumed_retryable_failure": resuming,
                    "consent_receipt_hash": next_claims["renewal"]["consent_receipt_hash"],
                    "model_receipt_hash": next_claims["renewal"]["model_receipt_hash"],
                },
                session=session,
            )

        return {
            "conversion_id": claims["conversion_id"],
            "operation_id": claims["operation_id"],
            "worker_token": new_token,
            "credential_id": next_claims["credential_id"],
            "credential_generation": next_claims["credential_generation"],
            "worker_lease_generation": next_worker_generation,
            "lease_ttl_seconds": lease_ttl_seconds,
            "bounded_operation_lease_seconds": bounded_lease_seconds,
            "expires_at": expires_at.isoformat(),
            "resumed_retryable_failure": resuming,
        }

    def report_provider_failure(
        self,
        worker_token: str,
        *,
        error_code: str,
        retryable: bool,
        cleanup_receipt_hash: str,
        cleanup_verified: bool,
        last_durable_checkpoint_hash: str | None = None,
        resource_use: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Retain a safe provider failure and cleanup decision without altering published bindings."""
        error_code = error_code.strip().upper()
        if not _FAILURE_CODE_PATTERN.fullmatch(error_code):
            raise ValidationError("HYB_PROVIDER_ERROR_CODE_INVALID", "provider error code must be a stable uppercase machine code")
        _require_digest(cleanup_receipt_hash, "cleanup_receipt_hash")
        if last_durable_checkpoint_hash is not None:
            _require_digest(last_durable_checkpoint_hash, "last_durable_checkpoint_hash")
        safe_resource_use = dict(resource_use or {})
        claims = self._verify_worker_token(
            worker_token,
            allowed_inactive_states={"failed_retryable", "failed_terminal", "cleanup_quarantined"},
        )
        failure_evidence = {
            "conversion_id": claims["conversion_id"],
            "operation_id": claims["operation_id"],
            "error_code": error_code,
            "retryable": bool(retryable),
            "cleanup_receipt_hash": cleanup_receipt_hash,
            "cleanup_verified": bool(cleanup_verified),
            "last_durable_checkpoint_hash": last_durable_checkpoint_hash,
            "resource_use": safe_resource_use,
        }
        failure_hash = canonical_sha256(failure_evidence)
        with self.database.session() as session:
            conversion = self._scoped_conversion(session, claims["conversion_id"], claims["tenant_id"], claims["project_id"])
            operation = session.get(OperationRow, conversion.operation_id)
            if conversion.state in {"failed_retryable", "failed_terminal", "cleanup_quarantined"}:
                prior_hash = str(conversion.failure_hash or "")
                if hmac.compare_digest(prior_hash, failure_hash):
                    return {
                        "conversion_id": conversion.conversion_id,
                        "operation_id": conversion.operation_id,
                        "state": conversion.state,
                        "failure": dict(conversion.failure_json or {}),
                        "failure_hash": failure_hash,
                        "cleanup_receipt_hash": conversion.cleanup_receipt_hash,
                        "idempotent_replay": True,
                    }
                raise ConflictError("HYB_PROVIDER_FAILURE_IMMUTABLE_CONFLICT", "provider failure is already bound to different evidence")
            if conversion.state not in {"admitted", "running"}:
                raise ConflictError("HYB_PROVIDER_FAILURE_STATE_INVALID", "conversion cannot accept provider failure evidence", {"state": conversion.state})
            preserved_bindings = [
                item.binding_id
                for item in session.scalars(select(RepresentationBindingRow).where(
                    RepresentationBindingRow.tenant_id == conversion.tenant_id,
                    RepresentationBindingRow.project_id == conversion.project_id,
                    RepresentationBindingRow.scene_id == conversion.scene_id,
                    RepresentationBindingRow.role.in_(conversion.output_roles_json),
                    RepresentationBindingRow.superseded_at.is_(None),
                ))
            ]

        self._ensure_operation_started(claims)
        self.operations.fail(
            claims["operation_id"],
            worker_id=claims["workload_identity"],
            code=error_code,
            message="provider execution failed; inspect retained governed failure evidence",
            retryable=bool(retryable and cleanup_verified),
        )
        state = "cleanup_quarantined" if not cleanup_verified else ("failed_retryable" if retryable else "failed_terminal")
        with self.database.session() as session:
            conversion = self._scoped_conversion(session, claims["conversion_id"], claims["tenant_id"], claims["project_id"])
            operation = session.get(OperationRow, conversion.operation_id)
            if operation is None:
                raise NotFoundError("operation", conversion.operation_id)
            operation.error_json = {
                "code": error_code if cleanup_verified else "HYB_PROVIDER_CLEANUP_UNVERIFIED",
                "message": "provider execution failed; governed cleanup evidence retained",
                "retryable": bool(retryable and cleanup_verified),
                "failure_hash": failure_hash,
                "cleanup_receipt_hash": cleanup_receipt_hash,
                "cleanup_verified": bool(cleanup_verified),
                "last_durable_checkpoint_hash": last_durable_checkpoint_hash,
                "resource_use": safe_resource_use,
            }
            if not cleanup_verified:
                operation.state = "quarantined"
            retained_failure = {
                **failure_evidence,
                "failure_hash": failure_hash,
                "state": state,
                "preserved_binding_ids": preserved_bindings,
            }
            conversion.failure_json = retained_failure
            conversion.failure_hash = failure_hash
            conversion.cleanup_receipt_hash = cleanup_receipt_hash
            conversion.state = state
            conversion.updated_at = db_now()
            session.add(self._event(
                session,
                event_type="representation.operation.failed",
                aggregate_type="spatial_conversion",
                aggregate_id=conversion.conversion_id,
                tenant_id=conversion.tenant_id,
                project_id=conversion.project_id,
                actor_id=None,
                workload_identity=claims["workload_identity"],
                payload={
                    **failure_evidence,
                    "failure_hash": failure_hash,
                    "state": state,
                    "preserved_binding_ids": preserved_bindings,
                },
            ))
            session.add(self._event(
                session,
                event_type="representation.cleanup.completed" if cleanup_verified else "representation.cleanup.failed",
                aggregate_type="spatial_conversion",
                aggregate_id=conversion.conversion_id,
                tenant_id=conversion.tenant_id,
                project_id=conversion.project_id,
                actor_id=None,
                workload_identity=claims["workload_identity"],
                payload={
                    "conversion_id": conversion.conversion_id,
                    "operation_id": conversion.operation_id,
                    "cleanup_receipt_hash": cleanup_receipt_hash,
                    "cleanup_verified": bool(cleanup_verified),
                    "failure_hash": failure_hash,
                },
            ))
            self.audit.append(
                tenant_id=conversion.tenant_id,
                project_id=conversion.project_id,
                actor_id=claims["workload_identity"],
                action="hybrid_conversion:fail",
                resource_type="spatial_conversion",
                resource_id=conversion.conversion_id,
                outcome="allowed" if cleanup_verified else "quarantined",
                details={
                    "error_code": error_code,
                    "retryable": bool(retryable and cleanup_verified),
                    "failure_hash": failure_hash,
                    "cleanup_verified": bool(cleanup_verified),
                    "preserved_binding_count": len(preserved_bindings),
                },
                session=session,
            )
        return {
            "conversion_id": claims["conversion_id"],
            "operation_id": claims["operation_id"],
            "state": state,
            "failure_hash": failure_hash,
            "cleanup_receipt_hash": cleanup_receipt_hash,
            "cleanup_verified": bool(cleanup_verified),
            "preserved_binding_ids": preserved_bindings,
            "idempotent_replay": False,
        }

    def record_progress(self, worker_token: str, progress: dict[str, Any] | ProviderProgressContract) -> dict[str, Any]:
        claims = self._verify_worker_token(worker_token)
        try:
            contract = progress if isinstance(progress, ProviderProgressContract) else ProviderProgressContract.model_validate(progress)
        except PydanticValidationError as exc:
            raise ValidationError("HYB_PROGRESS_INVALID", "provider progress violates the canonical contract", _safe_errors(exc)) from exc
        if contract.conversion_id != claims["conversion_id"]:
            raise AuthenticationError("HYB_WORKER_SCOPE_MISMATCH", "worker token does not authorize this conversion")

        with self.database.session() as session:
            row = self._scoped_conversion(session, contract.conversion_id, claims["tenant_id"], claims["project_id"])
            if row.state not in {"admitted", "running"}:
                raise ConflictError("HYB_PROGRESS_STATE_INVALID", "conversion cannot accept progress in its current state", {"state": row.state})
            prior = session.scalar(select(ProviderProgressRow).where(
                ProviderProgressRow.conversion_id == row.conversion_id
            ).order_by(ProviderProgressRow.sequence.desc()).limit(1))
            if prior and contract.sequence == prior.sequence:
                prior_payload = {
                    "conversion_id": prior.conversion_id,
                    "sequence": prior.sequence,
                    "stage": prior.stage,
                    "completed_work_units": prior.completed_work_units,
                    "total_work_units": prior.total_work_units,
                    "work_unit_name": prior.work_unit_name,
                    "resource_use": prior.resource_use_json,
                    "warnings": prior.warnings_json,
                    "last_durable_checkpoint_hash": prior.checkpoint_hash,
                    "estimated_output_bytes": prior.estimated_output_bytes,
                }
                if prior_payload == contract.model_dump(mode="json"):
                    return contract.model_dump(mode="json")
                raise ConflictError("HYB_PROGRESS_SEQUENCE_CONFLICT", "provider progress sequence is already bound to different evidence")
            if prior and contract.sequence < prior.sequence:
                raise ConflictError("HYB_PROGRESS_SEQUENCE_NOT_MONOTONIC", "provider progress sequence must advance monotonically")
            if prior and contract.completed_work_units < prior.completed_work_units and contract.work_unit_name == prior.work_unit_name:
                raise ConflictError("HYB_PROGRESS_REGRESSION", "provider objective progress cannot move backwards")
            provider = session.get(ProviderManifestRow, row.provider_id)
            recovery_units = set((provider.recovery_contract_json or {}).get("objective_progress_units", [])) if provider else set()
            if recovery_units and contract.work_unit_name not in recovery_units:
                raise ValidationError("HYB_PROGRESS_UNIT_UNDECLARED", "provider progress unit is not declared by its recovery contract")

        self._ensure_operation_started(claims)
        normalized = 0.0 if contract.total_work_units is None else min(1.0, contract.completed_work_units / contract.total_work_units)
        checkpoint = {
            "sequence": contract.sequence,
            "stage": contract.stage,
            "safe_to_resume": bool(contract.last_durable_checkpoint_hash),
            "checkpoint_hash": contract.last_durable_checkpoint_hash,
            "work_unit_name": contract.work_unit_name,
            "completed_work_units": contract.completed_work_units,
            "total_work_units": contract.total_work_units,
        }
        self.operations.checkpoint(
            claims["operation_id"],
            worker_id=claims["workload_identity"],
            progress=normalized,
            checkpoint=checkpoint,
        )

        with self.database.session() as session:
            row = self._scoped_conversion(session, contract.conversion_id, claims["tenant_id"], claims["project_id"])
            prior = session.scalar(select(ProviderProgressRow).where(
                ProviderProgressRow.conversion_id == row.conversion_id
            ).order_by(ProviderProgressRow.sequence.desc()).limit(1))
            if prior and contract.sequence <= prior.sequence:
                prior_payload = {
                    "conversion_id": prior.conversion_id,
                    "sequence": prior.sequence,
                    "stage": prior.stage,
                    "completed_work_units": prior.completed_work_units,
                    "total_work_units": prior.total_work_units,
                    "work_unit_name": prior.work_unit_name,
                    "resource_use": prior.resource_use_json,
                    "warnings": prior.warnings_json,
                    "last_durable_checkpoint_hash": prior.checkpoint_hash,
                    "estimated_output_bytes": prior.estimated_output_bytes,
                }
                if prior.sequence == contract.sequence and prior_payload == contract.model_dump(mode="json"):
                    return contract.model_dump(mode="json")
                raise ConflictError("HYB_PROGRESS_SEQUENCE_NOT_MONOTONIC", "provider progress sequence must advance monotonically")
            session.add(ProviderProgressRow(
                progress_id=new_uuid(),
                conversion_id=row.conversion_id,
                sequence=contract.sequence,
                stage=contract.stage,
                completed_work_units=contract.completed_work_units,
                total_work_units=contract.total_work_units,
                work_unit_name=contract.work_unit_name,
                resource_use_json=contract.resource_use,
                warnings_json=contract.warnings,
                checkpoint_hash=contract.last_durable_checkpoint_hash,
                estimated_output_bytes=contract.estimated_output_bytes,
            ))
            row.state = "running"
            row.updated_at = db_now()
            session.add(self._event(
                session,
                event_type="representation.provider.progressed",
                aggregate_type="spatial_conversion",
                aggregate_id=row.conversion_id,
                tenant_id=row.tenant_id,
                project_id=row.project_id,
                actor_id=None,
                workload_identity=claims["workload_identity"],
                payload={
                    "conversion_id": row.conversion_id,
                    "sequence": contract.sequence,
                    "stage": contract.stage,
                    "completed_work_units": contract.completed_work_units,
                    "total_work_units": contract.total_work_units,
                    "work_unit_name": contract.work_unit_name,
                    "checkpoint_hash": contract.last_durable_checkpoint_hash,
                },
            ))
        return contract.model_dump(mode="json")

    def complete_candidate(
        self,
        worker_token: str,
        *,
        output_asset_id: str,
        output_asset_sha256: str,
        output_role: str,
        kind: RepresentationKind,
        coordinate_frame_id: str,
        source_class: SourceClass,
        authority_class: AuthorityClass,
        lossy: bool,
        intended_uses: list[str],
        prohibited_uses: list[str],
        quality: dict[str, Any],
        support_map: dict[str, Any],
        worker_receipt_hash: str,
        candidate_core_hash: str,
        format_metadata: dict[str, Any] | None = None,
        limitations: list[str] | None = None,
        information_losses: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        claims = self._verify_worker_token(worker_token)
        for name, digest in (("output_asset_sha256", output_asset_sha256), ("worker_receipt_hash", worker_receipt_hash), ("candidate_core_hash", candidate_core_hash)):
            _require_digest(digest, name)
        with self.database.session() as session:
            conversion = self._scoped_conversion(session, claims["conversion_id"], claims["tenant_id"], claims["project_id"])
            if conversion.state not in {"admitted", "running", "returned_pending_validation"}:
                if conversion.candidate_representation_id:
                    return {"conversion_id": conversion.conversion_id, "representation_id": conversion.candidate_representation_id, "state": conversion.state, "idempotent_replay": True}
                raise ConflictError("HYB_COMPLETION_STATE_INVALID", "conversion cannot accept a candidate in its current state", {"state": conversion.state})
            if output_role not in set(conversion.output_roles_json):
                raise ValidationError("HYB_OUTPUT_ROLE_UNREQUESTED", "provider output role was not requested")
            _require_role_kind_compatibility(output_role, kind)
            if not set(intended_uses).issubset(set(conversion.intended_uses_json)):
                raise ValidationError("HYB_INTENDED_USE_UNREQUESTED", "candidate declares an intended use not admitted for the conversion")
            asset = session.get(AssetRefRow, output_asset_id)
            if not asset or asset.tenant_id != conversion.tenant_id or asset.project_id != conversion.project_id or asset.tombstoned_at is not None:
                raise NotFoundError("asset", output_asset_id)
            normalized_digest = _normalize_digest(output_asset_sha256)
            if asset.sha256 != normalized_digest:
                raise ValidationError("HYB_OUTPUT_HASH_MISMATCH", "quarantine output asset hash does not match the provider claim")
            output_object = session.get(AssetRow, asset.sha256)
            if output_object is None:
                raise ValidationError("HYB_OUTPUT_OBJECT_MISSING", "quarantine output object metadata is missing")
            maximum_output_bytes = int((claims.get("output_staging_scope") or {}).get("maximum_bytes", 0))
            if maximum_output_bytes < 1 or output_object.byte_count > maximum_output_bytes:
                raise AuthorizationError(
                    "HYB_OUTPUT_BYTE_ENVELOPE_EXCEEDED",
                    "provider output exceeds the exact admitted write-only quarantine envelope",
                    {"maximum_bytes": maximum_output_bytes, "actual_bytes": output_object.byte_count},
                )
            frame = session.get(CoordinateFrameRow, coordinate_frame_id)
            if not frame or frame.tenant_id != conversion.tenant_id or frame.project_id != conversion.project_id or frame.deprecated_at is not None:
                raise NotFoundError("coordinate_frame", coordinate_frame_id)
            provider = session.get(ProviderManifestRow, conversion.provider_id)
            if not provider or provider.manifest_hash != conversion.provider_manifest_hash:
                raise AuthorizationError("HYB_PROVIDER_SNAPSHOT_STALE", "provider descriptor changed before candidate completion")
            existing_rep = session.scalar(select(RepresentationAssetRow).where(RepresentationAssetRow.operation_id == conversion.operation_id))
            if existing_rep:
                if existing_rep.asset_id != output_asset_id or existing_rep.manifest_hash is None:
                    raise ConflictError("HYB_CANDIDATE_IDEMPOTENCY_CONFLICT", "conversion already produced a different candidate")
                return {"conversion_id": conversion.conversion_id, "representation_id": existing_rep.representation_id, "state": existing_rep.state, "idempotent_replay": True}
            privacy = {
                "allowed_audiences": list(conversion.policy_context_json.get("allowed_audiences", [conversion.policy_context_json.get("audience", "project")])),
                "allowed_purposes": [conversion.purpose],
                "consent_grant_ids": list(conversion.policy_context_json.get("consent_grant_ids", [])),
                "required_scopes": list(conversion.policy_context_json.get("required_consent_scopes", [])),
                "purpose": conversion.purpose,
                "policy_snapshot_hash": canonical_sha256(conversion.policy_context_json),
            }
            input_dependency_ids = [
                item["asset_id"] for item in conversion.source_assets_json + conversion.reference_assets_json
            ]
            provenance = {
                "source_ids": [item["asset_id"] for item in conversion.source_assets_json],
                "reference_ids": [item["asset_id"] for item in conversion.reference_assets_json],
                "conversion_id": conversion.conversion_id,
                "operation_id": conversion.operation_id,
                "request_hash": conversion.request_hash,
                "admission_decision_hash": conversion.admission_decision_hash,
                "provider_id": conversion.provider_id,
                "provider_version": conversion.provider_version,
                "provider_manifest_hash": conversion.provider_manifest_hash,
                "promotion_id": conversion.promotion_id,
                "worker_receipt_hash": worker_receipt_hash,
                "candidate_core_hash": candidate_core_hash,
                "output_role": output_role,
            }

        representation_id = self.representations.create_candidate(
            tenant_id=claims["tenant_id"],
            project_id=claims["project_id"],
            scene_id=claims["scene_id"],
            asset_id=output_asset_id,
            kind=kind,
            provider_id=claims["provider_id"],
            coordinate_frame_id=coordinate_frame_id,
            source_class=source_class,
            authority_class=authority_class,
            lossy=lossy,
            intended_uses=sorted(set(intended_uses)),
            prohibited_uses=sorted(set(prohibited_uses + ["automatic_publication"])),
            quality=quality,
            provenance=provenance,
            support_map=support_map,
            actor_id=claims["workload_identity"],
            operation_id=claims["operation_id"],
            format_metadata=format_metadata or {},
            derivation_policy={"publication": "independent_validation_required", "conversion_id": claims["conversion_id"]},
            limitations=limitations or [],
            information_losses=information_losses or [],
            privacy_inheritance=privacy,
            dependencies=input_dependency_ids,
            metadata={**(metadata or {}), "output_role": output_role, "truth_label": (metadata or {}).get("truth_label", _truth_label(kind))},
        )
        self.representations.attach_worker_receipt(
            tenant_id=claims["tenant_id"],
            project_id=claims["project_id"],
            operation_id=claims["operation_id"],
            worker_receipt_hash=worker_receipt_hash,
            candidate_core_hash=candidate_core_hash,
            actor_id=claims["workload_identity"],
        )
        self._ensure_operation_started(claims)
        self.operations.complete(
            claims["operation_id"],
            worker_id=claims["workload_identity"],
            output={
                "conversion_id": claims["conversion_id"],
                "representation_id": representation_id,
                "asset_id": output_asset_id,
                "asset_sha256": _normalize_digest(output_asset_sha256),
                "worker_receipt_hash": worker_receipt_hash,
                "candidate_core_hash": candidate_core_hash,
            },
        )
        with self.database.session() as session:
            conversion = self._scoped_conversion(session, claims["conversion_id"], claims["tenant_id"], claims["project_id"])
            conversion.candidate_representation_id = representation_id
            conversion.state = "quarantined"
            conversion.updated_at = db_now()
            rep = session.get(RepresentationAssetRow, representation_id)
            session.add(self._event(
                session,
                event_type="representation.output.quarantined",
                aggregate_type="representation",
                aggregate_id=representation_id,
                tenant_id=conversion.tenant_id,
                project_id=conversion.project_id,
                actor_id=None,
                workload_identity=claims["workload_identity"],
                payload={
                    "conversion_id": conversion.conversion_id,
                    "representation_id": representation_id,
                    "asset_id": output_asset_id,
                    "asset_sha256": _normalize_digest(output_asset_sha256),
                    "manifest_hash": rep.manifest_hash,
                    "output_role": output_role,
                    "state": "quarantined",
                },
            ))
        return {"conversion_id": claims["conversion_id"], "representation_id": representation_id, "state": "quarantined", "idempotent_replay": False}

    def validate_candidate(
        self,
        conversion_id: str,
        *,
        tenant_id: str,
        project_id: str,
        intended_use: str,
        profile_id: str,
        profile_version: str,
        validator_id: str,
        validator_manifest_hash: str,
        metrics: dict[str, Any],
        thresholds: dict[str, Any],
        coverage: dict[str, Any],
        topology: dict[str, Any],
        coordinate_validation: dict[str, Any],
        behavior_validation: dict[str, Any],
        limitations: list[str] | None = None,
    ) -> dict[str, Any]:
        _require_digest(validator_manifest_hash, "validator_manifest_hash")
        with self.database.session() as session:
            conversion = self._scoped_conversion(session, conversion_id, tenant_id, project_id)
            if not conversion.candidate_representation_id:
                raise ConflictError("HYB_VALIDATION_CANDIDATE_MISSING", "conversion has not produced a quarantined candidate")
            rep = session.get(RepresentationAssetRow, conversion.candidate_representation_id)
            if not rep or rep.tenant_id != tenant_id or rep.project_id != project_id:
                raise NotFoundError("representation", conversion.candidate_representation_id)
            if rep.state not in {"quarantined", "quality_failed", "approved"}:
                raise ConflictError("HYB_VALIDATION_STATE_INVALID", "candidate cannot be validated in its current state", {"state": rep.state})
            if intended_use not in set(conversion.intended_uses_json) or intended_use not in set(rep.intended_uses_json):
                raise ValidationError("HYB_VALIDATION_USE_UNREQUESTED", "validation cannot approve an unrequested intended use")
            if validator_id.startswith("sip-worker:") or validator_id.startswith("sip-provider:") or validator_id in {conversion.provider_id, conversion.requested_by}:
                raise AuthorizationError("HYB_VALIDATOR_NOT_INDEPENDENT", "provider, worker, or requester cannot independently validate provider output")
            if intended_use in _INTERACTION_USES:
                profile = session.get(InteractionProfileRow, profile_id)
                if not profile or profile.version != profile_version:
                    raise NotFoundError("interaction_profile", profile_id)
                if not self._interaction_profile_integrity_valid(profile):
                    raise AuthorizationError(
                        "HYB_INTERACTION_PROFILE_INTEGRITY_INVALID",
                        "interaction profile signature or retained validation evidence is invalid",
                    )
                if intended_use not in set(profile.intended_uses_json) or profile.profile_type != intended_use:
                    raise ValidationError("HYB_PROFILE_USE_MISMATCH", "interaction profile does not cover the intended use")
            candidate_snapshot_hash = rep.manifest_hash or canonical_sha256({"representation_id": rep.representation_id, "asset_id": rep.asset_id})
            policy_snapshot_hash = conversion.admission_decision_hash
            passed = _thresholds_pass(metrics, thresholds) and all(
                bool(section.get("passed")) for section in (coverage, topology, coordinate_validation, behavior_validation)
            )
            validation_evidence = {
                "conversion_id": conversion_id,
                "representation_id": rep.representation_id,
                "intended_use": intended_use,
                "profile_id": profile_id,
                "profile_version": profile_version,
                "validator_id": validator_id,
                "validator_manifest_hash": validator_manifest_hash,
                "metrics": metrics,
                "thresholds": thresholds,
                "coverage": coverage,
                "topology": topology,
                "coordinate_validation": coordinate_validation,
                "behavior_validation": behavior_validation,
                "limitations": sorted(set(limitations or [])),
                "passed": passed,
                "candidate_snapshot_hash": candidate_snapshot_hash,
                "policy_snapshot_hash": policy_snapshot_hash,
            }
            validation_hash = canonical_sha256(validation_evidence)
            existing = session.scalar(select(IntendedUseValidationRow).where(
                IntendedUseValidationRow.representation_id == rep.representation_id,
                IntendedUseValidationRow.intended_use == intended_use,
                IntendedUseValidationRow.profile_id == profile_id,
                IntendedUseValidationRow.profile_version == profile_version,
            ))
            if existing:
                if not hmac.compare_digest(existing.validation_hash, validation_hash):
                    raise ConflictError("HYB_VALIDATION_IMMUTABLE_CONFLICT", "validation identity is already bound to different evidence")
                return self._validation_dict(existing)
            body = {
                "validation_id": new_uuid(),
                **validation_evidence,
                "validation_hash": validation_hash,
            }
            contract = IntendedUseValidationContract.model_validate(body)
            row = IntendedUseValidationRow(
                validation_id=contract.validation_id,
                tenant_id=tenant_id,
                project_id=project_id,
                conversion_id=conversion_id,
                representation_id=rep.representation_id,
                intended_use=contract.intended_use,
                profile_id=contract.profile_id,
                profile_version=contract.profile_version,
                validator_id=contract.validator_id,
                validator_manifest_hash=contract.validator_manifest_hash,
                metrics_json=contract.metrics,
                thresholds_json=contract.thresholds,
                coverage_json=contract.coverage,
                topology_json=contract.topology,
                coordinate_validation_json=contract.coordinate_validation,
                behavior_validation_json=contract.behavior_validation,
                limitations_json=contract.limitations,
                passed=contract.passed,
                candidate_snapshot_hash=contract.candidate_snapshot_hash,
                policy_snapshot_hash=contract.policy_snapshot_hash,
                validation_hash=contract.validation_hash,
            )
            session.add(row)
            session.flush()
            passed_rows = list(session.scalars(select(IntendedUseValidationRow).where(
                IntendedUseValidationRow.representation_id == rep.representation_id,
                IntendedUseValidationRow.passed.is_(True),
                IntendedUseValidationRow.candidate_snapshot_hash == candidate_snapshot_hash,
                IntendedUseValidationRow.policy_snapshot_hash == policy_snapshot_hash,
            )))
            approved_uses = sorted({item.intended_use for item in passed_rows})
            session.add(self._event(
                session,
                event_type="representation.validation.completed",
                aggregate_type="representation",
                aggregate_id=rep.representation_id,
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=validator_id,
                payload={
                    "conversion_id": conversion_id,
                    "representation_id": rep.representation_id,
                    "validation_id": row.validation_id,
                    "intended_use": intended_use,
                    "profile_id": profile_id,
                    "passed": passed,
                    "validation_hash": validation_hash,
                },
            ))
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=validator_id,
                action="hybrid_candidate:validate",
                resource_type="intended_use_validation",
                resource_id=row.validation_id,
                outcome="allowed",
                details={"representation_id": rep.representation_id, "intended_use": intended_use, "passed": passed, "validation_hash": validation_hash},
                session=session,
            )
            representation_id = rep.representation_id
        self.representations.review_quality(
            representation_id,
            reviewer_id=validator_id,
            approved_uses=approved_uses if passed else [],
            metrics={
                "validation_hash": validation_hash,
                "profile_id": profile_id,
                "intended_use": intended_use,
                "passed": passed,
                "quantitative_metrics": metrics,
            },
            passed=bool(approved_uses),
        )
        with self.database.session() as session:
            conversion = self._scoped_conversion(session, conversion_id, tenant_id, project_id)
            conversion.state = "validated" if approved_uses else "quality_failed"
            conversion.updated_at = db_now()
            row = session.get(IntendedUseValidationRow, contract.validation_id)
            return self._validation_dict(row)

    def cancel_conversion(
        self,
        conversion_id: str,
        *,
        tenant_id: str,
        project_id: str,
        actor_id: str,
    ) -> dict[str, Any]:
        """Request durable cancellation and invalidate further worker use immediately."""
        with self.database.session() as session:
            row = self._scoped_conversion(session, conversion_id, tenant_id, project_id)
            operation_id = row.operation_id
            if row.state in {"cancelled", "rejected", "published"}:
                return {**self._conversion_dict(row), "idempotent_replay": True}
            if row.state in {"quarantined", "validated", "quality_failed"}:
                raise ConflictError(
                    "HYB_CANCELLATION_OUTPUT_EXISTS",
                    "conversion output already exists; use representation invalidation instead of cancelling execution",
                    {"state": row.state},
                )
        operation = self.operations.request_cancel(operation_id, actor_id=actor_id)
        with self.database.session() as session:
            row = self._scoped_conversion(session, conversion_id, tenant_id, project_id)
            row.state = "cancel_requested" if operation["state"] != "cancelled" else "cancelled"
            row.updated_at = db_now()
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="hybrid_conversion:cancel",
                resource_type="spatial_conversion",
                resource_id=conversion_id,
                outcome="allowed",
                details={"operation_id": operation_id, "operation_state": operation["state"]},
                session=session,
            )
            return {**self._conversion_dict(row), "idempotent_replay": False}

    def create_manual_export(
        self,
        conversion_id: str,
        *,
        tenant_id: str,
        project_id: str,
        approved_derivative_asset_ids: list[str],
        actor_id: str,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            conversion = self._scoped_conversion(session, conversion_id, tenant_id, project_id)
            provider = session.get(ProviderManifestRow, conversion.provider_id)
            if not provider or provider.provider_class != "manual_external" or "manual_external" not in set(provider.execution_modes_json or []):
                raise AuthorizationError("HYB_MANUAL_PROVIDER_REQUIRED", "manual export is only available for approved manual-external providers")
            classification = str(conversion.admission_decision_json.get("classification", "internal"))
            if classification in _HARD_EXTERNAL_DENY:
                raise AuthorizationError("HYB_MANUAL_EXPORT_SENSITIVE_DENIED", "critical infrastructure, biometric, and minor data cannot enter a manual external path")
            if not conversion.policy_context_json.get("allow_external_transfer", False):
                raise AuthorizationError("HYB_EXTERNAL_TRANSFER_NOT_APPROVED", "policy does not explicitly approve external transfer")
            allowed_ids = {item["asset_id"] for item in conversion.source_assets_json + conversion.reference_assets_json}
            approved = sorted(set(approved_derivative_asset_ids))
            if not approved or not set(approved).issubset(allowed_ids):
                raise ValidationError("HYB_MANUAL_EXPORT_SCOPE_INVALID", "manual export must contain only explicitly approved request assets")
            outbound_assets: list[dict[str, Any]] = []
            for asset_id in approved:
                asset = session.get(AssetRefRow, asset_id)
                if not asset or asset.tenant_id != tenant_id or asset.project_id != project_id or asset.tombstoned_at is not None:
                    raise NotFoundError("asset", asset_id)
                if asset.legal_hold and not conversion.policy_context_json.get("legal_hold_external_transfer_approved", False):
                    raise AuthorizationError("HYB_LEGAL_HOLD_TRANSFER_DENIED", "legal-held assets require explicit transfer approval")
                source_record = next(item for item in conversion.source_assets_json + conversion.reference_assets_json if item["asset_id"] == asset_id)
                if asset.source_class not in {
                    SourceClass.GENERATED.value,
                    SourceClass.INFERRED.value,
                    SourceClass.DESIGN.value,
                    SourceClass.PROPOSED.value,
                }:
                    raise AuthorizationError(
                        "HYB_MANUAL_EXPORT_RAW_SOURCE_DENIED",
                        "manual external export is limited to explicitly approved non-authoritative derivatives",
                        {"asset_id": asset_id, "source_class": asset.source_class},
                    )
                if asset.authority_class in {
                    AuthorityClass.EVIDENCE.value,
                    AuthorityClass.METRIC.value,
                    AuthorityClass.FIELD_VERIFIED.value,
                }:
                    raise AuthorizationError(
                        "HYB_MANUAL_EXPORT_AUTHORITATIVE_SOURCE_DENIED",
                        "authoritative evidence and metric assets cannot enter the manual external path",
                        {"asset_id": asset_id, "authority_class": asset.authority_class},
                    )
                outbound_assets.append({"asset_id": asset_id, "sha256": asset.sha256, "role": source_record["role"]})
            transfer_id = new_uuid()
            code = secrets.token_urlsafe(24)
            outbound = {
                "schema": "sip.manual-provider-export/1.1",
                "transfer_id": transfer_id,
                "conversion_id": conversion_id,
                "provider_id": conversion.provider_id,
                "assets": outbound_assets,
                "purpose": conversion.purpose,
                "intended_uses": conversion.intended_uses_json,
                "expires_at": conversion.policy_context_json.get("manual_export_expires_at"),
            }
            outbound_hash = canonical_sha256(outbound)
            policy_hash = canonical_sha256(conversion.policy_context_json)
            session.add(ManualProviderTransferRow(
                transfer_id=transfer_id,
                tenant_id=tenant_id,
                project_id=project_id,
                conversion_id=conversion_id,
                provider_id=conversion.provider_id,
                outbound_manifest_json=outbound,
                outbound_manifest_hash=outbound_hash,
                policy_decision_hash=policy_hash,
                one_time_code_hash=hashlib.sha256(code.encode("utf-8")).hexdigest(),
                state="exported",
                exported_by=actor_id,
            ))
            conversion.state = "manual_exported"
            conversion.updated_at = db_now()
            session.add(self._event(
                session,
                event_type="representation.manual_exported",
                aggregate_type="manual_provider_transfer",
                aggregate_id=transfer_id,
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                payload={"transfer_id": transfer_id, "conversion_id": conversion_id, "outbound_manifest_hash": outbound_hash, "asset_count": len(outbound_assets)},
            ))
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="hybrid_manual:export",
                resource_type="manual_provider_transfer",
                resource_id=transfer_id,
                outcome="allowed",
                details={"outbound_manifest_hash": outbound_hash, "asset_count": len(outbound_assets)},
                session=session,
            )
            return {"transfer_id": transfer_id, "outbound_manifest": outbound, "outbound_manifest_hash": outbound_hash, "one_time_return_code": code, "state": "exported"}

    def record_manual_return(
        self,
        transfer_id: str,
        *,
        tenant_id: str,
        project_id: str,
        one_time_return_code: str,
        receipt: dict[str, Any] | ManualExternalReceiptContract,
        returned_outputs: list[dict[str, str]],
        actor_id: str,
    ) -> dict[str, Any]:
        raw_receipt = receipt.model_dump(mode="json") if isinstance(receipt, ManualExternalReceiptContract) else dict(receipt)
        try:
            contract = ManualExternalReceiptContract.model_validate(raw_receipt)
        except PydanticValidationError as exc:
            raise ValidationError("HYB_MANUAL_RECEIPT_INVALID", "manual return receipt violates the canonical contract", _safe_errors(exc)) from exc
        receipt_body = contract.model_dump(mode="json")
        provided_receipt_hash = receipt_body.pop("receipt_hash")
        computed_receipt_hash = canonical_sha256(receipt_body)
        if not hmac.compare_digest(provided_receipt_hash, computed_receipt_hash):
            raise ValidationError("HYB_MANUAL_RECEIPT_HASH_MISMATCH", "manual return receipt hash does not match canonical content")
        retained_receipt = {**receipt_body, "receipt_hash": computed_receipt_hash}
        with self.database.session() as session:
            row = session.get(ManualProviderTransferRow, transfer_id)
            if not row or row.tenant_id != tenant_id or row.project_id != project_id:
                raise NotFoundError("manual_provider_transfer", transfer_id)
            if row.state != "exported":
                if row.state == "returned_pending_validation" and row.receipt_hash == computed_receipt_hash:
                    return {"transfer_id": transfer_id, "conversion_id": row.conversion_id, "state": row.state, "idempotent_replay": True}
                raise ConflictError("HYB_MANUAL_RETURN_STATE_INVALID", "manual transfer cannot accept a return in its current state")
            if not hmac.compare_digest(row.one_time_code_hash, hashlib.sha256(one_time_return_code.encode("utf-8")).hexdigest()):
                raise AuthenticationError("HYB_MANUAL_RETURN_CODE_INVALID", "manual return code is invalid")
            if contract.transfer_id != transfer_id or contract.conversion_id != row.conversion_id:
                raise ValidationError("HYB_MANUAL_RECEIPT_SCOPE_MISMATCH", "manual receipt does not match the transfer")
            expected_inputs = sorted(item["sha256"] for item in row.outbound_manifest_json["assets"])
            actual_inputs = sorted(_normalize_digest(item) for item in contract.input_hashes)
            if actual_inputs != expected_inputs:
                raise ValidationError("HYB_MANUAL_INPUT_HASH_MISMATCH", "manual provider receipt did not consume the exact authorized inputs")
            for evidence_asset_id in sorted(set(contract.evidence_asset_ids)):
                evidence_asset = session.get(AssetRefRow, evidence_asset_id)
                if (
                    evidence_asset is None
                    or evidence_asset.tenant_id != tenant_id
                    or evidence_asset.project_id != project_id
                    or evidence_asset.tombstoned_at is not None
                ):
                    raise NotFoundError("receipt_evidence_asset", evidence_asset_id)
            conversion = session.get(SpatialConversionRow, row.conversion_id)
            if conversion is None:
                raise NotFoundError("spatial_conversion", row.conversion_id)
            output_records: list[dict[str, str]] = []
            claimed_output_hashes = sorted(_normalize_digest(item) for item in contract.output_hashes)
            for output in returned_outputs:
                asset_id = str(output.get("asset_id", ""))
                digest = _normalize_digest(str(output.get("sha256", "")))
                asset = session.get(AssetRefRow, asset_id)
                if not asset or asset.tenant_id != tenant_id or asset.project_id != project_id or asset.tombstoned_at is not None:
                    raise NotFoundError("asset", asset_id)
                if asset.sha256 != digest:
                    raise ValidationError("HYB_MANUAL_OUTPUT_HASH_MISMATCH", "returned output asset hash does not match the receipt")
                role = str(output.get("role", "")).strip()
                if role not in set(conversion.output_roles_json):
                    raise ValidationError("HYB_MANUAL_OUTPUT_ROLE_UNREQUESTED", "manual provider returned an output role not admitted by the conversion")
                output_records.append({"asset_id": asset_id, "sha256": digest, "role": role})
            if sorted(item["sha256"] for item in output_records) != claimed_output_hashes:
                raise ValidationError("HYB_MANUAL_OUTPUT_SET_MISMATCH", "returned outputs do not match the provider receipt")
            receipt_hash = computed_receipt_hash
            row.receipt_json = retained_receipt
            row.receipt_hash = receipt_hash
            row.returned_outputs_json = output_records
            row.state = "returned_pending_validation"
            row.returned_by = actor_id
            row.returned_at = db_now()
            conversion.state = "returned_pending_validation"
            conversion.updated_at = db_now()
            session.add(self._event(
                session,
                event_type="representation.manual_returned",
                aggregate_type="manual_provider_transfer",
                aggregate_id=transfer_id,
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                payload={"transfer_id": transfer_id, "conversion_id": row.conversion_id, "receipt_hash": receipt_hash, "output_count": len(output_records), "state": row.state},
            ))
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="hybrid_manual:return",
                resource_type="manual_provider_transfer",
                resource_id=transfer_id,
                outcome="allowed",
                details={"receipt_hash": receipt_hash, "output_count": len(output_records), "state": row.state},
                session=session,
            )
            return {"transfer_id": transfer_id, "conversion_id": row.conversion_id, "receipt_hash": receipt_hash, "returned_outputs": output_records, "state": row.state, "idempotent_replay": False}

    def create_view_manifest(
        self,
        *,
        principal: SignedPrincipal,
        project_id: str,
        scene_id: str,
        scene_revision_id: str,
        purpose: str,
        audience: str,
        device_profile: str,
        time_context: dict[str, Any],
        intended_uses: list[str],
        spatial_region_ids: list[str] | None = None,
        ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        if not 30 <= ttl_seconds <= 900:
            raise ValidationError("HYB_VIEW_TTL_INVALID", "hybrid view TTL must be between 30 and 900 seconds")
        self.policy.require(
            principal,
            action="scene:read",
            tenant_id=principal.tenant_id,
            project_id=project_id,
            purpose=purpose,
        )
        allowed_regions = set(spatial_region_ids or principal.attributes.get("spatial_region_ids", []))
        now = db_now()
        expires_at = now + timedelta(seconds=ttl_seconds)
        with self.database.session() as session:
            commit = session.get(SceneCommitRow, scene_revision_id)
            if not commit or commit.tenant_id != principal.tenant_id or commit.project_id != project_id or commit.scene_id != scene_id:
                raise NotFoundError("scene_commit", scene_revision_id)
            bindings = list(session.scalars(select(RepresentationBindingRow).where(
                RepresentationBindingRow.tenant_id == principal.tenant_id,
                RepresentationBindingRow.project_id == project_id,
                RepresentationBindingRow.scene_id == scene_id,
                RepresentationBindingRow.commit_id == scene_revision_id,
                RepresentationBindingRow.superseded_at.is_(None),
            )))
            authorized: dict[str, list[str]] = {}
            truth_labels: dict[str, list[dict[str, Any]]] = {}
            excluded: dict[str, int] = {}
            for binding in bindings:
                rep = session.get(RepresentationAssetRow, binding.representation_id)
                reason = self._binding_view_denial_reason(
                    session,
                    binding=binding,
                    rep=rep,
                    purpose=purpose,
                    audience=audience,
                    device_profile=device_profile,
                    intended_uses=set(intended_uses),
                    allowed_regions=allowed_regions,
                    now=now,
                )
                if reason:
                    excluded[reason] = excluded.get(reason, 0) + 1
                    continue
                authorized.setdefault(binding.role, []).append(binding.binding_id)
                truth_labels.setdefault(binding.role, []).append({
                    "binding_id": binding.binding_id,
                    "representation_kind": rep.kind,
                    "source_class": rep.source_class,
                    "authority_class": rep.authority_class,
                    "authority_ceiling": rep.authority_ceiling,
                    "disposable": rep.disposable,
                    "lossy": rep.lossy,
                    "generated": rep.source_class == SourceClass.GENERATED.value,
                })
            authorized = {role: sorted(ids) for role, ids in sorted(authorized.items())}
            if not authorized:
                raise AuthorizationError("HYB_VIEW_NO_AUTHORIZED_BINDINGS", "no published representation binding is authorized for this view")
            interaction_policy = {
                "proxy_picking_requires_metric_reresolution": True,
                "proxy_measurements_authoritative": False,
                "navigation_claim": "interaction_only_unless_profile_validated",
                "allowed_intended_uses": sorted(set(intended_uses)),
            }
            policy_snapshot = {
                "principal_id": principal.subject_id,
                "roles": sorted(principal.roles),
                "purposes": sorted(principal.purposes),
                "audience": audience,
                "spatial_region_ids": sorted(allowed_regions),
                "bindings": authorized,
                "scene_revision_id": scene_revision_id,
            }
            policy_snapshot_hash = canonical_sha256(policy_snapshot)
            view_id = new_uuid()
            body = {
                "view_id": view_id,
                "tenant_id": principal.tenant_id,
                "project_id": project_id,
                "scene_id": scene_id,
                "scene_revision_id": scene_revision_id,
                "principal_id": principal.subject_id,
                "purpose": purpose,
                "audience": audience,
                "device_profile": device_profile,
                "time_context": time_context,
                "bindings": authorized,
                "interaction_policy": interaction_policy,
                "truth_labels": truth_labels,
                "streaming": {"contract": "binding-id-resolution-only", "binding_count": sum(len(ids) for ids in authorized.values()), "storage_objects_disclosed": False},
                "policy_snapshot_hash": policy_snapshot_hash,
                "expires_at": expires_at.isoformat(),
            }
            manifest_hash = canonical_sha256(body)
            body["manifest_hash"] = manifest_hash
            manifest = HybridSceneViewManifestContract.model_validate(body)
            token = self.token_codec.encode(
                {
                    "type": "hybrid-scene-view",
                    "view_id": view_id,
                    "tenant_id": principal.tenant_id,
                    "project_id": project_id,
                    "scene_id": scene_id,
                    "scene_revision_id": scene_revision_id,
                    "principal_id": principal.subject_id,
                    "purpose": purpose,
                    "audience": audience,
                    "manifest_hash": manifest_hash,
                    "policy_snapshot_hash": policy_snapshot_hash,
                    "binding_ids": sorted(item for ids in authorized.values() for item in ids),
                },
                ttl_seconds=ttl_seconds,
            )
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            session.add(HybridSceneViewRow(
                view_id=view_id,
                tenant_id=principal.tenant_id,
                project_id=project_id,
                scene_id=scene_id,
                scene_revision_id=scene_revision_id,
                principal_id=principal.subject_id,
                purpose=purpose,
                audience=audience,
                device_profile=device_profile,
                time_context_json=time_context,
                bindings_json=authorized,
                excluded_summary_json=excluded,
                interaction_policy_json=interaction_policy,
                truth_labels_json=truth_labels,
                streaming_json=manifest.streaming,
                policy_snapshot_hash=policy_snapshot_hash,
                manifest_hash=manifest_hash,
                token_hash=token_hash,
                expires_at=expires_at,
            ))
            session.add(self._event(
                session,
                event_type="hybrid_scene_view.issued",
                aggregate_type="hybrid_scene_view",
                aggregate_id=view_id,
                tenant_id=principal.tenant_id,
                project_id=project_id,
                actor_id=principal.subject_id,
                payload={"view_id": view_id, "scene_id": scene_id, "scene_revision_id": scene_revision_id, "manifest_hash": manifest_hash, "binding_count": sum(len(ids) for ids in authorized.values()), "expires_at": expires_at.isoformat()},
            ))
            self.audit.append(
                tenant_id=principal.tenant_id,
                project_id=project_id,
                actor_id=principal.subject_id,
                action="hybrid_view:issue",
                resource_type="hybrid_scene_view",
                resource_id=view_id,
                outcome="allowed",
                details={"manifest_hash": manifest_hash, "binding_count": sum(len(ids) for ids in authorized.values()), "excluded_summary": excluded},
                session=session,
            )
            return {"manifest": manifest.model_dump(mode="json"), "token": token, "excluded_summary": excluded}

    def verify_view_token(self, token: str, *, principal_id: str, purpose: str) -> dict[str, Any]:
        claims = self.token_codec.decode(token)
        if claims.get("type") != "hybrid-scene-view":
            raise AuthenticationError("HYB_VIEW_TOKEN_TYPE_INVALID", "token is not a hybrid scene view capability")
        if claims.get("principal_id") != principal_id or claims.get("purpose") != purpose:
            raise AuthenticationError("HYB_VIEW_TOKEN_SCOPE_INVALID", "hybrid view token does not match principal and purpose")
        with self.database.session() as session:
            row = session.get(HybridSceneViewRow, claims["view_id"])
            if not row:
                raise AuthenticationError("HYB_VIEW_TOKEN_UNKNOWN", "hybrid view token references an unknown view")
            expected_scope = {
                "tenant_id": row.tenant_id,
                "project_id": row.project_id,
                "scene_id": row.scene_id,
                "scene_revision_id": row.scene_revision_id,
            }
            mismatches = sorted(key for key, value in expected_scope.items() if claims.get(key) != value)
            if mismatches:
                raise AuthenticationError("HYB_VIEW_TOKEN_BINDING_INVALID", "hybrid view token scope differs from durable authorization", {"claims": mismatches})
            now = db_now()
            if _aware(row.expires_at) <= now:
                raise AuthenticationError("HYB_VIEW_TOKEN_EXPIRED", "hybrid view token has expired")
            if not hmac.compare_digest(row.token_hash, hashlib.sha256(token.encode("utf-8")).hexdigest()):
                raise AuthenticationError("HYB_VIEW_TOKEN_HASH_INVALID", "hybrid view token does not match retained authorization evidence")
            if row.manifest_hash != claims.get("manifest_hash") or row.policy_snapshot_hash != claims.get("policy_snapshot_hash"):
                raise AuthenticationError("HYB_VIEW_TOKEN_SNAPSHOT_INVALID", "hybrid view token snapshot does not match durable authorization")
            project = session.get(ProjectRow, row.project_id)
            commit = session.get(SceneCommitRow, row.scene_revision_id)
            if (
                not project
                or project.tenant_id != row.tenant_id
                or not commit
                or commit.tenant_id != row.tenant_id
                or commit.project_id != row.project_id
                or commit.scene_id != row.scene_id
            ):
                raise AuthorizationError("HYB_VIEW_SCENE_INVALIDATED", "hybrid view scene scope no longer resolves")
            try:
                audience = Audience(row.audience)
            except ValueError as exc:
                raise AuthenticationError("HYB_VIEW_AUDIENCE_INVALID", "hybrid view contains an invalid audience") from exc
            principal = self.policy.principal_for(row.tenant_id, principal_id, project_id=row.project_id, audience=audience)
            self.policy.require(
                principal,
                action="scene:read",
                tenant_id=row.tenant_id,
                project_id=row.project_id,
                purpose=purpose,
                classification=project.classification,
            )
            binding_ids = list(claims.get("binding_ids", []))
            bindings = list(session.scalars(select(RepresentationBindingRow).where(
                RepresentationBindingRow.binding_id.in_(binding_ids),
                RepresentationBindingRow.tenant_id == row.tenant_id,
                RepresentationBindingRow.project_id == row.project_id,
                RepresentationBindingRow.scene_id == row.scene_id,
                RepresentationBindingRow.commit_id == row.scene_revision_id,
                RepresentationBindingRow.superseded_at.is_(None),
            )))
            if {item.binding_id for item in bindings} != set(binding_ids):
                raise AuthorizationError("HYB_VIEW_BINDING_INVALIDATED", "one or more authorized bindings were superseded or moved after view issuance")
            intended_uses = set(row.interaction_policy_json.get("allowed_intended_uses", []))
            allowed_regions = set(principal.attributes.get("spatial_region_ids", []))
            denial_reasons: dict[str, str] = {}
            for binding in bindings:
                rep = session.get(RepresentationAssetRow, binding.representation_id)
                reason = self._binding_view_denial_reason(
                    session,
                    binding=binding,
                    rep=rep,
                    purpose=purpose,
                    audience=row.audience,
                    device_profile=row.device_profile,
                    intended_uses=intended_uses,
                    allowed_regions=allowed_regions,
                    now=now,
                )
                if reason:
                    denial_reasons[binding.binding_id] = reason
            if denial_reasons:
                raise AuthorizationError(
                    "HYB_VIEW_POLICY_INVALIDATED",
                    "one or more authorized bindings no longer satisfy current policy or consent",
                    {"bindings": denial_reasons},
                )
            current_policy_snapshot = {
                "principal_id": principal.subject_id,
                "roles": sorted(principal.roles),
                "purposes": sorted(principal.purposes),
                "audience": row.audience,
                "spatial_region_ids": sorted(allowed_regions),
                "bindings": row.bindings_json,
                "scene_revision_id": row.scene_revision_id,
            }
            if not hmac.compare_digest(canonical_sha256(current_policy_snapshot), row.policy_snapshot_hash):
                raise AuthorizationError(
                    "HYB_VIEW_POLICY_SNAPSHOT_CHANGED",
                    "principal policy changed after view issuance; issue a new view manifest",
                )
            return claims

    def register_interaction_profile(
        self,
        *,
        profile_id: str,
        profile_type: str,
        version: str,
        actor: dict[str, Any],
        intended_uses: list[str],
        limits: dict[str, Any],
        behavior: dict[str, Any],
        validation: dict[str, Any],
        safety_claims: list[str],
        validator_id: str,
        validator_manifest_hash: str,
        validation_evidence_hash: str,
        validated_at: datetime,
        created_by: str,
        review_due_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        profile_id = profile_id.strip()
        version = version.strip()
        validator_id = validator_id.strip()
        if profile_type not in {"collision", "navigation", "occlusion", "spatial_audio", "picking"}:
            raise ValidationError(
                "HYB_INTERACTION_PROFILE_TYPE_INVALID",
                "interaction profile type is unsupported",
            )
        if not profile_id or not version or not validator_id:
            raise ValidationError(
                "HYB_INTERACTION_PROFILE_IDENTITY_INVALID",
                "profile, version, and validator identities must be non-empty",
            )
        if validator_id == created_by:
            raise AuthorizationError(
                "HYB_INTERACTION_PROFILE_VALIDATOR_NOT_INDEPENDENT",
                "interaction profile validation evidence must be produced by an identity independent of the registrar",
            )
        _require_digest(validator_manifest_hash, "validator_manifest_hash")
        _require_digest(validation_evidence_hash, "validation_evidence_hash")
        if not actor or not intended_uses or not limits or not behavior or not validation:
            raise ValidationError(
                "HYB_INTERACTION_PROFILE_INCOMPLETE",
                "interaction profiles require actor, use, limits, behavior, and validation contracts",
            )
        normalized_uses = sorted(set(item.strip() for item in intended_uses if item.strip()))
        if not normalized_uses or profile_type not in normalized_uses:
            raise ValidationError(
                "HYB_INTERACTION_PROFILE_USE_MISMATCH",
                "interaction profile type must be included in its intended-use contract",
            )
        if validation.get("passed") is not True or not str(validation.get("method", "")).strip():
            raise ValidationError(
                "HYB_INTERACTION_PROFILE_EVIDENCE_INCOMPLETE",
                "interaction profile requires a passing retained validation method and evidence record",
            )
        validated_at = _aware(validated_at)
        now = db_now()
        if validated_at > now + timedelta(minutes=5):
            raise ValidationError(
                "HYB_INTERACTION_PROFILE_VALIDATED_AT_INVALID",
                "interaction profile validation time cannot be in the future",
            )
        if validated_at < now - timedelta(days=365):
            raise AuthorizationError(
                "HYB_INTERACTION_PROFILE_VALIDATION_EXPIRED",
                "interaction profile validation evidence is older than the permitted review interval",
            )
        review_due = _aware(review_due_at) if review_due_at else validated_at + timedelta(days=365)
        if review_due <= now or review_due > validated_at + timedelta(days=365, minutes=5):
            raise ValidationError(
                "HYB_INTERACTION_PROFILE_REVIEW_WINDOW_INVALID",
                "interaction profile review must remain current and cannot exceed one year from validation",
            )
        expiry = _aware(expires_at) if expires_at else None
        if expiry is not None and (expiry <= now or expiry > review_due):
            raise ValidationError(
                "HYB_INTERACTION_PROFILE_EXPIRY_INVALID",
                "interaction profile expiry must be current and no later than its review deadline",
            )

        normalized_safety_claims = sorted(set(item.strip() for item in safety_claims if item.strip()))
        forbidden = sorted(set(normalized_safety_claims) & _FORBIDDEN_SAFETY_CLAIMS)
        validated_claims = set(validation.get("validated_safety_claims", []))
        if forbidden and not set(forbidden).issubset(validated_claims):
            raise AuthorizationError(
                "HYB_UNVALIDATED_SAFETY_CLAIM",
                "interaction profile cannot make an unvalidated safety or compliance claim",
                {"claims": forbidden},
            )
        validation_payload = {
            **validation,
            "validator_id": validator_id,
            "validator_manifest_hash": validator_manifest_hash,
            "validation_evidence_hash": validation_evidence_hash,
            "validated_at": validated_at.isoformat(),
        }
        signed_by = "sip-interaction-profile-registry"
        body = {
            "profile_id": profile_id,
            "profile_type": profile_type,
            "version": version,
            "actor": actor,
            "intended_uses": normalized_uses,
            "limits": limits,
            "behavior": behavior,
            "validation": validation_payload,
            "safety_claims": normalized_safety_claims,
            "review_due_at": review_due.isoformat(),
            "expires_at": expiry.isoformat() if expiry else None,
            "signed_by": signed_by,
        }
        digest = canonical_sha256(body)
        signature = hmac.new(self.audit.signing_key, digest.encode("ascii"), hashlib.sha256).hexdigest()
        with self.database.session() as session:
            existing = session.get(InteractionProfileRow, profile_id)
            if existing:
                if existing.manifest_hash != digest or not self._interaction_profile_integrity_valid(existing):
                    raise ConflictError(
                        "HYB_INTERACTION_PROFILE_IMMUTABLE",
                        "interaction profile identifier is already bound to different or invalid content",
                    )
                return {**body, "manifest_hash": digest, "manifest_signature": signature}
            session.add(InteractionProfileRow(
                profile_id=profile_id,
                profile_type=profile_type,
                version=version,
                actor_json=actor,
                intended_uses_json=body["intended_uses"],
                limits_json=limits,
                behavior_json=behavior,
                validation_json=validation_payload,
                safety_claims_json=body["safety_claims"],
                validator_manifest_hash=validator_manifest_hash,
                validation_evidence_hash=validation_evidence_hash,
                manifest_signature=signature,
                signed_by=signed_by,
                review_due_at=review_due,
                expires_at=expiry,
                manifest_hash=digest,
                created_by=created_by,
            ))
            self.audit.append(
                tenant_id="system",
                project_id=None,
                actor_id=created_by,
                action="interaction_profile:register",
                resource_type="interaction_profile",
                resource_id=profile_id,
                outcome="allowed",
                details={
                    "manifest_hash": digest,
                    "validator_id": validator_id,
                    "validator_manifest_hash": validator_manifest_hash,
                    "validation_evidence_hash": validation_evidence_hash,
                    "review_due_at": review_due.isoformat(),
                    "expires_at": expiry.isoformat() if expiry else None,
                },
                session=session,
            )
        return {**body, "manifest_hash": digest, "manifest_signature": signature}

    def _interaction_profile_integrity_valid(self, row: InteractionProfileRow) -> bool:
        validation = dict(row.validation_json or {})
        required = {
            "validator_id",
            "validator_manifest_hash",
            "validation_evidence_hash",
            "validated_at",
            "method",
            "passed",
        }
        if (
            row.signed_by != "sip-interaction-profile-registry"
            or not row.manifest_signature
            or not required.issubset(validation)
            or validation.get("passed") is not True
        ):
            return False
        try:
            _require_digest(str(row.validator_manifest_hash), "validator_manifest_hash")
            _require_digest(str(row.validation_evidence_hash), "validation_evidence_hash")
            if not hmac.compare_digest(
                str(validation["validator_manifest_hash"]), str(row.validator_manifest_hash)
            ):
                return False
            if not hmac.compare_digest(
                str(validation["validation_evidence_hash"]), str(row.validation_evidence_hash)
            ):
                return False
            validated_at = _aware(datetime.fromisoformat(str(validation["validated_at"])))
            review_due = _aware(row.review_due_at)
            expiry = _aware(row.expires_at) if row.expires_at else None
        except Exception:
            return False
        now = db_now()
        if (
            validated_at > now + timedelta(minutes=5)
            or validated_at < now - timedelta(days=365)
            or review_due <= now
            or review_due > validated_at + timedelta(days=365, minutes=5)
            or (expiry is not None and (expiry <= now or expiry > review_due))
        ):
            return False
        body = {
            "profile_id": row.profile_id,
            "profile_type": row.profile_type,
            "version": row.version,
            "actor": dict(row.actor_json or {}),
            "intended_uses": list(row.intended_uses_json or []),
            "limits": dict(row.limits_json or {}),
            "behavior": dict(row.behavior_json or {}),
            "validation": validation,
            "safety_claims": list(row.safety_claims_json or []),
            "review_due_at": review_due.isoformat(),
            "expires_at": expiry.isoformat() if expiry else None,
            "signed_by": row.signed_by,
        }
        digest = canonical_sha256(body)
        expected_signature = hmac.new(
            self.audit.signing_key, digest.encode("ascii"), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(digest, row.manifest_hash) and hmac.compare_digest(
            row.manifest_signature, expected_signature
        )

    def register_representation_family(
        self,
        *,
        tenant_id: str,
        project_id: str,
        scene_id: str,
        role: str,
        coordinate_frame_id: str,
        tile_scheme_id: str,
        lods: list[dict[str, Any]],
        seam_validation_report_id: str | None,
        fallback_representation_id: str | None,
        actor_id: str,
        family_id: str | None = None,
    ) -> dict[str, Any]:
        role = role.strip()
        tile_scheme_id = tile_scheme_id.strip()
        if not role or not tile_scheme_id:
            raise ValidationError(
                "HYB_REPRESENTATION_FAMILY_IDENTITY_INVALID",
                "representation family role and tile scheme must be non-empty",
            )
        if not lods:
            raise ValidationError("HYB_REPRESENTATION_FAMILY_EMPTY", "representation family requires at least one LOD")

        normalized_lods: list[dict[str, Any]] = []
        for item in lods:
            if not isinstance(item, dict):
                raise ValidationError("HYB_LOD_CONTRACT_INVALID", "every LOD entry must be an object")
            try:
                level = int(item["level"])
                representation_id = str(item["representation_id"]).strip()
                maximum_screen_error_px = float(item["maximum_screen_error_px"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValidationError(
                    "HYB_LOD_CONTRACT_INVALID",
                    "every LOD requires level, representation_id, and positive maximum_screen_error_px",
                ) from exc
            if level < 0 or not representation_id or maximum_screen_error_px <= 0:
                raise ValidationError(
                    "HYB_LOD_CONTRACT_INVALID",
                    "LOD level must be non-negative, representation_id non-empty, and screen error positive",
                )
            normalized_lods.append({
                **item,
                "level": level,
                "representation_id": representation_id,
                "maximum_screen_error_px": maximum_screen_error_px,
            })
        normalized_lods.sort(key=lambda item: item["level"])
        levels = [item["level"] for item in normalized_lods]
        representation_ids = [item["representation_id"] for item in normalized_lods]
        if levels != list(range(len(levels))):
            raise ValidationError("HYB_LOD_LEVEL_INVALID", "LOD levels must be contiguous integers beginning at zero")
        if len(representation_ids) != len(set(representation_ids)):
            raise ValidationError("HYB_LOD_REPRESENTATION_DUPLICATE", "a representation may appear only once in a family")
        screen_errors = [item["maximum_screen_error_px"] for item in normalized_lods]
        if any(later >= earlier for earlier, later in zip(screen_errors, screen_errors[1:])):
            raise ValidationError(
                "HYB_LOD_ERROR_ORDER_INVALID",
                "maximum screen error must strictly decrease as LOD detail level increases",
            )
        if len(normalized_lods) > 1 and not (seam_validation_report_id or "").strip():
            raise ValidationError(
                "HYB_SEAM_VALIDATION_REQUIRED",
                "multi-LOD representation families require a retained seam validation report",
            )

        family_id = family_id or new_uuid()
        with self.database.session() as session:
            frame = session.get(CoordinateFrameRow, coordinate_frame_id)
            if not frame or frame.tenant_id != tenant_id or frame.project_id != project_id or frame.deprecated_at is not None:
                raise NotFoundError("coordinate_frame", coordinate_frame_id)
            for item in normalized_lods:
                representation_id = item["representation_id"]
                rep = session.get(RepresentationAssetRow, representation_id)
                if not rep or rep.tenant_id != tenant_id or rep.project_id != project_id or rep.scene_id != scene_id:
                    raise NotFoundError("representation", representation_id)
                if rep.deprecated_at is not None or rep.state != "approved":
                    raise ConflictError(
                        "HYB_FAMILY_REPRESENTATION_NOT_APPROVED",
                        "every family representation must be active and independently approved",
                        {"representation_id": representation_id, "state": rep.state},
                    )
                if rep.coordinate_frame_id != coordinate_frame_id:
                    raise ValidationError("HYB_FAMILY_FRAME_MISMATCH", "every family representation must share the canonical coordinate frame")
                output_role = str((rep.metadata_json or {}).get("output_role") or "")
                if output_role and output_role != role:
                    raise ValidationError(
                        "HYB_FAMILY_ROLE_MISMATCH",
                        "family role must match every representation output role",
                        {"representation_id": representation_id, "output_role": output_role, "family_role": role},
                    )
            if fallback_representation_id:
                fallback = session.get(RepresentationAssetRow, fallback_representation_id)
                if not fallback or fallback.tenant_id != tenant_id or fallback.project_id != project_id or fallback.scene_id != scene_id:
                    raise NotFoundError("fallback_representation", fallback_representation_id)
                if fallback.deprecated_at is not None or fallback.state != "approved":
                    raise ConflictError(
                        "HYB_FAMILY_FALLBACK_NOT_APPROVED",
                        "family fallback must be active and independently approved",
                    )
                if fallback.coordinate_frame_id != coordinate_frame_id:
                    raise ValidationError("HYB_FAMILY_FALLBACK_FRAME_MISMATCH", "family fallback must use the canonical family frame")
                fallback_role = str((fallback.metadata_json or {}).get("output_role") or "")
                if fallback_role and fallback_role != role:
                    raise ValidationError("HYB_FAMILY_FALLBACK_ROLE_MISMATCH", "family fallback output role must match the family role")
            body = {
                "family_id": family_id,
                "tenant_id": tenant_id,
                "project_id": project_id,
                "scene_id": scene_id,
                "role": role,
                "coordinate_frame_id": coordinate_frame_id,
                "tile_scheme_id": tile_scheme_id,
                "lods": normalized_lods,
                "seam_validation_report_id": seam_validation_report_id,
                "fallback_representation_id": fallback_representation_id,
            }
            digest = canonical_sha256(body)
            existing = session.get(RepresentationFamilyRow, family_id)
            if existing:
                if existing.family_hash != digest:
                    raise ConflictError("HYB_REPRESENTATION_FAMILY_IMMUTABLE", "representation family identifier is already bound to different content")
                return {**body, "family_hash": digest}
            session.add(RepresentationFamilyRow(
                family_id=family_id,
                tenant_id=tenant_id,
                project_id=project_id,
                scene_id=scene_id,
                role=role,
                coordinate_frame_id=coordinate_frame_id,
                tile_scheme_id=tile_scheme_id,
                lods_json=body["lods"],
                seam_validation_report_id=seam_validation_report_id,
                fallback_representation_id=fallback_representation_id,
                family_hash=digest,
                state="active",
                created_by=actor_id,
            ))
            return {**body, "family_hash": digest}

    def _validate_conversion_sources(
        self,
        contract: SpatialConversionRequestContract,
        *,
        policy_context: dict[str, Any],
    ) -> dict[str, Any]:
        source_snapshots: list[dict[str, Any]] = []
        reference_snapshots: list[dict[str, Any]] = []
        classifications: list[str] = []
        classification_basis: list[dict[str, Any]] = []
        byte_count = 0
        with self.database.session() as session:
            project = session.get(ProjectRow, contract.project_id)
            if not project or project.tenant_id != contract.tenant_id:
                raise NotFoundError("project", contract.project_id)
            classifications.append(project.classification)
            classification_basis.append({
                "type": "project_classification",
                "project_id": contract.project_id,
                "classification": project.classification,
            })
            commit = session.get(SceneCommitRow, contract.scene_revision_id)
            if not commit or commit.tenant_id != contract.tenant_id or commit.project_id != contract.project_id or commit.scene_id != contract.scene_id:
                raise NotFoundError("scene_commit", contract.scene_revision_id)
            seen: set[str] = set()
            for target, items in ((source_snapshots, contract.source_assets), (reference_snapshots, contract.reference_assets)):
                for item in items:
                    if item.asset_id in seen:
                        raise ValidationError("HYB_DUPLICATE_ASSET_REFERENCE", "conversion request references the same asset more than once", {"asset_id": item.asset_id})
                    seen.add(item.asset_id)
                    asset = session.get(AssetRefRow, item.asset_id)
                    if not asset or asset.tenant_id != contract.tenant_id or asset.project_id != contract.project_id or asset.tombstoned_at is not None:
                        raise NotFoundError("asset", item.asset_id)
                    digest = _normalize_digest(item.sha256)
                    if asset.sha256 != digest:
                        raise ValidationError("HYB_SOURCE_HASH_MISMATCH", "conversion source hash does not match immutable storage", {"asset_id": item.asset_id})
                    frame = session.get(CoordinateFrameRow, item.coordinate_frame_id)
                    if not frame or frame.tenant_id != contract.tenant_id or frame.project_id != contract.project_id or frame.deprecated_at is not None:
                        raise NotFoundError("coordinate_frame", item.coordinate_frame_id)
                    obj = session.get(AssetRow, asset.sha256)
                    if not obj:
                        raise ValidationError("HYB_SOURCE_OBJECT_MISSING", "conversion source object metadata is missing", {"asset_id": item.asset_id})
                    classifications.append(asset.classification)
                    classification_basis.append({
                        "type": "asset_classification",
                        "asset_id": asset.asset_id,
                        "role": item.role,
                        "classification": asset.classification,
                        "source_class": asset.source_class,
                        "authority_class": asset.authority_class,
                    })
                    byte_count += obj.byte_count
                    target.append({
                        "asset_id": asset.asset_id,
                        "sha256": asset.sha256,
                        "role": item.role,
                        "coordinate_frame_id": item.coordinate_frame_id,
                        "use": item.use,
                        "classification": asset.classification,
                        "source_class": asset.source_class,
                        "authority_class": asset.authority_class,
                        "legal_hold": asset.legal_hold,
                        "byte_count": obj.byte_count,
                    })

        raw_signals = policy_context.get("spatial_sensitivity", [])
        if raw_signals is None:
            raw_signals = []
        if not isinstance(raw_signals, list) or any(not isinstance(item, str) or not item.strip() for item in raw_signals):
            raise ValidationError(
                "HYB_SPATIAL_SENSITIVITY_INVALID",
                "spatial sensitivity signals must be a list of non-empty registered identifiers",
            )
        signals = sorted(set(item.strip() for item in raw_signals))
        unknown = sorted(set(signals) - set(_SPATIAL_SENSITIVITY_FLOORS))
        if unknown:
            raise AuthorizationError(
                "HYB_SPATIAL_SENSITIVITY_UNKNOWN",
                "unknown spatial sensitivity facts fail closed before provider admission",
                {"unknown_signal_count": len(unknown)},
            )
        for signal in signals:
            floor = _SPATIAL_SENSITIVITY_FLOORS[signal]
            classifications.append(floor)
            classification_basis.append({
                "type": "spatial_sensitivity",
                "signal": signal,
                "classification_floor": floor,
            })
        effective = max(classifications, key=lambda item: _CLASSIFICATION_RANK.get(item, 999))
        classification_context = {
            "effective_classification": effective,
            "basis": classification_basis,
            "spatial_sensitivity": signals,
            "external_processing_denied": bool(set(signals) & _EXTERNAL_DENY_SENSITIVITY_SIGNALS),
            "review_evidence_hash": policy_context.get("classification_review_evidence_hash"),
        }
        review_hash = classification_context["review_evidence_hash"]
        if review_hash is not None:
            _require_digest(str(review_hash), "classification_review_evidence_hash")
        return {
            "source_snapshots": source_snapshots,
            "reference_snapshots": reference_snapshots,
            "effective_classification": effective,
            "classification_context": classification_context,
            "input_bytes": byte_count,
        }

    def _validate_provider_for_request(
        self,
        *,
        selected: dict[str, Any],
        contract: SpatialConversionRequestContract,
        effective_classification: str,
        policy_context: dict[str, Any],
        classification_context: dict[str, Any],
    ) -> None:
        if not selected.get("dependency_inventory"):
            raise AuthorizationError("HYB_PROVIDER_DEPENDENCY_INVENTORY_MISSING", "provider cannot execute without a pinned dependency inventory")
        evidence = selected.get("license_evidence") or []
        if not evidence or any(str(item.get("review_state")) != "verified" for item in evidence):
            raise AuthorizationError("HYB_PROVIDER_LICENSE_EVIDENCE_INCOMPLETE", "provider license and output-right evidence must be verified before execution")
        evidence_components = [str(item.get("component", "")).strip().lower() for item in evidence]
        if len(set(evidence_components)) != len(evidence_components):
            raise AuthorizationError("HYB_PROVIDER_LICENSE_EVIDENCE_DUPLICATE", "provider license evidence components must be unique")
        required_license_components = {"code", "dependencies", "output"}
        if selected.get("model_manifest_ids"):
            required_license_components.update({"weights", "dataset"})
        missing_license_components = sorted(required_license_components - set(evidence_components))
        if missing_license_components:
            raise AuthorizationError(
                "HYB_PROVIDER_LICENSE_EVIDENCE_INCOMPLETE",
                "provider approval lacks separately reviewed source, dependency, model-data, or output-right evidence",
                {"missing_component_count": len(missing_license_components)},
            )
        descriptor = self.providers.get_descriptor(selected["provider_id"])
        if descriptor.get("output_rights", "").lower() in {"", "unknown", "research_only", "prohibited"}:
            raise AuthorizationError("HYB_PROVIDER_OUTPUT_RIGHTS_DENIED", "provider output rights are not approved for this execution")
        data_governance = descriptor.get("data_governance") or {}
        if data_governance.get("source_data_use") != "requested_operation_only":
            raise AuthorizationError("HYB_PROVIDER_DATA_USE_UNBOUNDED", "provider data use is not limited to the admitted operation")
        region = str(policy_context.get("region", ""))
        if region not in set(data_governance.get("processing_regions") or []):
            raise AuthorizationError("HYB_PROVIDER_PROCESSING_REGION_DENIED", "provider data-governance terms do not cover the requested processing region")
        for field, secondary_use in (
            ("training_use", "provider_training"),
            ("public_demonstration", "public_demonstration"),
            ("unrelated_retention", "unrelated_retention"),
        ):
            posture = str(data_governance.get(field, ""))
            if posture not in {"prohibited", "separate_authorization_required"}:
                raise AuthorizationError("HYB_PROVIDER_DATA_USE_UNKNOWN", "provider secondary-use posture is unknown")
            if posture != "prohibited":
                # A request body is not an authorization registry. Until a separately signed,
                # server-side approval record exists, secondary uses remain denied.
                raise AuthorizationError(
                    "HYB_PROVIDER_SECONDARY_USE_NOT_AUTHORIZED",
                    "provider secondary data use requires a separately signed server-side authorization",
                    {"secondary_use": secondary_use},
                )
        retention_days = int(descriptor.get("retention_days") or 0)
        if retention_days > 0:
            raise AuthorizationError(
                "HYB_PROVIDER_RETENTION_NOT_AUTHORIZED",
                "provider source-data retention requires a separately signed server-side authorization",
                {"retention_days": retention_days},
            )
        requested_input_roles = {item.role for item in contract.source_assets + contract.reference_assets}
        if not requested_input_roles.issubset(set(selected.get("input_roles", []))):
            raise ValidationError("HYB_PROVIDER_INPUT_ROLE_UNSUPPORTED", "provider does not accept every requested source or reference role")
        security = selected["security"]
        external = bool(security.get("external_processing"))
        if external and (
            effective_classification in _HARD_EXTERNAL_DENY
            or bool(classification_context.get("external_processing_denied"))
        ):
            raise AuthorizationError("HYB_SENSITIVE_EXTERNAL_PROCESSING_DENIED", "sensitive spatial classifications and disclosure contexts are denied from external providers")
        if external and not policy_context.get("allow_external_transfer", False):
            raise AuthorizationError("HYB_EXTERNAL_TRANSFER_NOT_APPROVED", "external provider transfer was not explicitly approved")
        if not security.get("supports_read_only_inputs") or not security.get("supports_write_only_staging"):
            raise AuthorizationError("HYB_PROVIDER_SECURITY_CONTRACT_INADEQUATE", "provider lacks read-only input and write-only quarantine support")
        if security.get("writes_outside_job_workspace"):
            raise AuthorizationError("HYB_PROVIDER_UNBOUNDED_WRITE_DENIED", "provider declares writes outside its isolated job workspace")

    def _validate_consents(
        self,
        *,
        tenant_id: str,
        project_id: str,
        purpose: str,
        intended_uses: list[str],
        audience: str,
        classification: str,
        policy_context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        grant_ids = sorted(set(_string_list(policy_context.get("consent_grant_ids", []), "consent_grant_ids")))
        required_scopes = set(_string_list(policy_context.get("required_consent_scopes", []), "required_consent_scopes"))
        if (classification in {Classification.BIOMETRIC.value, Classification.MINOR.value} or policy_context.get("consent_required")) and not grant_ids:
            raise AuthorizationError("HYB_CONSENT_REQUIRED", "conversion requires explicit active consent grants")
        receipts: list[dict[str, Any]] = []
        now = db_now()
        with self.database.session() as session:
            for grant_id in grant_ids:
                grant = session.get(ConsentGrantRow, grant_id)
                expiry = _aware(grant.expires_at) if grant and grant.expires_at else None
                if not grant or grant.tenant_id != tenant_id or grant.project_id != project_id or grant.state != "active" or grant.revoked_at is not None or (expiry and expiry <= now):
                    raise AuthorizationError("HYB_CONSENT_INVALID", "conversion consent grant is missing, revoked, expired, or out of scope", {"grant_id": grant_id})
                if purpose not in set(grant.purposes_json):
                    raise AuthorizationError("HYB_CONSENT_PURPOSE_DENIED", "consent does not permit the conversion purpose", {"grant_id": grant_id})
                if audience not in set(grant.audiences_json):
                    raise AuthorizationError("HYB_CONSENT_AUDIENCE_DENIED", "consent does not permit the requested audience", {"grant_id": grant_id})
                if required_scopes and not required_scopes.issubset(set(grant.scopes_json)):
                    raise AuthorizationError("HYB_CONSENT_SCOPE_DENIED", "consent does not include every required derivative scope", {"grant_id": grant_id})
                derivative = dict(grant.derivative_policy_json or {})
                prohibited_uses = set(derivative.get("prohibited_uses", []))
                if prohibited_uses & set(intended_uses):
                    raise AuthorizationError("HYB_CONSENT_DERIVATIVE_USE_DENIED", "consent derivative policy prohibits a requested intended use", {"grant_id": grant_id})
                receipts.append({
                    "grant_id": grant_id,
                    "grant_snapshot_hash": canonical_sha256({
                        "state": grant.state,
                        "purposes": grant.purposes_json,
                        "audiences": grant.audiences_json,
                        "scopes": grant.scopes_json,
                        "derivative_policy": grant.derivative_policy_json,
                        "expires_at": expiry.isoformat() if expiry else None,
                    }),
                })
        return receipts

    def _authorize_models(
        self,
        *,
        selected: dict[str, Any],
        purpose: str,
        classification: str,
        deployment_mode: str,
        region: str,
        tenant_id: str,
    ) -> list[dict[str, Any]]:
        receipts: list[dict[str, Any]] = []
        for model_id in selected.get("model_manifest_ids", []):
            with self.database.session() as session:
                row = session.get(ModelManifestRow, model_id)
                if not row:
                    raise AuthorizationError("MODEL_NOT_REGISTERED", "provider references an unregistered model manifest", {"model_id": model_id})
                checkpoint_hash = row.checkpoint_hash
            receipt = self.models.authorize(
                model_id,
                checkpoint_hash=checkpoint_hash,
                purpose=purpose,
                classification=Classification(classification),
                deployment=self.environment,
                region=region,
                customer_id=tenant_id,
            )
            receipts.append(receipt)
        return receipts

    def _resource_estimate(self, validated: dict[str, Any], contract: SpatialConversionRequestContract) -> dict[str, Any]:
        input_bytes = int(validated["input_bytes"])
        multiplier = float(contract.constraints.get("maximum_output_multiplier", 4.0))
        if multiplier <= 0 or multiplier > 100:
            raise ValidationError("HYB_OUTPUT_MULTIPLIER_INVALID", "maximum output multiplier must be in (0, 100]")
        return {
            "input_bytes": input_bytes,
            "source_count": len(validated["source_snapshots"]),
            "reference_count": len(validated["reference_snapshots"]),
            "max_output_bytes": max(1, int(input_bytes * multiplier)),
            "estimate_profile": str(contract.constraints.get("estimate_profile", "deterministic-byte-envelope-v1")),
            "estimated_gpu_seconds": float(contract.constraints.get("estimated_gpu_seconds", 0.0)),
        }

    def _ensure_operation_started(self, claims: dict[str, Any]) -> None:
        operation = self.operations.get(claims["operation_id"])
        worker_id = claims["workload_identity"]
        if operation["state"] == "pending" or operation["state"] == "failed":
            remaining_token_seconds = max(1, int(claims["exp"]) - int(datetime.now(UTC).timestamp()))
            declared_lease_seconds = int(claims.get("lease_ttl_seconds", 60))
            lease_seconds = max(1, min(900, declared_lease_seconds, remaining_token_seconds))
            self.operations.lease(operation["operation_id"], worker_id=worker_id, lease_seconds=lease_seconds)
            self.operations.start(operation["operation_id"], worker_id=worker_id)
        elif operation["state"] in {"leased", "running"}:
            if operation["lease_owner"] != worker_id:
                raise ConflictError("HYB_OPERATION_LEASE_OWNER_MISMATCH", "conversion operation is leased to another workload")
        elif operation["state"] == "succeeded":
            return
        else:
            raise ConflictError("HYB_OPERATION_STATE_INVALID", "conversion operation cannot be started", {"state": operation["state"]})

    def _verify_worker_token(
        self,
        token: str,
        *,
        allowed_inactive_states: set[str] | None = None,
    ) -> dict[str, Any]:
        claims = self.token_codec.decode(token)
        allowed_inactive_states = set(allowed_inactive_states or set())
        if claims.get("type") != "hybrid-worker-lease":
            raise AuthenticationError("HYB_WORKER_TOKEN_TYPE_INVALID", "token is not a hybrid worker lease")
        if claims.get("publication_permission") is not False:
            raise AuthenticationError("HYB_WORKER_PUBLICATION_SCOPE_INVALID", "hybrid worker token must explicitly deny publication")
        expected_permissions = {"asset:read_exact", "quarantine:write", "operation:checkpoint", "operation:complete"}
        if set(claims.get("permissions", [])) != expected_permissions:
            raise AuthenticationError("HYB_WORKER_PERMISSION_INVALID", "hybrid worker token permissions do not match the least-privilege contract")
        scope = claims.get("output_staging_scope", {})
        if scope.get("mode") != "write_only_quarantine":
            raise AuthenticationError("HYB_WORKER_STAGING_SCOPE_INVALID", "hybrid worker output scope is not write-only quarantine")
        with self.database.session() as session:
            row = session.get(SpatialConversionRow, claims.get("conversion_id"))
            if not row:
                raise AuthenticationError("HYB_WORKER_CONVERSION_UNKNOWN", "worker token references an unknown conversion")
            expected = {
                "operation_id": row.operation_id,
                "tenant_id": row.tenant_id,
                "project_id": row.project_id,
                "scene_id": row.scene_id,
                "scene_revision_id": row.scene_revision_id,
                "provider_id": row.provider_id,
                "provider_version": row.provider_version,
                "provider_manifest_hash": row.provider_manifest_hash,
                "promotion_id": row.promotion_id,
                "admission_decision_hash": row.admission_decision_hash,
            }
            mismatches = sorted(key for key, value in expected.items() if claims.get(key) != value)
            if mismatches:
                raise AuthenticationError("HYB_WORKER_CLAIM_MISMATCH", "worker token no longer matches durable conversion admission", {"claims": mismatches})
            durable_credential = dict(row.credential_claims_json or {})
            durable_credential_id = durable_credential.get("credential_id")
            if durable_credential_id and claims.get("credential_id") != durable_credential_id:
                raise AuthenticationError("HYB_WORKER_CREDENTIAL_SUPERSEDED", "worker credential has been rotated or revoked")
            durable_generation = durable_credential.get("credential_generation")
            if durable_generation is not None and int(claims.get("credential_generation", 0)) != int(durable_generation):
                raise AuthenticationError("HYB_WORKER_CREDENTIAL_SUPERSEDED", "worker credential generation is no longer current")
            durable_worker_generation = int(row.worker_lease_generation or 1)
            if int(claims.get("worker_lease_generation", 0)) != durable_worker_generation:
                raise AuthenticationError("HYB_WORKER_TOKEN_SUPERSEDED", "worker lease generation is no longer current")
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            if row.worker_token_hash and not hmac.compare_digest(row.worker_token_hash, token_hash):
                raise AuthenticationError("HYB_WORKER_TOKEN_SUPERSEDED", "worker token is no longer the active signed lease")
            if row.worker_token_expires_at is not None:
                durable_expiry = int(_aware(row.worker_token_expires_at).timestamp())
                if int(claims.get("exp", 0)) != durable_expiry:
                    raise AuthenticationError("HYB_WORKER_TOKEN_BINDING_INVALID", "worker token expiry does not match the durable lease record")
            inactive_states = {
                "cancel_requested",
                "cancelled",
                "rejected",
                "published",
                "failed_retryable",
                "failed_terminal",
                "cleanup_quarantined",
            }
            if row.state in inactive_states and row.state not in allowed_inactive_states:
                raise AuthenticationError("HYB_WORKER_CONVERSION_INACTIVE", "worker token references an inactive conversion")
        return claims

    def _binding_view_denial_reason(
        self,
        session: Any,
        *,
        binding: RepresentationBindingRow,
        rep: RepresentationAssetRow | None,
        purpose: str,
        audience: str,
        device_profile: str,
        intended_uses: set[str],
        allowed_regions: set[str],
        now: datetime,
    ) -> str | None:
        if rep is None or rep.state != "published" or rep.deprecated_at is not None:
            return "representation_inactive"
        if not intended_uses.issubset(set(binding.intended_uses_json or [])):
            return "intended_use_denied"
        audience_policy = dict(binding.audience_policy_json or {})
        allowed_audiences = set(audience_policy.get("allowed_audiences", []))
        if allowed_audiences and audience not in allowed_audiences:
            return "audience_denied"
        allowed_purposes = set(audience_policy.get("allowed_purposes", []))
        binding_purpose = audience_policy.get("purpose")
        if allowed_purposes and purpose not in allowed_purposes:
            return "purpose_denied"
        if binding_purpose and binding_purpose != purpose:
            return "purpose_denied"
        required_regions = set(audience_policy.get("spatial_region_ids", []))
        if required_regions and (not allowed_regions or not required_regions.issubset(allowed_regions)):
            return "spatial_region_denied"
        profile = dict(binding.client_profile_json or {})
        supported_devices = set(profile.get("device_profiles", []))
        if supported_devices and device_profile not in supported_devices:
            return "device_profile_denied"
        for grant_id in audience_policy.get("consent_grant_ids", []):
            grant = session.get(ConsentGrantRow, grant_id)
            expiry = _aware(grant.expires_at) if grant and grant.expires_at else None
            if not grant or grant.state != "active" or grant.revoked_at is not None or (expiry and expiry <= now):
                return "consent_invalid"
            if purpose not in set(grant.purposes_json) or audience not in set(grant.audiences_json):
                return "consent_denied"
        return None

    def _record_pre_admission_rejection(
        self,
        contract: SpatialConversionRequestContract,
        request_hash: str,
        actor_id: str,
        exc: Exception,
    ) -> None:
        """Retain a safe denial record even when no durable operation was created.

        Only the canonical request hash and stable error code are emitted; source asset
        identifiers and provider-selection details are intentionally omitted.
        """
        code = str(getattr(exc, "code", type(exc).__name__))
        aggregate_id = f"request:{request_hash}"
        with self.database.session() as session:
            session.add(self._event(
                session,
                event_type="representation.operation.rejected",
                aggregate_type="spatial_conversion",
                aggregate_id=aggregate_id,
                tenant_id=contract.tenant_id,
                project_id=contract.project_id,
                actor_id=actor_id,
                payload={
                    "request_hash": request_hash,
                    "error_code": code,
                    "retryable": bool(getattr(exc, "retryable", False)),
                    "operation_created": False,
                },
            ))
            self.audit.append(
                tenant_id=contract.tenant_id,
                project_id=contract.project_id,
                actor_id=actor_id,
                action="hybrid_conversion:admit",
                resource_type="spatial_conversion_request",
                resource_id=aggregate_id,
                outcome="denied",
                details={
                    "request_hash": request_hash,
                    "error_code": code,
                    "operation_created": False,
                },
                session=session,
            )

    def _mark_operation_rejected(self, operation_id: str, exc: Exception) -> None:
        code = str(getattr(exc, "code", type(exc).__name__))
        with self.database.session() as session:
            row = session.get(OperationRow, operation_id)
            if row:
                row.state = "quarantined"
                row.error_json = {"code": code, "message": "admission denied", "retryable": False}
                row.updated_at = db_now()
                session.add(self._event(
                    session,
                    event_type="representation.operation.rejected",
                    aggregate_type="spatial_conversion",
                    aggregate_id=operation_id,
                    tenant_id=row.tenant_id,
                    project_id=row.project_id,
                    actor_id=row.created_by,
                    payload={
                        "operation_id": operation_id,
                        "request_hash": row.input_json.get("request_hash"),
                        "error_code": code,
                        "retryable": bool(getattr(exc, "retryable", False)),
                        "operation_created": True,
                    },
                ))
                self.audit.append(
                    tenant_id=row.tenant_id,
                    project_id=row.project_id,
                    actor_id=row.created_by,
                    action="hybrid_conversion:admit",
                    resource_type="operation",
                    resource_id=operation_id,
                    outcome="denied",
                    details={
                        "request_hash": row.input_json.get("request_hash"),
                        "error_code": code,
                        "operation_created": True,
                    },
                    session=session,
                )

    @staticmethod
    def _scoped_conversion(session: Any, conversion_id: str, tenant_id: str, project_id: str) -> SpatialConversionRow:
        row = session.get(SpatialConversionRow, conversion_id)
        if not row or row.tenant_id != tenant_id or row.project_id != project_id:
            raise NotFoundError("spatial_conversion", conversion_id)
        return row

    @staticmethod
    def _conversion_dict(row: SpatialConversionRow) -> dict[str, Any]:
        return {
            "conversion_id": row.conversion_id,
            "operation_id": row.operation_id,
            "tenant_id": row.tenant_id,
            "project_id": row.project_id,
            "scene_id": row.scene_id,
            "scene_revision_id": row.scene_revision_id,
            "purpose": row.purpose,
            "intended_uses": row.intended_uses_json,
            "output_roles": row.output_roles_json,
            "source_assets": row.source_assets_json,
            "reference_assets": row.reference_assets_json,
            "provider_id": row.provider_id,
            "provider_version": row.provider_version,
            "provider_manifest_hash": row.provider_manifest_hash,
            "promotion_id": row.promotion_id,
            "request_hash": row.request_hash,
            "admission_state": row.admission_state,
            "admission_decision_hash": row.admission_decision_hash,
            "resource_estimate": row.resource_estimate_json,
            "worker_lease_generation": int(row.worker_lease_generation or 1),
            "worker_token_expires_at": row.worker_token_expires_at,
            "failure": row.failure_json or None,
            "failure_hash": row.failure_hash,
            "cleanup_receipt_hash": row.cleanup_receipt_hash,
            "candidate_representation_id": row.candidate_representation_id,
            "state": row.state,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _progress_dict(row: ProviderProgressRow) -> dict[str, Any]:
        return {
            "progress_id": row.progress_id,
            "conversion_id": row.conversion_id,
            "sequence": row.sequence,
            "stage": row.stage,
            "completed_work_units": row.completed_work_units,
            "total_work_units": row.total_work_units,
            "work_unit_name": row.work_unit_name,
            "resource_use": row.resource_use_json,
            "warnings": row.warnings_json,
            "last_durable_checkpoint_hash": row.checkpoint_hash,
            "estimated_output_bytes": row.estimated_output_bytes,
            "recorded_at": row.recorded_at,
        }

    @staticmethod
    def _validation_dict(row: IntendedUseValidationRow) -> dict[str, Any]:
        return {
            "validation_id": row.validation_id,
            "conversion_id": row.conversion_id,
            "representation_id": row.representation_id,
            "intended_use": row.intended_use,
            "profile_id": row.profile_id,
            "profile_version": row.profile_version,
            "validator_id": row.validator_id,
            "validator_manifest_hash": row.validator_manifest_hash,
            "metrics": row.metrics_json,
            "thresholds": row.thresholds_json,
            "coverage": row.coverage_json,
            "topology": row.topology_json,
            "coordinate_validation": row.coordinate_validation_json,
            "behavior_validation": row.behavior_validation_json,
            "limitations": row.limitations_json,
            "passed": row.passed,
            "candidate_snapshot_hash": row.candidate_snapshot_hash,
            "policy_snapshot_hash": row.policy_snapshot_hash,
            "validation_hash": row.validation_hash,
            "created_at": row.created_at,
        }

    @classmethod
    def _event(
        cls,
        session: Any,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        tenant_id: str,
        project_id: str,
        payload: dict[str, Any],
        actor_id: str | None,
        workload_identity: str | None = None,
    ) -> Any:
        return cls._events.create(
            session,
            event_type=event_type,
            schema_version="1.0.0",
            tenant_id=tenant_id,
            project_id=project_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            producer="representation-api",
            actor_id=actor_id,
            workload_identity=workload_identity,
            correlation_id=aggregate_id,
        )


def _thresholds_pass(metrics: dict[str, Any], thresholds: dict[str, Any]) -> bool:
    if not metrics or not thresholds:
        raise ValidationError("HYB_VALIDATION_EVIDENCE_INCOMPLETE", "validation requires quantitative metrics and explicit thresholds")
    evaluated = 0
    for name, rule in thresholds.items():
        if name not in metrics or not isinstance(rule, dict):
            raise ValidationError("HYB_VALIDATION_THRESHOLD_UNRESOLVED", "every threshold must resolve to a submitted metric", {"metric": name})
        value = metrics[name]
        if not isinstance(value, (int, float)):
            raise ValidationError("HYB_VALIDATION_METRIC_NON_NUMERIC", "thresholded validation metrics must be numeric", {"metric": name})
        if "max" in rule and value > float(rule["max"]):
            return False
        if "min" in rule and value < float(rule["min"]):
            return False
        if "equal" in rule and value != rule["equal"]:
            return False
        if not set(rule).intersection({"max", "min", "equal"}):
            raise ValidationError("HYB_VALIDATION_THRESHOLD_INVALID", "threshold rule requires min, max, or equal", {"metric": name})
        evaluated += 1
    return evaluated > 0


def _truth_label(kind: RepresentationKind) -> str:
    return {
        RepresentationKind.METRIC: "metric-derived-not-field-verified",
        RepresentationKind.VISUAL: "visual-non-metric",
        RepresentationKind.INTERACTION: "disposable-non-authoritative-proxy",
        RepresentationKind.DESIGN: "design-intent-not-observed",
        RepresentationKind.EVIDENCE: "evidence-linked",
    }[kind]


def _require_role_kind_compatibility(output_role: str, kind: RepresentationKind) -> None:
    allowed = _OUTPUT_ROLE_KIND_COMPATIBILITY.get(output_role)
    if allowed is None:
        raise ValidationError(
            "HYB_OUTPUT_ROLE_KIND_UNDECLARED",
            "output role has no platform authority-kind contract",
            {"output_role": output_role},
        )
    if kind not in allowed:
        raise ValidationError(
            "HYB_OUTPUT_ROLE_KIND_MISMATCH",
            "candidate representation kind is incompatible with the admitted output role",
            {
                "output_role": output_role,
                "kind": kind.value,
                "allowed_kinds": sorted(item.value for item in allowed),
            },
        )


def _safe_errors(exc: PydanticValidationError) -> dict[str, Any]:
    return {
        "errors": [
            {"loc": [str(part) for part in item.get("loc", [])], "type": str(item.get("type", "invalid")), "msg": str(item.get("msg", "invalid"))[:256]}
            for item in exc.errors()[:25]
        ]
    }


def _required_text(value: dict[str, Any], key: str) -> str:
    result = str(value.get(key, "")).strip()
    if not result:
        raise ValidationError("HYB_POLICY_CONTEXT_INCOMPLETE", "conversion policy context is missing a required field", {"field": key})
    return result


def _string_list(value: Any, name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError("HYB_LIST_INVALID", f"{name} must be a list")
    result = [str(item).strip() for item in value]
    if any(not item for item in result) or len(result) != len(set(result)):
        raise ValidationError("HYB_LIST_INVALID", f"{name} must contain unique non-empty strings")
    return result


def _normalize_digest(value: str) -> str:
    digest = value.removeprefix("sha256:").lower()
    _require_digest(digest, "sha256")
    return digest


def _require_digest(value: str, name: str) -> None:
    digest = value.removeprefix("sha256:").lower()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ValidationError("HYB_DIGEST_INVALID", f"{name} must be an exact lowercase SHA-256 digest")


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
