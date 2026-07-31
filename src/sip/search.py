from __future__ import annotations

import math
import re
import time
import unicodedata
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from .audit import AuditService
from .canonical import canonical_sha256, new_uuid
from .database import Database, SavedQueryRow, SearchDocumentRow
from .errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from .events import OutboxEventFactory
from .models import Audience, AuthorityClass, Classification, SignedPrincipal, SourceClass
from .spatial_query import (
    Bounds3D,
    CompiledSpatialQuery,
    SearchQuerySpec,
    bounds_intersect,
    bounds_within,
    compile_query,
    point_distance_to_bounds,
    substitute_parameters,
)
from .temporal import db_now

_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_PRIVILEGED_SENSITIVE_ROLES = {"tenant_admin", "project_admin", "privacy_officer", "reviewer"}
_AUDIENCE_ACCESS: dict[str, set[str]] = {
    Audience.PRIVATE.value: {"private", "family", "project", "owner", "public"},
    Audience.FAMILY.value: {"family", "public"},
    Audience.PROJECT.value: {"project", "public"},
    Audience.OWNER.value: {"owner", "project", "public"},
    Audience.PUBLIC.value: {"public"},
}


class SearchService:
    _events = OutboxEventFactory()

    def __init__(self, database: Database, audit: AuditService) -> None:
        self.database = database
        self.audit = audit

    def index(
        self,
        *,
        tenant_id: str,
        project_id: str,
        text: str,
        entity_id: str | None,
        asset_id: str | None,
        embedding: list[float] | None,
        spatial_bounds: dict[str, Any] | None,
        temporal_start: datetime | None,
        temporal_end: datetime | None,
        policy: dict[str, Any],
        entity_type: str | None = None,
        floor_id: str | None = None,
        room_id: str | None = None,
        source_class: str = SourceClass.OBSERVED.value,
        authority_class: str = AuthorityClass.EVIDENCE.value,
        confidence: float = 1.0,
        tags: list[str] | None = None,
        workflow_status: str | None = None,
        spatial_frame_id: str | None = None,
        relationships: list[dict[str, Any]] | None = None,
        evidence_ids: list[str] | None = None,
        embedding_model_manifest_id: str | None = None,
        embedding_source_region: dict[str, Any] | None = None,
        source_sequence: int = 0,
        index_sequence: int = 0,
        scene_commit_id: str | None = None,
        classification: str = Classification.INTERNAL.value,
        actor_id: str = "system",
    ) -> str:
        if temporal_start and temporal_end and _aware(temporal_end) < _aware(temporal_start):
            raise ValidationError("SEARCH_TEMPORAL_RANGE", "temporal end precedes start")
        if not text.strip() and embedding is None:
            raise ValidationError("SEARCH_CONTENT_REQUIRED", "search document requires text or an embedding")
        if not 0 <= confidence <= 1:
            raise ValidationError("SEARCH_CONFIDENCE_INVALID", "search confidence must be in [0,1]")
        if source_sequence < 0 or index_sequence < 0:
            raise ValidationError("SEARCH_SEQUENCE_INVALID", "search source/index sequences must be non-negative")
        try:
            SourceClass(source_class)
            AuthorityClass(authority_class)
            Classification(classification)
        except ValueError as exc:
            raise ValidationError("SEARCH_EVIDENCE_LABEL_INVALID", "search evidence or classification label is invalid") from exc
        if embedding is not None:
            if not embedding or any(not math.isfinite(float(value)) for value in embedding):
                raise ValidationError("SEARCH_EMBEDDING_INVALID", "embedding must contain finite values")
            if not embedding_model_manifest_id or not embedding_source_region:
                raise ValidationError(
                    "SEARCH_EMBEDDING_PROVENANCE_REQUIRED",
                    "semantic index entries require an embedding model manifest and source region",
                )
        if spatial_bounds is not None:
            Bounds3D.model_validate(spatial_bounds)
            if not spatial_frame_id:
                raise ValidationError("SEARCH_SPATIAL_FRAME_REQUIRED", "spatial bounds require an explicit coordinate frame")
        normalized_policy = _normalize_policy(policy, classification=classification)
        terms = sorted(set(_tokenize(text)))
        normalized_tags = sorted(set(str(item).strip().lower() for item in (tags or []) if str(item).strip()))
        normalized_evidence = sorted(set(evidence_ids or ([asset_id] if asset_id else [])))
        normalized_relationships = _normalize_relationships(relationships or [])
        document_id = new_uuid()
        source_manifest = {
            "text": text,
            "entity_id": entity_id,
            "entity_type": entity_type,
            "asset_id": asset_id,
            "embedding_model_manifest_id": embedding_model_manifest_id,
            "embedding_source_region": embedding_source_region,
            "spatial_bounds": spatial_bounds,
            "spatial_frame_id": spatial_frame_id,
            "temporal_start": temporal_start.isoformat() if temporal_start else None,
            "temporal_end": temporal_end.isoformat() if temporal_end else None,
            "source_class": source_class,
            "authority_class": authority_class,
            "confidence": confidence,
            "tags": normalized_tags,
            "workflow_status": workflow_status,
            "relationships": normalized_relationships,
            "evidence_ids": normalized_evidence,
            "source_sequence": source_sequence,
            "scene_commit_id": scene_commit_id,
        }
        source_hash = canonical_sha256(source_manifest)
        with self.database.session() as session:
            row = SearchDocumentRow(
                document_id=document_id,
                tenant_id=tenant_id,
                project_id=project_id,
                entity_id=entity_id,
                entity_type=entity_type,
                asset_id=asset_id,
                text=text,
                terms_json=terms,
                embedding_json=[float(value) for value in embedding] if embedding is not None else None,
                embedding_model_manifest_id=embedding_model_manifest_id,
                embedding_source_region_json=embedding_source_region,
                spatial_bounds_json=spatial_bounds,
                spatial_frame_id=spatial_frame_id,
                floor_id=floor_id,
                room_id=room_id,
                temporal_start=temporal_start,
                temporal_end=temporal_end,
                source_class=source_class,
                authority_class=authority_class,
                confidence=confidence,
                tags_json=normalized_tags,
                workflow_status=workflow_status,
                relationships_json=normalized_relationships,
                evidence_ids_json=normalized_evidence,
                policy_json=normalized_policy,
                classification=classification,
                source_sequence=source_sequence,
                index_sequence=index_sequence,
                indexed_at=db_now(),
                scene_commit_id=scene_commit_id,
                source_hash=source_hash,
            )
            session.add(row)
            session.add(
                self._events.create(
                    session,
                    event_type="search.document_indexed",
                    schema_version="1.0.0",
                    tenant_id=tenant_id,
                    project_id=project_id,
                    aggregate_type="search_document",
                    aggregate_id=document_id,
                    payload={
                        "document_id": document_id,
                        "entity_id": entity_id,
                        "asset_id": asset_id,
                        "source_hash": source_hash,
                        "source_sequence": source_sequence,
                        "index_sequence": index_sequence,
                    },
                    producer="search-service",
                    actor_id=actor_id,
                    workload_identity=None,
                    correlation_id=document_id,
                )
            )
            self.audit.append(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=actor_id,
                action="search:index",
                resource_type="search_document",
                resource_id=document_id,
                outcome="allowed",
                details={
                    "source_hash": source_hash,
                    "classification": classification,
                    "embedding_model_manifest_id": embedding_model_manifest_id,
                },
                session=session,
            )
        return document_id

    def query(self, *, principal: SignedPrincipal, spec: SearchQuerySpec) -> dict[str, Any]:
        if principal.tenant_id != spec.tenant_id:
            raise AuthorizationError("SEARCH_TENANT_SCOPE_DENIED", "search tenant does not match authenticated principal")
        if spec.project_id not in principal.project_ids and "tenant_admin" not in principal.roles:
            raise AuthorizationError("SEARCH_PROJECT_SCOPE_DENIED", "search project is outside authenticated scope")
        compiled = compile_query(spec)
        started = time.monotonic()
        with self.database.session() as session:
            rows = list(
                session.scalars(
                    select(SearchDocumentRow).where(
                        SearchDocumentRow.tenant_id == spec.tenant_id,
                        SearchDocumentRow.project_id == spec.project_id,
                    )
                )
            )
        # Authorization is deliberately evaluated before matching, ranking, snippets,
        # counts, or any exposure of vector/index metadata.
        authorized = [row for row in rows if _authorized(row, principal, spec)]
        terms = set(_tokenize(spec.full_text or ""))
        ranked: list[tuple[float, SearchDocumentRow, list[str]]] = []
        stale_authorized = 0
        stale_critical_omitted = 0
        for row in authorized:
            if (time.monotonic() - started) * 1_000 > spec.timeout_ms:
                raise ValidationError("QUERY_EXECUTION_TIMEOUT", "authorized search exceeded its execution budget")
            fresh = int(row.index_sequence) >= int(row.source_sequence)
            if not fresh:
                stale_authorized += 1
                if spec.critical_workflow:
                    stale_critical_omitted += 1
                    continue
            matched, reasons = _matches(row, compiled)
            if not matched:
                continue
            lexical = _lexical_score(terms, set(row.terms_json)) if terms else 0.0
            vector = (
                _cosine(spec.embedding, row.embedding_json)
                if spec.embedding is not None
                and row.embedding_json
                and spec.embedding_model_manifest_id == row.embedding_model_manifest_id
                else 0.0
            )
            structured = min(1.0, 0.12 * len(reasons))
            score = lexical * 0.50 + vector * 0.35 + structured * 0.15
            if not terms and spec.embedding is None:
                score = max(0.1, structured)
            if score > 0:
                ranked.append((score, row, reasons))
        ranked.sort(key=lambda item: (-item[0], item[1].document_id))
        items = [self._result(row, score, reasons, include_snippet=spec.include_snippets) for score, row, reasons in ranked[: spec.limit]]
        result = {
            "schema_version": "sip.search-results/v1",
            "query_hash": compiled.query_hash,
            "items": items,
            "authorized_count": len(items),
            "authorized_match_count": len(ranked),
            "truncated": len(ranked) > spec.limit,
            "explanation": compiled.explanation,
            "freshness": {
                "stale_authorized_documents": stale_authorized,
                "critical_stale_results_omitted": stale_critical_omitted,
                "canonical_lookup_required": bool(spec.critical_workflow and stale_authorized),
            },
            "ranking": {
                "lexical_weight": 0.50,
                "semantic_weight": 0.35,
                "structured_weight": 0.15,
                "permission_filters_applied_before_ranking": True,
            },
        }
        self.audit.append(
            tenant_id=spec.tenant_id,
            project_id=spec.project_id,
            actor_id=principal.subject_id,
            action="search:query",
            resource_type="search_query",
            resource_id=compiled.query_hash,
            outcome="allowed",
            details={
                "query_hash": compiled.query_hash,
                "authorized_match_count": len(ranked),
                "returned_count": len(items),
                "critical_workflow": spec.critical_workflow,
                "stale_authorized_documents": stale_authorized,
            },
        )
        return result

    def metadata_fallback(self, *, principal: SignedPrincipal, spec: SearchQuerySpec) -> dict[str, Any]:
        """Return bounded canonical navigation metadata when the search index is unavailable.

        Authorization and freshness filtering are applied before any navigation item, count,
        snippet, or ranking signal is constructed. Full-text and semantic inputs are ignored
        deliberately so sensitive terms cannot become an existence oracle in degraded mode.
        """
        if principal.tenant_id != spec.tenant_id:
            raise AuthorizationError("SEARCH_TENANT_SCOPE_DENIED", "search tenant does not match authenticated principal")
        if spec.project_id not in principal.project_ids and "tenant_admin" not in principal.roles:
            raise AuthorizationError("SEARCH_PROJECT_SCOPE_DENIED", "search project is outside authenticated scope")
        with self.database.session() as session:
            rows = list(
                session.scalars(
                    select(SearchDocumentRow).where(
                        SearchDocumentRow.tenant_id == spec.tenant_id,
                        SearchDocumentRow.project_id == spec.project_id,
                    )
                )
            )
        authorized = [row for row in rows if _authorized(row, principal, spec)]
        items: list[dict[str, Any]] = []
        stale_authorized = 0
        stale_critical_omitted = 0
        allowed_types = set(spec.entity_types)
        for row in sorted(authorized, key=lambda item: item.document_id):
            if allowed_types and row.entity_type not in allowed_types:
                continue
            fresh = int(row.index_sequence) >= int(row.source_sequence)
            if not fresh:
                stale_authorized += 1
                if spec.critical_workflow:
                    stale_critical_omitted += 1
                    continue
            items.append(
                {
                    "document_id": row.document_id,
                    "entity_id": row.entity_id,
                    "entity_type": row.entity_type,
                    "asset_id": row.asset_id,
                    "scene_commit_id": row.scene_commit_id,
                    "source_hash": row.source_hash,
                    "access": {
                        "audience": row.policy_json.get("audience", "private"),
                        "classification": row.classification,
                        "policy_enforced_server_side": True,
                    },
                    "freshness": {
                        "source_sequence": row.source_sequence,
                        "index_sequence": row.index_sequence,
                        "fresh": fresh,
                    },
                    "navigation": {
                        "entity_id": row.entity_id,
                        "asset_id": row.asset_id,
                        "scene_commit_id": row.scene_commit_id,
                        "spatial_frame_id": row.spatial_frame_id,
                    },
                }
            )
            if len(items) >= min(spec.limit, 200):
                break
        result = {
            "schema_version": "sip.search-metadata-fallback/v1",
            "degraded_mode": "bounded_metadata_navigation",
            "authorization_before_navigation": True,
            "full_text_applied": False,
            "semantic_ranking_applied": False,
            "snippets_included": False,
            "items": items,
            "authorized_count": len(items),
            "truncated": len(items) >= min(spec.limit, 200),
            "freshness": {
                "stale_authorized_documents": stale_authorized,
                "critical_stale_results_omitted": stale_critical_omitted,
                "canonical_lookup_required": True,
            },
        }
        self.audit.append(
            tenant_id=spec.tenant_id,
            project_id=spec.project_id,
            actor_id=principal.subject_id,
            action="search:metadata_fallback",
            resource_type="search_query",
            resource_id=canonical_sha256({"tenant_id": spec.tenant_id, "project_id": spec.project_id, "mode": "metadata_fallback"}),
            outcome="allowed",
            details={
                "returned_count": len(items),
                "critical_workflow": spec.critical_workflow,
                "stale_authorized_documents": stale_authorized,
                "full_text_ignored": bool(spec.full_text),
            },
        )
        return result

    def save_query(
        self,
        *,
        principal: SignedPrincipal,
        name: str,
        spec: SearchQuerySpec,
        permissions: dict[str, Any],
        parameters: dict[str, Any],
        expected_result_contract: dict[str, Any],
        supersedes_saved_query_id: str | None = None,
    ) -> dict[str, Any]:
        if principal.tenant_id != spec.tenant_id or (
            spec.project_id not in principal.project_ids and "tenant_admin" not in principal.roles
        ):
            raise AuthorizationError("SAVED_QUERY_SCOPE_DENIED", "saved query scope is outside authenticated access")
        compiled = compile_query(spec)
        normalized_permissions = _normalize_saved_permissions(permissions)
        if supersedes_saved_query_id:
            prior = self.get_saved_query(principal=principal, saved_query_id=supersedes_saved_query_id)
            version = int(prior["version"]) + 1
        else:
            version = 1
        saved_query_id = new_uuid()
        row = SavedQueryRow(
            saved_query_id=saved_query_id,
            tenant_id=spec.tenant_id,
            project_id=spec.project_id,
            name=name,
            schema_version=spec.schema_version,
            version=version,
            author_id=principal.subject_id,
            query_json=spec.model_dump(mode="json", by_alias=True),
            permissions_json=normalized_permissions,
            parameters_json=parameters,
            expected_result_contract_json=expected_result_contract,
            query_hash=compiled.query_hash,
            supersedes_saved_query_id=supersedes_saved_query_id,
            created_at=db_now(),
        )
        with self.database.session() as session:
            session.add(row)
            session.add(
                self._events.create(
                    session,
                    event_type="saved_query.created",
                    schema_version="1.0.0",
                    tenant_id=spec.tenant_id,
                    project_id=spec.project_id,
                    aggregate_type="saved_query",
                    aggregate_id=saved_query_id,
                    payload={
                        "saved_query_id": saved_query_id,
                        "query_hash": compiled.query_hash,
                        "version": version,
                        "supersedes_saved_query_id": supersedes_saved_query_id,
                    },
                    producer="search-service",
                    actor_id=principal.subject_id,
                    workload_identity=None,
                    correlation_id=saved_query_id,
                    causation_id=supersedes_saved_query_id,
                )
            )
            self.audit.append(
                tenant_id=spec.tenant_id,
                project_id=spec.project_id,
                actor_id=principal.subject_id,
                action="saved_query:create",
                resource_type="saved_query",
                resource_id=saved_query_id,
                outcome="allowed",
                details={"query_hash": compiled.query_hash, "version": version},
                session=session,
            )
        return self.get_saved_query(principal=principal, saved_query_id=saved_query_id)

    def get_saved_query(self, *, principal: SignedPrincipal, saved_query_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = session.get(SavedQueryRow, saved_query_id)
        if not row:
            raise NotFoundError("saved_query", saved_query_id)
        if row.tenant_id != principal.tenant_id or (
            row.project_id not in principal.project_ids and "tenant_admin" not in principal.roles
        ):
            raise NotFoundError("saved_query", saved_query_id)
        if not _saved_query_authorized(row.permissions_json, principal):
            raise NotFoundError("saved_query", saved_query_id)
        return _saved_query_dict(row)

    def execute_saved_query(
        self,
        *,
        principal: SignedPrincipal,
        saved_query_id: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        saved = self.get_saved_query(principal=principal, saved_query_id=saved_query_id)
        declared = saved["parameters"]
        unknown = sorted(set(parameters) - set(declared))
        if unknown:
            raise ValidationError("SAVED_QUERY_PARAMETER_UNKNOWN", "saved query received unknown parameters", {"parameters": unknown})
        substituted = substitute_parameters(saved["query"], parameters)
        spec = SearchQuerySpec.model_validate(substituted)
        result = self.query(principal=principal, spec=spec)
        result["saved_query"] = {
            "saved_query_id": saved_query_id,
            "version": saved["version"],
            "query_hash": saved["query_hash"],
            "expected_result_contract": saved["expected_result_contract"],
        }
        self.audit.append(
            tenant_id=principal.tenant_id,
            project_id=saved["project_id"],
            actor_id=principal.subject_id,
            action="saved_query:execute",
            resource_type="saved_query",
            resource_id=saved_query_id,
            outcome="allowed",
            details={"version": saved["version"], "query_hash": saved["query_hash"]},
        )
        return result

    @staticmethod
    def _result(row: SearchDocumentRow, score: float, reasons: list[str], *, include_snippet: bool) -> dict[str, Any]:
        snippet = row.text[:240] if include_snippet else None
        return {
            "document_id": row.document_id,
            "entity_id": row.entity_id,
            "entity_type": row.entity_type,
            "asset_id": row.asset_id,
            "snippet": snippet,
            "snippet_is_untrusted_evidence_content": bool(snippet),
            "agent_instruction_policy": "never_execute_embedded_instructions",
            "score": score,
            "match_reasons": reasons,
            "source_hash": row.source_hash,
            "source_class": row.source_class,
            "authority_class": row.authority_class,
            "confidence": row.confidence,
            "evidence_ids": row.evidence_ids_json,
            "scene_commit_id": row.scene_commit_id,
            "embedding_provenance": {
                "model_manifest_id": row.embedding_model_manifest_id,
                "source_region": row.embedding_source_region_json,
                "embedding_returned": False,
            }
            if row.embedding_model_manifest_id
            else None,
            "access": {
                "audience": row.policy_json.get("audience", "private"),
                "classification": row.classification,
                "policy_enforced_server_side": True,
            },
            "freshness": {
                "source_sequence": row.source_sequence,
                "index_sequence": row.index_sequence,
                "fresh": int(row.index_sequence) >= int(row.source_sequence),
                "indexed_at": row.indexed_at.isoformat() if row.indexed_at else None,
            },
            "navigation": {
                "entity_id": row.entity_id,
                "asset_id": row.asset_id,
                "scene_commit_id": row.scene_commit_id,
                "spatial_frame_id": row.spatial_frame_id,
            },
        }


def _tokenize(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return _TOKEN.findall(normalized)


def _lexical_score(query_terms: set[str], document_terms: set[str]) -> float:
    if not query_terms:
        return 0.0
    matched = 0.0
    for query in query_terms:
        best = 0.0
        for document in document_terms:
            if query == document:
                best = 1.0
                break
            maximum_distance = 2 if min(len(query), len(document)) >= 9 else 1
            if min(len(query), len(document)) >= 4 and _bounded_edit_distance(query, document, maximum_distance) <= maximum_distance:
                best = max(best, 0.78 if maximum_distance == 1 else 0.68)
        matched += best
    return matched / len(query_terms)


def _bounded_edit_distance(left: str, right: str, maximum: int) -> int:
    if abs(len(left) - len(right)) > maximum:
        return maximum + 1
    previous = list(range(len(right) + 1))
    for index, left_char in enumerate(left, start=1):
        current = [index]
        row_minimum = index
        for offset, right_char in enumerate(right, start=1):
            value = min(
                current[offset - 1] + 1,
                previous[offset] + 1,
                previous[offset - 1] + (left_char != right_char),
            )
            current.append(value)
            row_minimum = min(row_minimum, value)
        if row_minimum > maximum:
            return maximum + 1
        previous = current
    return previous[-1]


def _matches(row: SearchDocumentRow, compiled: CompiledSpatialQuery) -> tuple[bool, list[str]]:
    spec = compiled.query
    reasons: list[str] = []
    if spec.entity_types and row.entity_type not in set(spec.entity_types):
        return False, []
    if spec.entity_types:
        reasons.append("entity_type")
    if spec.floor_ids and row.floor_id not in set(spec.floor_ids):
        return False, []
    if spec.floor_ids:
        reasons.append("floor")
    if spec.room_ids and row.room_id not in set(spec.room_ids):
        return False, []
    if spec.room_ids:
        reasons.append("room")
    if spec.source_classes and row.source_class not in {item.value for item in spec.source_classes}:
        return False, []
    if spec.source_classes:
        reasons.append("source_class")
    if spec.authority_classes and row.authority_class not in {item.value for item in spec.authority_classes}:
        return False, []
    if spec.authority_classes:
        reasons.append("authority_class")
    if spec.minimum_confidence is not None and float(row.confidence) < spec.minimum_confidence:
        return False, []
    if spec.minimum_confidence is not None:
        reasons.append("confidence")
    if spec.tags and not set(item.lower() for item in spec.tags).issubset(set(row.tags_json)):
        return False, []
    if spec.tags:
        reasons.append("tags")
    if spec.workflow_statuses and row.workflow_status not in set(spec.workflow_statuses):
        return False, []
    if spec.workflow_statuses:
        reasons.append("workflow_status")
    if spec.evidence_ids and not set(spec.evidence_ids).intersection(row.evidence_ids_json):
        return False, []
    if spec.evidence_ids:
        reasons.append("evidence")
    if spec.scene_commit_id and row.scene_commit_id != spec.scene_commit_id:
        return False, []
    if spec.scene_commit_id:
        reasons.append("scene_commit")
    terms = set(_tokenize(spec.full_text or ""))
    if terms and _lexical_score(terms, set(row.terms_json)) <= 0:
        return False, []
    if terms:
        reasons.append("full_text")
    if spec.embedding is not None:
        if row.embedding_model_manifest_id != spec.embedding_model_manifest_id or row.embedding_json is None:
            return False, []
        reasons.append("semantic")
    if spec.temporal_interval and not _temporal_overlap(row, spec.temporal_interval.start, spec.temporal_interval.end):
        return False, []
    if spec.temporal_interval:
        reasons.append("temporal_interval")
    if spec.changed_between and not _temporal_overlap(row, spec.changed_between.start, spec.changed_between.end):
        return False, []
    if spec.changed_between:
        reasons.append("changed_between")
    for predicate in spec.spatial:
        if predicate.operator == "on_level":
            if row.floor_id != predicate.level_id:
                return False, []
        else:
            if not row.spatial_bounds_json or row.spatial_frame_id != predicate.frame_id:
                return False, []
            row_bounds = Bounds3D.model_validate(row.spatial_bounds_json)
            if predicate.operator == "within" and not bounds_within(row_bounds, predicate.bounds):
                return False, []
            if predicate.operator == "intersects" and not bounds_intersect(row_bounds, predicate.bounds):
                return False, []
            if predicate.operator == "near" and point_distance_to_bounds(predicate.point or [], row_bounds) > float(predicate.distance_m):
                return False, []
            if predicate.operator == "visible_from":
                visible_ids = set(row.policy_json.get("visible_from_entity_ids", []))
                if predicate.observer_entity_id and predicate.observer_entity_id not in visible_ids:
                    return False, []
                if predicate.point is not None and not bool(row.policy_json.get("visibility_precomputed", False)):
                    return False, []
        reasons.append(f"spatial:{predicate.operator}")
    if spec.graph:
        allowed_types = set(spec.graph.relationship_types)
        starts = set(spec.graph.start_entity_ids)
        matched = any(
            relationship.get("type") in allowed_types
            and int(relationship.get("depth", 1)) <= spec.graph.max_depth
            and (
                relationship.get("source_id") in starts
                or relationship.get("target_id") in starts
                or row.entity_id in starts
            )
            for relationship in row.relationships_json
        )
        if not matched:
            return False, []
        reasons.append("graph")
    return True, reasons


def _authorized(row: SearchDocumentRow, principal: SignedPrincipal, spec: SearchQuerySpec) -> bool:
    policy = row.policy_json or {}
    if policy.get("redacted") or policy.get("consent_active") is False:
        return False
    allowed_subjects = set(policy.get("allowed_subject_ids", []))
    if allowed_subjects and principal.subject_id not in allowed_subjects and "tenant_admin" not in principal.roles:
        return False
    allowed_roles = set(policy.get("allowed_roles", []))
    if allowed_roles and not allowed_roles.intersection(principal.roles):
        return False
    required_purposes = set(policy.get("purposes", []))
    if required_purposes and not required_purposes.intersection(principal.purposes) and "tenant_admin" not in principal.roles:
        return False
    if spec.purpose and spec.purpose not in principal.purposes and "tenant_admin" not in principal.roles:
        return False
    audience = str(policy.get("audience", "private"))
    if audience not in _AUDIENCE_ACCESS.get(principal.audience.value, {"public"}) and "tenant_admin" not in principal.roles:
        return False
    if row.classification in {
        Classification.CRITICAL_INFRASTRUCTURE.value,
        Classification.BIOMETRIC.value,
        Classification.MINOR.value,
    } and not _PRIVILEGED_SENSITIVE_ROLES.intersection(principal.roles):
        return False
    row_regions = set(policy.get("spatial_region_ids", []))
    principal_regions = set(principal.attributes.get("spatial_region_ids", []))
    if principal_regions and row_regions and not row_regions.intersection(principal_regions):
        return False
    return True


def _normalize_policy(policy: dict[str, Any], *, classification: str) -> dict[str, Any]:
    allowed = {
        "audience",
        "allowed_subject_ids",
        "allowed_roles",
        "purposes",
        "spatial_region_ids",
        "consent_active",
        "redacted",
        "visible_from_entity_ids",
        "visibility_precomputed",
    }
    unknown = sorted(set(policy) - allowed)
    if unknown:
        raise ValidationError("SEARCH_POLICY_FIELD_UNKNOWN", "search policy contains unsupported fields", {"fields": unknown})
    audience = str(policy.get("audience", Audience.PRIVATE.value))
    try:
        Audience(audience)
    except ValueError as exc:
        raise ValidationError("SEARCH_AUDIENCE_INVALID", "search audience is invalid") from exc
    return {
        "audience": audience,
        "allowed_subject_ids": sorted(set(policy.get("allowed_subject_ids", []))),
        "allowed_roles": sorted(set(policy.get("allowed_roles", []))),
        "purposes": sorted(set(policy.get("purposes", []))),
        "spatial_region_ids": sorted(set(policy.get("spatial_region_ids", []))),
        "consent_active": bool(policy.get("consent_active", True)),
        "redacted": bool(policy.get("redacted", False)),
        "visible_from_entity_ids": sorted(set(policy.get("visible_from_entity_ids", []))),
        "visibility_precomputed": bool(policy.get("visibility_precomputed", False)),
        "classification": classification,
    }


def _normalize_relationships(relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for relationship in relationships:
        keys = {"type", "source_id", "target_id", "depth"}
        if not set(relationship).issubset(keys) or not relationship.get("type"):
            raise ValidationError("SEARCH_RELATIONSHIP_INVALID", "search relationship has an invalid contract")
        depth = int(relationship.get("depth", 1))
        if depth < 1 or depth > 5:
            raise ValidationError("SEARCH_RELATIONSHIP_DEPTH_INVALID", "search relationship depth must be in [1,5]")
        normalized.append(
            {
                "type": str(relationship["type"]),
                "source_id": relationship.get("source_id"),
                "target_id": relationship.get("target_id"),
                "depth": depth,
            }
        )
    return normalized


def _normalize_saved_permissions(permissions: dict[str, Any]) -> dict[str, Any]:
    allowed = {"audience", "allowed_subject_ids", "allowed_roles"}
    unknown = sorted(set(permissions) - allowed)
    if unknown:
        raise ValidationError("SAVED_QUERY_PERMISSION_FIELD_UNKNOWN", "saved query permission contains unknown fields", {"fields": unknown})
    audience = str(permissions.get("audience", Audience.PRIVATE.value))
    try:
        Audience(audience)
    except ValueError as exc:
        raise ValidationError("SAVED_QUERY_AUDIENCE_INVALID", "saved query audience is invalid") from exc
    return {
        "audience": audience,
        "allowed_subject_ids": sorted(set(permissions.get("allowed_subject_ids", []))),
        "allowed_roles": sorted(set(permissions.get("allowed_roles", []))),
    }


def _saved_query_authorized(permissions: dict[str, Any], principal: SignedPrincipal) -> bool:
    if "tenant_admin" in principal.roles:
        return True
    subjects = set(permissions.get("allowed_subject_ids", []))
    if subjects and principal.subject_id not in subjects:
        return False
    roles = set(permissions.get("allowed_roles", []))
    if roles and not roles.intersection(principal.roles):
        return False
    audience = str(permissions.get("audience", "private"))
    return audience in _AUDIENCE_ACCESS.get(principal.audience.value, {"public"})


def _saved_query_dict(row: SavedQueryRow) -> dict[str, Any]:
    return {
        "saved_query_id": row.saved_query_id,
        "tenant_id": row.tenant_id,
        "project_id": row.project_id,
        "name": row.name,
        "schema_version": row.schema_version,
        "version": row.version,
        "author_id": row.author_id,
        "query": row.query_json,
        "permissions": row.permissions_json,
        "parameters": row.parameters_json,
        "expected_result_contract": row.expected_result_contract_json,
        "query_hash": row.query_hash,
        "supersedes_saved_query_id": row.supersedes_saved_query_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "immutable": True,
    }


def _temporal_overlap(row: SearchDocumentRow, start: datetime, end: datetime) -> bool:
    row_start = _aware(row.temporal_start) if row.temporal_start else datetime.min.replace(tzinfo=UTC)
    row_end = _aware(row.temporal_end) if row.temporal_end else datetime.max.replace(tzinfo=UTC)
    return row_start <= _aware(end) and _aware(start) <= row_end


def _cosine(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    a_norm = math.sqrt(sum(a * a for a in left))
    b_norm = math.sqrt(sum(b * b for b in right))
    return dot / (a_norm * b_norm) if a_norm and b_norm else 0.0


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
