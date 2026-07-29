from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

from tools.build_progress05_checkpoint import CHECKPOINT_ID, TOP_LEVEL, _render_coverage
from tools.checkpoint_common import FIXED_ZIP_TIME
from tools.verify_delivery_envelope import verify as verify_delivery
from tools.verify_checkpoint import Verification
from tools.verify_progress05_checkpoint import (
    _verify_concurrent_idempotency_remediation,
    _verify_renderer_remediation,
    verify_archive,
)

ROOT = Path(__file__).resolve().parents[2]


def _zip_info(name: str, mode: int = 0o644) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
    info.create_system = 3
    info.external_attr = mode << 16
    return info


def test_progress05_verifier_rejects_unsafe_paths_before_claims(tmp_path: Path) -> None:
    """CONTROL: the Progress 05 verifier rejects traversal before accepting package claims."""
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(_zip_info("../escape.txt"), b"escape")
    report = verify_archive(archive)
    assert report["status"] == "failed"
    assert any(item["code"] == "ZIP_UNSAFE_PATH" for item in report["findings"])


def test_progress05_verifier_rejects_manifest_hash_and_root_tamper(tmp_path: Path) -> None:
    """CONTROL: the Progress 05 verifier independently rehashes files and aggregate content root."""
    archive = tmp_path / "tampered.zip"
    manifest = {
        "schema": "sip.checkpoint-content-manifest/v1",
        "checkpoint_id": CHECKPOINT_ID,
        "top_level": TOP_LEVEL,
        "excluded_from_content_root": ["CHECKPOINT_CONTENT_MANIFEST.json"],
        "file_count": 1,
        "total_uncompressed_bytes": 4,
        "content_root_sha256": "0" * 64,
        "files": [{"kind": "file", "mode": "0644", "path": "payload.txt", "sha256": "0" * 64, "size": 4}],
    }
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(_zip_info(f"{TOP_LEVEL}/payload.txt"), b"real")
        output.writestr(
            _zip_info(f"{TOP_LEVEL}/CHECKPOINT_CONTENT_MANIFEST.json"),
            (json.dumps(manifest, sort_keys=True) + "\n").encode(),
        )
    report = verify_archive(archive)
    codes = {item["code"] for item in report["findings"]}
    assert report["status"] == "failed"
    assert "MANIFEST_HASH_MISMATCH" in codes
    assert "CONTENT_ROOT_MISMATCH" in codes


def test_outer_delivery_verifier_rejects_unexpected_and_unindexed_payload(tmp_path: Path) -> None:
    """CONTROL: the consolidated envelope rejects unexpected files and an incomplete payload index."""
    top = "Spatial-Intelligence-Platform-v1.1.0-progress-05-r2-delivery"
    project_name = "Spatial-Intelligence-Platform-v1.1.0-progress-05-r2.zip"
    project = b"not-a-real-checkpoint"
    checksum_name = project_name + ".sha256"
    verification_name = project_name + ".verification.json"
    expected_payload = {
        "path": project_name,
        "size": len(project),
        "sha256": hashlib.sha256(project).hexdigest(),
        "mode": "0644",
        "kind": "file",
    }
    index = {
        "schema": "sip.delivery-envelope-index/v1",
        "delivery_id": "sip-v1.1.0-progress-05-r2-delivery",
        "top_level": top,
        "self_exclusion": {
            "path": "DELIVERY_INDEX.json",
            "included_in_archive": True,
            "excluded_from_listed_payload": True,
            "reason": "non-recursive index",
        },
        "project_checkpoint": {
            "path": project_name,
            "sha256": expected_payload["sha256"],
            "sha256_file": checksum_name,
            "verification_report": verification_name,
        },
        "payload_file_count": 1,
        "payload_total_bytes": len(project),
        "payload_content_root_sha256": "0" * 64,
        "files": [expected_payload],
    }
    archive = tmp_path / "outer.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(_zip_info(f"{top}/{project_name}"), project)
        output.writestr(_zip_info(f"{top}/{checksum_name}"), f"{expected_payload['sha256']}  {project_name}\n")
        output.writestr(_zip_info(f"{top}/{verification_name}"), b"{}\n")
        output.writestr(_zip_info(f"{top}/unexpected.txt"), b"unexpected")
        output.writestr(_zip_info(f"{top}/DELIVERY_INDEX.json"), (json.dumps(index, sort_keys=True) + "\n").encode())
    report = verify_delivery(archive)
    codes = {item["code"] for item in report["findings"]}
    assert report["status"] == "failed"
    assert "OUTER_UNEXPECTED_FILE" in codes
    assert "OUTER_CONTENT_ROOT" in codes


def test_progress05_acceptance_sequence_contains_new_runtime_gates() -> None:
    """CONTROL: clean-source acceptance cannot omit desktop or scene-runtime verification."""
    path = ROOT / "tools/run_checkpoint_acceptance.py"
    spec = importlib.util.spec_from_file_location("sip_progress05_acceptance", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert "desktop-test" in module.REQUIRED_TARGETS
    assert "demo-scene-runtime" in module.REQUIRED_TARGETS
    source = path.read_text(encoding="utf-8")
    assert "sip-v1.1.0-progress-05-r2" in source
    assert "release-readiness-progress-05-r2.json" in source


def test_progress05_generated_coverage_states_production_no_go() -> None:
    """CONTROL: every generated status document explicitly preserves the blocked production posture."""
    rendered = _render_coverage(
        {
            "checkpoint_id": CHECKPOINT_ID,
            "commit": "a" * 40,
            "source_tree_root_sha256": "b" * 64,
            "python_tests_passed": 1,
            "requirements_total": 1,
        },
        {
            "requirements": [
                {"priority": "P0", "implementation_status": "IMPLEMENTED_UNVERIFIED"}
            ]
        },
    )
    assert "Production" in rendered
    assert "NO-GO" in rendered


def test_progress05_renderer_verifier_accepts_behavior_and_rejects_evidence_or_cleanup_tamper(tmp_path: Path) -> None:
    """CONTROL: the R2 verifier preserves the five-role implementation without claiming viewer integration."""
    for relative in (
        "apps/web/components/HybridViewer.tsx",
        "apps/web/components/HybridCanvas.tsx",
        "apps/web/lib/spatial-runtime.ts",
    ):
        source = ROOT / relative
        destination = tmp_path / "source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())

    valid = Verification(tmp_path / "valid.zip")
    _verify_renderer_remediation(tmp_path, valid)
    assert valid.findings == []

    canvas = tmp_path / "source/apps/web/components/HybridCanvas.tsx"
    original = canvas.read_text(encoding="utf-8")
    canvas.write_text(
        original.replace('layerDirective(directives, "evidence")', 'layerDirective(directives, "design")')
        .replace("observer?.disconnect();", "// observer cleanup removed"),
        encoding="utf-8",
    )
    tampered = Verification(tmp_path / "tampered.zip")
    _verify_renderer_remediation(tmp_path, tampered)
    codes = {finding.code for finding in tampered.findings}
    assert "HYBRID_CANVAS_ROLE_CONTROL" in codes
    assert "HYBRID_CANVAS_CLEANUP" in codes


def test_progress05_r2_verifier_requires_concurrent_idempotency_recovery_and_barrier_test(tmp_path: Path) -> None:
    """CONTROL: the R2 verifier rejects loss of governed concurrent replay or its two-session test."""
    for relative in (
        "src/sip/scene_runtime.py",
        "tests/integration/test_scene_runtime_review.py",
    ):
        source = ROOT / relative
        destination = tmp_path / "source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())

    valid = Verification(tmp_path / "valid.zip")
    _verify_concurrent_idempotency_remediation(tmp_path, valid)
    assert valid.findings == []

    service = tmp_path / "source/src/sip/scene_runtime.py"
    service.write_text(
        service.read_text(encoding="utf-8").replace(
            "CHANGE_APPLICATION_CONCURRENT_STATE_CONFLICT",
            "REMOVED_CONCURRENT_CONFLICT_CODE",
        ),
        encoding="utf-8",
    )
    tests = tmp_path / "source/tests/integration/test_scene_runtime_review.py"
    tests.write_text(
        tests.read_text(encoding="utf-8").replace("Barrier(2)", "Barrier(3)"),
        encoding="utf-8",
    )
    tampered = Verification(tmp_path / "tampered.zip")
    _verify_concurrent_idempotency_remediation(tmp_path, tampered)
    codes = {finding.code for finding in tampered.findings}
    assert "CONCURRENT_IDEMPOTENCY_IMPLEMENTATION" in codes
    assert "CONCURRENT_IDEMPOTENCY_TEST" in codes


def test_progress05_r2_traceability_demotes_pltview_007_without_mounted_viewer_integration() -> None:
    """CONTROL: source traceability cannot promote PLTVIEW-007 on dependency-free evidence alone."""
    from tools.build_traceability_map import build

    overlay = build(declared_source_state=True)["requirements"]["PLTVIEW-007"]
    assert overlay["implementation_status"] == "IMPLEMENTED_UNVERIFIED"
    assert "viewer integration test has not run" in overlay["notes"]
    assert (
        "tests/contract/test_web_viewer_runtime.py::"
        "test_pltview_007_reference_layer_contract_is_implemented_but_not_viewer_integrated"
    ) in overlay["test_ids"]
