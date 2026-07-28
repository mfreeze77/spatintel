from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

from .canonical import canonical_json, canonical_sha256, new_uuid
from .errors import AuthenticationError, ValidationError
from .observability import normalize_traceparent
from .security import SignedTokenCodec
from .worker_manifest import WorkerManifest, WorkerResourceLimits


class OutputStagingScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_id: str
    mode: Literal["write_only_quarantine"] = "write_only_quarantine"
    tenant_id: str
    project_id: str
    operation_id: str
    maximum_bytes: int = Field(gt=0)
    expires_at: datetime


class WorkerLease(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["sip.worker-lease/v1"] = "sip.worker-lease/v1"
    lease_id: str
    run_id: str
    operation_id: str
    attempt: int = Field(ge=1)
    operation_type: str
    adapter_profile: str
    input_manifest: dict[str, Any]
    input_manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    input_byte_count: int = Field(ge=0)
    traceparent: str | None = None
    resume_checkpoint: dict[str, Any] = Field(default_factory=dict)
    resume_progress: float = Field(default=0.0, ge=0, le=1)
    output_staging_scope: OutputStagingScope
    resource_limits: WorkerResourceLimits
    deadline_at: datetime
    cancellation_token: str = Field(min_length=32)
    workload_identity: str
    capabilities: list[str] = Field(min_length=1)
    worker_manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    issued_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def check_integrity(self) -> "WorkerLease":
        if self.traceparent != normalize_traceparent(self.traceparent):
            raise ValueError("worker lease traceparent is not normalized")
        if canonical_sha256(self.input_manifest) != self.input_manifest_hash:
            raise ValueError("lease input manifest hash mismatch")
        if len(canonical_json(self.input_manifest)) != self.input_byte_count:
            raise ValueError("lease input byte count mismatch")
        if self.operation_type not in self.capabilities:
            raise ValueError("lease capability does not include operation type")
        if self.deadline_at > self.expires_at:
            raise ValueError("lease deadline cannot exceed lease expiry")
        if self.output_staging_scope.operation_id != self.operation_id:
            raise ValueError("output staging scope is not bound to operation")
        if self.output_staging_scope.expires_at != self.expires_at:
            raise ValueError("output staging scope expiry must match lease expiry")
        if self.issued_at >= self.deadline_at:
            raise ValueError("lease deadline must be after issue time")
        return self

    @property
    def lease_hash(self) -> str:
        return canonical_sha256(self.model_dump(mode="json"))


class SignedWorkerLease(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lease: WorkerLease
    token: str


class ProgressRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1)
    stage: str = Field(min_length=1)
    progress: float = Field(ge=0, le=1)
    completed_units: int | None = Field(default=None, ge=0)
    total_units: int | None = Field(default=None, ge=0)
    unit: str | None = None
    warnings: list[str] = Field(default_factory=list)
    quality: dict[str, Any] = Field(default_factory=dict)
    resource_use: dict[str, float | int] = Field(default_factory=dict)
    safe_to_resume: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)
    checkpoint_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def check_integrity(self) -> "ProgressRecord":
        if self.total_units is not None and self.completed_units is None:
            raise ValueError("completed units are required when total units are declared")
        if self.completed_units is not None and self.total_units is not None and self.completed_units > self.total_units:
            raise ValueError("completed units cannot exceed total units")
        payload = self.model_dump(mode="json", exclude={"checkpoint_hash"})
        if self.checkpoint_hash != canonical_sha256(payload):
            raise ValueError("checkpoint hash does not match progress record")
        return self


class CandidateRequest(BaseModel):
    """Admitted request to stage a derived representation for independent review.

    Representation kind, source class, authority class, and provider executable
    identity are deliberately omitted. The control plane derives them from the
    signed operation type and immutable worker manifest; a caller cannot elevate
    a worker result by changing request fields.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["sip.representation-candidate-request/v1"] = (
        "sip.representation-candidate-request/v1"
    )
    scene_id: str = Field(min_length=1)
    source_scene_revision_id: str | None = None
    coordinate_frame_id: str = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    region: str = Field(min_length=1)
    classification: str = Field(default="internal", min_length=1)
    source_asset_ids: list[str] = Field(min_length=1)
    retention_class: str = Field(default="derived-review", min_length=1)
    intended_uses: list[str] = Field(min_length=1)
    prohibited_uses: list[str] = Field(default_factory=list)
    quality: dict[str, Any] = Field(default_factory=dict)
    support_map: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    media_type: str = Field(default="application/vnd.sip.worker-result+json", min_length=1)

    @model_validator(mode="after")
    def check_policy(self) -> "CandidateRequest":
        for name, values in (
            ("source asset IDs", self.source_asset_ids),
            ("intended uses", self.intended_uses),
            ("prohibited uses", self.prohibited_uses),
            ("limitations", self.limitations),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must be unique")
        overlap = sorted(set(self.intended_uses) & set(self.prohibited_uses))
        if overlap:
            raise ValueError(f"uses cannot be both intended and prohibited: {overlap}")
        return self


class CandidatePackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["sip.representation-candidate/v1"] = "sip.representation-candidate/v1"
    candidate_id: str
    representation_id: str
    asset_id: str
    asset_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    media_type: str
    operation_id: str
    operation_type: str
    state: Literal["quarantined"] = "quarantined"
    output_role: str
    representation_kind: str
    coordinate_frame_id: str
    source_scene_revision_id: str | None = None
    source_asset_ids: list[str] = Field(min_length=1)
    payload_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    parameters_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    environment_manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    provider_id: str
    provider_version: str
    provider_executable_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    worker_receipt_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    authority_ceiling: str
    disposable: bool
    lossy: bool
    intended_uses: list[str] = Field(default_factory=list)
    prohibited_uses: list[str] = Field(default_factory=lambda: ["verified_measurement", "automatic_publication"])
    provider_metrics: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    publication_permission: Literal[False] = False
    independent_validation_required: Literal[True] = True
    human_review_required: bool = True

    @model_validator(mode="after")
    def check_policy(self) -> "CandidatePackage":
        if "automatic_publication" not in self.prohibited_uses:
            raise ValueError("candidate packages must prohibit automatic publication")
        if self.authority_ceiling in {"verified", "field_verified", "contract_authoritative"}:
            raise ValueError("worker candidate authority ceiling cannot be authoritative")
        if self.representation_kind == "interaction":
            if self.authority_ceiling != "derived_non_authoritative":
                raise ValueError("interaction candidates require the exact derived_non_authoritative authority ceiling")
            if not self.disposable:
                raise ValueError("interaction candidates must be disposable")
        if self.asset_sha256 != self.payload_hash:
            raise ValueError("candidate asset digest must match staged payload hash")
        if len(self.source_asset_ids) != len(set(self.source_asset_ids)):
            raise ValueError("candidate source asset IDs must be unique")
        return self

    @property
    def candidate_core_hash(self) -> str:
        return canonical_sha256(self.model_dump(mode="json", exclude={"worker_receipt_hash"}))


class WorkerReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["sip.worker-receipt/v1"] = "sip.worker-receipt/v1"
    lease_id: str
    run_id: str
    operation_id: str
    operation_type: str
    adapter_profile: str
    attempt: int = Field(ge=1)
    worker_name: str
    workload_identity: str
    lease_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    worker_manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    runtime_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    protocol_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    sandbox_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    input_manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    parameters_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    traceparent: str | None = None
    handler_output_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    candidate_core_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    resume_checkpoint_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    checkpoints: list[ProgressRecord]
    execution_environment: dict[str, Any]
    model_artifacts: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    completed_at: datetime
    elapsed_wall_seconds: float = Field(ge=0)
    elapsed_cpu_seconds: float = Field(ge=0)
    maximum_rss_bytes: int = Field(ge=0)
    input_byte_count: int = Field(ge=0)
    handler_output_byte_count: int = Field(ge=0)
    software_version: str
    code_commit: str
    container_digest: str
    python_version: str
    platform_profile: str
    environment_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    shell_access_allowed: Literal[False] = False
    network_access_allowed: Literal[False] = False
    publication_permission: Literal[False] = False
    receipt_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def check_integrity(self, info: ValidationInfo) -> "WorkerReceipt":
        if self.traceparent != normalize_traceparent(self.traceparent):
            raise ValueError("worker receipt traceparent is not normalized")
        if self.completed_at < self.started_at:
            raise ValueError("worker receipt completion precedes start")
        if not self.checkpoints:
            raise ValueError("worker receipt must retain checkpoints")
        sequences = [item.sequence for item in self.checkpoints]
        if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
            raise ValueError("worker receipt checkpoint sequences must be unique and monotonic")
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        skip_digest = bool((info.context or {}).get("skip_receipt_digest"))
        if not skip_digest and self.receipt_sha256 != canonical_sha256(payload):
            raise ValueError("worker receipt digest does not match canonical contents")
        return self

    @classmethod
    def seal(cls, payload: dict[str, Any]) -> "WorkerReceipt":
        """Normalize a receipt, then seal and revalidate its canonical digest."""
        draft = cls.model_validate(
            {**payload, "receipt_sha256": "0" * 64},
            context={"skip_receipt_digest": True},
        )
        normalized = draft.model_dump(mode="json", exclude={"receipt_sha256"})
        return cls.model_validate({**normalized, "receipt_sha256": canonical_sha256(normalized)})


class WorkerLeaseAuthority:
    """Issues and verifies signed, immutable worker lease envelopes."""

    def __init__(self, signing_key: bytes, *, issuer: str = "sip-worker-control") -> None:
        self.codec = SignedTokenCodec(signing_key, issuer=issuer)

    def issue(
        self,
        *,
        operation: dict[str, Any],
        manifest: WorkerManifest,
        lease_seconds: int,
        adapter_profile: str = "deterministic-reference",
        now: datetime | None = None,
    ) -> SignedWorkerLease:
        if operation["operation_type"] not in manifest.capabilities:
            raise ValidationError("WORKER_CAPABILITY_DENIED", "manifest does not permit operation type")
        now = now or datetime.now(UTC)
        expiry = now + timedelta(seconds=lease_seconds)
        lease = WorkerLease(
            lease_id=new_uuid(),
            run_id=new_uuid(),
            operation_id=operation["operation_id"],
            attempt=int(operation["attempt"]),
            operation_type=operation["operation_type"],
            adapter_profile=adapter_profile,
            input_manifest=operation["input"],
            input_manifest_hash=operation["input_manifest_hash"],
            input_byte_count=int(operation["input_byte_count"]),
            traceparent=operation.get("traceparent"),
            resume_checkpoint=dict(operation.get("checkpoint") or {}),
            resume_progress=float(operation.get("progress") or 0.0),
            output_staging_scope=OutputStagingScope(
                scope_id=new_uuid(),
                tenant_id=operation["tenant_id"],
                project_id=operation["project_id"],
                operation_id=operation["operation_id"],
                maximum_bytes=manifest.resource_limits.max_output_bytes,
                expires_at=expiry,
            ),
            resource_limits=manifest.resource_limits,
            deadline_at=now + timedelta(seconds=min(lease_seconds, manifest.resource_limits.max_wall_seconds)),
            cancellation_token=secrets.token_urlsafe(32),
            workload_identity=manifest.workload_identity,
            capabilities=manifest.capabilities,
            worker_manifest_sha256=manifest.manifest_sha256,
            issued_at=now,
            expires_at=expiry,
        )
        token = self.codec.encode(
            {
                "kind": "sip.worker-lease/v1",
                "lease_hash": lease.lease_hash,
                "lease_id": lease.lease_id,
                "run_id": lease.run_id,
                "operation_id": lease.operation_id,
                "attempt": lease.attempt,
                "operation_type": lease.operation_type,
                "workload_identity": lease.workload_identity,
                "worker_manifest_sha256": lease.worker_manifest_sha256,
                "traceparent": lease.traceparent,
            },
            ttl_seconds=lease_seconds,
        )
        return SignedWorkerLease(lease=lease, token=token)

    def verify(self, signed: SignedWorkerLease, manifest: WorkerManifest, *, now: datetime | None = None) -> WorkerLease:
        claims = self.codec.decode(signed.token)
        lease = signed.lease
        now = now or datetime.now(UTC)
        expected = {
            "kind": "sip.worker-lease/v1",
            "lease_hash": lease.lease_hash,
            "lease_id": lease.lease_id,
            "run_id": lease.run_id,
            "operation_id": lease.operation_id,
            "attempt": lease.attempt,
            "operation_type": lease.operation_type,
            "workload_identity": lease.workload_identity,
            "worker_manifest_sha256": lease.worker_manifest_sha256,
            "traceparent": lease.traceparent,
        }
        for key, value in expected.items():
            if claims.get(key) != value:
                raise AuthenticationError("WORKER_LEASE_CLAIM_MISMATCH", "worker lease claim does not match envelope", {"claim": key})
        if lease.expires_at < now or lease.deadline_at < now:
            raise AuthenticationError("WORKER_LEASE_EXPIRED", "worker lease has expired")
        if lease.worker_manifest_sha256 != manifest.manifest_sha256 or lease.workload_identity != manifest.workload_identity:
            raise AuthenticationError("WORKER_LEASE_IDENTITY_MISMATCH", "worker lease is not bound to this worker manifest")
        if lease.operation_type not in manifest.capabilities:
            raise AuthenticationError("WORKER_LEASE_CAPABILITY_MISMATCH", "worker lease capability is not permitted")
        return lease
