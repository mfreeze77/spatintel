from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _json(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_progress06_r1_generated_contracts_expose_only_scoped_mutations() -> None:
    """REQ: ARCIAM-001, LIFCONS-001, CONQC-006 public vertical contracts expose project-scoped consent and deficiency mutations only."""
    construction = _json("schemas/openapi/construction.openapi.json")["paths"]
    liveforever = _json("schemas/openapi/liveforever.openapi.json")["paths"]
    assert "/v1/projects/{project_id}/construction/deficiencies/{deficiency_id}/retest" in construction
    assert "/v1/construction/deficiencies/{deficiency_id}/retest" not in construction
    assert "/v1/projects/{project_id}/construction/restricted-export-approvals" in construction
    assert "/v1/projects/{project_id}/liveforever/consents/{grant_id}/revoke" in liveforever
    assert "/v1/liveforever/consents/{grant_id}/revoke" not in liveforever


def test_progress06_r1_append_only_migration_is_integrity_locked() -> None:
    """REQ: DATDB-002 Progress 06-R1 schema work begins at append-only migration 0015 with retained byte identity."""
    path = ROOT / "migrations/versions/0015_progress06_r1_security_controls.py"
    payload = path.read_bytes()
    manifest = _json("migrations/manifest.json")
    record = next(item for item in manifest["migrations"] if item["path"] == "migrations/versions/0015_progress06_r1_security_controls.py")
    assert len(payload) == 3584
    assert hashlib.sha256(payload).hexdigest() == "41722da684ea9661de60263998abe8e10969dc7139a519e348f94a6ba1ae0b4a"
    assert record["byte_count"] == len(payload)
    assert record["sha256"] == hashlib.sha256(payload).hexdigest()
    source = path.read_text(encoding="utf-8")
    assert 'down_revision = "0014_vertical_mvp"' in source


def test_progress06_r1_scope_traceability_and_release_posture_are_fail_closed() -> None:
    """REQ: GOVDOC-001, TSTGATE-001 R1 scope and evidence are explicit while Progress 07 and production remain unauthorized."""
    scope = _json("requirements/MILESTONE_SCOPE_PROGRESS_06_R1.json")
    audit = _json("requirements/progress-06-r1-traceability-audit.json")
    ledger = {item["requirement_id"]: item for item in _json("requirements/requirements-ledger.json")["requirements"]}
    assert scope["included_requirement_count"] == 18
    assert scope["progress_07_authorized"] is False
    assert scope["production_authorized"] is False
    assert audit["status"] == "passed_complete"
    assert audit["finding_count"] == 0
    assert audit["requirement_count"] == 18
    assert audit["progress_07_authorized"] is False
    assert audit["production_authorized"] is False
    assert ledger["PLTVIEW-007"]["implementation_status"] == "IMPLEMENTED_UNVERIFIED"
