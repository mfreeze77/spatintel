from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from tools.build_progress09_checkpoint import SECURITY_DIRECT_EVIDENCE_PATH, _render_coverage
from tools.verify_progress09_checkpoint import (
    EXPECTED_BASE_COMMIT,
    EXPECTED_BASE_OUTER_SHA256,
    EXPECTED_BASE_SOURCE_ROOT,
    EXPECTED_BASE_ZIP_SHA256,
    EXPECTED_DEFERRED,
    EXPECTED_INCLUDED,
    EXPECTED_MIGRATION_BYTES,
    EXPECTED_MIGRATION_SHA256,
    EXPECTED_SCOPE_TOTAL,
)

ROOT = Path(__file__).resolve().parents[2]


def _json(relative: str) -> dict:
    value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_progress09_predecessor_record_identifies_exact_accepted_progress08_checkpoint() -> None:
    """CONTROL: Progress 09 provenance is bound to the accepted Progress 08 commit and packages."""

    record = _json("PREDECESSOR_CHECKPOINT.json")["accepted_progress_08_checkpoint"]
    assert record["checkpoint_id"] == "sip-v1.1.0-progress-08"
    assert record["branch"] == "progress-08-observability"
    assert record["commit"] == EXPECTED_BASE_COMMIT
    assert record["project_zip_sha256"] == EXPECTED_BASE_ZIP_SHA256
    assert record["outer_delivery_zip_sha256"] == EXPECTED_BASE_OUTER_SHA256
    assert record["source_tree_root_sha256"] == EXPECTED_BASE_SOURCE_ROOT


def test_progress09_scope_traceability_and_posture_are_exact_and_fail_closed() -> None:
    """CONTROL: the authorized deployment-profile scope is exact while later phases remain denied."""

    scope = _json("requirements/MILESTONE_SCOPE_PROGRESS_09.json")
    audit = _json("requirements/progress-09-traceability-audit.json")
    included = scope["included_requirements"]
    deferred = scope["deferred_requirements"]
    assert scope["accepted_base_commit"] == EXPECTED_BASE_COMMIT
    assert scope["authorized_epics"] == ["OPS-003"]
    assert scope["scope_statement"].startswith("Progress 09 is limited to OPS-003")
    assert "Progress 10" in scope["scope_statement"] and "production promotion" in scope["scope_statement"]
    assert len(included) == EXPECTED_INCLUDED == EXPECTED_SCOPE_TOTAL
    assert len(deferred) == EXPECTED_DEFERRED == 0
    identifiers = {item["requirement_id"] for item in included}
    assert len(identifiers) == EXPECTED_SCOPE_TOTAL
    assert all(identifier.startswith(("ARCDEP-", "OPSHYB-", "OPSAWS-")) for identifier in identifiers)
    assert scope["progress_09_authorized"] is True
    assert scope["progress_10_authorized"] is False
    assert scope["production_authorized"] is False
    assert audit["status"] == "passed_complete"
    assert audit["finding_count"] == 0
    assert audit["requirement_count"] == EXPECTED_SCOPE_TOTAL
    assert {item["requirement_id"] for item in audit["requirements_audited"]} == identifiers
    assert audit["progress_09_authorized"] is True
    assert audit["progress_10_authorized"] is False
    assert audit["production_authorized"] is False
    ledger = {item["requirement_id"]: item for item in _json("requirements/requirements-ledger.json")["requirements"]}
    assert ledger["PLTVIEW-007"]["implementation_status"] == "IMPLEMENTED_UNVERIFIED"


def test_progress09_append_only_migration_is_integrity_locked() -> None:
    """REQ: DATDB-002 Progress 09 schema additions are append-only and byte-locked at migration 0019."""

    path = ROOT / "migrations/versions/0019_progress09_deployment_profiles.py"
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    assert len(payload) == EXPECTED_MIGRATION_BYTES
    assert digest == EXPECTED_MIGRATION_SHA256
    manifest = _json("migrations/manifest.json")
    record = next(item for item in manifest["migrations"] if item["path"] == path.relative_to(ROOT).as_posix())
    assert record["byte_count"] == len(payload)
    assert record["sha256"] == digest
    source = payload.decode("utf-8")
    assert "down_revision = '0018_progress08_observability_cost_support'" in source


def test_progress09_generated_service_and_event_contracts_are_owned_by_deployment_control() -> None:
    """CONTROL: generated contracts preserve the deployment-control boundary."""

    service = _json("services/deployment-control/service.json")
    assert service["service_name"] == "deployment-control"
    operation_paths = {item["path"] for item in service["operations"]}
    assert operation_paths
    openapi = _json("schemas/openapi/deployment-control.openapi.json")
    public_operations = {path for path in operation_paths if path not in {"/health/live", "/health/ready", "/metrics"}}
    assert public_operations <= set(openapi["paths"])
    assert any("/deployment/profiles" in path for path in public_operations)
    assert any("/deployment/residency" in path for path in public_operations)
    assert any("/deployment/edge" in path for path in public_operations)
    catalog = _json("schemas/events/event-catalog.json")
    owned = [item for item in catalog["events"] if item.get("owner") == "deployment-control"]
    assert len(owned) >= 20
    assert {item["type"] for item in owned} >= {
        "deployment.profile.registered",
        "deployment.residency.registered",
        "deployment.edge.enrolled",
        "deployment.update.applied",
        "deployment.migration.completed",
        "deployment.aws.registered",
    }


def test_progress09_acceptance_cli_rejects_concurrent_evidence_writers() -> None:
    """CONTROL: concurrent Progress 09 acceptance cannot overwrite immutable gate snapshots."""

    from tools.run_progress09_checkpoint_acceptance import _acceptance_lock_path

    lock_path = _acceptance_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    assert not lock_path.is_relative_to(ROOT)
    with lock_path.open("a+", encoding="utf-8") as handle:
        acquired_here = False
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired_here = True
        except BlockingIOError:
            pass
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "from tools.run_progress09_checkpoint_acceptance import _exclusive_acceptance_lock; ctx=_exclusive_acceptance_lock(); ctx.__enter__()",
            ],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": f"{ROOT / 'src'}:{ROOT}"},
            capture_output=True,
            text=True,
            check=False,
        )
        if acquired_here:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    assert completed.returncode != 0
    assert "already running" in (completed.stdout + completed.stderr)


def test_progress09_checkpoint_builder_uses_separate_direct_security_evidence() -> None:
    """CONTROL: the security gate cannot overwrite the source-bound complete matrix artifacts."""

    assert SECURITY_DIRECT_EVIDENCE_PATH == "build/reports/security-direct/security.xml"
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    security_recipe = makefile.split("security:\n", 1)[1].split("\nlicense-check:", 1)[0]
    assert "SIP_TEST_REPORT_ROOT=build/reports/security-direct" in security_recipe
    assert "run_test_matrix.py --suite security" in security_recipe


def test_matrix_report_root_override_is_explicit_and_rooted(tmp_path: Path, monkeypatch) -> None:
    """CONTROL: isolated gate output roots are deterministic and cannot alias canonical evidence accidentally."""

    from tools.run_test_matrix import _configured_output_path

    default = tmp_path / "default"
    monkeypatch.delenv("SIP_TEST_REPORT_ROOT", raising=False)
    assert _configured_output_path("SIP_TEST_REPORT_ROOT", default, root=tmp_path) == default
    monkeypatch.setenv("SIP_TEST_REPORT_ROOT", "build/reports/security-direct")
    assert _configured_output_path("SIP_TEST_REPORT_ROOT", default, root=tmp_path) == tmp_path / "build/reports/security-direct"
    absolute = tmp_path / "absolute"
    monkeypatch.setenv("SIP_TEST_REPORT_ROOT", str(absolute))
    assert _configured_output_path("SIP_TEST_REPORT_ROOT", default, root=tmp_path) == absolute


def test_progress09_coverage_report_retains_later_phase_denial() -> None:
    """CONTROL: packaged coverage keeps Progress 10 unauthorized and production fail closed."""

    text = _render_coverage(
        {
            "checkpoint_id": "sip-v1.1.0-progress-09",
            "commit": "a" * 40,
            "source_tree_root_sha256": "b" * 64,
            "python_tests_passed": 1,
            "requirements_total": 1,
        },
        {"requirements": [{"priority": "P0", "implementation_status": "IMPLEMENTED_UNVERIFIED"}]},
    )
    assert "Progress 09" in text and "delivered" in text
    assert "Progress 10" in text and "unauthorized" in text
    assert "Production" in text and "NO-GO" in text
