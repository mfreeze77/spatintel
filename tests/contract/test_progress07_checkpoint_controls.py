from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from tools.build_progress07_checkpoint import SECURITY_DIRECT_EVIDENCE_PATH, _render_coverage
from tools.verify_progress07_checkpoint import (
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


def test_progress07_predecessor_record_identifies_exact_accepted_progress06_r2_checkpoint() -> None:
    """CONTROL: Progress 07 provenance is bound to the accepted Progress 06-R2 commit and packages."""

    record = _json("PREDECESSOR_CHECKPOINT.json")["accepted_progress_06_r2_checkpoint"]
    assert record["checkpoint_id"] == "sip-v1.1.0-progress-06-r2"
    assert record["commit"] == EXPECTED_BASE_COMMIT
    assert record["project_zip_sha256"] == EXPECTED_BASE_ZIP_SHA256
    assert record["outer_delivery_zip_sha256"] == EXPECTED_BASE_OUTER_SHA256
    assert record["source_tree_root_sha256"] == EXPECTED_BASE_SOURCE_ROOT


def test_progress07_scope_traceability_and_posture_are_exact_and_fail_closed() -> None:
    """CONTROL: the bounded security-operations scope is exact while Progress 08 and production remain unauthorized."""

    scope = _json("requirements/MILESTONE_SCOPE_PROGRESS_07.json")
    audit = _json("requirements/progress-07-traceability-audit.json")
    included = scope["included_requirements"]
    deferred = scope["deferred_requirements"]
    assert scope["accepted_base_commit"] == EXPECTED_BASE_COMMIT
    assert scope["authorized_epics"] == ["OPS-001"]
    assert len(included) == EXPECTED_INCLUDED
    assert len(deferred) == EXPECTED_DEFERRED
    identifiers = {item["requirement_id"] for item in [*included, *deferred]}
    assert len(identifiers) == EXPECTED_SCOPE_TOTAL
    assert {item["requirement_id"] for item in deferred} == {"OPSSEC-005", "OPSPRIV-005", "OPSAUDIT-006"}
    assert scope["progress_08_authorized"] is False
    assert scope["production_authorized"] is False
    assert audit["status"] == "passed_complete"
    assert audit["finding_count"] == 0
    assert audit["requirement_count"] == EXPECTED_SCOPE_TOTAL
    assert {item["requirement_id"] for item in audit["requirements_audited"]} == identifiers
    assert audit["progress_08_authorized"] is False
    assert audit["production_authorized"] is False
    ledger = {item["requirement_id"]: item for item in _json("requirements/requirements-ledger.json")["requirements"]}
    assert ledger["PLTVIEW-007"]["implementation_status"] == "IMPLEMENTED_UNVERIFIED"


def test_progress07_append_only_migration_is_integrity_locked() -> None:
    """REQ: DATDB-002 Progress 07 schema additions are append-only and byte-locked at migration 0017."""

    path = ROOT / "migrations/versions/0017_progress07_security_privacy_readiness.py"
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    assert len(payload) == EXPECTED_MIGRATION_BYTES
    assert digest == EXPECTED_MIGRATION_SHA256
    manifest = _json("migrations/manifest.json")
    record = next(item for item in manifest["migrations"] if item["path"] == path.relative_to(ROOT).as_posix())
    assert record["byte_count"] == len(payload)
    assert record["sha256"] == digest
    source = payload.decode("utf-8")
    assert 'down_revision: Union[str, None] = "0016_progress06_r2_truth_and_restricted_data"' in source


def test_progress07_generated_service_and_event_contracts_are_owned_by_security_ops() -> None:
    """REQ: OPSSEC-006, OPSAUDIT-001 generated service and event contracts preserve the security-ops authority boundary."""

    service = _json("services/security-ops/service.json")
    assert service["service_name"] == "security-ops"
    operation_paths = {item["path"] for item in service["operations"]}
    assert operation_paths
    aggregate = _json("schemas/openapi/security-ops.openapi.json")
    assert aggregate["paths"]
    public_operations = {path for path in operation_paths if path != "/metrics"}
    assert public_operations == set(aggregate["paths"])
    assert any("/security/" in path for path in public_operations)
    assert any("/privacy/" in path for path in public_operations)
    catalog = _json("schemas/events/event-catalog.json")
    owned = [item for item in catalog["events"] if item.get("owner") == "security-ops"]
    assert len(owned) >= 20
    assert {item["type"] for item in owned} >= {
        "privileged_access.granted",
        "workload_identity.issued",
        "audit_verification.completed",
        "supply_chain_release.promoted",
        "provider_output.validated",
    }


def test_progress07_acceptance_cli_rejects_concurrent_evidence_writers(tmp_path: Path) -> None:
    """CONTROL: concurrent Progress 07 acceptance cannot overwrite immutable gate snapshots."""

    from tools.run_progress07_checkpoint_acceptance import _acceptance_lock_path

    lock_path = _acceptance_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # The lock must not live beneath any generated repository directory: the
    # matrix replaces build/locks while acceptance is active.
    assert not lock_path.is_relative_to(ROOT)
    with lock_path.open("a+", encoding="utf-8") as handle:
        acquired_here = False
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired_here = True
        except BlockingIOError:
            # The outer acceptance runner may already own the lock while this test
            # executes in the complete matrix. Either state proves a second writer
            # must fail closed.
            pass
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from tools.run_progress07_checkpoint_acceptance import _exclusive_acceptance_lock; "
                    "ctx=_exclusive_acceptance_lock(); ctx.__enter__()"
                ),
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


def test_progress07_checkpoint_builder_uses_separate_direct_security_evidence() -> None:
    """CONTROL: the security gate cannot overwrite the source-bound complete matrix artifacts."""

    assert SECURITY_DIRECT_EVIDENCE_PATH == "build/reports/tests/security-direct.xml"
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    security_recipe = makefile.split("security:\n", 1)[1].split("\nlicense-check:", 1)[0]
    assert "security-direct.xml" in security_recipe
    assert "run_test_matrix.py --suite security" not in security_recipe


def test_progress07_coverage_report_retains_later_phase_denial() -> None:
    """CONTROL: packaged coverage explicitly keeps Progress 08 and production fail closed."""

    text = _render_coverage(
        {
            "checkpoint_id": "sip-v1.1.0-progress-07",
            "commit": "a" * 40,
            "source_tree_root_sha256": "b" * 64,
            "python_tests_passed": 1,
            "requirements_total": 1,
        },
        {"requirements": [{"priority": "P0", "implementation_status": "IMPLEMENTED_UNVERIFIED"}]},
    )
    assert "Progress 08" in text and "unauthorized" in text
    assert "Production" in text and "NO-GO" in text
