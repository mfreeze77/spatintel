from __future__ import annotations

import hashlib
import hmac
import re
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from .canonical import canonical_sha256
from .contracts import ModelManifestContract
from .database import Database, ModelManifestRow
from .errors import AuthorizationError, ValidationError
from .models import Classification
from .temporal import db_now

HEX64 = re.compile(r"^[0-9a-f]{64}$")
INCOMPATIBLE_LICENSES = {
    "unknown",
    "missing",
    "incompatible",
    "proprietary-unapproved",
}
LIMITED_USE_LICENSES = {"research-only", "research_only", "restricted-use"}
EXECUTABLE_STATES = {"approved", "research_only"}


class ModelRegistry:
    """Fail-closed model/checkpoint governance registry.

    The server normalizes and signs each manifest at registration. Authorization
    reconstructs the canonical record from durable storage and verifies both its
    digest and signature before evaluating state, deployment, rights, purpose,
    classification, geography, customer, review, and checkpoint constraints.
    Legacy rows created before the v1.1 manifest contract remain preserved but
    are deliberately non-executable because they cannot satisfy completeness.
    """

    def __init__(self, database: Database, signing_key: bytes) -> None:
        if len(signing_key) < 32:
            raise ValueError("model manifest signing key must contain at least 32 bytes")
        self.database = database
        self._signing_key = signing_key

    def register(self, manifest: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        if not isinstance(manifest, dict):
            raise ValidationError("MODEL_MANIFEST_INVALID", "model manifest must be an object")
        raw = dict(manifest)
        provided_hash = raw.pop("manifest_hash", None)
        provided_signature = raw.pop("manifest_signature", raw.pop("signature", None))
        raw["signed_by"] = actor_id or raw.get("signed_by") or raw.get("approved_by")
        raw.setdefault("schema", "sip.model-manifest/v1.2")
        raw.setdefault("schema_version", "1.2.0")

        # Validate and normalize before hashing. Placeholder values are replaced
        # immediately and never persisted or returned.
        try:
            provisional = ModelManifestContract.model_validate(
                {**raw, "manifest_hash": "0" * 64, "manifest_signature": "0" * 64}
            )
        except PydanticValidationError as exc:
            missing = sorted(
                {
                    str(error["loc"][0])
                    for error in exc.errors()
                    if error.get("type") == "missing" and error.get("loc")
                }
            )
            raise ValidationError(
                "MODEL_MANIFEST_INCOMPLETE" if missing else "MODEL_MANIFEST_INVALID",
                "model manifest is incomplete" if missing else "model manifest violates the canonical contract",
                {"missing": missing, "errors": _safe_validation_errors(exc)},
            ) from exc

        body = provisional.model_dump(mode="json", by_alias=True)
        body.pop("manifest_hash", None)
        body.pop("manifest_signature", None)
        digest = canonical_sha256(body)
        signature = self._signature(digest)
        if provided_hash is not None and not hmac.compare_digest(str(provided_hash), digest):
            raise ValidationError("MODEL_MANIFEST_HASH_MISMATCH", "provided model manifest hash does not match canonical content")
        if provided_signature is not None and not hmac.compare_digest(str(provided_signature), signature):
            raise ValidationError("MODEL_MANIFEST_SIGNATURE_INVALID", "provided model manifest signature is invalid")

        contract = ModelManifestContract.model_validate(
            {**body, "manifest_hash": digest, "manifest_signature": signature}
        )
        self._validate_registration_policy(contract)
        values = self._row_values(contract)
        now = db_now()
        values["updated_at"] = now
        with self.database.session() as session:
            row = session.get(ModelManifestRow, contract.model_id)
            if row:
                for key, value in values.items():
                    setattr(row, key, value)
                if row.registered_at is None:
                    row.registered_at = now
            else:
                session.add(ModelManifestRow(**values, registered_at=now))
        return {
            "model_id": contract.model_id,
            "manifest_hash": digest,
            "manifest_signature": signature,
            "approval_state": contract.approval_state,
            "review_due_at": contract.review_due_at.isoformat(),
        }

    def authorize(
        self,
        model_id: str,
        *,
        checkpoint_hash: str,
        purpose: str,
        classification: Classification,
        deployment: str = "development",
        region: str = "local",
        customer_id: str | None = None,
    ) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(ModelManifestRow, model_id)
            if not row:
                raise AuthorizationError("MODEL_NOT_REGISTERED", "model execution is denied without a manifest")
            try:
                contract = self._contract_from_row(row)
            except (PydanticValidationError, TypeError, ValueError):
                raise AuthorizationError(
                    "MODEL_EXECUTION_DENIED",
                    "model governance gate denied execution",
                    {"reasons": ["manifest_incomplete"]},
                ) from None

            reasons: list[str] = []
            body = contract.model_dump(mode="json", by_alias=True)
            stored_hash = body.pop("manifest_hash")
            stored_signature = body.pop("manifest_signature")
            recomputed_hash = canonical_sha256(body)
            if not hmac.compare_digest(stored_hash, recomputed_hash):
                reasons.append("manifest_hash_invalid")
            if not hmac.compare_digest(stored_signature, self._signature(recomputed_hash)):
                reasons.append("manifest_signature_invalid")

            now = db_now()
            state = contract.approval_state
            research_execution = state == "research_only" and deployment in {"development", "test"}
            if state != "approved" and not research_execution:
                reasons.append("state_not_executable")
            if deployment == "production" and state != "approved":
                reasons.append("production_state_not_approved")
            if state in {"expired", "revoked", "denied", "pending"}:
                reasons.append(f"state_{state}")
            if contract.revoked_at is not None:
                reasons.append("approval_revoked")
            if _aware(contract.review_due_at) <= now:
                reasons.append("review_expired")
            if contract.expires_at and _aware(contract.expires_at) <= now:
                reasons.append("approval_expired")
            if deployment not in contract.allowed_deployments:
                reasons.append("deployment_not_allowed")
            if contract.checkpoint_hash != checkpoint_hash:
                reasons.append("checkpoint_hash_mismatch")
            if purpose not in contract.permitted_uses:
                reasons.append("purpose_not_permitted")
            if purpose in contract.prohibited_uses:
                reasons.append("purpose_prohibited")
            if contract.usage_scope != "local_internal":
                reasons.append("usage_scope_not_local_internal")
            if classification not in contract.allowed_classifications:
                reasons.append("classification_not_allowed")
            if not _restriction_allows(contract.geographic_restrictions.model_dump(), region):
                reasons.append("region_not_allowed")
            if not _restriction_allows(contract.customer_restrictions.model_dump(), customer_id):
                reasons.append("customer_not_allowed")

            license_name = contract.weights_license.strip().lower()
            if license_name in INCOMPATIBLE_LICENSES:
                reasons.append("weights_license_incompatible")
            if license_name in LIMITED_USE_LICENSES and not research_execution:
                reasons.append("weights_license_research_only")
            if state in EXECUTABLE_STATES and not _license_evidence_complete(contract):
                reasons.append("license_evidence_incomplete")
            if state in EXECUTABLE_STATES and not HEX64.fullmatch(contract.checkpoint_hash):
                reasons.append("checkpoint_hash_invalid")

            if reasons:
                raise AuthorizationError(
                    "MODEL_EXECUTION_DENIED",
                    "model governance gate denied execution",
                    {"reasons": sorted(set(reasons))},
                )
            return {
                "allowed": True,
                "model_id": model_id,
                "provider": contract.provider,
                "model_name": contract.model_name,
                "revision": contract.revision,
                "manifest_hash": contract.manifest_hash,
                "manifest_signature": contract.manifest_signature,
                "checkpoint_hash": contract.checkpoint_hash,
                "approval_state": contract.approval_state,
                "review_due_at": contract.review_due_at.isoformat(),
                "deployment": deployment,
            }

    def _validate_registration_policy(self, contract: ModelManifestContract) -> None:
        executable = contract.approval_state in EXECUTABLE_STATES
        if executable and not HEX64.fullmatch(contract.checkpoint_hash):
            raise ValidationError(
                "MODEL_CHECKPOINT_HASH_INVALID",
                "executable model manifests require an exact lowercase SHA-256 checkpoint hash",
            )
        if executable and not _license_evidence_complete(contract):
            raise ValidationError(
                "MODEL_LICENSE_EVIDENCE_INCOMPLETE",
                "executable model manifests require verified code, weights, dataset, and output license evidence",
            )
        if contract.approval_state == "approved":
            if contract.weights_license.strip().lower() in INCOMPATIBLE_LICENSES | LIMITED_USE_LICENSES:
                raise ValidationError("MODEL_WEIGHTS_LICENSE_INCOMPATIBLE", "approved model weights rights are incompatible")
            if contract.review_due_at <= db_now():
                raise ValidationError("MODEL_REVIEW_EXPIRED", "approved model review date must be in the future")
            if contract.approved_by.strip().lower() in {"unapproved", "unknown", "none"}:
                raise ValidationError("MODEL_APPROVER_INVALID", "approved model requires an accountable approver")
        if contract.approval_state == "research_only" and "production" in contract.allowed_deployments:
            raise ValidationError(
                "MODEL_RESEARCH_PRODUCTION_INVALID",
                "research-only model manifests cannot permit production deployment",
            )
        if any(value in {"", "UNRESOLVED", "unknown"} for value in contract.source_urls):
            raise ValidationError("MODEL_SOURCE_URL_INVALID", "model source URLs must be explicit")

    def _row_values(self, contract: ModelManifestContract) -> dict[str, Any]:
        return {
            "model_id": contract.model_id,
            "version": contract.version,
            "checkpoint_hash": contract.checkpoint_hash,
            "code_revision": contract.code_revision,
            "code_license": contract.code_license,
            "weights_license": contract.weights_license,
            "dataset_terms_json": contract.dataset_terms,
            "output_terms": contract.output_terms,
            "approval_state": contract.approval_state,
            "usage_scope": contract.usage_scope,
            "allowed_purposes_json": contract.permitted_uses,
            "expires_at": contract.expires_at,
            "manifest_hash": contract.manifest_hash,
            "schema_version": contract.schema_version,
            "provider": contract.provider,
            "model_name": contract.model_name,
            "revision": contract.revision,
            "source_urls_json": contract.source_urls,
            "license_documents_json": [item.model_dump(mode="json") for item in contract.license_documents],
            "allowed_classifications_json": [item.value for item in contract.allowed_classifications],
            "permitted_uses_json": contract.permitted_uses,
            "prohibited_uses_json": contract.prohibited_uses,
            "geographic_restrictions_json": contract.geographic_restrictions.model_dump(mode="json"),
            "customer_restrictions_json": contract.customer_restrictions.model_dump(mode="json"),
            "allowed_deployments_json": contract.allowed_deployments,
            "approved_by": contract.approved_by,
            "reviewed_at": contract.reviewed_at,
            "review_due_at": contract.review_due_at,
            "revoked_at": contract.revoked_at,
            "manifest_signature": contract.manifest_signature,
            "signed_by": contract.signed_by,
        }

    def _contract_from_row(self, row: ModelManifestRow) -> ModelManifestContract:
        return ModelManifestContract.model_validate(
            {
                "schema": "sip.model-manifest/v1.2",
                "schema_version": row.schema_version,
                "model_id": row.model_id,
                "provider": row.provider,
                "model_name": row.model_name,
                "version": row.version,
                "revision": row.revision,
                "checkpoint_hash": row.checkpoint_hash,
                "source_urls": row.source_urls_json,
                "license_documents": row.license_documents_json,
                "code_revision": row.code_revision,
                "code_license": row.code_license,
                "weights_license": row.weights_license,
                "dataset_terms": row.dataset_terms_json,
                "output_terms": row.output_terms,
                "approval_state": row.approval_state,
                "usage_scope": row.usage_scope,
                "allowed_classifications": row.allowed_classifications_json,
                "permitted_uses": row.permitted_uses_json,
                "prohibited_uses": row.prohibited_uses_json,
                "geographic_restrictions": row.geographic_restrictions_json,
                "customer_restrictions": row.customer_restrictions_json,
                "allowed_deployments": row.allowed_deployments_json,
                "approved_by": row.approved_by,
                # SQLite stores timezone-aware values as naive timestamps.  Restore
                # the canonical UTC offset before reconstructing the signed body so
                # authorization verifies the exact digest that was registered.
                "reviewed_at": _aware(row.reviewed_at),
                "review_due_at": _aware(row.review_due_at),
                "expires_at": _aware(row.expires_at) if row.expires_at else None,
                "revoked_at": _aware(row.revoked_at) if row.revoked_at else None,
                "manifest_hash": row.manifest_hash,
                "manifest_signature": row.manifest_signature,
                "signed_by": row.signed_by,
            }
        )

    def _signature(self, digest: str) -> str:
        return hmac.new(self._signing_key, digest.encode("ascii"), hashlib.sha256).hexdigest()


def lingbot_source_manifest() -> dict[str, Any]:
    return {
        "provider_id": "lingbot-map-source-adapter",
        "version": "1.1.0",
        "source_url": "https://github.com/Robbyant/lingbot-map",
        "source_revision": "1f480aeb8a47a24656090d46d053115b7fe60435",
        "license_id": "Apache-2.0",
        "approval_state": "approved",
        "allowed_classifications": ["public", "internal"],
        "allowed_purposes": ["synthetic_evaluation", "research_shadow"],
        "allowed_regions": ["local"],
        "retention_days": 0,
        "notes": "Source readiness does not include a model checkpoint or its training data.",
    }


def lingbot_checkpoint_denied_manifest() -> dict[str, Any]:
    return {
        "schema": "sip.model-manifest/v1.2",
        "schema_version": "1.2.0",
        "model_id": "lingbot-map-checkpoint",
        "provider": "Robbyant",
        "model_name": "LingBot-Map",
        "version": "unapproved",
        "revision": "1f480aeb8a47a24656090d46d053115b7fe60435",
        "checkpoint_hash": "UNAVAILABLE",
        "source_urls": [
            "https://github.com/Robbyant/lingbot-map",
            "https://huggingface.co/robbyant/lingbot-map",
        ],
        "license_documents": [
            {
                "component": "code",
                "title": "LingBot-Map source license",
                "license_id": "Apache-2.0",
                "source_url": "https://github.com/Robbyant/lingbot-map/blob/1f480aeb8a47a24656090d46d053115b7fe60435/LICENSE.txt",
                "document_sha256": "a8b9758f15712cb329503838d53cc0931a79a039f9676677967570c8c0e9e7ff",
                "review_state": "verified",
            },
            {
                "component": "weights",
                "title": "LingBot-Map checkpoint terms",
                "license_id": "unknown",
                "source_url": "https://huggingface.co/robbyant/lingbot-map",
                "document_sha256": None,
                "review_state": "missing",
            },
            {
                "component": "dataset",
                "title": "LingBot-Map training/evaluation data terms",
                "license_id": "unknown",
                "source_url": "https://github.com/Robbyant/lingbot-map",
                "document_sha256": None,
                "review_state": "missing",
            },
            {
                "component": "output",
                "title": "LingBot-Map output-use terms",
                "license_id": "unknown",
                "source_url": "https://huggingface.co/robbyant/lingbot-map",
                "document_sha256": None,
                "review_state": "missing",
            },
        ],
        "code_revision": "1f480aeb8a47a24656090d46d053115b7fe60435",
        "code_license": "Apache-2.0",
        "weights_license": "unknown",
        "dataset_terms": ["unknown"],
        "output_terms": "unknown",
        "approval_state": "denied",
        "usage_scope": "local_internal",
        "allowed_classifications": ["public", "internal"],
        "permitted_uses": ["synthetic_evaluation", "research_shadow"],
        "prohibited_uses": ["external_distribution", "confidential_input", "verified_measurement"],
        "geographic_restrictions": {"mode": "allowlist", "values": ["local"]},
        "customer_restrictions": {"mode": "denylist", "values": ["*"]},
        "allowed_deployments": ["development", "test"],
        "approved_by": "sip-governance-deny-by-default",
        "reviewed_at": "2026-07-27T00:00:00Z",
        "review_due_at": "2027-07-27T00:00:00Z",
    }


def _restriction_allows(restriction: dict[str, Any], value: str | None) -> bool:
    mode = restriction.get("mode")
    values = set(restriction.get("values") or [])
    if mode == "unrestricted":
        return True
    if value is None:
        return False
    if mode == "allowlist":
        return value in values or "*" in values
    if mode == "denylist":
        return value not in values and "*" not in values
    return False


def _license_evidence_complete(contract: ModelManifestContract) -> bool:
    reviewed = {
        item.component
        for item in contract.license_documents
        if item.review_state == "verified" and item.document_sha256 is not None
    }
    return {"code", "weights", "dataset", "output"} <= reviewed


def _safe_validation_errors(exc: PydanticValidationError) -> list[dict[str, Any]]:
    return [
        {
            "field": ".".join(str(item) for item in error.get("loc", ())),
            "type": str(error.get("type", "invalid")),
            "message": str(error.get("msg", "invalid value")),
        }
        for error in exc.errors()[:32]
    ]


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
