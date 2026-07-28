from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .canonical import canonical_sha256
from .errors import ValidationError
from .models import AuthorityClass, SourceClass


class Bounds3D(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum: list[float] = Field(min_length=3, max_length=3, alias="min")
    maximum: list[float] = Field(min_length=3, max_length=3, alias="max")

    @model_validator(mode="after")
    def validate_bounds(self) -> "Bounds3D":
        if any(not math.isfinite(value) for value in [*self.minimum, *self.maximum]):
            raise ValueError("bounds values must be finite")
        if any(self.maximum[index] < self.minimum[index] for index in range(3)):
            raise ValueError("bounds maximum must not precede minimum")
        return self

    @property
    def volume(self) -> float:
        return math.prod(self.maximum[index] - self.minimum[index] for index in range(3))


class SpatialPredicate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operator: Literal["within", "intersects", "near", "visible_from", "on_level"]
    frame_id: str | None = None
    bounds: Bounds3D | None = None
    point: list[float] | None = Field(default=None, min_length=3, max_length=3)
    distance_m: float | None = Field(default=None, ge=0, le=100_000)
    observer_entity_id: str | None = None
    level_id: str | None = None

    @model_validator(mode="after")
    def validate_operator_fields(self) -> "SpatialPredicate":
        if self.operator in {"within", "intersects"}:
            if not self.frame_id or self.bounds is None:
                raise ValueError(f"{self.operator} requires frame_id and bounds")
        elif self.operator == "near":
            if not self.frame_id or self.point is None or self.distance_m is None:
                raise ValueError("near requires frame_id, point, and distance_m")
        elif self.operator == "visible_from":
            if not self.frame_id or (self.point is None and not self.observer_entity_id):
                raise ValueError("visible_from requires frame_id and observer_entity_id or point")
        elif self.operator == "on_level" and not self.level_id:
            raise ValueError("on_level requires level_id")
        if self.point is not None and any(not math.isfinite(value) for value in self.point):
            raise ValueError("spatial point values must be finite")
        return self


class TemporalInterval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_interval(self) -> "TemporalInterval":
        if self.end < self.start:
            raise ValueError("temporal interval end precedes start")
        return self


class GraphTraversal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_entity_ids: list[str] = Field(min_length=1, max_length=100)
    relationship_types: list[str] = Field(min_length=1, max_length=20)
    direction: Literal["outbound", "inbound", "either"] = "either"
    max_depth: int = Field(default=1, ge=1, le=5)


class SearchQueryInput(BaseModel):
    """Safe public query AST; tenant and project scope are injected server-side."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["sip.spatial-query/v1"] = "sip.spatial-query/v1"
    full_text: str | None = Field(default=None, max_length=4_000)
    embedding: list[float] | None = Field(default=None, max_length=4_096)
    embedding_model_manifest_id: str | None = None
    entity_types: list[str] = Field(default_factory=list, max_length=100)
    floor_ids: list[str] = Field(default_factory=list, max_length=100)
    room_ids: list[str] = Field(default_factory=list, max_length=100)
    spatial: list[SpatialPredicate] = Field(default_factory=list, max_length=20)
    temporal_interval: TemporalInterval | None = None
    changed_between: TemporalInterval | None = None
    graph: GraphTraversal | None = None
    source_classes: list[SourceClass] = Field(default_factory=list)
    authority_classes: list[AuthorityClass] = Field(default_factory=list)
    minimum_confidence: float | None = Field(default=None, ge=0, le=1)
    tags: list[str] = Field(default_factory=list, max_length=100)
    workflow_statuses: list[str] = Field(default_factory=list, max_length=100)
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    scene_commit_id: str | None = None
    purpose: str | None = None
    critical_workflow: bool = False
    include_snippets: bool = True
    limit: int = Field(default=50, ge=1, le=200)
    timeout_ms: int = Field(default=2_000, ge=10, le=5_000)

    @model_validator(mode="after")
    def validate_semantic_query(self) -> "SearchQueryInput":
        if self.embedding is not None:
            if not self.embedding or any(not math.isfinite(value) for value in self.embedding):
                raise ValueError("query embedding must contain finite values")
            if not self.embedding_model_manifest_id:
                raise ValueError("semantic query requires embedding_model_manifest_id")
        return self


class SearchQuerySpec(SearchQueryInput):
    """Authorized internal query with server-bound tenant and project scope."""

    tenant_id: str
    project_id: str


class SavedQueryContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    saved_query_id: str
    tenant_id: str
    project_id: str
    name: str
    schema_version: Literal["sip.spatial-query/v1"]
    version: int = Field(ge=1)
    author_id: str
    query: SearchQuerySpec
    permissions: dict[str, Any]
    parameters: dict[str, Any]
    expected_result_contract: dict[str, Any]
    query_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    supersedes_saved_query_id: str | None = None
    created_at: datetime
    immutable: Literal[True] = True


class QueryLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    maximum_complexity: int = Field(default=60, ge=1)
    maximum_results: int = Field(default=200, ge=1)
    maximum_timeout_ms: int = Field(default=5_000, ge=10)
    maximum_spatial_volume_m3: float = Field(default=10_000_000.0, gt=0)


class CompiledSpatialQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["sip.compiled-spatial-query/v1"] = "sip.compiled-spatial-query/v1"
    query: SearchQuerySpec
    query_hash: str
    complexity: int
    spatial_volume_m3: float
    explanation: list[str]
    storage_contract: Literal["authorized-service-query"] = "authorized-service-query"
    raw_sql_exposed: Literal[False] = False


def compile_query(spec: SearchQuerySpec, *, limits: QueryLimits | None = None) -> CompiledSpatialQuery:
    limits = limits or QueryLimits()
    complexity = 1
    explanation: list[str] = [f"tenant={spec.tenant_id}", f"project={spec.project_id}"]
    scalar_filters = (
        len(spec.entity_types)
        + len(spec.floor_ids)
        + len(spec.room_ids)
        + len(spec.source_classes)
        + len(spec.authority_classes)
        + len(spec.tags)
        + len(spec.workflow_statuses)
        + len(spec.evidence_ids)
    )
    complexity += scalar_filters
    if spec.full_text:
        complexity += min(10, max(1, len(spec.full_text.split()) // 4))
        explanation.append("full-text terms are matched after authorization filters")
    if spec.embedding is not None:
        complexity += 12
        explanation.append(f"semantic ranking model={spec.embedding_model_manifest_id}")
    spatial_volume = 0.0
    for predicate in spec.spatial:
        complexity += {"within": 5, "intersects": 6, "near": 5, "visible_from": 12, "on_level": 2}[predicate.operator]
        if predicate.bounds:
            spatial_volume += predicate.bounds.volume
        elif predicate.operator == "near" and predicate.distance_m is not None:
            spatial_volume += (4.0 / 3.0) * math.pi * predicate.distance_m**3
        explanation.append(f"spatial:{predicate.operator} frame={predicate.frame_id or 'semantic-level'}")
    if spec.temporal_interval:
        complexity += 3
        explanation.append("temporal interval overlap")
    if spec.changed_between:
        complexity += 5
        explanation.append("changed-between interval overlap")
    if spec.graph:
        complexity += 4 * spec.graph.max_depth + len(spec.graph.relationship_types)
        explanation.append(f"graph traversal depth<={spec.graph.max_depth}")
    if spec.minimum_confidence is not None:
        explanation.append(f"confidence>={spec.minimum_confidence}")
    if spec.limit > limits.maximum_results:
        raise ValidationError(
            "QUERY_RESULT_LIMIT_EXCEEDED",
            "query result limit exceeds the service budget",
            {"requested": spec.limit, "maximum": limits.maximum_results},
        )
    if spec.timeout_ms > limits.maximum_timeout_ms:
        raise ValidationError(
            "QUERY_TIME_LIMIT_EXCEEDED",
            "query timeout exceeds the service budget",
            {"requested_ms": spec.timeout_ms, "maximum_ms": limits.maximum_timeout_ms},
        )
    if complexity > limits.maximum_complexity:
        raise ValidationError(
            "QUERY_COMPLEXITY_EXCEEDED",
            "query complexity exceeds the service budget",
            {"complexity": complexity, "maximum": limits.maximum_complexity},
        )
    if spatial_volume > limits.maximum_spatial_volume_m3:
        raise ValidationError(
            "QUERY_SPATIAL_VOLUME_EXCEEDED",
            "query spatial volume exceeds the service budget",
            {"volume_m3": spatial_volume, "maximum_m3": limits.maximum_spatial_volume_m3},
        )
    canonical = spec.model_dump(mode="json", by_alias=True)
    return CompiledSpatialQuery(
        query=spec,
        query_hash=canonical_sha256(canonical),
        complexity=complexity,
        spatial_volume_m3=spatial_volume,
        explanation=explanation,
    )


def bounds_intersect(left: Bounds3D, right: Bounds3D) -> bool:
    return all(left.minimum[index] <= right.maximum[index] and right.minimum[index] <= left.maximum[index] for index in range(3))


def bounds_within(inner: Bounds3D, outer: Bounds3D) -> bool:
    return all(outer.minimum[index] <= inner.minimum[index] and inner.maximum[index] <= outer.maximum[index] for index in range(3))


def point_distance_to_bounds(point: list[float], bounds: Bounds3D) -> float:
    squared = 0.0
    for index in range(3):
        delta = max(bounds.minimum[index] - point[index], 0.0, point[index] - bounds.maximum[index])
        squared += delta * delta
    return math.sqrt(squared)


def substitute_parameters(value: Any, parameters: dict[str, Any]) -> Any:
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        name = value[2:-1]
        if name not in parameters:
            raise ValidationError("SAVED_QUERY_PARAMETER_REQUIRED", "saved query parameter is missing", {"parameter": name})
        return parameters[name]
    if isinstance(value, list):
        return [substitute_parameters(item, parameters) for item in value]
    if isinstance(value, dict):
        return {key: substitute_parameters(item, parameters) for key, item in value.items()}
    return value
