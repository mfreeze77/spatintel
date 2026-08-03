from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tools.build_progress11_checkpoint import (
    BRANCH,
    CHECKPOINT_ID,
    EXPECTED_BASE_COMMIT,
    EXPECTED_BASE_OUTER_SHA256,
    EXPECTED_BASE_SOURCE_ROOT,
    EXPECTED_BASE_ZIP_SHA256,
    EXPECTED_SCOPE_TOTAL,
    MIGRATION_PATH,
)
from tools.verify_progress11_checkpoint import EXPECTED_MIGRATION_BYTES, EXPECTED_MIGRATION_SHA256

ROOT = Path(__file__).resolve().parents[2]


def _json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_progress11_predecessor_is_exact_accepted_progress10_checkpoint() -> None:
    """CONTROL: Progress 11 provenance is bound to the accepted Progress 10 commit and package identities."""
    predecessor = _json("PREDECESSOR_CHECKPOINT.json")["accepted_progress_10_checkpoint"]
    assert predecessor["commit"] == EXPECTED_BASE_COMMIT
    assert predecessor["project_zip_sha256"] == EXPECTED_BASE_ZIP_SHA256
    assert predecessor["outer_delivery_zip_sha256"] == EXPECTED_BASE_OUTER_SHA256
    assert predecessor["source_tree_root_sha256"] == EXPECTED_BASE_SOURCE_ROOT


def test_progress11_scope_traceability_and_posture_are_exact() -> None:
    """CONTROL: The authorized release-assurance epic scope is exact and Progress 12/production remain denied."""
    scope = _json("requirements/MILESTONE_SCOPE_PROGRESS_11.json")
    audit = _json("requirements/progress-11-traceability-audit.json")
    included = scope["included_requirements"]
    identifiers = {item["requirement_id"] for item in included}
    assert scope["checkpoint_id"] == CHECKPOINT_ID
    assert scope["accepted_base_commit"] == EXPECTED_BASE_COMMIT
    assert scope["authorized_epics"] == ["QA-002"]
    assert len(included) == EXPECTED_SCOPE_TOTAL == 96
    assert scope["deferred_requirement_count"] == 0
    assert len(identifiers) == EXPECTED_SCOPE_TOTAL
    assert scope["progress_11_authorized"] is True
    assert scope["progress_12_authorized"] is False
    assert scope["production_authorized"] is False
    assert audit["status"] == "passed_complete"
    assert audit["finding_count"] == 0
    assert audit["requirement_count"] == EXPECTED_SCOPE_TOTAL
    assert len(audit["requirements_audited"]) == EXPECTED_SCOPE_TOTAL


def test_progress11_roadmap_is_dependency_ordered_reversible_and_evidence_bound() -> None:
    """REQ: DELROAD-001, DELROAD-002, DELROAD-003, DELROAD-004, DELROAD-005, DELROAD-006 the Progress 11 roadmap is dependency-ordered, evidence-driven, reversible, local-first, and non-authorizing."""
    roadmap = _json("requirements/PROGRESS_11_ROADMAP.json")
    assert roadmap["schema"] == "sip.progress11-roadmap/v1"
    assert roadmap["checkpoint_id"] == CHECKPOINT_ID
    assert roadmap["sequencing_basis"] == "dependency_graph_not_calendar_quarters"
    assert roadmap["local_only_commitment"] is True
    assert roadmap["open_export_commitment"] is True
    assert roadmap["production_authorized"] is False
    assert roadmap["progress_12_authorized"] is False
    assert {
        "benchmark results",
        "cost and capacity evidence",
        "support burden",
        "consent incidents",
        "security and privacy incidents",
    } <= set(roadmap["review_inputs"])

    stages = roadmap["stages"]
    assert [stage["order"] for stage in stages] == [1, 2, 3]
    assert len({stage["stage_id"] for stage in stages}) == len(stages)
    for stage in stages:
        assert stage["reversible"] is True
        assert stage["open_local_path"] is True
        assert stage["owner"]
        assert stage["prerequisites"]
        assert stage["exit_criteria"]
        assert stage["fallback_exit"]
        assert stage["risks"]
        assert stage["architecture_impact"]
        assert stage["customer_outcome"]
        assert stage["deprecation_migration"]

    qualification, external, future = stages
    assert qualification["stage_id"] == "qa002-local-release-qualification"
    assert {"benchmarks", "cost reports", "support burden", "security incidents", "privacy incidents"} <= set(
        qualification["evidence_inputs"]
    )
    assert external["stage_id"] == "external-evidence-closure"
    assert external["research_spike"] == {
        "decision_required": True,
        "permanent_fork_allowed": False,
        "time_bounded": True,
    }
    assert future["stage_id"] == "future-pilot-readiness"
    assert future["architecture_impact"] == "No implementation authorized by Progress 11."


def test_progress11_append_only_migration_is_byte_locked() -> None:
    """REQ: SIPMIG-003 Progress 11 release-assurance schema is append-only and byte-locked at revision 0021."""
    import hashlib
    path = ROOT / MIGRATION_PATH
    payload = path.read_bytes()
    assert len(payload) == EXPECTED_MIGRATION_BYTES
    assert hashlib.sha256(payload).hexdigest() == EXPECTED_MIGRATION_SHA256
    manifest = _json("migrations/manifest.json")
    records = [item for item in manifest["migrations"] if item["path"] == MIGRATION_PATH]
    assert records == [{"path": MIGRATION_PATH, "byte_count": EXPECTED_MIGRATION_BYTES, "sha256": EXPECTED_MIGRATION_SHA256}]


def test_progress11_release_assurance_service_contract_and_events_are_generated() -> None:
    """REQ: DELDOD-001, DELDOD-006 release-assurance has one typed service boundary, generated OpenAPI, and owned immutable events."""
    service = _json("services/release-assurance/service.json")
    assert service["service_name"] == "release-assurance"
    assert service["logical_boundary"] is True
    openapi = _json("schemas/openapi/release-assurance.openapi.json")
    paths = set(openapi["paths"])
    assert any("/qa/campaigns" in path for path in paths)
    assert any("/production-admission" in path for path in paths)
    catalog = _json("schemas/events/event-catalog.json")
    owned = {item["type"] for item in catalog["events"] if item.get("owner") == "release-assurance"}
    assert {"qa.campaign.created", "qa.gate.recorded", "qa.candidate.signed", "qa.production_admission.denied"} <= owned


def test_progress11_acceptance_lock_is_outside_generated_repository_paths(tmp_path: Path) -> None:
    """CONTROL: concurrent acceptance writers cannot replace each other's immutable evidence."""
    from tools.run_progress11_checkpoint_acceptance import _acceptance_lock_path, _exclusive_acceptance_lock
    lock = _acceptance_lock_path()
    assert not lock.resolve().is_relative_to(ROOT.resolve())
    code = (
        "from tools.run_progress11_checkpoint_acceptance import _exclusive_acceptance_lock; "
        "ctx=_exclusive_acceptance_lock(); ctx.__enter__(); import time; time.sleep(8)"
    )
    env = {**os.environ, "PYTHONPATH": f"{ROOT / 'src'}:{ROOT}", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    process = subprocess.Popen([sys.executable, "-c", code], cwd=ROOT, env=env)
    try:
        import time
        time.sleep(1)
        try:
            with _exclusive_acceptance_lock():
                acquired = True
        except RuntimeError:
            acquired = False
        assert acquired is False
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_progress11_make_and_acceptance_order_include_all_release_dependencies() -> None:
    """REQ: TSTSTRAT-001, TSTGATE-003 exact-commit acceptance includes dual vertical, recovery, release, and evidence-bound traceability gates."""
    from tools.run_progress11_checkpoint_acceptance import POST_EVIDENCE_TARGETS, REQUIRED_TARGETS, TARGET_REPORT_PATHS
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "demo-release:" in makefile
    assert "build_progress11_scope.py --check" in makefile
    assert "audit_progress11_traceability.py --check" in makefile
    assert REQUIRED_TARGETS.index("demo-recovery") < REQUIRED_TARGETS.index("demo-release")
    assert TARGET_REPORT_PATHS["demo-release"].endswith("demo-progress11-release.json")
    assert POST_EVIDENCE_TARGETS == ["traceability-evidence"]


def test_progress11_documentation_and_external_evidence_posture_are_explicit() -> None:
    """REQ: DELDOD-002, DELDOD-003, DELDOD-004, DELDOD-005, DELDOD-012 operating envelope, limitations, support, rollback, and verification instructions remain explicit."""
    required = [
        "docs/operator/PROGRESS_11_RELEASE_GATES.md",
        "docs/operator/PROGRESS_11_OPERATING_ENVELOPE.md",
        "docs/operator/PROGRESS_11_RECOVERY_AND_ROLLBACK.md",
        "docs/operator/PROGRESS_11_SUPPORT_AND_ESCALATION.md",
        "docs/operator/PROGRESS_11_CHECKPOINT_VERIFICATION.md",
        "docs/release/PROGRESS_11_KNOWN_LIMITATIONS.md",
        "docs/security/PROGRESS_11_RELEASE_SECURITY.md",
    ]
    for relative in required:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "Progress 11" in text
        assert any(token in text for token in ("NO-GO", "production", "Production"))
    limitations = (ROOT / "docs/release/PROGRESS_11_KNOWN_LIMITATIONS.md").read_text(encoding="utf-8")
    assert "browser" in limitations.lower() and "lidar" in limitations.lower() and "cloud" in limitations.lower()


def test_progress11_builder_and_verifiers_are_milestone_specific_and_fail_closed() -> None:
    """CONTROL: checkpoint tooling is bound to Progress 11 and never self-authorizes Progress 12 or production."""
    from tools import build_progress11_checkpoint as builder
    from tools import verify_progress11_checkpoint as verifier
    assert builder.CHECKPOINT_ID == verifier.CHECKPOINT_ID == CHECKPOINT_ID
    assert builder.BRANCH == verifier.EXPECTED_BRANCH == BRANCH
    assert builder.EXPECTED_SCOPE_TOTAL == verifier.EXPECTED_SCOPE_TOTAL == 96
    for relative in (
        "tools/build_progress11_checkpoint.py",
        "tools/verify_progress11_checkpoint.py",
        "tools/verify_progress11_delivery_envelope.py",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "progress_12_authorized" in text
        assert "production_authorized" in text


def test_progress11_traceability_reads_a_non_authorizing_provisional_acceptance_record(tmp_path, monkeypatch):
    """REQ: TSTGATE-003, TSTGATE-007, TSTGATE-009 The post-evidence gate sees a fail-closed provisional record, never a fabricated final acceptance."""
    import json

    import tools.run_progress11_checkpoint_acceptance as acceptance

    source = {
        "commit": "c" * 40,
        "source_tree_root_sha256": "r" * 64,
        "working_tree_clean": True,
    }
    monkeypatch.setattr(acceptance, "ROOT", tmp_path)
    monkeypatch.setattr(acceptance, "ADDITIONAL_LOCAL_TARGETS", [])
    monkeypatch.setattr(acceptance, "REQUIRED_TARGETS", [])
    monkeypatch.setattr(acceptance, "EXPECTED_BLOCKED_TARGETS", [])
    monkeypatch.setattr(acceptance, "POST_EVIDENCE_TARGETS", ["traceability-evidence"])
    monkeypatch.setattr(acceptance, "current_source_binding", lambda _root: dict(source))

    attestation = tmp_path / "build/evidence/source-attestation.json"
    attestation.parent.mkdir(parents=True)
    attestation.write_text(
        json.dumps(
            {
                "commit": source["commit"],
                "source_tree_root_sha256": source["source_tree_root_sha256"],
                "clean_before_tests": True,
                "branch": "progress-11-release-gates",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "build/reports/checkpoint-acceptance-gates.json"

    def fake_run_target(target, *, env, log_root):
        if target == "traceability-evidence":
            provisional = json.loads(output.read_text(encoding="utf-8"))
            assert provisional["status"] == "provisional_non_authorizing"
            assert provisional["provisional"] is True
            assert provisional["production_authorized"] is False
            assert provisional["progress_12_authorized"] is False
        else:
            assert target == "release"
        return {
            "target": target,
            "command": ["make", target],
            "exit_code": 0,
            "elapsed_seconds": 0.0,
            "log_path": "build/evidence/gates/traceability-evidence.log",
            "log_sha256": "0" * 64,
            "execution_status": "completed_successfully",
            "control_status": "passed_complete",
            "status": "passed_complete",
        }

    monkeypatch.setattr(acceptance, "_run_target", fake_run_target)
    report = acceptance.run(attestation_path=attestation, provisional_output_path=output)
    assert report["status"] == "passed_complete"
    assert report["production_authorized"] is False
    assert report["progress_12_authorized"] is False


def test_progress11_checkpoint_tools_accept_canonical_matrix_totals_schema() -> None:
    """REQ: TSTGATE-003 — Checkpoint tooling consumes the canonical hermetic matrix schema."""

    from tools.build_progress11_checkpoint import _matrix_counts as build_counts
    from tools.verify_progress11_checkpoint import _audited_requirement_ids, _matrix_counts as verify_counts

    canonical = {"tests": 489, "failures": 0, "errors": 0, "skipped": 0}
    historical = {"passed": 489, "failed": 0, "errors": 0, "skipped": 0}
    assert build_counts(canonical) == (489, 0, 0, 0)
    assert verify_counts(canonical) == (489, 0, 0, 0)
    assert build_counts(historical) == (489, 0, 0, 0)
    assert verify_counts(historical) == (489, 0, 0, 0)

    audit_records = [{"requirement_id": f"REQ-{index:03d}"} for index in range(96)]
    assert _audited_requirement_ids(audit_records) == {f"REQ-{index:03d}" for index in range(96)}
    assert _audited_requirement_ids([*audit_records, audit_records[0]]) == set()
    assert _audited_requirement_ids(96) == set()


def test_progress11_bundle_verification_does_not_require_caller_repository(tmp_path: Path) -> None:
    """CONTROL: independent checkpoint verification can validate a Git bundle outside any checkout."""

    from tools.verify_progress11_checkpoint import Verification, _verify_bundle_integrity

    repository = tmp_path / "source"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    (repository / "proof.txt").write_text("bundle proof\n", encoding="utf-8")
    subprocess.run(["git", "add", "proof.txt"], cwd=repository, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=SIP Test",
            "-c",
            "user.email=sip-test@local.invalid",
            "commit",
            "-q",
            "-m",
            "test bundle",
        ],
        cwd=repository,
        check=True,
    )
    bundle = tmp_path / "source.bundle"
    subprocess.run(["git", "bundle", "create", str(bundle), "--all"], cwd=repository, check=True)

    verification = Verification()
    _verify_bundle_integrity(bundle, verification)

    assert verification.findings == []
