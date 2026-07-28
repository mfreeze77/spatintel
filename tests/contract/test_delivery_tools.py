from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import re
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _release_module():
    path = ROOT / "tools/release.py"
    spec = importlib.util.spec_from_file_location("sip_release_tool", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _demo_module():
    path = ROOT / "tools/run_demo.py"
    spec = importlib.util.spec_from_file_location("sip_demo_tool", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.contract
def test_make_and_just_commands_resolve_to_implemented_tools() -> None:
    """REQ: DELDEV-004, DELDEV-005 advertised developer commands must be executable."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    justfile = (ROOT / "justfile").read_text(encoding="utf-8")
    expected = {
        "bootstrap",
        "doctor",
        "dev",
        "test",
        "test-all",
        "lint",
        "typecheck",
        "security",
        "license-check",
        "spec-check",
        "benchmark",
        "demo-foundation",
        "demo-hybrid",
        "demo-construction",
        "demo-liveforever",
        "export-demo",
        "restore-demo",
        "release",
    }
    make_targets = set(re.findall(r"^([a-z][a-z0-9-]+):", makefile, re.MULTILINE))
    just_targets = set(re.findall(r"^([a-z][a-z0-9-]+):", justfile, re.MULTILINE))
    assert expected <= make_targets
    assert expected <= just_targets
    for script in re.findall(r"tools/([A-Za-z0-9_/-]+\.py)", makefile):
        assert (ROOT / "tools" / script).is_file(), script


@pytest.mark.contract
def test_demo_output_lock_serializes_destructive_setup(tmp_path: Path) -> None:
    """REQ: DELDEV-002 synthetic demo state remains isolated under concurrent invocations."""
    module = _demo_module()
    destination = tmp_path / "construction"
    first_acquired = threading.Event()
    release_first = threading.Event()
    second_acquired = threading.Event()
    errors: list[BaseException] = []

    def first() -> None:
        try:
            with module._exclusive_destination_lock(destination):
                first_acquired.set()
                assert release_first.wait(timeout=5)
        except BaseException as exc:
            errors.append(exc)

    def second() -> None:
        try:
            assert first_acquired.wait(timeout=5)
            with module._exclusive_destination_lock(destination):
                second_acquired.set()
        except BaseException as exc:
            errors.append(exc)

    first_thread = threading.Thread(target=first, daemon=True)
    second_thread = threading.Thread(target=second, daemon=True)
    first_thread.start()
    second_thread.start()
    assert first_acquired.wait(timeout=5)
    assert not second_acquired.wait(timeout=0.2)
    release_first.set()
    assert second_acquired.wait(timeout=5)
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)
    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert errors == []


@pytest.mark.contract
def test_github_actions_are_sha_pinned_and_least_privilege() -> None:
    """REQ: OPSCICD-001 CI actions must be immutable and default permissions least privilege."""
    workflows = list((ROOT / ".github/workflows").glob("*.yml"))
    assert {path.name for path in workflows} >= {"ci.yml", "release.yml"}
    action_pattern = re.compile(r"uses:\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([^\s]+)")
    for path in workflows:
        text = path.read_text(encoding="utf-8")
        actions = action_pattern.findall(text)
        assert actions, path
        for action, revision in actions:
            assert re.fullmatch(r"[0-9a-f]{40}", revision), f"{path}: {action}@{revision} is mutable"
        assert "contents: read" in text
        assert "persist-credentials: false" in text
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "pull_request:" in ci
    assert "cancel-in-progress: true" in ci
    release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "tools/release.py --mode release" in release
    assert "SIP_RELEASE_SIGNING_KEY_B64" in release


@pytest.mark.contract
def test_release_source_zip_is_byte_deterministic(tmp_path: Path) -> None:
    """REQ: OPSCICD-002 identical source inputs produce a stable archive hash."""
    module = _release_module()
    paths = [ROOT / "LICENSE", ROOT / "NOTICE.md", ROOT / "pyproject.toml"]
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    module._write_zip(first, paths, "sip")
    module._write_zip(second, list(reversed(paths)), "sip")
    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(second.read_bytes()).digest()


@pytest.mark.contract
def test_release_readiness_fails_closed_for_open_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    """REQ: TSTGATE-003, OPSCICD-002 release promotion must reject unresolved evidence."""
    module = _release_module()
    version = module._project_version()
    blockers = module._requirements_blockers() + module._environment_blockers(version, signing_available=False)
    codes = {item.code for item in blockers}
    assert "REQUIREMENTS_RELEASE_GATES_OPEN" in codes
    assert "RELEASE_SIGNING_KEY_MISSING" in codes
    assert "WEB_LOCKFILE_MISSING" in codes
    monkeypatch.setenv("SIP_RELEASE_SIGNING_KEY_B64", base64.b64encode(b"short").decode("ascii"))
    key, error = module._signing_key()
    assert key is None
    assert error and "32 raw Ed25519" in error


@pytest.mark.contract
def test_cyclonedx_sbom_covers_runtime_web_workers_and_governance() -> None:
    """REQ: GOVLIC-003 release SBOM includes code, workers, containers, providers, and models."""
    module = _release_module()
    sbom = module._sbom(module._project_version(), "a" * 40, "2026-07-27T00:00:00Z")
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.6"
    components = sbom["components"]
    purls = {item.get("purl") for item in components}
    assert "pkg:pypi/fastapi@0.128.2" in purls
    assert "pkg:npm/next@16.2.11" in purls
    types = {item["type"] for item in components}
    assert {"application", "container", "service", "machine-learning-model"} <= types
    worker_components = [item for item in components if str(item["bom-ref"]).startswith("urn:sip:worker:")]
    assert len(worker_components) == 16

@pytest.mark.contract
def test_gpu_doctor_requires_compatible_runtime_and_approved_local_checkpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """REQ: DELDEV-005 GPU setup verifies runtime compatibility and refuses unapproved or hash-mismatched checkpoints."""
    from sip import cli

    checkpoint = tmp_path / "fixture.pt"
    checkpoint.write_bytes(b"approved deterministic fixture checkpoint")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    manifest = tmp_path / "fixture.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "sip.model-manifest/v1",
                "model_id": "fixture-approved",
                "approval_state": "approved",
                "checkpoint_hash": digest,
                "local_path": str(checkpoint),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "_nvidia_report", lambda: {"available": True, "devices": [{"name": "fixture"}], "error": None})
    monkeypatch.setattr(
        cli,
        "_probe_torch_cuda",
        lambda: {"installed": True, "available": True, "version": "fixture", "compiled_cuda": "fixture", "error": None},
    )
    ready = cli.gpu_doctor(tmp_path)
    assert ready["status"] == "ready"
    assert ready["production_execution_allowed"] is True
    assert ready["checkpoints"]["implicit_downloads_allowed"] is False

    checkpoint.write_bytes(b"tampered")
    blocked = cli.gpu_doctor(tmp_path)
    assert blocked["status"] == "blocked"
    assert blocked["production_execution_allowed"] is False
    assert blocked["checkpoints"]["rejected"][0]["reason"] == "checkpoint_hash_mismatch"


@pytest.mark.contract
def test_third_party_manifest_lock_is_deterministic_and_fail_closed() -> None:
    """REQ: GOVLIC-001, GOVLIC-002 every imported source/runtime dependency has a deterministic governed lock record."""
    module_path = ROOT / "tools/generate_third_party_lock.py"
    spec = importlib.util.spec_from_file_location("sip_third_party_lock_tool", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    expected = module.build()
    actual = __import__("json").loads((ROOT / "third_party/manifest.lock.json").read_text(encoding="utf-8"))
    assert actual == expected
    assert actual["runtime_downloads_allowed"] is False
    assert len(actual["imported_sources"]) == 2
    assert all(item["revision"] and len(item["revision"]) == 40 for item in actual["imported_sources"])
    assert all(item["version"] for item in actual["dependencies"])
    assert all(item["digest"].startswith("sha256:") for item in actual["container_images"])

@pytest.mark.contract
def test_synthetic_fixture_corpus_is_deterministic_hashed_and_fail_closed() -> None:
    """REQ: TSTLAY-002, TSTLAY-004, TSTSEC-003 synthetic fixtures cover valid, corrupt, malicious, geometry, vertical, and provider-failure cases."""
    import subprocess

    result = subprocess.run(
        [sys.executable, "tools/generate_test_fixtures.py", "--check"],
        cwd=ROOT,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")},
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((ROOT / "tests/fixtures/manifest.json").read_text(encoding="utf-8"))
    assert manifest["synthetic_only"] is True
    assert manifest["fixture_count"] >= 15
    records = {item["path"]: item for item in manifest["fixtures"]}
    required = {
        "capture/canonical-room.sipcapture",
        "capture/future-schema.sipcapture",
        "capture/tampered-asset.sipcapture",
        "capture/truncated.sipcapture",
        "security/path-traversal.zip",
        "security/compression-bomb.zip",
        "security/cross-tenant-attempts.json",
        "geometry/known-transform.json",
        "geometry/mixed-coordinate-frames.json",
        "geometry/proxy-missing-surface.json",
        "construction/synthetic-project.json",
        "liveforever/conflicting-recollections.json",
        "providers/failure-matrix.json",
    }
    assert required <= records.keys()
    for relative, record in records.items():
        path = ROOT / "tests/fixtures" / relative
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
        assert path.stat().st_size == record["byte_count"]
    assert records["capture/canonical-room.sipcapture"]["expected_result"] == "accepted"
    assert records["capture/future-schema.sipcapture"]["expected_error_code"] == "CAPTURE_FUTURE_SCHEMA"
    assert records["capture/tampered-asset.sipcapture"]["expected_error_code"] == "CAPTURE_ASSET_INTEGRITY"
    assert records["capture/truncated.sipcapture"]["expected_error_code"] == "CAPTURE_ARCHIVE_INVALID"
    assert records["security/path-traversal.zip"]["expected_error_code"] == "ARCHIVE_PATH_UNSAFE"
    assert records["security/compression-bomb.zip"]["expected_error_code"] == "ARCHIVE_COMPRESSION_RATIO"

@pytest.mark.contract
def test_license_gate_runs_directly_without_repository_root_pythonpath() -> None:
    """REQ: GOVLIC-001 governance and license tooling must be independently executable and fail closed."""
    import os
    import subprocess

    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "tools/license_check.py", "--output", "build/reports/license-gate-direct.json"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((ROOT / "build/reports/license-gate-direct.json").read_text(encoding="utf-8"))
    assert report["status"] == "passed_complete"
    assert not report["errors"]
