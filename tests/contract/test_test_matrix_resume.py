from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _module():
    path = ROOT / "tools/run_test_matrix.py"
    spec = importlib.util.spec_from_file_location("sip_test_matrix_tool", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_generated_traceability_outputs_do_not_create_a_test_evidence_bootstrap_loop() -> None:
    """REQ: TSTSTRAT-002 generated evidence cannot invalidate the run that produced it."""
    module = _module()
    assert module._source_path_is_relevant("src/sip/search.py") is True
    assert module._source_path_is_relevant("migrations/versions/0009_example.py") is True
    assert module._source_path_is_relevant("schemas/openapi/all.openapi.json") is True
    assert module._source_path_is_relevant("requirements/implementation-map.json") is False
    assert module._source_path_is_relevant("tests/spec/requirements/DATSEARC-001.yaml") is False
    spec_lint_test = ROOT / "tests/contract/test_spec_lint.py"
    assert "requirements/implementation-map.json" in module._declared_generated_inputs(spec_lint_test)
    assert "requirements/requirements-ledger.json" in module._declared_generated_inputs(spec_lint_test)
    assert "build/reports/test-matrix.json" not in module._declared_generated_inputs(spec_lint_test)
    assert module._bootstrap_excluded_inputs(spec_lint_test) == ()


def test_suite_sidecar_rejects_changed_source_or_tampered_outputs(tmp_path: Path, monkeypatch) -> None:
    """REQ: TSTSTRAT-002 resumed suites remain bound to exact source, test inputs, JUnit and logs."""
    module = _module()
    monkeypatch.setattr(module, "REPORT_ROOT", tmp_path)
    junit = tmp_path / "contract.xml"
    log = tmp_path / "contract.log"
    junit.write_text('<testsuite tests="1" failures="0" errors="0" skipped="0"></testsuite>', encoding="utf-8")
    log.write_text("1 passed\n", encoding="utf-8")
    result = module.SuiteResult(
        name="contract",
        command=["pytest"],
        status="passed",
        exit_code=0,
        elapsed_seconds=1.0,
        tests=1,
        failures=0,
        errors=0,
        skipped=0,
        junit_path=str(junit),
        log_path=str(log),
        input_root_sha256=module._hash_path_set(("tests/contract",)),
        source_tree_root_sha256="a" * 64,
        junit_sha256=module._sha256_file(junit),
        log_sha256=module._sha256_file(log),
        captured_at="2026-07-27T00:00:00+00:00",
    )
    (tmp_path / "contract.evidence.json").write_text(
        json.dumps({"schema": "sip.test-suite-evidence/v1", "result": asdict(result)}),
        encoding="utf-8",
    )
    loaded, findings = module._load_sidecar(
        "contract", ("tests/contract",), source_tree_root="a" * 64
    )
    assert loaded is not None
    assert findings == []

    log.write_text("tampered\n", encoding="utf-8")
    _, findings = module._load_sidecar("contract", ("tests/contract",), source_tree_root="b" * 64)
    codes = {item["code"] for item in findings}
    assert "SUITE_SOURCE_STALE" in codes
    assert "SUITE_LOG_HASH_MISMATCH" in codes


def test_staged_shard_resume_is_hash_bound_and_rejects_mutation(tmp_path: Path, monkeypatch) -> None:
    """REQ: TSTSTRAT-002 interrupted matrix controllers resume only exact completed shards."""
    module = _module()
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='fixture'\nversion='0.0.0'\n", encoding="utf-8")
    test_path = root / "tests" / "contract" / "test_resume_fixture.py"
    test_path.parent.mkdir(parents=True)
    test_path.write_text("def test_fixture():\n    assert True\n", encoding="utf-8")
    staged = root / "build" / "reports" / "tests" / ".contract.shards.next"
    staged.mkdir(parents=True)
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(module, "REPORT_ROOT", staged.parent)

    shard_name = module._safe_shard_name(test_path)
    junit = staged / f"{shard_name}.xml"
    log = staged / f"{shard_name}.log"
    junit.write_text('<testsuite tests="1" failures="0" errors="0" skipped="0"></testsuite>', encoding="utf-8")
    log.write_text("1 passed\n", encoding="utf-8")
    source_root = "c" * 64
    result = {
        "schema": "sip.pytest-shard-result/v2",
        "name": shard_name,
        "path": str(test_path.relative_to(root)),
        "command": ["pytest", str(test_path.relative_to(root))],
        "status": "passed",
        "exit_code": 0,
        "elapsed_seconds": 0.1,
        "input_sha256": module._sha256_file(test_path),
        "declared_generated_inputs": [],
        "declared_generated_input_root_sha256": module._hash_declared_input_roots(()),
        "bootstrap_excluded_inputs": [],
        "source_tree_root_sha256": source_root,
        "junit_path": str(junit),
        "log_path": str(log),
        "junit_sha256": module._sha256_file(junit),
        "log_sha256": module._sha256_file(log),
    }
    result_path = staged / f"{shard_name}.result.json"
    result_path.write_text(json.dumps(result, sort_keys=True), encoding="utf-8")

    resumed = module._load_staged_shard(
        path=test_path, staged_shard_root=staged, source_tree_root=source_root
    )
    assert resumed is not None
    assert resumed["status"] == "passed"

    log.write_text("tampered\n", encoding="utf-8")
    assert module._load_staged_shard(
        path=test_path, staged_shard_root=staged, source_tree_root=source_root
    ) is None


def test_staged_shard_resume_rejects_evidence_outside_atomic_staging_root(
    tmp_path: Path, monkeypatch
) -> None:
    """REQ: TSTSTRAT-002 resumable records cannot borrow artifacts from an old publication."""
    module = _module()
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        "[project]\nname='fixture'\nversion='0.0.0'\n", encoding="utf-8"
    )
    test_path = root / "tests" / "contract" / "test_resume_fixture.py"
    test_path.parent.mkdir(parents=True)
    test_path.write_text("def test_fixture():\n    assert True\n", encoding="utf-8")
    staged = root / "build" / "reports" / "tests" / ".contract.shards.next"
    final = root / "build" / "reports" / "tests" / "contract-shards"
    staged.mkdir(parents=True)
    final.mkdir(parents=True)
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(module, "REPORT_ROOT", staged.parent)

    shard_name = module._safe_shard_name(test_path)
    final_junit = final / f"{shard_name}.xml"
    final_log = final / f"{shard_name}.log"
    final_junit.write_text(
        '<testsuite tests="1" failures="0" errors="0" skipped="0"></testsuite>',
        encoding="utf-8",
    )
    final_log.write_text("1 passed\n", encoding="utf-8")
    result = {
        "schema": "sip.pytest-shard-result/v2",
        "name": shard_name,
        "path": str(test_path.relative_to(root)),
        "command": ["pytest", str(test_path.relative_to(root))],
        "status": "passed",
        "exit_code": 0,
        "elapsed_seconds": 0.1,
        "input_sha256": module._sha256_file(test_path),
        "declared_generated_inputs": [],
        "declared_generated_input_root_sha256": module._hash_declared_input_roots(()),
        "bootstrap_excluded_inputs": [],
        "source_tree_root_sha256": "e" * 64,
        "junit_path": str(final_junit),
        "log_path": str(final_log),
        "junit_sha256": module._sha256_file(final_junit),
        "log_sha256": module._sha256_file(final_log),
    }
    (staged / f"{shard_name}.result.json").write_text(
        json.dumps(result, sort_keys=True), encoding="utf-8"
    )

    assert module._load_staged_shard(
        path=test_path, staged_shard_root=staged, source_tree_root="e" * 64
    ) is None


def test_traceability_shard_resume_is_invalidated_by_generated_input_change_without_matrix_bootstrap(
    tmp_path: Path, monkeypatch
) -> None:
    """REQ: TSTSTRAT-002 generated traceability inputs invalidate only the consuming shard."""
    module = _module()
    root = tmp_path / "repo"
    (root / "tests" / "contract").mkdir(parents=True)
    (root / "requirements").mkdir(parents=True)
    (root / "tests" / "spec" / "requirements").mkdir(parents=True)
    (root / "build" / "reports" / "tests" / ".contract.shards.next").mkdir(parents=True)
    (root / "build" / "reports").mkdir(parents=True, exist_ok=True)
    (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='fixture'\nversion='0.0.0'\n", encoding="utf-8")
    test_path = root / "tests" / "contract" / "test_spec_lint.py"
    test_path.write_text("def test_fixture():\n    assert True\n", encoding="utf-8")
    (root / "requirements" / "implementation-map.json").write_text('{"revision": 1}\n', encoding="utf-8")
    (root / "requirements" / "requirements-ledger.json").write_text('{"requirements": []}\n', encoding="utf-8")
    (root / "requirements" / "requirements-ledger.sqlite").write_bytes(b"sqlite-fixture-v1")
    (root / "tests" / "spec" / "requirements" / "REQ-001.yaml").write_text("requirement_id: REQ-001\n", encoding="utf-8")
    matrix = root / "build" / "reports" / "test-matrix.json"
    matrix.write_text('{"attempt": 1}\n', encoding="utf-8")
    staged = root / "build" / "reports" / "tests" / ".contract.shards.next"
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(module, "REPORT_ROOT", staged.parent)

    shard_name = module._safe_shard_name(test_path)
    junit = staged / f"{shard_name}.xml"
    log = staged / f"{shard_name}.log"
    junit.write_text('<testsuite tests="1" failures="0" errors="0" skipped="0"></testsuite>', encoding="utf-8")
    log.write_text("1 passed\n", encoding="utf-8")
    source_root = "d" * 64
    declared_inputs = module._declared_generated_inputs(test_path)
    result = {
        "schema": "sip.pytest-shard-result/v2",
        "name": shard_name,
        "path": str(test_path.relative_to(root)),
        "command": ["pytest", str(test_path.relative_to(root))],
        "status": "passed",
        "exit_code": 0,
        "elapsed_seconds": 0.1,
        "input_sha256": module._sha256_file(test_path),
        "declared_generated_inputs": list(declared_inputs),
        "declared_generated_input_root_sha256": module._hash_declared_input_roots(declared_inputs),
        "bootstrap_excluded_inputs": list(module._bootstrap_excluded_inputs(test_path)),
        "source_tree_root_sha256": source_root,
        "junit_path": str(junit),
        "log_path": str(log),
        "junit_sha256": module._sha256_file(junit),
        "log_sha256": module._sha256_file(log),
    }
    (staged / f"{shard_name}.result.json").write_text(json.dumps(result, sort_keys=True), encoding="utf-8")

    assert module._load_staged_shard(
        path=test_path, staged_shard_root=staged, source_tree_root=source_root
    ) is not None

    matrix.write_text('{"attempt": 2}\n', encoding="utf-8")
    assert module._load_staged_shard(
        path=test_path, staged_shard_root=staged, source_tree_root=source_root
    ) is not None

    (root / "requirements" / "implementation-map.json").write_text('{"revision": 2}\n', encoding="utf-8")
    assert module._load_staged_shard(
        path=test_path, staged_shard_root=staged, source_tree_root=source_root
    ) is None
    log.write_text("1 passed\n", encoding="utf-8")
    test_path.write_text("def test_fixture():\n    assert False\n", encoding="utf-8")
    assert module._load_staged_shard(
        path=test_path, staged_shard_root=staged, source_tree_root=source_root
    ) is None


def test_source_tree_hash_prunes_generated_trees_and_changes_only_for_relevant_source(tmp_path: Path, monkeypatch) -> None:
    """REQ: TSTSTRAT-002 source-bound evidence hashes executable inputs without traversing generated trees."""
    module = _module()
    root = tmp_path / "repo"
    (root / "governance").mkdir(parents=True)
    (root / "governance" / "source-root-policy.json").write_bytes(
        (ROOT / "governance" / "source-root-policy.json").read_bytes()
    )
    (root / "src").mkdir(parents=True)
    (root / "build" / "reports").mkdir(parents=True)
    (root / ".git" / "objects").mkdir(parents=True)
    (root / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "build" / "reports" / "report.json").write_text('{"run": 1}', encoding="utf-8")
    (root / ".git" / "objects" / "ignored.py").write_text("ignored = 1\n", encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", root)

    first = module._source_tree_root()
    (root / "build" / "reports" / "report.json").write_text('{"run": 2}', encoding="utf-8")
    (root / ".git" / "objects" / "ignored.py").write_text("ignored = 2\n", encoding="utf-8")
    assert module._source_tree_root() == first

    (root / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    assert module._source_tree_root() != first


def test_finalized_shard_records_use_repository_relative_live_paths(tmp_path: Path, monkeypatch) -> None:
    """REQ: TSTSTRAT-002 published shard evidence never references deleted staging paths."""
    module = _module()
    root = tmp_path / "repo"
    staged = root / "build" / "reports" / "tests" / ".contract.shards.next"
    final = root / "build" / "reports" / "tests" / "contract-shards"
    staged.mkdir(parents=True)
    monkeypatch.setattr(module, "ROOT", root)

    name = "tests__contract__test_fixture"
    staged_junit = staged / f"{name}.xml"
    staged_log = staged / f"{name}.log"
    staged_junit.write_text('<testsuite tests="1" failures="0" errors="0" skipped="0"></testsuite>', encoding="utf-8")
    staged_log.write_text("1 passed\n", encoding="utf-8")
    shard = {
        "schema": "sip.pytest-shard-result/v2",
        "name": name,
        "path": "tests/contract/test_fixture.py",
        "command": ["pytest", "tests/contract/test_fixture.py", f"--junitxml={staged_junit}"],
        "status": "passed",
        "exit_code": 0,
        "elapsed_seconds": 0.1,
        "input_sha256": "a" * 64,
        "declared_generated_inputs": [],
        "declared_generated_input_root_sha256": module._hash_declared_input_roots(()),
        "bootstrap_excluded_inputs": [],
        "source_tree_root_sha256": "b" * 64,
        "junit_path": str(staged_junit),
        "log_path": str(staged_log),
        "junit_sha256": module._sha256_file(staged_junit),
        "log_sha256": module._sha256_file(staged_log),
    }
    staged.replace(final)

    finalized = module._finalize_shard_records([shard], final_shard_root=final)
    record = finalized[0]
    assert record["junit_path"] == f"build/reports/tests/contract-shards/{name}.xml"
    assert record["log_path"] == f"build/reports/tests/contract-shards/{name}.log"
    assert not Path(record["junit_path"]).is_absolute()
    assert not Path(record["log_path"]).is_absolute()
    assert (root / record["junit_path"]).is_file()
    assert (root / record["log_path"]).is_file()
    retained = json.loads((final / f"{name}.result.json").read_text(encoding="utf-8"))
    assert retained == record
    assert retained["command"][-1].startswith("--junitxml=")
    assert retained["portable_command"][0] == "pytest"
    assert retained["portable_command"][-1] == f"--junitxml=build/reports/tests/contract-shards/{name}.xml"
    assert ".contract.shards.next" not in json.dumps(retained["portable_command"])

    manifest = module._shard_manifest_payload(
        name="contract",
        timeout_seconds=30,
        shard_jobs=1,
        files=[root / "tests/contract/test_fixture.py"],
        shards=finalized,
    )
    assert manifest["schema"] == "sip.pytest-shard-manifest/v2"
    assert manifest["shards"][0]["junit_path"] == f"{name}.xml"
    assert manifest["shards"][0]["log_path"] == f"{name}.log"
    assert ".contract.shards.next" not in json.dumps(manifest["shards"][0]["portable_command"])



def test_stage_owner_token_rejects_orphaned_shard_writes(tmp_path: Path) -> None:
    """REQ: TSTSTRAT-002 stale shard processes cannot publish into a new controller's staging area."""
    module = _module()
    staged = tmp_path / ".contract.shards.next"
    module._write_stage_owner(staged, "current-writer")
    module._assert_stage_owner(staged, "current-writer")
    module._write_stage_owner(staged, "replacement-writer")
    with pytest.raises(RuntimeError, match="ownership changed"):
        module._assert_stage_owner(staged, "current-writer")


def test_suite_writer_lease_serializes_independent_processes(tmp_path: Path) -> None:
    """REQ: TSTSTRAT-002 concurrent matrix controllers cannot share one suite staging directory."""
    lock_root = tmp_path / "locks"
    log_path = tmp_path / "critical-sections.log"
    script = r"""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

module_path = Path(sys.argv[1])
log_path = Path(sys.argv[2])
label = sys.argv[3]
spec = importlib.util.spec_from_file_location(f"sip_matrix_lock_{label}", module_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
with module._suite_lock("contract"):
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"enter:{label}\n")
        handle.flush()
        os.fsync(handle.fileno())
        time.sleep(0.35)
        handle.write(f"exit:{label}\n")
        handle.flush()
        os.fsync(handle.fileno())
"""
    environment = dict(os.environ)
    environment["SIP_TEST_MATRIX_LOCK_ROOT"] = str(lock_root)
    environment["SIP_TEST_MATRIX_LOCK_TIMEOUT_SECONDS"] = "10"
    command = [sys.executable, "-c", script, str(ROOT / "tools/run_test_matrix.py"), str(log_path)]
    first = subprocess.Popen([*command, "first"], env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(0.05)
    second = subprocess.Popen([*command, "second"], env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    first_output, first_error = first.communicate(timeout=10)
    second_output, second_error = second.communicate(timeout=10)
    assert first.returncode == 0, first_output + first_error
    assert second.returncode == 0, second_output + second_error
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4
    first_label = lines[0].split(":", 1)[1]
    second_label = lines[2].split(":", 1)[1]
    assert first_label != second_label
    assert lines == [f"enter:{first_label}", f"exit:{first_label}", f"enter:{second_label}", f"exit:{second_label}"]
    assert not list(lock_root.glob("*.writer.lock"))


def test_isolated_pytest_runner_terminates_when_controller_disappears(tmp_path: Path) -> None:
    """REQ: TSTSTRAT-002 evidence shards cannot outlive a terminated matrix controller."""
    sleeping_test = tmp_path / "test_sleeping_orphan.py"
    sleeping_test.write_text("import time\ndef test_sleeping_orphan():\n    time.sleep(30)\n", encoding="utf-8")
    environment = dict(os.environ)
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    environment["SIP_TEST_MATRIX_PARENT_PID"] = "999999999"
    started = time.monotonic()
    process = subprocess.Popen(
        [sys.executable, str(ROOT / "tools/run_pytest_isolated.py"), "-q", str(sleeping_test), "-p", "no:cacheprovider"],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    output, _ = process.communicate(timeout=5)
    elapsed = time.monotonic() - started
    assert process.returncode != 0, output
    assert elapsed < 3.0


def test_active_staging_is_isolated_from_published_report_cleanup(tmp_path: Path, monkeypatch) -> None:
    """REQ: TSTSTRAT-002 publication cleanup cannot erase a live controller's shards."""
    module = _module()
    report_root = tmp_path / "published"
    lock_root = tmp_path / "controller-state"
    monkeypatch.setattr(module, "REPORT_ROOT", report_root)
    monkeypatch.setattr(module, "LOCK_ROOT", lock_root)

    staged_junit, staged_log, staged_shards = module._suite_staging_paths("contract")
    assert staged_shards.is_relative_to(lock_root)
    assert not staged_shards.is_relative_to(report_root)
    module._write_stage_owner(staged_shards, "active-writer")
    staged_junit.parent.mkdir(parents=True, exist_ok=True)
    staged_junit.write_text("in progress\n", encoding="utf-8")
    staged_log.write_text("in progress\n", encoding="utf-8")

    legacy_staging = report_root / ".contract.shards.next"
    legacy_staging.mkdir(parents=True, exist_ok=True)
    (legacy_staging / "stale.xml").write_text("stale", encoding="utf-8")
    import shutil
    shutil.rmtree(legacy_staging)

    module._assert_stage_owner(staged_shards, "active-writer")
    assert staged_junit.read_text(encoding="utf-8") == "in progress\n"
    assert staged_log.read_text(encoding="utf-8") == "in progress\n"
