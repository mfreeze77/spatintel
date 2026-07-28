from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from tools.checkpoint_common import FIXED_ZIP_TIME
from tools.source_identity import source_tree_root
from tools.verify_checkpoint import verify_archive

ROOT = Path(__file__).resolve().parents[2]


def test_packaging_metadata_cannot_change_canonical_source_root(tmp_path: Path) -> None:
    """CONTROL: checkpoint packaging metadata is excluded by the one canonical source-root policy."""
    project = tmp_path / "project"
    (project / "governance").mkdir(parents=True)
    shutil.copy2(ROOT / "governance/source-root-policy.json", project / "governance/source-root-policy.json")
    (project / "src").mkdir()
    (project / "src/example.py").write_text("VALUE = 1\n", encoding="utf-8")
    before = source_tree_root(project)

    (project / "CHECKPOINT_CONTENT_MANIFEST.json").write_text("{}\n", encoding="utf-8")
    (project / "IMPLEMENTATION_STATUS.md").write_text("generated status\n", encoding="utf-8")
    (project / "build/reports").mkdir(parents=True)
    (project / "build/reports/test.json").write_text("{}\n", encoding="utf-8")
    after_packaging = source_tree_root(project)
    assert after_packaging == before

    (project / "src/example.py").write_text("VALUE = 2\n", encoding="utf-8")
    assert source_tree_root(project) != before


def test_checkpoint_verifier_rejects_unsafe_zip_paths(tmp_path: Path) -> None:
    """CONTROL: archive traversal is rejected before any checkpoint claim is accepted."""
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as output:
        info = zipfile.ZipInfo("../escape.txt", FIXED_ZIP_TIME)
        output.writestr(info, b"escape")
    report = verify_archive(archive)
    assert report["status"] == "failed"
    assert any(item["code"] == "ZIP_UNSAFE_PATH" for item in report["findings"])


def test_checkpoint_verifier_rejects_content_manifest_tamper(tmp_path: Path) -> None:
    """CONTROL: every file hash and aggregate root must reproduce exactly."""
    archive = tmp_path / "tampered.zip"
    top = "Spatial-Intelligence-Platform-v1.1.0-progress-04-r1"
    manifest = {
        "schema": "sip.checkpoint-content-manifest/v1",
        "checkpoint_id": "sip-v1.1.0-progress-04-r1",
        "top_level": top,
        "excluded_from_content_root": ["CHECKPOINT_CONTENT_MANIFEST.json"],
        "file_count": 1,
        "total_uncompressed_bytes": 4,
        "content_root_sha256": "0" * 64,
        "files": [
            {
                "kind": "file",
                "mode": "0644",
                "path": "payload.txt",
                "sha256": "0" * 64,
                "size": 4,
            }
        ],
    }
    with zipfile.ZipFile(archive, "w") as output:
        payload = zipfile.ZipInfo(f"{top}/payload.txt", FIXED_ZIP_TIME)
        payload.create_system = 3
        payload.external_attr = 0o644 << 16
        output.writestr(payload, b"real")
        info = zipfile.ZipInfo(f"{top}/CHECKPOINT_CONTENT_MANIFEST.json", FIXED_ZIP_TIME)
        info.create_system = 3
        info.external_attr = 0o644 << 16
        output.writestr(info, (json.dumps(manifest) + "\n").encode())
    report = verify_archive(archive)
    assert report["status"] == "failed"
    codes = {item["code"] for item in report["findings"]}
    assert "MANIFEST_HASH_MISMATCH" in codes
    assert "CONTENT_ROOT_MISMATCH" in codes


def test_generated_post_commit_evidence_does_not_dirty_source_worktree(tmp_path: Path) -> None:
    """CONTROL: retained evidence is ignored while actual source edits remain visible to Git."""
    import subprocess

    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.email", "sip-tests@example.invalid"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "SIP Test"], cwd=project, check=True)
    shutil.copy2(ROOT / ".gitignore", project / ".gitignore")
    (project / "build/evidence").mkdir(parents=True)
    (project / "build/reports").mkdir(parents=True)
    (project / "build/evidence/.gitkeep").write_text("", encoding="utf-8")
    (project / "build/reports/.gitkeep").write_text("", encoding="utf-8")
    (project / "src").mkdir()
    (project / "src/example.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=project, check=True)

    (project / "build/evidence/source-test-attestation.json").write_text("{}\n", encoding="utf-8")
    (project / "build/reports/test-matrix.json").write_text("{}\n", encoding="utf-8")
    clean = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )
    assert clean.stdout == ""

    (project / "src/example.py").write_text("VALUE = 2\n", encoding="utf-8")
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "src/example.py" in dirty.stdout
