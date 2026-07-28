from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import select

from .audit import AuditService
from .canonical import canonical_sha256, new_uuid
from .database import ConstructionRecordRow, Database, MeasurementRow
from .errors import ConflictError, NotFoundError, ValidationError
from .temporal import db_now


HIERARCHY_PARENT = {
    "site": None,
    "building": "site",
    "level": "building",
    "zone": "level",
    "room": "level",
}

CONDITION_STATES = {"observed", "inferred", "design", "proposed", "measured", "verified", "disputed", "superseded"}

SYSTEM_TYPES = {
    "fire_alarm_panel",
    "fire_alarm_annunciator",
    "fire_alarm_device",
    "fire_alarm_circuit",
    "fire_alarm_network",
    "fire_alarm_interface",
    "access_opening",
    "access_reader",
    "access_lock",
    "access_contact",
    "access_rex",
    "access_controller",
    "bas_equipment",
    "bas_point",
    "mechanical_equipment",
    "electrical_equipment",
    "system_interconnection",
}

DOCUMENT_TYPES = {"drawing", "specification", "submittal", "rfi", "photo", "video", "note", "cutsheet", "test_record", "programming_record"}


class ConstructionService:
    def __init__(self, database: Database, audit: AuditService) -> None:
        self.database = database
        self.audit = audit

    def create_hierarchy_item(
        self,
        *,
        tenant_id: str,
        project_id: str,
        record_type: str,
        name: str,
        parent_id: str | None,
        state: str,
        actor_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> str:
        if record_type not in HIERARCHY_PARENT:
            raise ValidationError("CONSTRUCTION_HIERARCHY_TYPE", "unsupported construction hierarchy type")
        if state not in CONDITION_STATES:
            raise ValidationError("CONSTRUCTION_STATE", "unsupported condition state")
        with self.database.session() as session:
            expected_parent = HIERARCHY_PARENT[record_type]
            if expected_parent is None and parent_id is not None:
                raise ValidationError("CONSTRUCTION_PARENT_INVALID", f"{record_type} cannot have a parent")
            if expected_parent is not None:
                parent = session.get(ConstructionRecordRow, parent_id) if parent_id else None
                if not parent or parent.tenant_id != tenant_id or parent.project_id != project_id or parent.record_type != expected_parent:
                    raise ValidationError("CONSTRUCTION_PARENT_INVALID", f"{record_type} requires parent type {expected_parent}")
            identifier = new_uuid()
            session.add(
                ConstructionRecordRow(
                    record_id=identifier,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    record_type=record_type,
                    parent_id=parent_id,
                    state=state,
                    data_json={"name": name, **(attributes or {})},
                    created_by=actor_id,
                )
            )
            self._audit(session, tenant_id, project_id, actor_id, "construction:hierarchy_create", identifier, {"record_type": record_type, "state": state})
            return identifier

    def create_system_record(
        self,
        *,
        tenant_id: str,
        project_id: str,
        system_type: str,
        parent_id: str | None,
        entity_id: str | None,
        state: str,
        data: dict[str, Any],
        evidence_asset_ids: list[str],
        actor_id: str,
    ) -> str:
        if system_type not in SYSTEM_TYPES:
            raise ValidationError("CONSTRUCTION_SYSTEM_TYPE", "unsupported building system record")
        if state not in CONDITION_STATES:
            raise ValidationError("CONSTRUCTION_STATE", "unsupported condition state")
        if state in {"observed", "measured", "verified"} and not evidence_asset_ids:
            raise ValidationError("CONSTRUCTION_EVIDENCE_REQUIRED", "observed/measured/verified system records require evidence")
        if state == "verified" and not data.get("verified_by"):
            raise ValidationError("CONSTRUCTION_VERIFIER_REQUIRED", "verified system record requires a verifier")
        identifier = new_uuid()
        with self.database.session() as session:
            session.add(
                ConstructionRecordRow(
                    record_id=identifier,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    record_type=system_type,
                    parent_id=parent_id,
                    entity_id=entity_id,
                    state=state,
                    data_json=data,
                    evidence_asset_ids_json=evidence_asset_ids,
                    created_by=actor_id,
                )
            )
            self._audit(session, tenant_id, project_id, actor_id, "construction:system_create", identifier, {"system_type": system_type, "state": state})
        return identifier

    def attach_document(
        self,
        *,
        tenant_id: str,
        project_id: str,
        document_type: str,
        asset_id: str,
        parent_id: str | None,
        page_region: dict[str, Any] | None,
        spatial_anchor: dict[str, Any] | None,
        data: dict[str, Any],
        actor_id: str,
    ) -> str:
        if document_type not in DOCUMENT_TYPES:
            raise ValidationError("CONSTRUCTION_DOCUMENT_TYPE", "unsupported construction document type")
        if page_region and not asset_id:
            raise ValidationError("PAGE_REGION_ASSET_REQUIRED", "page-region anchor requires an asset")
        identifier = new_uuid()
        with self.database.session() as session:
            session.add(
                ConstructionRecordRow(
                    record_id=identifier,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    record_type=document_type,
                    parent_id=parent_id,
                    state="observed",
                    data_json={**data, "asset_id": asset_id, "page_region": page_region, "spatial_anchor": spatial_anchor},
                    evidence_asset_ids_json=[asset_id],
                    created_by=actor_id,
                )
            )
        return identifier

    def create_deficiency(
        self,
        *,
        tenant_id: str,
        project_id: str,
        entity_id: str,
        description: str,
        severity: str,
        evidence_asset_ids: list[str],
        actor_id: str,
    ) -> str:
        if severity not in {"low", "medium", "high", "life_safety"}:
            raise ValidationError("DEFICIENCY_SEVERITY", "unsupported deficiency severity")
        if not evidence_asset_ids:
            raise ValidationError("DEFICIENCY_EVIDENCE_REQUIRED", "deficiency requires evidence")
        identifier = new_uuid()
        with self.database.session() as session:
            session.add(
                ConstructionRecordRow(
                    record_id=identifier,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    record_type="deficiency",
                    entity_id=entity_id,
                    state="open",
                    data_json={"description": description, "severity": severity, "history": [{"state": "open", "at": db_now().isoformat(), "actor": actor_id}]},
                    evidence_asset_ids_json=evidence_asset_ids,
                    created_by=actor_id,
                )
            )
        return identifier

    def correct_and_retest(
        self,
        deficiency_id: str,
        *,
        correction: str,
        correction_asset_ids: list[str],
        test_result: str,
        test_asset_ids: list[str],
        tester_id: str,
    ) -> dict[str, Any]:
        if test_result not in {"pass", "fail"}:
            raise ValidationError("RETEST_RESULT", "retest result must be pass or fail")
        if not correction_asset_ids or not test_asset_ids:
            raise ValidationError("CORRECTION_RETEST_EVIDENCE", "correction and retest each require evidence")
        with self.database.session() as session:
            row = session.get(ConstructionRecordRow, deficiency_id)
            if not row or row.record_type != "deficiency":
                raise NotFoundError("deficiency", deficiency_id)
            if row.state == "closed":
                raise ConflictError("DEFICIENCY_ALREADY_CLOSED", "closed deficiency cannot be changed without a new record")
            history = list(row.data_json.get("history", []))
            history.append({"state": "corrected", "correction": correction, "asset_ids": correction_asset_ids, "at": db_now().isoformat(), "actor": tester_id})
            history.append({"state": "retested", "result": test_result, "asset_ids": test_asset_ids, "at": db_now().isoformat(), "actor": tester_id})
            row.state = "closed" if test_result == "pass" else "open"
            row.data_json = {**row.data_json, "history": history, "last_test_result": test_result, "closed_by": tester_id if test_result == "pass" else None}
            row.evidence_asset_ids_json = sorted(set(row.evidence_asset_ids_json + correction_asset_ids + test_asset_ids))
            return {"deficiency_id": deficiency_id, "state": row.state, "test_result": test_result, "history_count": len(history)}

    def compare_temporal_states(self, tenant_id: str, project_id: str, *, before_ids: list[str], after_ids: list[str]) -> dict[str, Any]:
        with self.database.session() as session:
            rows = {
                row.record_id: row
                for row in session.scalars(
                    select(ConstructionRecordRow).where(
                        ConstructionRecordRow.tenant_id == tenant_id,
                        ConstructionRecordRow.project_id == project_id,
                        ConstructionRecordRow.record_id.in_(set(before_ids + after_ids)),
                    )
                )
            }
        before, after = set(before_ids), set(after_ids)
        modified = [identifier for identifier in sorted(before & after) if rows.get(identifier) and rows[identifier].superseded_at is not None]
        return {"added": sorted(after - before), "removed": sorted(before - after), "modified_or_superseded": modified}

    def technical_report(self, tenant_id: str, project_id: str) -> dict[str, Any]:
        with self.database.session() as session:
            rows = list(session.scalars(select(ConstructionRecordRow).where(ConstructionRecordRow.tenant_id == tenant_id, ConstructionRecordRow.project_id == project_id)))
            measurements = list(session.scalars(select(MeasurementRow).where(MeasurementRow.tenant_id == tenant_id, MeasurementRow.project_id == project_id)))
        states = Counter(row.state for row in rows)
        types = Counter(row.record_type for row in rows)
        report = {
            "report_type": "construction_technical",
            "tenant_id": tenant_id,
            "project_id": project_id,
            "generated_at": db_now().isoformat(),
            "record_counts": dict(sorted(types.items())),
            "state_counts": dict(sorted(states.items())),
            "measurements": [
                {
                    "measurement_id": item.measurement_id,
                    "value": item.value,
                    "unit": item.unit,
                    "uncertainty": item.uncertainty,
                    "authority_class": item.authority_class,
                    "verifier_id": item.verifier_id,
                    "verified_at": item.verified_at.isoformat() if item.verified_at else None,
                    "source_asset_ids": item.source_asset_ids_json,
                    "calibration": item.calibration_json,
                }
                for item in measurements
            ],
            "warnings": [
                "Phone-derived geometry is not survey-grade, fabrication-ready, contract-authoritative, code-compliant, or verified as-built without independent verification."
            ],
        }
        report["report_hash"] = canonical_sha256(report)
        return report

    def owner_report(self, tenant_id: str, project_id: str) -> dict[str, Any]:
        technical = self.technical_report(tenant_id, project_id)
        return {
            "report_type": "construction_owner",
            "project_id": project_id,
            "generated_at": technical["generated_at"],
            "open_deficiencies": technical["state_counts"].get("open", 0),
            "verified_measurement_count": sum(1 for item in technical["measurements"] if item["authority_class"] == "field_verified"),
            "systems": {key: value for key, value in technical["record_counts"].items() if key in SYSTEM_TYPES},
            "warning": technical["warnings"][0],
            "technical_report_hash": technical["report_hash"],
        }

    def export_bcf(self, tenant_id: str, project_id: str, destination: Path) -> dict[str, Any]:
        with self.database.session() as session:
            deficiencies = list(
                session.scalars(
                    select(ConstructionRecordRow).where(
                        ConstructionRecordRow.tenant_id == tenant_id,
                        ConstructionRecordRow.project_id == project_id,
                        ConstructionRecordRow.record_type == "deficiency",
                    )
                )
            )
        payload = {
            "bcf_version": "3.0",
            "project_id": project_id,
            "topics": [
                {
                    "guid": row.record_id,
                    "title": row.data_json.get("description", "Deficiency"),
                    "topic_status": row.state,
                    "priority": row.data_json.get("severity"),
                    "reference_links": row.evidence_asset_ids_json,
                    "labels": ["SIP", "synthetic-compatible-open-handoff"],
                }
                for row in deficiencies
            ],
        }
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return {"path": str(destination), "sha256": canonical_sha256(payload), "topics": len(payload["topics"]), "format": "BCF-JSON-reference"}

    def export_ifc_handoff_manifest(self, tenant_id: str, project_id: str, destination: Path) -> dict[str, Any]:
        report = self.technical_report(tenant_id, project_id)
        payload = {
            "format": "SIP-IFC-HANDOFF-MANIFEST-1.0",
            "project_id": project_id,
            "design_authority_preserved": True,
            "observed_geometry_not_promoted_to_design": True,
            "record_counts": report["record_counts"],
            "measurement_ids": [item["measurement_id"] for item in report["measurements"]],
            "limitations": report["warnings"],
        }
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return {"path": str(destination), "sha256": canonical_sha256(payload), "format": payload["format"]}

    def _audit(self, session: Any, tenant_id: str, project_id: str, actor_id: str, action: str, record_id: str, details: dict[str, Any]) -> None:
        self.audit.append(
            tenant_id=tenant_id,
            project_id=project_id,
            actor_id=actor_id,
            action=action,
            resource_type="construction_record",
            resource_id=record_id,
            outcome="allowed",
            details=details,
            session=session,
        )
