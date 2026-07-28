from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Classification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    CRITICAL_INFRASTRUCTURE = "critical_infrastructure"
    BIOMETRIC = "biometric"
    MINOR = "minor"


class SourceClass(StrEnum):
    DIRECT_CAPTURE = "direct_capture"
    OBSERVED = "observed"
    MEASURED = "measured"
    VERIFIED = "verified"
    DESIGN = "design"
    PROPOSED = "proposed"
    INFERRED = "inferred"
    GENERATED = "generated"
    RECALLED = "recalled"
    CORROBORATED = "corroborated"
    DISPUTED = "disputed"
    SUPERSEDED = "superseded"


class AuthorityClass(StrEnum):
    NONE = "none"
    EVIDENCE = "evidence"
    METRIC = "metric"
    DESIGN = "design"
    VISUAL = "visual"
    DERIVED_NON_AUTHORITATIVE = "derived_non_authoritative"
    FIELD_VERIFIED = "field_verified"
    HISTORICAL_ASSERTION = "historical_assertion"


class RepresentationKind(StrEnum):
    METRIC = "metric"
    VISUAL = "visual"
    INTERACTION = "interaction"
    DESIGN = "design"
    EVIDENCE = "evidence"


class Audience(StrEnum):
    PRIVATE = "private"
    FAMILY = "family"
    PROJECT = "project"
    OWNER = "owner"
    PUBLIC = "public"


class OperationState(StrEnum):
    PENDING = "pending"
    LEASED = "leased"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    QUARANTINED = "quarantined"


class ProvenanceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ids: list[str] = Field(min_length=1)
    run_id: str | None = None
    code_commit: str | None = None
    container_digest: str | None = None
    model_manifest_id: str | None = None
    model_checkpoint_hash: str | None = None
    parameters_hash: str | None = None
    environment_hash: str | None = None
    output_hash: str | None = None
    validation_result_id: str | None = None
    notes: str | None = None


class CoordinateFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frame_id: str
    name: str
    parent_frame_id: str | None = None
    convention: str = "right_handed_y_up_meters"
    units: str = "meter"
    transform_to_parent: list[list[float]] | None = None
    uncertainty_m: float | None = Field(default=None, ge=0)

    @field_validator("transform_to_parent")
    @classmethod
    def validate_transform(cls, value: list[list[float]] | None) -> list[list[float]] | None:
        if value is not None and (len(value) != 4 or any(len(row) != 4 for row in value)):
            raise ValueError("transform_to_parent must be 4x4")
        return value


class EvidenceLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_class: SourceClass
    authority_class: AuthorityClass
    confidence: float = Field(ge=0, le=1)
    provenance: ProvenanceRef
    generated: bool = False
    warning: str | None = None


class SignedPrincipal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str
    tenant_id: str
    project_ids: list[str] = []
    roles: list[str] = []
    purposes: list[str] = []
    audience: Audience = Audience.PRIVATE
    attributes: dict[str, Any] = {}
