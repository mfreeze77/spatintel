from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from collections import Counter
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any, Iterable, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from .archive_safety import validate_zip_members, verify_checksum_manifest
from .audit import AuditService
from .canonical import canonical_json, canonical_sha256, merkle_root, new_uuid, sha256_bytes, sha256_file
from .database import (
    AssetRefRow,
    ConstructionCommissioningRow,
    ConstructionDocumentRevisionRow,
    ConstructionHandoffRow,
    ConstructionInterchangeRow,
    ConstructionIssueRow,
    ConstructionRecordRow,
    ConstructionRestrictedExportApprovalRow,
    ConstructionSurveyRow,
    ConstructionVisitRow,
    Database,
    MeasurementRow,
    SceneCommitRow,
)
from .errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from .events import OutboxEventFactory
from .temporal import db_now


HIERARCHY_PARENT = {"site": None, "building": "site", "level": "building", "zone": "level", "room": "level"}
CONDITION_STATES = {"observed", "inferred", "design", "proposed", "measured", "verified", "disputed", "superseded"}
SYSTEM_TYPES = {
    "fire_alarm_panel", "fire_alarm_annunciator", "fire_alarm_device", "fire_alarm_circuit",
    "fire_alarm_network", "fire_alarm_interface", "access_opening", "access_reader",
    "access_lock", "access_contact", "access_rex", "access_controller", "bas_equipment",
    "bas_point", "mechanical_equipment", "electrical_equipment", "system_interconnection",
}
DOCUMENT_TYPES = {"drawing", "specification", "submittal", "rfi", "photo", "video", "note", "cutsheet", "test_record", "programming_record"}
ISSUE_STATES = {"open", "acknowledged", "corrected", "retest_required", "verified_closed", "disputed", "superseded"}
COMMISSIONING_FORBIDDEN_IDENTITY_KEYS = {
    "badge_id", "card_number", "credential_id", "credential_number", "pin", "password",
    "passcode", "token", "secret", "biometric_template", "access_code", "cardholder_id",
}
SYSTEM_PACKS: dict[str, dict[str, Any]] = {
    "fire_alarm": {
        "types": {item for item in SYSTEM_TYPES if item.startswith("fire_alarm_")},
        "required": {"manufacturer", "model"},
        "restricted": {"network_address", "programming_password", "dialer_account", "remote_access_endpoint"},
    },
    "access_control": {
        "types": {item for item in SYSTEM_TYPES if item.startswith("access_")},
        "required": {"manufacturer", "model"},
        "restricted": {"credential_secret", "controller_password", "network_address", "unlock_override"},
    },
    "mep": {
        "types": {"bas_equipment", "bas_point", "mechanical_equipment", "electrical_equipment", "system_interconnection"},
        "required": {"manufacturer", "model"},
        "restricted": {"network_address", "write_override", "control_password", "security_key"},
    },
}

OWNER_HANDOFF_MEMBERS = {
    "manifest.json",
    "checksums.json",
    "reports/technical.json",
    "reports/owner.json",
    "data/inventory.json",
    "data/documents.json",
    "data/issues.json",
    "data/commissioning.json",
    "data/interchange.json",
    "data/handoff-validation.json",
    "viewer/index.html",
    "README.txt",
}

T = TypeVar("T")


def _zip_write(handle: zipfile.ZipFile, name: str, data: bytes) -> str:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    handle.writestr(info, data)
    return sha256_bytes(data)


def _handoff_request_payload(
    *,
    scope: dict[str, Any],
    accepted_scene_commit_id: str | None,
    warranties: list[dict[str, Any]],
    training: list[dict[str, Any]],
    exclusions: list[str],
    audience_profiles: dict[str, Any],
    destination_name: str,
    classification: str,
    audience: str,
    purpose: str,
) -> dict[str, Any]:
    return {
        "scope": scope,
        "accepted_scene_commit_id": accepted_scene_commit_id,
        "warranties": warranties,
        "training": training,
        "exclusions": exclusions,
        "audience_profiles": audience_profiles,
        "destination_name": destination_name,
        "classification": classification,
        "audience": audience,
        "purpose": purpose,
    }


def _hex64(value: str, code: str = "SHA256_INVALID") -> str:
    normalized = value.removeprefix("sha256:").lower()
    if not re.fullmatch(r"[a-f0-9]{64}", normalized):
        raise ValidationError(code, "expected a lowercase SHA-256 digest")
    return normalized


def _forbidden_identity_paths(value: Any, *, path: str = "$") -> list[str]:
    """Return sensitive credential-like paths that commissioning records may not retain."""
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).strip().lower()
            child = f"{path}.{key}"
            if normalized in COMMISSIONING_FORBIDDEN_IDENTITY_KEYS or any(
                token in normalized for token in ("password", "secret", "credential", "passcode", "biometric")
            ):
                findings.append(child)
            findings.extend(_forbidden_identity_paths(item, path=child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_forbidden_identity_paths(item, path=f"{path}[{index}]"))
    return findings


class ConstructionService:
    def __init__(self, database: Database, audit: AuditService) -> None:
        self.database = database
        self.audit = audit
        self.events = OutboxEventFactory()

    # Existing hierarchy and entity-pack core -------------------------------------------------
    def create_hierarchy_item(self, *, tenant_id: str, project_id: str, record_type: str, name: str,
                              parent_id: str | None, state: str, actor_id: str,
                              attributes: dict[str, Any] | None = None) -> str:
        if record_type not in HIERARCHY_PARENT:
            raise ValidationError("CONSTRUCTION_HIERARCHY_TYPE", "unsupported construction hierarchy type")
        if state not in CONDITION_STATES:
            raise ValidationError("CONSTRUCTION_STATE", "unsupported condition state")
        if not name.strip():
            raise ValidationError("CONSTRUCTION_NAME_REQUIRED", "hierarchy name is required")
        with self.database.session() as session:
            expected_parent = HIERARCHY_PARENT[record_type]
            if expected_parent is None and parent_id is not None:
                raise ValidationError("CONSTRUCTION_PARENT_INVALID", f"{record_type} cannot have a parent")
            if expected_parent is not None:
                parent = session.get(ConstructionRecordRow, parent_id) if parent_id else None
                if not parent or parent.tenant_id != tenant_id or parent.project_id != project_id or parent.record_type != expected_parent:
                    raise ValidationError("CONSTRUCTION_PARENT_INVALID", f"{record_type} requires parent type {expected_parent}")
            identifier = new_uuid()
            session.add(ConstructionRecordRow(record_id=identifier, tenant_id=tenant_id, project_id=project_id,
                                               record_type=record_type, parent_id=parent_id, state=state,
                                               data_json={"name": name.strip(), **(attributes or {})}, created_by=actor_id))
            self._record(session, tenant_id, project_id, actor_id, "construction:hierarchy_create", "construction_record",
                         identifier, {"record_type": record_type, "state": state},
                         "construction.hierarchy.created", "construction_record")
            return identifier

    def create_system_record(self, *, tenant_id: str, project_id: str, system_type: str, parent_id: str | None,
                             entity_id: str | None, state: str, data: dict[str, Any],
                             evidence_asset_ids: list[str], actor_id: str) -> str:
        if system_type not in SYSTEM_TYPES:
            raise ValidationError("CONSTRUCTION_SYSTEM_TYPE", "unsupported building system record")
        if state not in CONDITION_STATES:
            raise ValidationError("CONSTRUCTION_STATE", "unsupported condition state")
        if state in {"observed", "measured", "verified"} and not evidence_asset_ids:
            raise ValidationError("CONSTRUCTION_EVIDENCE_REQUIRED", "observed/measured/verified system records require evidence")
        if state == "verified" and not data.get("verified_by"):
            raise ValidationError("CONSTRUCTION_VERIFIER_REQUIRED", "verified system record requires a verifier")
        pack = self._pack_for_type(system_type)
        missing = sorted(pack["required"] - {key for key, value in data.items() if value not in (None, "")})
        normalized_data = {
            **data,
            "pack": pack["name"],
            "missing_required_fields": missing,
            "completeness_status": "complete" if not missing else "incomplete_review_required",
        }
        identifier = new_uuid()
        with self.database.session() as session:
            if parent_id:
                self._scoped_record(session, parent_id, tenant_id, project_id)
            session.add(ConstructionRecordRow(record_id=identifier, tenant_id=tenant_id, project_id=project_id,
                                               record_type=system_type, parent_id=parent_id, entity_id=entity_id,
                                               state=state, data_json=normalized_data,
                                               evidence_asset_ids_json=sorted(set(evidence_asset_ids)), created_by=actor_id))
            self._record(session, tenant_id, project_id, actor_id, "construction:system_create", "construction_record",
                         identifier, {"system_type": system_type, "state": state, "pack": pack["name"]},
                         "construction.system_record.created", "construction_record")
        return identifier

    def export_system_pack(self, tenant_id: str, project_id: str, *, pack: str, include_restricted: bool = False) -> dict[str, Any]:
        if pack not in SYSTEM_PACKS:
            raise ValidationError("CONSTRUCTION_PACK_UNKNOWN", "unknown system pack")
        spec = SYSTEM_PACKS[pack]
        with self.database.session() as session:
            rows = list(session.scalars(select(ConstructionRecordRow).where(
                ConstructionRecordRow.tenant_id == tenant_id,
                ConstructionRecordRow.project_id == project_id,
                ConstructionRecordRow.record_type.in_(spec["types"]),
            )))
        records = []
        for row in rows:
            data = dict(row.data_json)
            redacted: list[str] = []
            if not include_restricted:
                for key in sorted(spec["restricted"]):
                    if key in data:
                        data.pop(key)
                        redacted.append(key)
            records.append({"record_id": row.record_id, "record_type": row.record_type, "state": row.state,
                            "data": data, "evidence_asset_ids": row.evidence_asset_ids_json,
                            "redacted_fields": redacted})
        body = {"pack": pack, "project_id": project_id, "records": records,
                "restricted_fields_included": include_restricted,
                "truth_rule": "design, observed, inferred, and verified states remain distinct"}
        return {**body, "root_hash": canonical_sha256(body)}

    # Survey and visit workflow ---------------------------------------------------------------
    def create_survey_plan(self, *, tenant_id: str, project_id: str, name: str, objectives: list[str],
                           required_place_ids: list[str], required_system_types: list[str],
                           sensitive_regions: list[dict[str, Any]], control_requirements: dict[str, Any],
                           measurement_requirements: dict[str, Any], safety: dict[str, Any],
                           permissions: dict[str, Any], deliverables: list[dict[str, Any]],
                           actor_id: str, idempotency_key: str, baseline_commit_id: str | None = None,
                           return_visit_of_id: str | None = None) -> dict[str, Any]:
        if not name.strip() or not objectives or not required_place_ids or not deliverables:
            raise ValidationError("SURVEY_PLAN_INCOMPLETE", "survey plan requires a name, objectives, places, and deliverables")
        unknown = sorted(set(required_system_types) - SYSTEM_TYPES)
        if unknown:
            raise ValidationError("SURVEY_SYSTEM_UNKNOWN", "survey plan contains unknown system types", {"types": unknown})
        request = {"name": name.strip(), "objectives": objectives, "required_place_ids": sorted(set(required_place_ids)),
                   "required_system_types": sorted(set(required_system_types)), "sensitive_regions": sensitive_regions,
                   "control_requirements": control_requirements, "measurement_requirements": measurement_requirements,
                   "safety": safety, "permissions": permissions, "deliverables": deliverables,
                   "baseline_commit_id": baseline_commit_id, "return_visit_of_id": return_visit_of_id}
        request_hash = canonical_sha256(request)
        with self.database.session() as session:
            prior = self._idempotent(session, ConstructionSurveyRow, tenant_id, project_id, idempotency_key, request_hash)
            if prior:
                return self._survey_result(prior, True)
            if baseline_commit_id:
                self._scoped_commit(session, baseline_commit_id, tenant_id, project_id)
            if return_visit_of_id:
                prior_survey = self._scoped(session, ConstructionSurveyRow, return_visit_of_id, tenant_id, project_id, "survey")
                if prior_survey.state not in {"accepted", "closed"}:
                    raise ConflictError("RETURN_VISIT_BASELINE_NOT_ACCEPTED", "return visit requires an accepted prior survey")
            row = ConstructionSurveyRow(survey_id=new_uuid(), tenant_id=tenant_id, project_id=project_id,
                                        name=name.strip(), idempotency_key=idempotency_key, request_hash=request_hash,
                                        objectives_json=objectives, required_place_ids_json=sorted(set(required_place_ids)),
                                        required_system_types_json=sorted(set(required_system_types)),
                                        sensitive_regions_json=sensitive_regions, control_requirements_json=control_requirements,
                                        measurement_requirements_json=measurement_requirements, safety_json=safety,
                                        permissions_json=permissions, deliverables_json=deliverables,
                                        baseline_commit_id=baseline_commit_id, return_visit_of_id=return_visit_of_id,
                                        state="planned", created_by=actor_id)
            session.add(row)
            self._record(session, tenant_id, project_id, actor_id, "construction:survey_create", "construction_survey",
                         row.survey_id, {"request_hash": request_hash, "return_visit": bool(return_visit_of_id)},
                         "construction.survey.planned", "construction_survey")
            return self._survey_result(row, False)

    def record_field_visit(self, *, tenant_id: str, project_id: str, survey_id: str,
                           scope: dict[str, Any], capture_ids: list[str], checklist: list[dict[str, Any]],
                           detail_evidence: list[dict[str, Any]], inaccessible_regions: list[dict[str, Any]],
                           coverage: dict[str, Any], tracking: dict[str, Any], registration: dict[str, Any],
                           controls: dict[str, Any], inventory: dict[str, Any],
                           unresolved_questions: list[dict[str, Any]], privacy: dict[str, Any],
                           actor_id: str, idempotency_key: str, exact_prior_commit_id: str | None = None,
                           complete: bool = True) -> dict[str, Any]:
        if not checklist or not capture_ids:
            raise ValidationError("FIELD_VISIT_INCOMPLETE", "field visit requires captures and a checklist")
        if coverage.get("observed_fraction") is not None and not 0 <= float(coverage["observed_fraction"]) <= 1:
            raise ValidationError("FIELD_VISIT_COVERAGE", "observed coverage fraction must be between zero and one")
        request = {"survey_id": survey_id, "scope": scope, "capture_ids": sorted(set(capture_ids)),
                   "checklist": checklist, "detail_evidence": detail_evidence, "inaccessible_regions": inaccessible_regions,
                   "coverage": coverage, "tracking": tracking, "registration": registration, "controls": controls,
                   "inventory": inventory, "unresolved_questions": unresolved_questions, "privacy": privacy,
                   "exact_prior_commit_id": exact_prior_commit_id, "complete": complete}
        request_hash = canonical_sha256(request)
        with self.database.session() as session:
            prior = self._idempotent(session, ConstructionVisitRow, tenant_id, project_id, idempotency_key, request_hash)
            if prior:
                return self._visit_result(prior, True)
            survey = self._scoped(session, ConstructionSurveyRow, survey_id, tenant_id, project_id, "survey")
            if survey.state in {"rejected", "superseded"}:
                raise ConflictError("SURVEY_NOT_EXECUTABLE", "rejected or superseded survey cannot accept a visit")
            if exact_prior_commit_id:
                self._scoped_commit(session, exact_prior_commit_id, tenant_id, project_id)
                if survey.baseline_commit_id and survey.baseline_commit_id != exact_prior_commit_id:
                    raise ConflictError("FIELD_VISIT_BASELINE_MISMATCH", "visit prior commit differs from the survey baseline")
            report = {"survey_id": survey_id, "scope": scope, "capture_ids": sorted(set(capture_ids)),
                      "checklist": checklist, "detail_evidence": detail_evidence,
                      "inaccessible_regions": inaccessible_regions, "coverage": coverage, "tracking": tracking,
                      "registration": registration, "controls": controls, "inventory": inventory,
                      "unresolved_questions": unresolved_questions, "privacy": privacy,
                      "limitations": ["Unobserved or inaccessible regions are not represented as verified absence."]}
            row = ConstructionVisitRow(visit_id=new_uuid(), survey_id=survey_id, tenant_id=tenant_id,
                                       project_id=project_id, idempotency_key=idempotency_key, request_hash=request_hash,
                                       exact_prior_commit_id=exact_prior_commit_id, scope_json=scope,
                                       capture_ids_json=sorted(set(capture_ids)), checklist_json=checklist,
                                       detail_evidence_json=detail_evidence, inaccessible_regions_json=inaccessible_regions,
                                       coverage_json=coverage, tracking_json=tracking, registration_json=registration,
                                       controls_json=controls, inventory_json=inventory,
                                       unresolved_questions_json=unresolved_questions, privacy_json=privacy,
                                       state="completed" if complete else "active", report_hash=canonical_sha256(report),
                                       created_by=actor_id, completed_at=db_now() if complete else None)
            session.add(row)
            survey.state = "in_review" if complete else "in_progress"
            self._record(session, tenant_id, project_id, actor_id, "construction:visit_record", "construction_visit",
                         row.visit_id, {"survey_id": survey_id, "report_hash": row.report_hash, "state": row.state},
                         "construction.field_visit.recorded", "construction_visit")
            return self._visit_result(row, False)

    def review_survey(self, survey_id: str, *, tenant_id: str, project_id: str, reviewer_id: str,
                      decision: str, checklist: dict[str, Any], accepted_commit_id: str | None = None,
                      limitations: list[str] | None = None) -> dict[str, Any]:
        if decision not in {"accept", "reject", "request_return_visit"}:
            raise ValidationError("SURVEY_REVIEW_DECISION", "unsupported survey review decision")
        with self.database.session() as session:
            survey = self._scoped(session, ConstructionSurveyRow, survey_id, tenant_id, project_id, "survey")
            visits = list(session.scalars(select(ConstructionVisitRow).where(ConstructionVisitRow.survey_id == survey_id)))
            if decision == "accept":
                if not visits or any(row.state != "completed" for row in visits):
                    raise ConflictError("SURVEY_VISIT_INCOMPLETE", "all survey visits must be completed before acceptance")
                if accepted_commit_id:
                    self._scoped_commit(session, accepted_commit_id, tenant_id, project_id)
                required = {item.get("id") for item in checklist.get("items", []) if item.get("required")}
                passed = {item.get("id") for item in checklist.get("items", []) if item.get("status") in {"pass", "not_applicable"}}
                if required - passed:
                    raise ConflictError("SURVEY_ACCEPTANCE_CRITERIA", "required closeout criteria are incomplete", {"missing": sorted(required - passed)})
            survey.state = {"accept": "accepted", "reject": "rejected", "request_return_visit": "return_visit_required"}[decision]
            survey.accepted_commit_id = accepted_commit_id if decision == "accept" else None
            survey.review_json = {"reviewer_id": reviewer_id, "decision": decision, "checklist": checklist,
                                  "limitations": limitations or [], "reviewed_at": db_now().isoformat()}
            survey.completion_hash = canonical_sha256({"survey_id": survey_id, "visits": [row.report_hash for row in visits],
                                                       "review": survey.review_json, "accepted_commit_id": survey.accepted_commit_id})
            self._record(session, tenant_id, project_id, reviewer_id, "construction:survey_review", "construction_survey",
                         survey_id, {"decision": decision, "completion_hash": survey.completion_hash},
                         "construction.survey.reviewed", "construction_survey")
            return self._survey_result(survey, False)

    def survey(self, tenant_id: str, project_id: str, survey_id: str) -> dict[str, Any]:
        """Return a policy-ready survey aggregate with every visit and review artifact."""
        with self.database.session() as session:
            survey = self._scoped(session, ConstructionSurveyRow, survey_id, tenant_id, project_id, "survey")
            visits = list(session.scalars(select(ConstructionVisitRow).where(
                ConstructionVisitRow.tenant_id == tenant_id,
                ConstructionVisitRow.project_id == project_id,
                ConstructionVisitRow.survey_id == survey_id,
            ).order_by(ConstructionVisitRow.started_at, ConstructionVisitRow.visit_id)))
            body = {
                "survey_id": survey.survey_id, "name": survey.name, "state": survey.state,
                "objectives": survey.objectives_json, "required_place_ids": survey.required_place_ids_json,
                "required_system_types": survey.required_system_types_json,
                "sensitive_regions": survey.sensitive_regions_json,
                "control_requirements": survey.control_requirements_json,
                "measurement_requirements": survey.measurement_requirements_json,
                "safety": survey.safety_json, "permissions": survey.permissions_json,
                "deliverables": survey.deliverables_json, "baseline_commit_id": survey.baseline_commit_id,
                "return_visit_of_id": survey.return_visit_of_id, "review": survey.review_json,
                "accepted_commit_id": survey.accepted_commit_id, "completion_hash": survey.completion_hash,
                "visits": [{
                    "visit_id": row.visit_id, "state": row.state, "exact_prior_commit_id": row.exact_prior_commit_id,
                    "scope": row.scope_json, "captures": row.capture_ids_json, "checklist": row.checklist_json,
                    "detail_evidence": row.detail_evidence_json, "inaccessible_regions": row.inaccessible_regions_json,
                    "coverage": row.coverage_json, "tracking": row.tracking_json,
                    "registration": row.registration_json, "controls": row.controls_json,
                    "inventory": row.inventory_json, "unresolved_questions": row.unresolved_questions_json,
                    "privacy": row.privacy_json, "report_hash": row.report_hash,
                    "started_at": row.started_at.isoformat(),
                    "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                } for row in visits],
                "truth_rule": "Inaccessible and unobserved regions are never represented as verified absence.",
            }
            return {**body, "aggregate_hash": canonical_sha256(body)}

    def document_revision(self, tenant_id: str, project_id: str, revision_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = self._scoped(session, ConstructionDocumentRevisionRow, revision_id, tenant_id, project_id, "document_revision")
            body = {"revision_id": row.revision_id, "stable_document_id": row.stable_document_id,
                    **self._document_body(row), "created_by": row.created_by, "created_at": row.created_at.isoformat()}
            return {**body, "revision_hash": canonical_sha256(self._document_body(row))}

    def issue(self, tenant_id: str, project_id: str, issue_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = self._scoped(session, ConstructionIssueRow, issue_id, tenant_id, project_id, "issue")
            return {
                "issue_id": row.issue_id, "issue_type": row.issue_type, "description": row.description,
                "entity_id": row.entity_id, "place_id": row.place_id,
                "observed_commit_id": row.observed_commit_id, "observed_at": row.observed_at.isoformat(),
                "evidence": row.evidence_json, "reporter_id": row.reporter_id, "severity": row.severity,
                "responsible_party": row.responsible_party,
                "due_at": row.due_at.isoformat() if row.due_at else None, "status": row.status,
                "permissions": row.permissions_json, "history": row.history_json,
                "verification": row.verification_json, "residual_limitations": row.residual_limitations_json,
                "updated_at": row.updated_at.isoformat(),
            }

    def handoff(self, tenant_id: str, project_id: str, handoff_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            row = self._scoped(session, ConstructionHandoffRow, handoff_id, tenant_id, project_id, "handoff")
            return {**self._handoff_result(row, False), "scope": row.scope_json,
                    "accepted_scene_commit_id": row.accepted_scene_commit_id,
                    "inventory": row.inventory_json, "verified_attributes": row.verified_attributes_json,
                    "documents": row.documents_json, "tests": row.tests_json, "warranties": row.warranties_json,
                    "training": row.training_json, "open_issues": row.open_issues_json,
                    "exclusions": row.exclusions_json, "exports": row.exports_json,
                    "audience_profiles": row.audience_profiles_json, "offline_viewer": row.offline_viewer_json,
                    "limitations": row.limitations_json, "checksums": row.checksums_json}

    def search_facility_records(self, tenant_id: str, project_id: str, *, query: str = "",
                                system_pack: str | None = None, state: str | None = None,
                                include_restricted: bool = False) -> dict[str, Any]:
        normalized = query.strip().lower()
        if system_pack is not None and system_pack not in SYSTEM_PACKS:
            raise ValidationError("CONSTRUCTION_PACK_UNKNOWN", "unknown system pack")
        allowed_types = SYSTEM_PACKS[system_pack]["types"] if system_pack else None
        restricted = set().union(*(pack["restricted"] for pack in SYSTEM_PACKS.values()))
        with self.database.session() as session:
            records = list(session.scalars(select(ConstructionRecordRow).where(
                ConstructionRecordRow.tenant_id == tenant_id, ConstructionRecordRow.project_id == project_id)))
            documents = list(session.scalars(select(ConstructionDocumentRevisionRow).where(
                ConstructionDocumentRevisionRow.tenant_id == tenant_id,
                ConstructionDocumentRevisionRow.project_id == project_id)))
            issues = list(session.scalars(select(ConstructionIssueRow).where(
                ConstructionIssueRow.tenant_id == tenant_id, ConstructionIssueRow.project_id == project_id)))
        items: list[dict[str, Any]] = []
        for row in records:
            if allowed_types is not None and row.record_type not in allowed_types:
                continue
            if state and row.state != state:
                continue
            data = dict(row.data_json)
            haystack = json.dumps({"type": row.record_type, "state": row.state, "data": data}, sort_keys=True).lower()
            if normalized and normalized not in haystack:
                continue
            redacted = []
            if not include_restricted:
                for field in sorted(restricted):
                    if field in data:
                        data.pop(field)
                        redacted.append(field)
            items.append({"kind": "record", "id": row.record_id, "record_type": row.record_type,
                          "state": row.state, "parent_id": row.parent_id, "entity_id": row.entity_id,
                          "data": data, "redacted_fields": redacted})
        for row in documents:
            haystack = json.dumps({"title": row.title, "type": row.document_type, "revision": row.revision,
                                   "links": row.spatial_links_json}, sort_keys=True).lower()
            if normalized and normalized not in haystack:
                continue
            items.append({"kind": "document", "id": row.revision_id, "document_type": row.document_type,
                          "title": row.title, "revision": row.revision, "status": row.status,
                          "stable_document_id": row.stable_document_id, "spatial_links": row.spatial_links_json})
        for row in issues:
            haystack = json.dumps({"type": row.issue_type, "description": row.description,
                                   "status": row.status, "history": row.history_json}, sort_keys=True).lower()
            if normalized and normalized not in haystack:
                continue
            items.append({"kind": "issue", "id": row.issue_id, "issue_type": row.issue_type,
                          "description": row.description, "status": row.status, "severity": row.severity,
                          "entity_id": row.entity_id, "place_id": row.place_id})
        body = {"project_id": project_id, "query": query, "system_pack": system_pack, "state": state,
                "include_restricted": include_restricted, "items": sorted(items, key=lambda item: (item["kind"], item["id"]))}
        return {**body, "result_hash": canonical_sha256(body)}

    # Documents, RFIs, issues and commissioning ------------------------------------------------
    def create_document_revision(self, *, tenant_id: str, project_id: str, stable_document_id: str | None,
                                 document_type: str, title: str, revision: str, issue_date: str, issuer: str,
                                 status: str, asset_id: str, source_sha256: str, page_count: int,
                                 permissions: dict[str, Any], page_regions: list[dict[str, Any]],
                                 spatial_links: list[dict[str, Any]], extraction: dict[str, Any],
                                 review: dict[str, Any], actor_id: str,
                                 supersedes_revision_id: str | None = None) -> dict[str, Any]:
        if document_type not in DOCUMENT_TYPES:
            raise ValidationError("CONSTRUCTION_DOCUMENT_TYPE", "unsupported construction document type")
        if page_count < 1 or not title.strip() or not revision.strip():
            raise ValidationError("DOCUMENT_REVISION_INVALID", "document title, revision, and positive page count are required")
        digest = _hex64(source_sha256)
        stable_document_id = stable_document_id or new_uuid()
        with self.database.session() as session:
            asset = session.get(AssetRefRow, asset_id)
            if not asset or asset.tenant_id != tenant_id or asset.project_id != project_id or asset.sha256 != digest or asset.tombstoned_at:
                raise ValidationError("DOCUMENT_ASSET_SCOPE", "document asset scope or digest is invalid")
            if supersedes_revision_id:
                prior = self._scoped(session, ConstructionDocumentRevisionRow, supersedes_revision_id, tenant_id, project_id, "document_revision")
                if prior.stable_document_id != stable_document_id:
                    raise ConflictError("DOCUMENT_LINEAGE_MISMATCH", "superseded revision belongs to another stable document")
            existing = session.scalar(select(ConstructionDocumentRevisionRow).where(
                ConstructionDocumentRevisionRow.tenant_id == tenant_id,
                ConstructionDocumentRevisionRow.project_id == project_id,
                ConstructionDocumentRevisionRow.stable_document_id == stable_document_id,
                ConstructionDocumentRevisionRow.revision == revision,
            ))
            body = {"document_type": document_type, "title": title.strip(), "revision": revision,
                    "issue_date": issue_date, "issuer": issuer, "status": status, "asset_id": asset_id,
                    "source_sha256": digest, "page_count": page_count, "permissions": permissions,
                    "supersedes_revision_id": supersedes_revision_id, "page_regions": page_regions,
                    "spatial_links": spatial_links, "extraction": extraction, "review": review}
            if existing:
                current = self._document_body(existing)
                if canonical_sha256(current) != canonical_sha256(body):
                    raise ConflictError("DOCUMENT_REVISION_CONFLICT", "document revision already exists with different content")
                return {"revision_id": existing.revision_id, "stable_document_id": stable_document_id,
                        "revision_hash": canonical_sha256(current), "idempotent_replay": True}
            row = ConstructionDocumentRevisionRow(revision_id=new_uuid(), stable_document_id=stable_document_id,
                                                   tenant_id=tenant_id, project_id=project_id,
                                                   document_type=document_type, title=title.strip(), revision=revision,
                                                   issue_date=issue_date, issuer=issuer, status=status, asset_id=asset_id,
                                                   source_sha256=digest, page_count=page_count, permissions_json=permissions,
                                                   supersedes_revision_id=supersedes_revision_id,
                                                   page_regions_json=page_regions, spatial_links_json=spatial_links,
                                                   extraction_json=extraction, review_json=review, created_by=actor_id)
            session.add(row)
            self._record(session, tenant_id, project_id, actor_id, "construction:document_revision", "construction_document_revision",
                         row.revision_id, {"stable_document_id": stable_document_id, "revision": revision, "source_sha256": digest},
                         "construction.document.revised", "construction_document_revision")
            return {"revision_id": row.revision_id, "stable_document_id": stable_document_id,
                    "revision_hash": canonical_sha256(body), "idempotent_replay": False}

    def create_issue(self, *, tenant_id: str, project_id: str, issue_type: str, description: str,
                     evidence: list[dict[str, Any]], reporter_id: str, severity: str, idempotency_key: str,
                     entity_id: str | None = None, place_id: str | None = None,
                     observed_commit_id: str | None = None, responsible_party: str | None = None,
                     due_at: datetime | None = None, permissions: dict[str, Any] | None = None) -> dict[str, Any]:
        if severity not in {"low", "medium", "high", "life_safety"} or not evidence:
            raise ValidationError("ISSUE_INVALID", "issue requires valid severity and evidence")
        request = {"issue_type": issue_type, "description": description, "evidence": evidence, "severity": severity,
                   "entity_id": entity_id, "place_id": place_id, "observed_commit_id": observed_commit_id,
                   "responsible_party": responsible_party, "due_at": due_at.isoformat() if due_at else None,
                   "permissions": permissions or {}}
        request_hash = canonical_sha256(request)
        with self.database.session() as session:
            prior = self._idempotent(session, ConstructionIssueRow, tenant_id, project_id, idempotency_key, request_hash)
            if prior:
                return self._issue_result(prior, True)
            if observed_commit_id:
                self._scoped_commit(session, observed_commit_id, tenant_id, project_id)
            now = db_now()
            row = ConstructionIssueRow(issue_id=new_uuid(), tenant_id=tenant_id, project_id=project_id,
                                       idempotency_key=idempotency_key, request_hash=request_hash,
                                       issue_type=issue_type, description=description, entity_id=entity_id,
                                       place_id=place_id, observed_commit_id=observed_commit_id, observed_at=now,
                                       evidence_json=evidence, reporter_id=reporter_id, severity=severity,
                                       responsible_party=responsible_party, due_at=due_at, status="open",
                                       permissions_json=permissions or {},
                                       history_json=[{"state": "open", "at": now.isoformat(), "actor_id": reporter_id}],
                                       residual_limitations_json=[], verification_json={})
            session.add(row)
            self._record(session, tenant_id, project_id, reporter_id, "construction:issue_create", "construction_issue",
                         row.issue_id, {"severity": severity, "issue_type": issue_type},
                         "construction.issue.created", "construction_issue")
            return self._issue_result(row, False)

    def transition_issue(self, issue_id: str, *, tenant_id: str, project_id: str, actor_id: str,
                         target_state: str, evidence: list[dict[str, Any]], note: str,
                         residual_limitations: list[str] | None = None) -> dict[str, Any]:
        if target_state not in ISSUE_STATES:
            raise ValidationError("ISSUE_STATE_INVALID", "unsupported issue state")
        transitions = {
            "open": {"acknowledged", "corrected", "disputed", "superseded"},
            "acknowledged": {"corrected", "disputed", "superseded"},
            "corrected": {"retest_required", "verified_closed", "open", "disputed"},
            "retest_required": {"verified_closed", "open", "disputed"},
            "disputed": {"open", "acknowledged", "superseded"},
            "verified_closed": set(), "superseded": set(),
        }
        with self.database.session() as session:
            row = self._scoped(session, ConstructionIssueRow, issue_id, tenant_id, project_id, "issue")
            if target_state == row.status:
                return self._issue_result(row, True)
            if target_state not in transitions.get(row.status, set()):
                raise ConflictError("ISSUE_TRANSITION_INVALID", f"cannot transition {row.status} to {target_state}")
            if target_state in {"corrected", "retest_required", "verified_closed"} and not evidence:
                raise ValidationError("ISSUE_TRANSITION_EVIDENCE", "correction, retest, and closure require evidence")
            verifier_id = actor_id if target_state == "verified_closed" else None
            if target_state == "verified_closed" and actor_id == row.reporter_id:
                raise ValidationError("ISSUE_INDEPENDENT_VERIFIER", "verified closure requires an independent verifier")
            history = list(row.history_json)
            history.append({"state": target_state, "at": db_now().isoformat(), "actor_id": actor_id,
                            "note": note, "evidence": evidence, "verifier_id": verifier_id})
            row.status = target_state
            row.history_json = history
            row.residual_limitations_json = residual_limitations or []
            if target_state == "verified_closed":
                row.verification_json = {"verifier_id": verifier_id, "verified_at": db_now().isoformat(),
                                         "evidence": evidence, "residual_limitations": residual_limitations or []}
            self._record(session, tenant_id, project_id, actor_id, "construction:issue_transition", "construction_issue",
                         issue_id, {"target_state": target_state, "verifier_id": verifier_id},
                         "construction.issue.transitioned", "construction_issue")
            return self._issue_result(row, False)

    def record_commissioning(self, *, tenant_id: str, project_id: str, system_type: str,
                             entity_ids: list[str], procedure: dict[str, Any], prerequisites: list[dict[str, Any]],
                             steps: list[dict[str, Any]], participants: list[dict[str, Any]],
                             instruments: list[dict[str, Any]], attachments: list[str], results: dict[str, Any],
                             actor_id: str, idempotency_key: str, issue_id: str | None = None,
                             retest_of_id: str | None = None, accept: bool = False) -> dict[str, Any]:
        if system_type not in SYSTEM_TYPES and system_type not in SYSTEM_PACKS:
            raise ValidationError("COMMISSIONING_SYSTEM_UNKNOWN", "unknown commissioning system")
        if not steps or not participants or not results:
            raise ValidationError("COMMISSIONING_INCOMPLETE", "commissioning requires steps, participants, and results")
        if any(not item.get("calibration_state") for item in instruments):
            raise ValidationError("INSTRUMENT_CALIBRATION_REQUIRED", "each instrument requires a calibration state")
        sensitive_paths = sorted(set(_forbidden_identity_paths(participants, path="$.participants") +
                                     _forbidden_identity_paths(instruments, path="$.instruments")))
        if sensitive_paths:
            raise ValidationError(
                "COMMISSIONING_CREDENTIAL_DATA_PROHIBITED",
                "commissioning records may retain actor references but not access credentials or biometric identifiers",
                {"paths": sensitive_paths},
            )
        request = {"system_type": system_type, "entity_ids": sorted(set(entity_ids)), "issue_id": issue_id,
                   "procedure": procedure, "prerequisites": prerequisites, "steps": steps,
                   "participants": participants, "instruments": instruments, "attachments": sorted(set(attachments)),
                   "results": results, "retest_of_id": retest_of_id, "accept": accept}
        request_hash = canonical_sha256(request)
        with self.database.session() as session:
            prior = self._idempotent(session, ConstructionCommissioningRow, tenant_id, project_id, idempotency_key, request_hash)
            if prior:
                return self._commissioning_result(prior, True)
            if issue_id:
                self._scoped(session, ConstructionIssueRow, issue_id, tenant_id, project_id, "issue")
            if retest_of_id:
                base = self._scoped(session, ConstructionCommissioningRow, retest_of_id, tenant_id, project_id, "commissioning_run")
                if base.system_type != system_type:
                    raise ConflictError("COMMISSIONING_RETEST_SYSTEM", "retest must target the same system")
            passed = bool(results.get("passed"))
            state = "accepted" if accept and passed else ("failed" if not passed else "completed")
            row = ConstructionCommissioningRow(commissioning_id=new_uuid(), tenant_id=tenant_id,
                                                project_id=project_id, idempotency_key=idempotency_key,
                                                request_hash=request_hash, system_type=system_type,
                                                entity_ids_json=sorted(set(entity_ids)), issue_id=issue_id,
                                                procedure_json=procedure, prerequisites_json=prerequisites,
                                                steps_json=steps, participants_json=participants,
                                                instruments_json=instruments, attachments_json=sorted(set(attachments)),
                                                results_json=results, retest_of_id=retest_of_id, state=state,
                                                accepted_by=actor_id if state == "accepted" else None,
                                                accepted_at=db_now() if state == "accepted" else None, created_by=actor_id)
            session.add(row)
            self._record(session, tenant_id, project_id, actor_id, "construction:commissioning_record", "construction_commissioning",
                         row.commissioning_id, {"system_type": system_type, "state": state, "passed": passed},
                         "construction.commissioning.recorded", "construction_commissioning")
            return self._commissioning_result(row, False)

    # Interchange, reports and handoff ----------------------------------------------------------
    def record_interchange(self, *, tenant_id: str, project_id: str, format: str, direction: str,
                           source_asset_id: str, source_sha256: str, schema_version: str, units: str,
                           crs: dict[str, Any], owner_history: dict[str, Any], global_ids: list[str],
                           classifications: dict[str, Any], properties: dict[str, Any], relationships: list[dict[str, Any]],
                           geometry_conversion_report: dict[str, Any], unsupported_constructs: list[dict[str, Any]],
                           alignment: dict[str, Any], mappings: list[dict[str, Any]], issues: list[dict[str, Any]],
                           truth_labels: dict[str, Any], actor_id: str, idempotency_key: str) -> dict[str, Any]:
        format_name = format.upper()
        if format_name not in {"IFC", "BCF", "CSV", "GLB", "PLY", "LAS", "E57", "SIP-OPEN"}:
            raise ValidationError("INTERCHANGE_FORMAT", "unsupported construction interchange format")
        if direction not in {"import", "export"} or not units or not schema_version:
            raise ValidationError("INTERCHANGE_INVALID", "interchange direction, units, and schema version are required")
        digest = _hex64(source_sha256)
        request = {"format": format_name, "direction": direction, "source_asset_id": source_asset_id,
                   "source_sha256": digest, "schema_version": schema_version, "units": units, "crs": crs,
                   "owner_history": owner_history, "global_ids": sorted(set(global_ids)),
                   "classifications": classifications, "properties": properties, "relationships": relationships,
                   "geometry_conversion_report": geometry_conversion_report,
                   "unsupported_constructs": unsupported_constructs, "alignment": alignment, "mappings": mappings,
                   "issues": issues, "truth_labels": truth_labels}
        request_hash = canonical_sha256(request)
        with self.database.session() as session:
            prior = self._idempotent(session, ConstructionInterchangeRow, tenant_id, project_id, idempotency_key, request_hash)
            if prior:
                return self._interchange_result(prior, True)
            if not source_asset_id:
                raise ValidationError("INTERCHANGE_ASSET_REQUIRED", "interchange records require an immutable source asset")
            asset = session.get(AssetRefRow, source_asset_id)
            if (
                not asset
                or asset.tenant_id != tenant_id
                or asset.project_id != project_id
                or asset.sha256 != digest
                or asset.tombstoned_at is not None
            ):
                raise ValidationError("INTERCHANGE_ASSET_SCOPE", "interchange source asset is out of scope or mismatched")
            row = ConstructionInterchangeRow(interchange_id=new_uuid(), tenant_id=tenant_id, project_id=project_id,
                                              idempotency_key=idempotency_key, request_hash=request_hash,
                                              format=format_name, direction=direction, source_asset_id=source_asset_id,
                                              source_sha256=digest, schema_version=schema_version, units=units, crs_json=crs,
                                              owner_history_json=owner_history, global_ids_json=sorted(set(global_ids)),
                                              classifications_json=classifications, properties_json=properties,
                                              relationships_json=relationships,
                                              geometry_conversion_report_json=geometry_conversion_report,
                                              unsupported_constructs_json=unsupported_constructs,
                                              alignment_json=alignment, mappings_json=mappings, issues_json=issues,
                                              truth_labels_json=truth_labels, status="validated" if not issues else "review_required",
                                              created_by=actor_id)
            session.add(row)
            self._record(session, tenant_id, project_id, actor_id, "construction:interchange_record", "construction_interchange",
                         row.interchange_id, {"format": format_name, "direction": direction, "status": row.status},
                         "construction.interchange.recorded", "construction_interchange")
            return self._interchange_result(row, False)

    def technical_report(self, tenant_id: str, project_id: str, *, as_of: datetime | None = None,
                         audience: str = "technical", scope: dict[str, Any] | None = None,
                         visit_id: str | None = None, scene_commit_id: str | None = None,
                         author_id: str = "sip-report-service", template_version: str = "1.0",
                         filters: dict[str, Any] | None = None, design_revision_ids: list[str] | None = None,
                         representations_used: list[str] | None = None,
                         excluded_areas: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        with self.database.session() as session:
            rows = list(session.scalars(select(ConstructionRecordRow).where(ConstructionRecordRow.tenant_id == tenant_id,
                                                                            ConstructionRecordRow.project_id == project_id)))
            measurements = list(session.scalars(select(MeasurementRow).where(MeasurementRow.tenant_id == tenant_id,
                                                                             MeasurementRow.project_id == project_id)))
            issues = list(session.scalars(select(ConstructionIssueRow).where(ConstructionIssueRow.tenant_id == tenant_id,
                                                                            ConstructionIssueRow.project_id == project_id)))
            commissioning = list(session.scalars(select(ConstructionCommissioningRow).where(
                ConstructionCommissioningRow.tenant_id == tenant_id, ConstructionCommissioningRow.project_id == project_id)))
            documents = list(session.scalars(select(ConstructionDocumentRevisionRow).where(
                ConstructionDocumentRevisionRow.tenant_id == tenant_id, ConstructionDocumentRevisionRow.project_id == project_id)))
        if as_of:
            rows = [r for r in rows if r.created_at <= as_of]
            issues = [r for r in issues if r.created_at <= as_of]
            commissioning = [r for r in commissioning if r.created_at <= as_of]
            documents = [r for r in documents if r.created_at <= as_of]
        generated_at = db_now()
        source_timestamps = [
            *(row.created_at for row in rows),
            *(issue.updated_at or issue.created_at for issue in issues),
            *(run.accepted_at or run.created_at for run in commissioning),
            *(document.created_at for document in documents),
            *(measurement.verified_at or measurement.measured_at or measurement.created_at for measurement in measurements),
        ]
        data_cutoff = as_of or (max(source_timestamps) if source_timestamps else None)
        report = {
            "report_type": "construction_technical", "tenant_id": tenant_id, "project_id": project_id,
            "scope": scope or {"project_id": project_id}, "visit_id": visit_id,
            "scene_commit_id": scene_commit_id, "design_revision_ids": sorted(set(design_revision_ids or [])),
            "author_id": author_id, "template_version": template_version,
            "audience": audience, "query_filters": filters or {},
            "as_of": as_of.isoformat() if as_of else None,
            "data_cutoff": data_cutoff.isoformat() if data_cutoff else None,
            "generated_at": generated_at.isoformat(),
            "representations_used": representations_used or ["semantic", "evidence"],
            "excluded_areas": excluded_areas or [],
            "record_counts": dict(sorted(Counter(r.record_type for r in rows).items())),
            "state_counts": dict(sorted(Counter(r.state for r in rows).items())),
            "issue_counts": dict(sorted(Counter(r.status for r in issues).items())),
            "commissioning_counts": dict(sorted(Counter(r.state for r in commissioning).items())),
            "document_revisions": len(documents),
            "measurements": [{"measurement_id": m.measurement_id, "value": m.value, "unit": m.unit,
                               "uncertainty": m.uncertainty, "authority_class": m.authority_class,
                               "verifier_id": m.verifier_id, "verified_at": m.verified_at.isoformat() if m.verified_at else None,
                               "source_asset_ids": m.source_asset_ids_json, "calibration": m.calibration_json}
                              for m in sorted(measurements, key=lambda item: item.measurement_id)],
            "measurement_authority": {
                "field_verified": "eligible for its explicitly recorded permitted use only",
                "scan_estimate": "unverified estimate; not fabrication or survey authority",
                "design": "design intent; not field-observed as-built evidence",
            },
            "limitations": [
                "Counts and states reflect the selected project snapshot and filters.",
                "Unobserved or inaccessible areas are not evidence of absence.",
            ],
            "warnings": ["Phone-derived geometry is not survey-grade, fabrication-ready, contract-authoritative, code-compliant, or verified as-built without independent verification."],
        }
        stable = {k: v for k, v in report.items() if k != "generated_at"}
        report["report_hash"] = canonical_sha256(stable)
        return report

    def owner_report(self, tenant_id: str, project_id: str, *, as_of: datetime | None = None) -> dict[str, Any]:
        technical = self.technical_report(tenant_id, project_id, as_of=as_of, audience="owner")
        body = {"report_type": "construction_owner", "project_id": project_id, "as_of": technical["as_of"],
                "open_issues": sum(v for k, v in technical["issue_counts"].items() if k not in {"verified_closed", "superseded"}),
                "verified_measurement_count": sum(1 for item in technical["measurements"] if item["authority_class"] == "field_verified"),
                "systems": {k: v for k, v in technical["record_counts"].items() if k in SYSTEM_TYPES},
                "commissioning": technical["commissioning_counts"], "document_revisions": technical["document_revisions"],
                "warning": technical["warnings"][0], "technical_report_hash": technical["report_hash"]}
        return {**body, "report_hash": canonical_sha256(body)}

    def approve_restricted_export(
        self,
        *,
        tenant_id: str,
        project_id: str,
        scope: dict[str, Any],
        accepted_scene_commit_id: str | None,
        warranties: list[dict[str, Any]],
        training: list[dict[str, Any]],
        exclusions: list[str],
        audience_profiles: dict[str, Any],
        destination_name: str,
        classification: str,
        audience: str,
        purpose: str,
        approver_id: str,
        expires_at: datetime,
    ) -> dict[str, Any]:
        if scope.get("include_restricted_annex") is not True:
            raise ValidationError(
                "RESTRICTED_EXPORT_SCOPE_REQUIRED",
                "restricted-export approval requires an explicit restricted annex scope",
            )
        if not classification.strip() or not audience.strip() or not purpose.strip():
            raise ValidationError(
                "RESTRICTED_EXPORT_CONTEXT_REQUIRED",
                "classification, audience, and purpose are required",
            )
        normalized_expiry = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
        if normalized_expiry <= db_now():
            raise ValidationError("RESTRICTED_EXPORT_APPROVAL_EXPIRED", "approval expiry must be in the future")
        request = _handoff_request_payload(
            scope=scope,
            accepted_scene_commit_id=accepted_scene_commit_id,
            warranties=warranties,
            training=training,
            exclusions=exclusions,
            audience_profiles=audience_profiles,
            destination_name=destination_name,
            classification=classification,
            audience=audience,
            purpose=purpose,
        )
        request_hash = canonical_sha256(request)
        approval_body = {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "request_hash": request_hash,
            "scope": scope,
            "classification": classification,
            "audience": audience,
            "purpose": purpose,
            "approver_id": approver_id,
            "expires_at": normalized_expiry.isoformat(),
        }
        approval_hash = canonical_sha256(approval_body)
        with self.database.session() as session:
            if accepted_scene_commit_id:
                self._scoped_commit(session, accepted_scene_commit_id, tenant_id, project_id)
            existing = session.scalar(select(ConstructionRestrictedExportApprovalRow).where(
                ConstructionRestrictedExportApprovalRow.tenant_id == tenant_id,
                ConstructionRestrictedExportApprovalRow.project_id == project_id,
                ConstructionRestrictedExportApprovalRow.request_hash == request_hash,
                ConstructionRestrictedExportApprovalRow.approver_id == approver_id,
            ))
            if existing:
                if existing.approval_hash != approval_hash:
                    raise ConflictError(
                        "RESTRICTED_EXPORT_APPROVAL_CONFLICT",
                        "an approval already exists for this request with different immutable context",
                    )
                return self._restricted_export_approval_result(existing, True)
            row = ConstructionRestrictedExportApprovalRow(
                approval_id=new_uuid(),
                tenant_id=tenant_id,
                project_id=project_id,
                request_hash=request_hash,
                scope_json=scope,
                classification=classification,
                audience=audience,
                purpose=purpose,
                approver_id=approver_id,
                expires_at=normalized_expiry,
                approval_hash=approval_hash,
            )
            session.add(row)
            self._record(
                session,
                tenant_id,
                project_id,
                approver_id,
                "construction:restricted_export_approve",
                "construction_restricted_export_approval",
                row.approval_id,
                {
                    "request_hash": request_hash,
                    "classification": classification,
                    "audience": audience,
                    "purpose": purpose,
                    "expires_at": normalized_expiry.isoformat(),
                },
                "construction.restricted_export.approved",
                "construction_restricted_export_approval",
            )
            return self._restricted_export_approval_result(row, False)

    def create_owner_handoff(self, *, tenant_id: str, project_id: str, destination: Path, scope: dict[str, Any],
                             accepted_scene_commit_id: str | None, warranties: list[dict[str, Any]],
                             training: list[dict[str, Any]], exclusions: list[str], audience_profiles: dict[str, Any],
                             actor_id: str, idempotency_key: str,
                             classification: str = "internal", audience: str = "owner",
                             purpose: str = "owner_handoff",
                             restricted_export_approval_id: str | None = None) -> dict[str, Any]:
        if audience_profiles.get("restricted_owner_export_approved") is True:
            raise ValidationError(
                "RESTRICTED_EXPORT_CALLER_ASSERTION_PROHIBITED",
                "caller-controlled restricted-export approval flags are not authorization",
            )
        request = _handoff_request_payload(
            scope=scope,
            accepted_scene_commit_id=accepted_scene_commit_id,
            warranties=warranties,
            training=training,
            exclusions=exclusions,
            audience_profiles=audience_profiles,
            destination_name=destination.name,
            classification=classification,
            audience=audience,
            purpose=purpose,
        )
        request_hash = canonical_sha256(request)
        with self.database.session() as session:
            prior = self._idempotent(session, ConstructionHandoffRow, tenant_id, project_id, idempotency_key, request_hash)
            if prior and prior.status == "verified" and prior.package_path and Path(prior.package_path).is_file():
                replay_validation = self.verify_owner_handoff(Path(prior.package_path))
                retained_zip_hash = str((prior.validation_json or {}).get("zip_sha256") or "")
                if (
                    not replay_validation["valid"]
                    or replay_validation["root_hash"] != prior.root_hash
                    or not retained_zip_hash
                    or replay_validation["zip_sha256"] != retained_zip_hash
                ):
                    raise ConflictError(
                        "HANDOFF_REPLAY_PACKAGE_CHANGED",
                        "the retained handoff package no longer matches its verified identity",
                        {
                            "handoff_id": prior.handoff_id,
                            "retained_root_hash": prior.root_hash,
                            "current_root_hash": replay_validation.get("root_hash"),
                        },
                    )
                return self._handoff_result(prior, True)
            if prior and prior.status == "verified":
                raise ConflictError(
                    "HANDOFF_REPLAY_PACKAGE_MISSING",
                    "the retained verified handoff package is missing",
                    {"handoff_id": prior.handoff_id},
                )
            if prior:
                row = prior
            else:
                if accepted_scene_commit_id:
                    self._scoped_commit(session, accepted_scene_commit_id, tenant_id, project_id)
                row = ConstructionHandoffRow(handoff_id=new_uuid(), tenant_id=tenant_id, project_id=project_id,
                                              idempotency_key=idempotency_key, request_hash=request_hash,
                                              scope_json=scope, accepted_scene_commit_id=accepted_scene_commit_id,
                                              inventory_json={}, verified_attributes_json={}, documents_json=[], tests_json=[],
                                              warranties_json=warranties, training_json=training, open_issues_json=[],
                                              exclusions_json=exclusions, exports_json=[], representation_manifest_json={},
                                              audience_profiles_json=audience_profiles, offline_viewer_json={},
                                              limitations_json=[], checksums_json={}, root_hash="", package_path=None,
                                              status="building", validation_json={}, created_by=actor_id)
                session.add(row)
            include_restricted = scope.get("include_restricted_annex") is True
            if include_restricted:
                if not restricted_export_approval_id:
                    raise AuthorizationError(
                        "RESTRICTED_EXPORT_APPROVAL_REQUIRED",
                        "restricted owner export requires a current server-side approval record",
                    )
                approval = self._scoped(
                    session,
                    ConstructionRestrictedExportApprovalRow,
                    restricted_export_approval_id,
                    tenant_id,
                    project_id,
                    "restricted_export_approval",
                )
                approval_expiry = approval.expires_at if approval.expires_at.tzinfo else approval.expires_at.replace(tzinfo=UTC)
                mismatch = (
                    approval.request_hash != request_hash
                    or canonical_sha256(approval.scope_json) != canonical_sha256(scope)
                    or approval.classification != classification
                    or approval.audience != audience
                    or approval.purpose != purpose
                )
                if mismatch:
                    raise AuthorizationError(
                        "RESTRICTED_EXPORT_APPROVAL_MISMATCH",
                        "restricted-export approval does not match this handoff request",
                    )
                if approval_expiry <= db_now():
                    raise AuthorizationError(
                        "RESTRICTED_EXPORT_APPROVAL_EXPIRED",
                        "restricted-export approval has expired",
                    )
                if approval.approver_id == actor_id:
                    raise AuthorizationError(
                        "RESTRICTED_EXPORT_SEPARATION_OF_DUTIES",
                        "the handoff requester cannot approve their own restricted export",
                    )
            snapshot = self._handoff_snapshot(
                session, tenant_id, project_id, accepted_scene_commit_id,
                scope=scope, warranties=warranties, training=training, exclusions=exclusions,
                audience_profiles=audience_profiles, include_restricted=include_restricted,
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            checksums: dict[str, str] = {}
            with zipfile.ZipFile(temporary, "w") as archive:
                files = {
                    "manifest.json": canonical_json(snapshot["manifest"]),
                    "reports/technical.json": canonical_json(snapshot["technical"]),
                    "reports/owner.json": canonical_json(snapshot["owner"]),
                    "data/inventory.json": canonical_json(snapshot["inventory"]),
                    "data/documents.json": canonical_json(snapshot["documents"]),
                    "data/issues.json": canonical_json(snapshot["issues"]),
                    "data/commissioning.json": canonical_json(snapshot["commissioning"]),
                    "data/interchange.json": canonical_json(snapshot["interchange"]),
                    "data/handoff-validation.json": canonical_json(snapshot["handoff_validation"]),
                    "viewer/index.html": self._offline_owner_viewer(snapshot).encode(),
                    "README.txt": ("SIP open owner handoff. Verify checksums.json before use.\n"
                                   "Observed geometry is not survey-grade or design-authoritative without independent verification.\n").encode(),
                }
                for name, data in sorted(files.items()):
                    checksums[name] = _zip_write(archive, name, data)
                root = merkle_root(checksums.items())
                checksums_body = canonical_json({"algorithm": "sha256", "files": checksums, "root_hash": root})
                _zip_write(archive, "checksums.json", checksums_body)
            temporary.replace(destination)
            validation = self.verify_owner_handoff(destination)
            row.inventory_json = snapshot["inventory"]
            row.verified_attributes_json = snapshot["verified_attributes"]
            row.documents_json = snapshot["documents"]
            row.tests_json = snapshot["commissioning"]
            row.open_issues_json = [item for item in snapshot["issues"] if item["status"] not in {"verified_closed", "superseded"}]
            row.exports_json = snapshot["interchange"]
            row.representation_manifest_json = snapshot["manifest"]["representations"]
            row.offline_viewer_json = {"path": "viewer/index.html", "network_required": False}
            row.limitations_json = snapshot["manifest"]["limitations"]
            row.checksums_json = checksums
            row.root_hash = validation["root_hash"]
            row.package_path = str(destination)
            row.status = "verified" if validation["valid"] else "failed"
            row.validation_json = validation
            self._record(session, tenant_id, project_id, actor_id, "construction:handoff_create", "construction_handoff",
                         row.handoff_id, {"root_hash": row.root_hash, "status": row.status},
                         "construction.handoff.created", "construction_handoff")
            return self._handoff_result(row, False)

    @staticmethod
    def verify_owner_handoff(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise ValidationError("HANDOFF_MISSING", "handoff package does not exist")
        with zipfile.ZipFile(path) as archive:
            names = validate_zip_members(archive.infolist(), code_prefix="HANDOFF")
            validation = verify_checksum_manifest(
                archive,
                names,
                allowed_members=OWNER_HANDOFF_MEMBERS,
                required_members=OWNER_HANDOFF_MEMBERS,
                code_prefix="HANDOFF",
            )
        return {
            **validation,
            "zip_sha256": sha256_file(path),
            "member_count": len(names),
        }

    # Legacy adapters ---------------------------------------------------------------------------
    def attach_document(self, *, tenant_id: str, project_id: str, document_type: str, asset_id: str,
                        parent_id: str | None, page_region: dict[str, Any] | None,
                        spatial_anchor: dict[str, Any] | None, data: dict[str, Any], actor_id: str) -> str:
        if document_type not in DOCUMENT_TYPES:
            raise ValidationError("CONSTRUCTION_DOCUMENT_TYPE", "unsupported construction document type")
        identifier = new_uuid()
        with self.database.session() as session:
            session.add(ConstructionRecordRow(record_id=identifier, tenant_id=tenant_id, project_id=project_id,
                                               record_type=document_type, parent_id=parent_id, state="observed",
                                               data_json={**data, "asset_id": asset_id, "page_region": page_region,
                                                          "spatial_anchor": spatial_anchor},
                                               evidence_asset_ids_json=[asset_id], created_by=actor_id))
        return identifier

    def create_deficiency(self, *, tenant_id: str, project_id: str, entity_id: str, description: str,
                          severity: str, evidence_asset_ids: list[str], actor_id: str) -> str:
        result = self.create_issue(tenant_id=tenant_id, project_id=project_id, issue_type="deficiency",
                                   description=description, evidence=[{"asset_id": item} for item in evidence_asset_ids],
                                   reporter_id=actor_id, severity=severity, idempotency_key=f"legacy-deficiency:{new_uuid()}",
                                   entity_id=entity_id)
        # Keep legacy table compatibility for prior APIs and BCF export.
        identifier = new_uuid()
        with self.database.session() as session:
            session.add(ConstructionRecordRow(record_id=identifier, tenant_id=tenant_id, project_id=project_id,
                                               record_type="deficiency", entity_id=entity_id, state="open",
                                               data_json={"description": description, "severity": severity,
                                                          "issue_id": result["issue_id"],
                                                          "history": [{"state": "open", "at": db_now().isoformat(), "actor": actor_id}]},
                                               evidence_asset_ids_json=evidence_asset_ids, created_by=actor_id))
        return identifier

    def correct_and_retest(
        self,
        deficiency_id: str,
        *,
        tenant_id: str,
        project_id: str,
        correction: str,
        correction_asset_ids: list[str],
        test_result: str,
        test_asset_ids: list[str],
        tester_id: str,
    ) -> dict[str, Any]:
        if test_result not in {"pass", "fail"} or not correction_asset_ids or not test_asset_ids:
            raise ValidationError("CORRECTION_RETEST_EVIDENCE", "valid correction and retest evidence are required")
        with self.database.session() as session:
            row = self._scoped(session, ConstructionRecordRow, deficiency_id, tenant_id, project_id, "deficiency")
            if row.record_type != "deficiency":
                raise NotFoundError("deficiency", deficiency_id)
            if row.state == "closed":
                raise ConflictError("DEFICIENCY_ALREADY_CLOSED", "closed deficiency cannot be changed without a new record")
            history = list(row.data_json.get("history", []))
            history.extend([
                {"state": "corrected", "correction": correction, "asset_ids": correction_asset_ids,
                 "at": db_now().isoformat(), "actor": tester_id},
                {"state": "retested", "result": test_result, "asset_ids": test_asset_ids,
                 "at": db_now().isoformat(), "actor": tester_id},
            ])
            row.state = "closed" if test_result == "pass" else "open"
            row.data_json = {**row.data_json, "history": history, "last_test_result": test_result,
                             "closed_by": tester_id if test_result == "pass" else None}
            row.evidence_asset_ids_json = sorted(set(row.evidence_asset_ids_json + correction_asset_ids + test_asset_ids))
            return {"deficiency_id": deficiency_id, "state": row.state, "test_result": test_result, "history_count": len(history)}

    def compare_temporal_states(
        self, tenant_id: str, project_id: str, *, before_ids: list[str], after_ids: list[str],
        confirmed_removed_ids: list[str] | None = None, occluded_ids: list[str] | None = None,
        unobserved_ids: list[str] | None = None, uncertain_ids: list[str] | None = None,
        baseline_commit_id: str | None = None, comparison_commit_id: str | None = None,
        comparable_coverage: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        before, after = set(before_ids), set(after_ids)
        all_ids = before | after
        with self.database.session() as session:
            rows = {row.record_id: row for row in session.scalars(select(ConstructionRecordRow).where(
                ConstructionRecordRow.tenant_id == tenant_id,
                ConstructionRecordRow.project_id == project_id,
                ConstructionRecordRow.record_id.in_(all_ids),
            ))}
            if baseline_commit_id:
                self._scoped_commit(session, baseline_commit_id, tenant_id, project_id)
            if comparison_commit_id:
                self._scoped_commit(session, comparison_commit_id, tenant_id, project_id)
        missing_records = sorted(all_ids - set(rows))
        if missing_records:
            raise NotFoundError("construction_record", missing_records[0])
        removal_candidates = before - after
        confirmed_removed = set(confirmed_removed_ids or [])
        occluded = set(occluded_ids or [])
        unobserved = set(unobserved_ids or [])
        uncertain = set(uncertain_ids or [])
        invalid_confirmed = confirmed_removed - removal_candidates
        if invalid_confirmed:
            raise ValidationError(
                "TEMPORAL_REMOVAL_NOT_CANDIDATE",
                "confirmed removals must exist in the baseline and be absent from the comparison",
                {"record_ids": sorted(invalid_confirmed)},
            )
        conflicting = confirmed_removed & (occluded | unobserved | uncertain)
        if conflicting:
            raise ValidationError(
                "TEMPORAL_REMOVAL_COVERAGE_CONFLICT",
                "occluded, unobserved, or uncertain records cannot be confirmed removed",
                {"record_ids": sorted(conflicting)},
            )
        unresolved = removal_candidates - confirmed_removed - occluded - unobserved - uncertain
        modified = [record_id for record_id in sorted(before & after)
                    if rows[record_id].superseded_at is not None]
        body = {
            "baseline_commit_id": baseline_commit_id,
            "comparison_commit_id": comparison_commit_id,
            "comparable_coverage": comparable_coverage or {},
            "added": sorted(after - before),
            "removed": sorted(confirmed_removed),
            "modified_or_superseded": modified,
            "occluded": sorted(occluded & removal_candidates),
            "unobserved": sorted(unobserved & removal_candidates),
            "uncertain": sorted((uncertain | unresolved) & removal_candidates),
            "review_required": sorted((occluded | unobserved | uncertain | unresolved) & removal_candidates),
            "semantic_state_changed": False,
            "warning": "Only explicitly confirmed, comparably observed absences are classified as removed; all other gaps require review.",
        }
        return {**body, "comparison_hash": canonical_sha256(body)}

    def export_bcf(self, tenant_id: str, project_id: str, destination: Path) -> dict[str, Any]:
        with self.database.session() as session:
            issues = list(session.scalars(select(ConstructionIssueRow).where(ConstructionIssueRow.tenant_id == tenant_id,
                                                                            ConstructionIssueRow.project_id == project_id)))
        payload = {"bcf_version": "3.0", "project_id": project_id,
                   "topics": [{"guid": r.issue_id, "title": r.description, "topic_status": r.status,
                               "priority": r.severity, "reference_links": r.evidence_json,
                               "labels": ["SIP", "open-handoff"]} for r in issues]}
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return {"path": str(destination), "sha256": canonical_sha256(payload), "topics": len(payload["topics"]), "format": "BCF-JSON-reference"}

    def export_ifc_handoff_manifest(self, tenant_id: str, project_id: str, destination: Path) -> dict[str, Any]:
        report = self.technical_report(tenant_id, project_id)
        payload = {"format": "SIP-IFC-HANDOFF-MANIFEST-1.0", "project_id": project_id,
                   "design_authority_preserved": True, "observed_geometry_not_promoted_to_design": True,
                   "record_counts": report["record_counts"],
                   "measurement_ids": [m["measurement_id"] for m in report["measurements"]],
                   "limitations": report["warnings"]}
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return {"path": str(destination), "sha256": canonical_sha256(payload), "format": payload["format"]}

    # Internal helpers --------------------------------------------------------------------------
    def _record(self, session: Session, tenant_id: str, project_id: str, actor_id: str, action: str,
                resource_type: str, resource_id: str, details: dict[str, Any], event_type: str,
                aggregate_type: str) -> None:
        self.audit.append(tenant_id=tenant_id, project_id=project_id, actor_id=actor_id, action=action,
                          resource_type=resource_type, resource_id=resource_id, outcome="allowed",
                          details=details, session=session)
        event = self.events.create(session, event_type=event_type, schema_version="1.0.0", tenant_id=tenant_id,
                                   project_id=project_id, aggregate_type=aggregate_type, aggregate_id=resource_id,
                                   payload={"resource_id": resource_id, **details}, producer="construction",
                                   actor_id=actor_id, workload_identity=None)
        session.add(event)

    @staticmethod
    def _idempotent(session: Session, model: type[T], tenant_id: str, project_id: str,
                    key: str, request_hash: str) -> T | None:
        prior = session.scalar(select(model).where(model.tenant_id == tenant_id, model.project_id == project_id,
                                                   model.idempotency_key == key))
        if prior and prior.request_hash != request_hash:
            raise ConflictError("IDEMPOTENCY_PAYLOAD_CONFLICT", "idempotency key was reused with different input")
        return prior

    @staticmethod
    def _scoped(session: Session, model: type[T], identifier: str, tenant_id: str, project_id: str, label: str) -> T:
        row = session.get(model, identifier)
        if not row or row.tenant_id != tenant_id or row.project_id != project_id:
            raise NotFoundError(label, identifier)
        return row

    def _scoped_record(self, session: Session, identifier: str, tenant_id: str, project_id: str) -> ConstructionRecordRow:
        return self._scoped(session, ConstructionRecordRow, identifier, tenant_id, project_id, "construction_record")

    @staticmethod
    def _scoped_commit(session: Session, identifier: str, tenant_id: str, project_id: str) -> SceneCommitRow:
        row = session.get(SceneCommitRow, identifier)
        if not row or row.tenant_id != tenant_id or row.project_id != project_id:
            raise NotFoundError("scene_commit", identifier)
        return row

    @staticmethod
    def _pack_for_type(system_type: str) -> dict[str, Any]:
        for name, pack in SYSTEM_PACKS.items():
            if system_type in pack["types"]:
                return {**pack, "name": name}
        raise ValidationError("CONSTRUCTION_PACK_UNKNOWN", "system type is not assigned to a pack")

    @staticmethod
    def _survey_result(row: ConstructionSurveyRow, replay: bool) -> dict[str, Any]:
        return {"survey_id": row.survey_id, "state": row.state, "request_hash": row.request_hash,
                "accepted_commit_id": row.accepted_commit_id, "completion_hash": row.completion_hash,
                "idempotent_replay": replay}

    @staticmethod
    def _visit_result(row: ConstructionVisitRow, replay: bool) -> dict[str, Any]:
        return {"visit_id": row.visit_id, "survey_id": row.survey_id, "state": row.state,
                "report_hash": row.report_hash, "idempotent_replay": replay}

    @staticmethod
    def _issue_result(row: ConstructionIssueRow, replay: bool) -> dict[str, Any]:
        return {"issue_id": row.issue_id, "status": row.status, "severity": row.severity,
                "history_count": len(row.history_json), "verification": row.verification_json,
                "idempotent_replay": replay}

    @staticmethod
    def _commissioning_result(row: ConstructionCommissioningRow, replay: bool) -> dict[str, Any]:
        return {"commissioning_id": row.commissioning_id, "state": row.state, "system_type": row.system_type,
                "results": row.results_json, "idempotent_replay": replay}

    @staticmethod
    def _interchange_result(row: ConstructionInterchangeRow, replay: bool) -> dict[str, Any]:
        return {"interchange_id": row.interchange_id, "format": row.format, "direction": row.direction,
                "status": row.status, "request_hash": row.request_hash, "idempotent_replay": replay}

    @staticmethod
    def _handoff_result(row: ConstructionHandoffRow, replay: bool) -> dict[str, Any]:
        return {"handoff_id": row.handoff_id, "status": row.status, "package_path": row.package_path,
                "root_hash": row.root_hash, "validation": row.validation_json, "idempotent_replay": replay}

    @staticmethod
    def _restricted_export_approval_result(
        row: ConstructionRestrictedExportApprovalRow,
        replay: bool,
    ) -> dict[str, Any]:
        return {
            "approval_id": row.approval_id,
            "request_hash": row.request_hash,
            "classification": row.classification,
            "audience": row.audience,
            "purpose": row.purpose,
            "approver_id": row.approver_id,
            "expires_at": row.expires_at.isoformat(),
            "approval_hash": row.approval_hash,
            "idempotent_replay": replay,
        }

    @staticmethod
    def _document_body(row: ConstructionDocumentRevisionRow) -> dict[str, Any]:
        return {"document_type": row.document_type, "title": row.title, "revision": row.revision,
                "issue_date": row.issue_date, "issuer": row.issuer, "status": row.status,
                "asset_id": row.asset_id, "source_sha256": row.source_sha256, "page_count": row.page_count,
                "permissions": row.permissions_json, "supersedes_revision_id": row.supersedes_revision_id,
                "page_regions": row.page_regions_json, "spatial_links": row.spatial_links_json,
                "extraction": row.extraction_json, "review": row.review_json}

    def _handoff_snapshot(self, session: Session, tenant_id: str, project_id: str,
                          accepted_commit_id: str | None, *, scope: dict[str, Any],
                          warranties: list[dict[str, Any]], training: list[dict[str, Any]],
                          exclusions: list[str], audience_profiles: dict[str, Any],
                          include_restricted: bool) -> dict[str, Any]:
        records = list(session.scalars(select(ConstructionRecordRow).where(
            ConstructionRecordRow.tenant_id == tenant_id,
            ConstructionRecordRow.project_id == project_id,
        )))
        docs = list(session.scalars(select(ConstructionDocumentRevisionRow).where(
            ConstructionDocumentRevisionRow.tenant_id == tenant_id,
            ConstructionDocumentRevisionRow.project_id == project_id,
        )))
        issues = list(session.scalars(select(ConstructionIssueRow).where(
            ConstructionIssueRow.tenant_id == tenant_id,
            ConstructionIssueRow.project_id == project_id,
        )))
        runs = list(session.scalars(select(ConstructionCommissioningRow).where(
            ConstructionCommissioningRow.tenant_id == tenant_id,
            ConstructionCommissioningRow.project_id == project_id,
        )))
        interchanges = list(session.scalars(select(ConstructionInterchangeRow).where(
            ConstructionInterchangeRow.tenant_id == tenant_id,
            ConstructionInterchangeRow.project_id == project_id,
        )))

        inventory: list[dict[str, Any]] = []
        redaction_summary: list[dict[str, Any]] = []
        required_field_findings: list[dict[str, Any]] = []
        for record in records:
            data = dict(record.data_json)
            redacted: list[str] = []
            if record.record_type in SYSTEM_TYPES:
                pack = self._pack_for_type(record.record_type)
                if not include_restricted:
                    for key in sorted(pack["restricted"]):
                        if key in data:
                            data.pop(key)
                            redacted.append(key)
                missing = list(data.get("missing_required_fields", []))
                if missing:
                    required_field_findings.append({
                        "record_id": record.record_id,
                        "record_type": record.record_type,
                        "missing_fields": missing,
                    })
            if redacted:
                redaction_summary.append({"record_id": record.record_id, "fields": redacted})
            inventory.append({
                "record_id": record.record_id, "type": record.record_type, "parent_id": record.parent_id,
                "entity_id": record.entity_id, "state": record.state, "data": data,
                "evidence_asset_ids": record.evidence_asset_ids_json, "redacted_fields": redacted,
            })

        doc_data: list[dict[str, Any]] = []
        excluded_documents: list[dict[str, Any]] = []
        for document in docs:
            permissions = document.permissions_json or {}
            restricted_document = document.document_type in {"programming_record"} or permissions.get("owner_export") is False
            if restricted_document and not include_restricted:
                excluded_documents.append({
                    "revision_id": document.revision_id,
                    "document_type": document.document_type,
                    "reason": "restricted_owner_export",
                })
                continue
            doc_data.append({"revision_id": document.revision_id, "stable_document_id": document.stable_document_id,
                             **self._document_body(document)})

        issue_data = [{"issue_id": item.issue_id, "type": item.issue_type, "description": item.description,
                       "status": item.status, "severity": item.severity, "evidence": item.evidence_json,
                       "history": item.history_json, "verification": item.verification_json} for item in issues]
        run_data = [{"commissioning_id": run.commissioning_id, "system_type": run.system_type, "state": run.state,
                     "procedure": run.procedure_json, "steps": run.steps_json, "results": run.results_json,
                     "participants": run.participants_json, "instruments": run.instruments_json} for run in runs]
        interchange_data = [{"interchange_id": item.interchange_id, "format": item.format,
                             "direction": item.direction, "source_sha256": item.source_sha256,
                             "schema_version": item.schema_version, "units": item.units, "crs": item.crs_json,
                             "status": item.status, "unsupported_constructs": item.unsupported_constructs_json,
                             "truth_labels": item.truth_labels_json} for item in interchanges]
        technical = self.technical_report(
            tenant_id, project_id, audience="owner", scope=scope,
            scene_commit_id=accepted_commit_id, author_id="sip-owner-handoff-service",
            template_version="1.0", filters={"handoff": True},
            representations_used=["semantic", "evidence", "metric", "design"],
        )
        owner = self.owner_report(tenant_id, project_id)
        handoff_validation = {
            "status": "passed" if not required_field_findings else "needs_review",
            "required_field_findings": required_field_findings,
            "excluded_documents": excluded_documents,
            "redactions": redaction_summary,
            "restricted_annex_included": include_restricted,
        }
        manifest = {
            "format": "SIP-CONSTRUCTION-HANDOFF-1.0", "tenant_id": tenant_id, "project_id": project_id,
            "scope": scope, "accepted_scene_commit_id": accepted_commit_id,
            "inventory_count": len(inventory), "document_revision_count": len(doc_data),
            "issue_count": len(issue_data), "commissioning_count": len(run_data),
            "interchange_count": len(interchange_data), "warranties": warranties, "training": training,
            "exclusions": exclusions, "audience_profiles": audience_profiles,
            "handoff_validation": handoff_validation,
            "representations": {"metric": "authoritative only when independently verified",
                                "visual": "photorealistic non-metric", "interaction": "disposable proxy",
                                "design": "design intent", "evidence": "immutable source links"},
            "limitations": technical["warnings"], "open_format": True, "offline_viewer": True,
        }
        verified = {record.record_id: {"state": record.state, "verified_by": record.data_json.get("verified_by")}
                    for record in records if record.state == "verified"}
        return {"manifest": manifest, "inventory": inventory, "documents": doc_data, "issues": issue_data,
                "commissioning": run_data, "interchange": interchange_data, "technical": technical,
                "owner": owner, "verified_attributes": verified, "handoff_validation": handoff_validation}

    @staticmethod
    def _offline_owner_viewer(snapshot: dict[str, Any]) -> str:
        manifest = snapshot["manifest"]
        return """<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>
<title>SIP Owner Handoff</title><style>body{font:16px system-ui;max-width:72rem;margin:auto;padding:2rem}table{border-collapse:collapse}td,th{border:1px solid #777;padding:.4rem} .warn{border:2px solid;padding:1rem}</style>
<h1>SIP Construction Owner Handoff</h1><p class='warn'>%s</p><dl><dt>Project</dt><dd>%s</dd><dt>Inventory</dt><dd>%d records</dd><dt>Documents</dt><dd>%d revisions</dd><dt>Issues</dt><dd>%d</dd><dt>Commissioning</dt><dd>%d runs</dd></dl><p>This viewer is read-only and requires no network connection.</p></html>""" % (
            escape(manifest["limitations"][0]), escape(manifest["project_id"]), manifest["inventory_count"],
            manifest["document_revision_count"], manifest["issue_count"], manifest["commissioning_count"])
