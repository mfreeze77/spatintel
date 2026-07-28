from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from .audit import AuditService
from .canonical import canonical_sha256, new_uuid
from .database import AgentProposalRow, Database, RepresentationAssetRow
from .errors import AuthorizationError, NotFoundError, ValidationError
from .events import OutboxEventFactory
from .models import AuthorityClass, SignedPrincipal, SourceClass
from .policy import PolicyService
from .search import SearchService
from .spatial_query import SearchQuerySpec


class AgentToolSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["sip.agent-tool/v1"] = "sip.agent-tool/v1"
    name: str
    description: str
    required_permissions: list[str] = Field(min_length=1)
    side_effect: Literal["none", "review_proposal"]
    idempotency: Literal["read_only", "idempotency_key_required"]
    evidence_requirements: list[str] = Field(min_length=1)
    allowed_source_classes: list[SourceClass] = Field(min_length=1)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    authority_ceiling: Literal["none", "inferred", "metric_unverified"]
    prohibited_actions: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def enforce_agent_boundary(self) -> "AgentToolSpec":
        forbidden = {
            "publish_scene",
            "verify_measurement",
            "alter_consent",
            "expand_audience",
            "life_safety_control",
            "impersonate_person",
            "delete_evidence",
        }
        if not forbidden.issubset(set(self.prohibited_actions)):
            raise ValueError("agent tools must explicitly prohibit all authority-escalating actions")
        return self


class GroundedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=4_000)
    claim_type: Literal["fact", "inference", "proposal", "unknown"]
    entity_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_class: SourceClass | None = None

    @model_validator(mode="after")
    def require_grounding(self) -> "GroundedClaim":
        if self.claim_type == "fact" and (not self.evidence_ids or not self.entity_ids):
            raise ValueError("factual agent claims require entity and evidence identifiers")
        if self.claim_type == "inference" and not self.evidence_ids:
            raise ValueError("inference must cite supporting evidence")
        return self


class AgentAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["sip.agent-answer/v1"] = "sip.agent-answer/v1"
    claims: list[GroundedClaim]
    generated_content: Literal[True] = True
    persistent_label: Literal["AI-generated; verify against cited evidence"] = "AI-generated; verify against cited evidence"
    refused: bool = False
    refusal_code: str | None = None


class AgentProposalContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    state: Literal["review_required"] = "review_required"
    rationale: str
    affected_resource_ids: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    required_reviewer: str
    proposed_by: str
    authority: Literal["inferred"] = "inferred"
    auto_committed: Literal[False] = False
    publication_permission: Literal[False] = False


class AgentToolRegistry:
    def __init__(self) -> None:
        prohibited = [
            "publish_scene",
            "verify_measurement",
            "alter_consent",
            "expand_audience",
            "life_safety_control",
            "impersonate_person",
            "delete_evidence",
        ]
        common_sources = list(SourceClass)
        self._tools = {
            "search_evidence": AgentToolSpec(
                name="search_evidence",
                description="Search authorized spatial and documentary evidence.",
                required_permissions=["scene:read"],
                side_effect="none",
                idempotency="read_only",
                evidence_requirements=["result source hashes", "entity/evidence identifiers"],
                allowed_source_classes=common_sources,
                input_schema={"$ref": "https://schemas.sip.local/v1.1.0/spatial-query.schema.json"},
                output_schema={"type": "object", "required": ["items", "query_hash", "authorized_count"]},
                authority_ceiling="none",
                prohibited_actions=prohibited,
            ),
            "measure_metric_distance": AgentToolSpec(
                name="measure_metric_distance",
                description="Measure between two points on an accepted metric representation.",
                required_permissions=["scene:read"],
                side_effect="none",
                idempotency="read_only",
                evidence_requirements=["published metric representation", "source asset IDs", "point uncertainty"],
                allowed_source_classes=[SourceClass.DIRECT_CAPTURE, SourceClass.OBSERVED, SourceClass.MEASURED, SourceClass.VERIFIED],
                input_schema={
                    "type": "object",
                    "required": ["representation_id", "point_a", "point_b", "uncertainty_a_m", "uncertainty_b_m"],
                },
                output_schema={
                    "type": "object",
                    "required": ["distance_m", "uncertainty_m", "source_representation_id", "authority"],
                },
                authority_ceiling="metric_unverified",
                prohibited_actions=prohibited,
            ),
            "propose_annotation": AgentToolSpec(
                name="propose_annotation",
                description="Create an uncommitted review proposal grounded in evidence.",
                required_permissions=["scene:read"],
                side_effect="review_proposal",
                idempotency="idempotency_key_required",
                evidence_requirements=["rationale", "affected resources", "source evidence", "confidence", "reviewer role"],
                allowed_source_classes=common_sources,
                input_schema={
                    "type": "object",
                    "required": ["idempotency_key", "rationale", "affected_resource_ids", "evidence_ids", "confidence", "required_reviewer"],
                },
                output_schema={"type": "object", "required": ["proposal_id", "state", "auto_committed"]},
                authority_ceiling="inferred",
                prohibited_actions=prohibited,
            ),
        }

    def list(self) -> list[AgentToolSpec]:
        return [self._tools[name] for name in sorted(self._tools)]

    def get(self, name: str) -> AgentToolSpec:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise NotFoundError("agent_tool", name) from exc


class AgentService:
    _events = OutboxEventFactory()

    def __init__(self, database: Database, policy: PolicyService, search: SearchService, audit: AuditService) -> None:
        self.database = database
        self.policy = policy
        self.search = search
        self.audit = audit
        self.registry = AgentToolRegistry()

    def list_tools(self, *, principal: SignedPrincipal, project_id: str) -> list[dict[str, Any]]:
        self.policy.require(principal, action="scene:read", tenant_id=principal.tenant_id, project_id=project_id)
        return [tool.model_dump(mode="json") for tool in self.registry.list()]

    def execute(
        self,
        *,
        principal: SignedPrincipal,
        project_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        tool = self.registry.get(tool_name)
        for permission in tool.required_permissions:
            self.policy.require(principal, action=permission, tenant_id=principal.tenant_id, project_id=project_id)
        if tool_name == "search_evidence":
            spec = SearchQuerySpec.model_validate(
                {**arguments, "tenant_id": principal.tenant_id, "project_id": project_id}
            )
            result = self.search.query(principal=principal, spec=spec)
        elif tool_name == "measure_metric_distance":
            result = self._measure_metric(principal=principal, project_id=project_id, arguments=arguments)
        elif tool_name == "propose_annotation":
            result = self._propose(principal=principal, project_id=project_id, arguments=arguments)
        else:  # Registry lookup already prevents this; retain fail-closed dispatch.
            raise ValidationError("AGENT_TOOL_UNIMPLEMENTED", "agent tool has no constrained implementation")
        self.audit.append(
            tenant_id=principal.tenant_id,
            project_id=project_id,
            actor_id=principal.subject_id,
            action=f"agent_tool:{tool_name}",
            resource_type="agent_tool",
            resource_id=tool_name,
            outcome="allowed",
            details={"side_effect": tool.side_effect, "result_hash": canonical_sha256(result)},
        )
        return result

    def answer(self, claims: list[dict[str, Any]]) -> dict[str, Any]:
        parsed = [GroundedClaim.model_validate(claim) for claim in claims]
        return AgentAnswer(claims=parsed).model_dump(mode="json")

    @staticmethod
    def safe_refusal(*, code: str, message: str) -> dict[str, Any]:
        claim = GroundedClaim(text=message, claim_type="unknown")
        return AgentAnswer(claims=[claim], refused=True, refusal_code=code).model_dump(mode="json")

    def evaluate_request(self, request_kind: str, *, simulation_enabled: bool = False, consent_verified: bool = False) -> dict[str, Any]:
        if request_kind in {"life_safety_control", "access_control_command", "fire_alarm_command"}:
            return self.safe_refusal(
                code="AGENT_LIFE_SAFETY_CONTROL_DENIED",
                message="Spatial agents cannot operate life-safety or access-control systems.",
            )
        if request_kind in {"deceased_first_person", "voice_simulation", "likeness_simulation"} and not (
            simulation_enabled and consent_verified
        ):
            return self.safe_refusal(
                code="AGENT_PERSON_SIMULATION_DISABLED",
                message="Person simulation is disabled until explicit consent and safety gates are enabled.",
            )
        return {"allowed": True, "request_kind": request_kind}

    def _measure_metric(self, *, principal: SignedPrincipal, project_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        representation_id = str(arguments.get("representation_id", ""))
        point_a = _point(arguments.get("point_a"), "point_a")
        point_b = _point(arguments.get("point_b"), "point_b")
        uncertainty_a = _uncertainty(arguments.get("uncertainty_a_m"), "uncertainty_a_m")
        uncertainty_b = _uncertainty(arguments.get("uncertainty_b_m"), "uncertainty_b_m")
        with self.database.session() as session:
            representation = session.scalar(
                select(RepresentationAssetRow).where(
                    RepresentationAssetRow.representation_id == representation_id,
                    RepresentationAssetRow.tenant_id == principal.tenant_id,
                    RepresentationAssetRow.project_id == project_id,
                )
            )
        if not representation:
            raise NotFoundError("representation", representation_id)
        if representation.kind != "metric" or representation.state != "published":
            raise AuthorizationError(
                "AGENT_MEASUREMENT_SOURCE_DENIED",
                "agent measurement requires an accepted published metric representation",
            )
        if representation.authority_class not in {AuthorityClass.METRIC.value, AuthorityClass.FIELD_VERIFIED.value}:
            raise AuthorizationError(
                "AGENT_MEASUREMENT_AUTHORITY_DENIED",
                "representation authority is not eligible for metric measurement",
            )
        distance = math.dist(point_a, point_b)
        uncertainty = math.sqrt(uncertainty_a**2 + uncertainty_b**2)
        source_ids = sorted(set(representation.provenance_json.get("source_ids", [])))
        if not source_ids:
            raise ValidationError("AGENT_MEASUREMENT_PROVENANCE_INCOMPLETE", "metric representation lacks source evidence")
        return {
            "distance_m": distance,
            "uncertainty_m": uncertainty,
            "source_representation_id": representation_id,
            "source_asset_ids": source_ids,
            "coordinate_frame_id": representation.coordinate_frame_id,
            "authority": representation.authority_class,
            "verified": representation.authority_class == AuthorityClass.FIELD_VERIFIED.value,
            "certification": "none",
            "warning": "Phone-derived or reconstructed geometry is not survey-grade unless independently verified.",
        }

    def _propose(self, *, principal: SignedPrincipal, project_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        required = {
            "idempotency_key",
            "rationale",
            "affected_resource_ids",
            "evidence_ids",
            "confidence",
            "required_reviewer",
        }
        missing = sorted(required - set(arguments))
        if missing:
            raise ValidationError("AGENT_PROPOSAL_FIELDS_REQUIRED", "agent proposal is incomplete", {"missing": missing})
        confidence = float(arguments["confidence"])
        if not 0 <= confidence <= 1:
            raise ValidationError("AGENT_PROPOSAL_CONFIDENCE_INVALID", "proposal confidence must be in [0,1]")
        if not arguments["affected_resource_ids"] or not arguments["evidence_ids"]:
            raise ValidationError("AGENT_PROPOSAL_EVIDENCE_REQUIRED", "proposal requires affected resources and evidence")
        idempotency_key = str(arguments["idempotency_key"])
        payload_hash = canonical_sha256(arguments)
        with self.database.session() as session:
            existing = session.scalar(
                select(AgentProposalRow).where(
                    AgentProposalRow.tenant_id == principal.tenant_id,
                    AgentProposalRow.project_id == project_id,
                    AgentProposalRow.idempotency_key == idempotency_key,
                )
            )
            if existing:
                if existing.input_hash != payload_hash:
                    raise ValidationError(
                        "AGENT_PROPOSAL_IDEMPOTENCY_CONFLICT",
                        "idempotency key was reused with different input",
                    )
                return dict(existing.proposal_json)
            result = {
                "proposal_id": new_uuid(),
                "state": "review_required",
                "rationale": str(arguments["rationale"]),
                "affected_resource_ids": list(arguments["affected_resource_ids"]),
                "evidence_ids": list(arguments["evidence_ids"]),
                "confidence": confidence,
                "required_reviewer": str(arguments["required_reviewer"]),
                "proposed_by": principal.subject_id,
                "authority": "inferred",
                "auto_committed": False,
                "publication_permission": False,
            }
            session.add(
                AgentProposalRow(
                    proposal_id=result["proposal_id"],
                    tenant_id=principal.tenant_id,
                    project_id=project_id,
                    idempotency_key=idempotency_key,
                    input_hash=payload_hash,
                    proposal_json=result,
                    state="review_required",
                    created_by=principal.subject_id,
                )
            )
            session.add(
                self._events.create(
                    session,
                    event_type="agent.proposal_created",
                    schema_version="1.0.0",
                    tenant_id=principal.tenant_id,
                    project_id=project_id,
                    aggregate_type="agent_proposal",
                    aggregate_id=result["proposal_id"],
                    payload={
                        "proposal_id": result["proposal_id"],
                        "input_hash": payload_hash,
                        "state": "review_required",
                        "evidence_count": len(result["evidence_ids"]),
                        "affected_resource_count": len(result["affected_resource_ids"]),
                    },
                    producer="search-service",
                    actor_id=principal.subject_id,
                    workload_identity=None,
                    correlation_id=result["proposal_id"],
                )
            )
            self.audit.append(
                tenant_id=principal.tenant_id,
                project_id=project_id,
                actor_id=principal.subject_id,
                action="agent_proposal:create",
                resource_type="agent_proposal",
                resource_id=result["proposal_id"],
                outcome="allowed",
                details={
                    "input_hash": payload_hash,
                    "confidence": confidence,
                    "state": "review_required",
                },
                session=session,
            )
            return result


def _point(value: Any, name: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 3:
        raise ValidationError("AGENT_MEASUREMENT_POINT_INVALID", f"{name} must be a three-element point")
    point = [float(item) for item in value]
    if any(not math.isfinite(item) for item in point):
        raise ValidationError("AGENT_MEASUREMENT_POINT_INVALID", f"{name} must contain finite values")
    return point


def _uncertainty(value: Any, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValidationError("AGENT_MEASUREMENT_UNCERTAINTY_INVALID", f"{name} must be a positive finite value")
    return result
