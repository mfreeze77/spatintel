from __future__ import annotations

import json
from pathlib import Path

import pytest

from sip.errors import ConflictError, ValidationError
from sip.failures import FailureCatalog

ROOT = Path(__file__).resolve().parents[2]


def test_failure_catalog_covers_mandated_modes_with_complete_stable_fields() -> None:
    """REQ: APPFAIL-001, APPFAIL-002, APPFAIL-010 all required failure modes have stable machine-readable behavior."""
    catalog = FailureCatalog.load()
    covered = {tag for item in catalog.document.failures for tag in item.coverage_tags}
    assert set(catalog.document.required_coverage_tags) <= covered
    for failure in catalog.document.failures:
        assert failure.code == failure.code.upper()
        assert failure.operator_action
        assert failure.customer_message
        assert failure.test_references
        assert failure.recovery_mode
        assert failure.fallback
        assert failure.remediation
        assert failure.introduced_version == "1.1.0"


def test_unsafe_and_fatal_failures_block_or_withdraw_publication() -> None:
    """REQ: APPFAIL-004, APPFAIL-007 unsafe and fatal conditions cannot partially publish or increase authority."""
    catalog = FailureCatalog.load()
    for failure in catalog.document.failures:
        if failure.severity in {"unsafe", "fatal"}:
            assert failure.publication_action in {"block", "withdraw"}
            with pytest.raises(ConflictError) as exc:
                catalog.assert_publication_allowed(failure.code)
            assert exc.value.code == "FAILURE_BLOCKS_PUBLICATION"


def test_diagnostics_are_allowlisted_bounded_and_contain_no_raw_sensitive_content() -> None:
    """REQ: APPFAIL-003, APPFAIL-006 diagnostics retain reproducible hashes and IDs without raw sensitive data."""
    catalog = FailureCatalog.load()
    diagnostic = catalog.create_diagnostic(
        "REGISTRATION_MISALIGNED",
        tenant_id="tenant-a",
        project_id="project-a",
        operation_id="operation-a",
        run_id="run-a",
        diagnostic={
            "operation_id": "operation-a",
            "input_hash": "a" * 64,
            "output_hash": "b" * 64,
            "adapter_version": "1.1.0",
            "environment_hash": "c" * 64,
            "raw_geometry": [[1, 2, 3]],
            "transcript_text": "must not survive",
            "password": "must not survive",
            "unregistered_field": "must not survive",
        },
    )
    assert diagnostic.diagnostic == {
        "operation_id": "operation-a",
        "input_hash": "a" * 64,
        "output_hash": "b" * 64,
        "adapter_version": "1.1.0",
        "environment_hash": "c" * 64,
    }
    serialized = diagnostic.model_dump_json(by_alias=True)
    assert "raw_geometry" not in serialized
    assert "transcript" not in serialized
    assert "password" not in serialized
    assert diagnostic.raw_sensitive_data_retained is False


def test_recovery_creates_new_lineage_and_never_rewrites_failed_evidence() -> None:
    """REQ: APPFAIL-005 recovery creates a distinct run or revision linked to immutable failed evidence."""
    catalog = FailureCatalog.load()
    failed = catalog.create_diagnostic(
        "POSE_COLLAPSE_DETECTED",
        tenant_id="tenant-a",
        project_id="project-a",
        operation_id="operation-a",
        run_id="run-failed",
    )
    with pytest.raises(ValidationError):
        catalog.recovery_lineage(failed, new_run_id="run-failed")
    recovery = catalog.recovery_lineage(failed, new_run_id="run-recovery", new_revision_id="revision-recovery")
    assert recovery.failed_record_id == failed.failure_record_id
    assert recovery.new_run_id != recovery.failed_run_id
    assert recovery.preserves_failed_evidence is True
    assert recovery.rewrites_failed_record is False


def test_hybrid_failure_preserves_prior_assets_and_has_independent_component_fallbacks() -> None:
    """REQ: APPFAIL-008, APPFAIL-009 hybrid failures preserve source/accepted state and degrade each interaction function explicitly."""
    catalog = FailureCatalog.load()
    safe = catalog.hybrid_safe_state("PROVIDER_OUTPUT_MALFORMED")
    assert safe["partial_publication_allowed"] is False
    assert all(safe["preserve"].values())
    components = {"picking", "collision", "navigation", "occlusion", "spatial_audio", "visual_rendering"}
    fallbacks = {component: catalog.component_fallback(component) for component in components}
    assert len(fallbacks) == len(components)
    assert all(fallbacks.values())
    assert "guided" in fallbacks["navigation"]


def test_catalog_json_is_deterministic_and_has_no_duplicate_codes() -> None:
    """REQ: APPFAIL-010 code compatibility metadata is deterministic and queryable."""
    raw = json.loads((ROOT / "governance/failure-catalog.json").read_text(encoding="utf-8"))
    codes = [item["code"] for item in raw["failures"]]
    assert len(codes) == len(set(codes))
    assert raw["compatibility_policy"].startswith("Codes and semantics are append-only")
