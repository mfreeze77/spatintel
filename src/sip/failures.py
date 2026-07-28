from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .canonical import canonical_json, canonical_sha256, new_uuid
from .errors import ConflictError, SIPError, ValidationError

FailureSeverity = Literal["info", "warning", "error", "unsafe", "fatal"]
RetryClass = Literal[
    "transient",
    "capacity",
    "policy",
    "invalid_input",
    "deterministic_algorithm",
    "manual_review",
    "non_retryable",
]
PublicationAction = Literal["none", "quarantine", "block", "withdraw"]


class FailureDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,127}$")
    introduced_version: str
    category: str
    coverage_tags: list[str] = Field(min_length=1)
    severity: FailureSeverity
    retry_class: RetryClass
    retryable: bool
    safe_checkpoint: str | None
    operator_action: str = Field(min_length=1)
    customer_message: str = Field(min_length=1)
    audit_required: bool
    test_references: list[str] = Field(min_length=1)
    publication_action: PublicationAction
    diagnostic_fields: list[str]
    recovery_mode: str = Field(min_length=1)
    fallback: str = Field(min_length=1)
    remediation: list[str] = Field(min_length=1)
    affected_representations: list[str] = Field(default_factory=list)
    compatibility_aliases: list[str] = Field(default_factory=list)

    @field_validator("coverage_tags", "diagnostic_fields", "compatibility_aliases")
    @classmethod
    def unique_sorted(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("catalog lists must not contain duplicates")
        return sorted(value)

    @model_validator(mode="after")
    def enforce_safety(self) -> "FailureDefinition":
        if self.severity in {"unsafe", "fatal"} and self.publication_action not in {"block", "withdraw"}:
            raise ValueError("unsafe and fatal failures must block or withdraw publication")
        if self.retry_class in {"policy", "invalid_input", "non_retryable"} and self.retryable:
            raise ValueError("policy, invalid-input, and non-retryable failures cannot auto-retry")
        return self


class FailureCatalogDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: Literal["sip.failure-catalog/v1"] = Field(default="sip.failure-catalog/v1", alias="schema", serialization_alias="schema")
    catalog_version: str
    compatibility_policy: str
    sensitive_diagnostic_policy: str
    required_coverage_tags: list[str] = Field(min_length=1)
    component_fallbacks: dict[str, str]
    failures: list[FailureDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_catalog(self) -> "FailureCatalogDocument":
        codes = [item.code for item in self.failures]
        if len(codes) != len(set(codes)):
            raise ValueError("failure codes must be unique")
        aliases = [alias for item in self.failures for alias in item.compatibility_aliases]
        if set(aliases) & set(codes):
            raise ValueError("compatibility aliases cannot shadow canonical codes")
        if len(aliases) != len(set(aliases)):
            raise ValueError("compatibility aliases must be unique")
        covered = {tag for item in self.failures for tag in item.coverage_tags}
        missing = sorted(set(self.required_coverage_tags) - covered)
        if missing:
            raise ValueError(f"failure catalog is missing required coverage tags: {missing}")
        required_components = {"picking", "collision", "navigation", "occlusion", "spatial_audio", "visual_rendering"}
        missing_components = sorted(required_components - set(self.component_fallbacks))
        if missing_components:
            raise ValueError(f"component fallbacks are missing: {missing_components}")
        return self


class FailureDiagnosticManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: Literal["sip.failure-diagnostic/v1"] = Field(default="sip.failure-diagnostic/v1", alias="schema", serialization_alias="schema")
    failure_record_id: str
    code: str
    occurred_at: datetime
    tenant_id: str
    project_id: str
    operation_id: str | None
    run_id: str | None
    diagnostic: dict[str, Any]
    diagnostic_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    raw_sensitive_data_retained: Literal[False] = False
    publication_blocked: bool
    audit_required: bool


class RecoveryLineage(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: Literal["sip.failure-recovery/v1"] = Field(default="sip.failure-recovery/v1", alias="schema", serialization_alias="schema")
    recovery_id: str
    failed_record_id: str
    failed_run_id: str | None
    new_run_id: str
    new_revision_id: str | None
    preserves_failed_evidence: Literal[True] = True
    rewrites_failed_record: Literal[False] = False
    created_at: datetime


class CataloguedFailure(SIPError):
    def __init__(self, definition: FailureDefinition, manifest: FailureDiagnosticManifest) -> None:
        status_code = 503 if definition.retry_class in {"transient", "capacity"} else 409
        super().__init__(
            definition.code,
            definition.customer_message,
            {
                "failure_record_id": manifest.failure_record_id,
                "diagnostic_hash": manifest.diagnostic_hash,
                "remediation": definition.remediation,
                "publication_action": definition.publication_action,
            },
            status_code,
            retryable=definition.retryable,
        )
        self.definition = definition
        self.manifest = manifest


class FailureCatalog:
    """Versioned failure taxonomy with safe diagnostics and publication controls."""

    def __init__(self, document: FailureCatalogDocument) -> None:
        self.document = document
        self._by_code = {item.code: item for item in document.failures}
        self._aliases = {alias: item.code for item in document.failures for alias in item.compatibility_aliases}

    @classmethod
    def load(cls, path: Path | None = None) -> "FailureCatalog":
        import json

        path = path or Path(__file__).resolve().parents[2] / "governance" / "failure-catalog.json"
        try:
            document = FailureCatalogDocument.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            raise ValidationError("FAILURE_CATALOG_INVALID", "failure catalog is invalid", {"path": str(path)}) from exc
        return cls(document)

    def resolve(self, code: str) -> FailureDefinition:
        canonical = self._aliases.get(code, code)
        definition = self._by_code.get(canonical)
        if definition is None:
            raise ValidationError("FAILURE_CODE_UNKNOWN", "failure code is not registered", {"code": code})
        return definition

    def create_diagnostic(
        self,
        code: str,
        *,
        tenant_id: str,
        project_id: str,
        operation_id: str | None = None,
        run_id: str | None = None,
        diagnostic: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> FailureDiagnosticManifest:
        definition = self.resolve(code)
        safe = self._sanitize_diagnostic(definition, diagnostic or {})
        diagnostic_hash = canonical_sha256(safe)
        return FailureDiagnosticManifest(
            failure_record_id=new_uuid(),
            code=definition.code,
            occurred_at=occurred_at or datetime.now(UTC),
            tenant_id=tenant_id,
            project_id=project_id,
            operation_id=operation_id,
            run_id=run_id,
            diagnostic=safe,
            diagnostic_hash=diagnostic_hash,
            publication_blocked=definition.publication_action in {"block", "withdraw"},
            audit_required=definition.audit_required,
        )

    def raise_failure(self, code: str, **context: Any) -> None:
        definition = self.resolve(code)
        manifest = self.create_diagnostic(code, **context)
        raise CataloguedFailure(definition, manifest)

    def assert_publication_allowed(self, code: str) -> None:
        definition = self.resolve(code)
        if definition.publication_action in {"block", "withdraw"}:
            raise ConflictError(
                "FAILURE_BLOCKS_PUBLICATION",
                "candidate cannot be published while an unsafe failure is active",
                {"failure_code": definition.code, "publication_action": definition.publication_action},
            )

    def recovery_lineage(
        self,
        failed: FailureDiagnosticManifest,
        *,
        new_run_id: str,
        new_revision_id: str | None = None,
        created_at: datetime | None = None,
    ) -> RecoveryLineage:
        if not new_run_id or new_run_id == failed.run_id:
            raise ValidationError(
                "RECOVERY_LINEAGE_INVALID",
                "recovery must create a distinct run identifier",
                {"failed_run_id": failed.run_id, "new_run_id": new_run_id},
            )
        return RecoveryLineage(
            recovery_id=new_uuid(),
            failed_record_id=failed.failure_record_id,
            failed_run_id=failed.run_id,
            new_run_id=new_run_id,
            new_revision_id=new_revision_id,
            created_at=created_at or datetime.now(UTC),
        )

    def hybrid_safe_state(self, code: str) -> dict[str, Any]:
        definition = self.resolve(code)
        return {
            "failure_code": definition.code,
            "publication_allowed": definition.publication_action == "none",
            "partial_publication_allowed": False,
            "preserve": {
                "source": True,
                "metric": True,
                "visual": True,
                "evidence": True,
                "prior_accepted_interaction": True,
                "failed_provider_evidence": True,
            },
            "affected_representations": definition.affected_representations,
            "fallback": definition.fallback,
        }

    def component_fallback(self, component: str) -> str:
        try:
            return self.document.component_fallbacks[component]
        except KeyError as exc:
            raise ValidationError("COMPONENT_FALLBACK_UNKNOWN", "component fallback is not registered", {"component": component}) from exc

    @staticmethod
    def _sanitize_diagnostic(definition: FailureDefinition, diagnostic: dict[str, Any]) -> dict[str, Any]:
        forbidden_fragments = {
            "raw",
            "photo",
            "image",
            "frame_bytes",
            "transcript",
            "recording",
            "secret",
            "token",
            "password",
            "biometric",
            "precise_coordinates",
        }
        safe: dict[str, Any] = {}
        allowed = set(definition.diagnostic_fields)
        for key, value in diagnostic.items():
            normalized = key.lower()
            if key not in allowed or any(fragment in normalized for fragment in forbidden_fragments):
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                safe[key] = value
            elif isinstance(value, list) and len(value) <= 32 and all(isinstance(item, (str, int, float, bool)) for item in value):
                safe[key] = value
            elif isinstance(value, dict) and len(value) <= 32 and all(
                isinstance(k, str) and isinstance(v, (str, int, float, bool, type(None))) for k, v in value.items()
            ):
                safe[key] = value
        if len(canonical_json(safe)) > 32_768:
            raise ValidationError("FAILURE_DIAGNOSTIC_TOO_LARGE", "diagnostic manifest exceeds the bounded safe size")
        return safe
