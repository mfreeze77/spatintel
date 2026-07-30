from __future__ import annotations

import json
import subprocess
import zipfile
from pathlib import Path

from tools.build_progress06_checkpoint import CHECKPOINT_ID, P06_SCOPE_IDS, TOP_LEVEL
from tools.checkpoint_common import FIXED_ZIP_TIME
from tools.verify_progress06_checkpoint import (
    EXPECTED_BASE_COMMIT,
    EXPECTED_MIGRATION_BYTES,
    EXPECTED_MIGRATION_SHA256,
    verify_archive,
)

ROOT = Path(__file__).resolve().parents[2]


def _zip_info(name: str, mode: int = 0o644) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
    info.create_system = 3
    info.external_attr = mode << 16
    return info


def test_progress06_verifier_rejects_unsafe_paths_before_package_claims(tmp_path: Path) -> None:
    """CONTROL: Progress 06 verification rejects traversal before evaluating project claims."""
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(_zip_info("../escape.txt"), b"escape")
    report = verify_archive(archive)
    assert report["status"] == "failed"
    assert any(item["code"] == "ZIP_UNSAFE_PATH" for item in report["findings"])


def test_progress06_verifier_rehashes_manifest_and_content_root(tmp_path: Path) -> None:
    """CONTROL: Progress 06 verification independently detects file and aggregate-root tamper."""
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


def test_progress06_checkpoint_scope_and_predecessor_are_exact() -> None:
    """CONTROL: Progress 06 cannot drift beyond the 206 authorized requirements or the accepted R2 base."""
    scope = json.loads((ROOT / "requirements/MILESTONE_SCOPE_PROGRESS_06.json").read_text(encoding="utf-8"))
    predecessor = json.loads((ROOT / "PREDECESSOR_CHECKPOINT.json").read_text(encoding="utf-8"))
    included = {item["requirement_id"] for item in scope["included_requirements"]}
    deferred = {item["requirement_id"] for item in scope["deferred_requirements"]}
    assert included.isdisjoint(deferred)
    assert included | deferred == set(P06_SCOPE_IDS)
    assert len(included) == 118
    assert len(deferred) == 88
    assert scope["progress_07_authorized"] is False
    assert scope["production_authorized"] is False
    assert predecessor["accepted_progress_05_r2_checkpoint"]["commit"] == EXPECTED_BASE_COMMIT


def test_progress06_migration_and_viewer_truth_are_fail_closed() -> None:
    """CONTROL: revision 0014 is byte-locked and PLTVIEW-007 remains unverified."""
    migration = ROOT / "migrations/versions/0014_vertical_mvp.py"
    import hashlib

    assert migration.stat().st_size == EXPECTED_MIGRATION_BYTES
    assert hashlib.sha256(migration.read_bytes()).hexdigest() == EXPECTED_MIGRATION_SHA256
    implementation = json.loads((ROOT / "requirements/implementation-map.json").read_text(encoding="utf-8"))
    assert implementation["requirements"]["PLTVIEW-007"]["implementation_status"] == "IMPLEMENTED_UNVERIFIED"

def test_progress06_coverage_report_retains_later_phase_posture() -> None:
    """CONTROL: generated coverage retains Progress 07 prohibition and production NO-GO."""
    text = (ROOT / "requirements/coverage-report.md").read_text(encoding="utf-8")
    assert "Progress 07" in text
    assert "unauthorized" in text
    assert "Production promotion" in text
    assert "NO-GO" in text

def test_progress06_final_commit_descends_from_accepted_r2_base() -> None:
    """CONTROL: Progress 06 may use multiple commits but must descend from the accepted R2 base."""
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", EXPECTED_BASE_COMMIT, "HEAD"],
        cwd=ROOT,
        check=False,
    )
    assert result.returncode == 0


def test_progress06_packaged_coverage_retains_progress07_and_production_posture() -> None:
    """CONTROL: package-specific coverage rendering retains later-phase prohibitions."""
    from tools.build_progress06_checkpoint import _render_coverage

    ledger = json.loads((ROOT / "requirements/requirements-ledger.json").read_text(encoding="utf-8"))
    text = _render_coverage(
        {
            "checkpoint_id": CHECKPOINT_ID,
            "commit": "1" * 40,
            "source_tree_root_sha256": "2" * 64,
            "python_tests_passed": 1,
            "requirements_total": 1028,
        },
        ledger,
    )
    assert "Progress 07" in text
    assert "unauthorized" in text
    assert "NO-GO" in text
