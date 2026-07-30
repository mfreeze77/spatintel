#!/usr/bin/env python3
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import fcntl
import json
import os
import platform
import signal
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from tools.source_identity import source_tree_root as canonical_source_tree_root

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "build" / "reports" / "tests"
MATRIX_PATH = ROOT / "build" / "reports" / "test-matrix.json"


def _default_lock_root(root: Path) -> Path:
    """Return stable controller state outside generated repository trees.

    Test and acceptance workflows may atomically replace ``build`` subtrees.
    Keeping writer leases and resumable staging there can unlink a live
    controller's inode and permit a competing process to publish into the same
    paths.  A per-worktree operating-system temporary directory survives those
    cleanups while still serializing all controllers for one checkout.
    """

    identity = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:24]
    return Path(tempfile.gettempdir()) / f"sip-test-matrix-{identity}"


LOCK_ROOT = Path(os.environ.get("SIP_TEST_MATRIX_LOCK_ROOT", str(_default_lock_root(ROOT))))


def _matrix_controller_lock_path(root: Path = ROOT) -> Path:
    identity = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:24]
    return Path(tempfile.gettempdir()) / f"sip-test-matrix-controller-{identity}.lock"

CONFIGURED_SUITES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("contract", ("tests/contract",)),
    ("integration", ("tests/integration",)),
    ("migration", ("tests/migration",)),
    ("security", ("tests/security",)),
    ("unit", ("tests/unit",)),
    ("property", ("tests/property",)),
    ("privacy", ("tests/privacy",)),
    ("e2e", ("tests/e2e",)),
    ("acceptance", ("tests/acceptance",)),
    ("spec", ("tests/spec",)),
)

# These files are regenerated from the immutable specification and canonical
# test reports. They are evidence overlays, not executable source inputs. Keeping
# them out of the source root prevents a report from invalidating the test run
# that produced it while all implementation, migrations, schemas and tests stay
# source-bound.
GENERATED_EVIDENCE_FILES = {
    "IMPLEMENTATION_STATUS.md",
    "RESUME_IMPLEMENTATION.md",
    "requirements/coverage-report.md",
    "requirements/implementation-map.json",
    "requirements/requirements-ledger.csv",
    "requirements/requirements-ledger.json",
    "requirements/requirements-ledger.sqlite",
}
GENERATED_EVIDENCE_PREFIXES = ("tests/spec/requirements/",)

# Generated inputs that a test reads and whose content can change the result.
# They are excluded from the global source root to avoid a report bootstrap
# loop, so resumable shard evidence must bind them explicitly instead. Keep
# self-produced matrix outputs in SHARD_BOOTSTRAP_EXCLUSIONS: those are checked
# for internal honesty by the test but cannot be inputs to the same run.
SHARD_DECLARED_GENERATED_INPUTS: dict[str, tuple[str, ...]] = {
    "tests/contract/test_spec_lint.py": (
        "requirements/implementation-map.json",
        "requirements/requirements-ledger.json",
        "requirements/requirements-ledger.sqlite",
        "tests/spec/requirements",
    ),
}

# A test must not consume an output produced by the same matrix run.  The
# mapping remains explicit and empty so shard manifests can prove that no
# bootstrap exclusions were used to justify a pass.
SHARD_BOOTSTRAP_EXCLUSIONS: dict[str, tuple[str, ...]] = {}


@dataclass(frozen=True)
class SuiteResult:
    name: str
    command: list[str]
    status: str
    exit_code: int
    elapsed_seconds: float
    tests: int
    failures: int
    errors: int
    skipped: int
    junit_path: str
    log_path: str
    input_root_sha256: str
    source_tree_root_sha256: str
    junit_sha256: str
    log_sha256: str
    captured_at: str
    shard_count: int = 1
    shard_commands: list[list[str]] = field(default_factory=list)
    shard_manifest_path: str = ""
    shard_manifest_sha256: str = ""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes()) if path.is_file() else ""


def _declared_generated_inputs(path: Path) -> tuple[str, ...]:
    try:
        relative = path.relative_to(ROOT).as_posix()
    except ValueError:
        return ()
    return SHARD_DECLARED_GENERATED_INPUTS.get(relative, ())


def _bootstrap_excluded_inputs(path: Path) -> tuple[str, ...]:
    try:
        relative = path.relative_to(ROOT).as_posix()
    except ValueError:
        return ()
    return SHARD_BOOTSTRAP_EXCLUSIONS.get(relative, ())


def _hash_declared_input_roots(configured_paths: Sequence[str]) -> str:
    """Hash exact generated inputs without making generated outputs source.

    Directory declarations recursively bind every regular file by relative
    path and bytes. Missing declarations are represented explicitly so a shard
    cannot be resumed after an input disappears.
    """

    records: list[bytes] = []
    for configured in sorted(set(configured_paths)):
        candidate = ROOT / configured
        if candidate.is_file():
            records.append(
                configured.encode("utf-8")
                + b"\0file\0"
                + hashlib.sha256(candidate.read_bytes()).digest()
            )
            continue
        if candidate.is_dir():
            files = sorted(path for path in candidate.rglob("*") if path.is_file())
            records.append(configured.encode("utf-8") + b"\0directory\0")
            for path in files:
                relative = path.relative_to(ROOT).as_posix()
                records.append(
                    relative.encode("utf-8")
                    + b"\0"
                    + hashlib.sha256(path.read_bytes()).digest()
                )
            continue
        records.append(configured.encode("utf-8") + b"\0missing\0")
    return _sha256_bytes(b"\n".join(records))


def _shard_declared_input_root(path: Path) -> str:
    return _hash_declared_input_roots(_declared_generated_inputs(path))


def _hash_path_set(paths: Sequence[str]) -> str:
    records: list[bytes] = []
    for configured in sorted(paths):
        candidate = ROOT / configured
        files = [candidate] if candidate.is_file() else sorted(candidate.rglob("test_*.py"))
        for path in files:
            relative = path.relative_to(ROOT).as_posix().encode("utf-8")
            records.append(relative + b"\0" + hashlib.sha256(path.read_bytes()).digest())
            declared_root = _shard_declared_input_root(path)
            records.append(relative + b"\0declared-generated-inputs\0" + declared_root.encode("ascii"))
    for configuration in (ROOT / "pytest.ini", ROOT / "pyproject.toml"):
        records.append(
            configuration.relative_to(ROOT).as_posix().encode("utf-8")
            + b"\0"
            + hashlib.sha256(configuration.read_bytes()).digest()
        )
    return _sha256_bytes(b"\n".join(records))


def _source_path_is_relevant(relative: str) -> bool:
    if relative in GENERATED_EVIDENCE_FILES:
        return False
    return not any(relative.startswith(prefix) for prefix in GENERATED_EVIDENCE_PREFIXES)


def _source_tree_root() -> str:
    return canonical_source_tree_root(ROOT)


def _git_value(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "UNAVAILABLE"


def _environment_evidence(source_tree_root: str) -> dict[str, object]:
    freeze = subprocess.run([sys.executable, "-m", "pip", "freeze", "--all"], cwd=ROOT, text=True, capture_output=True, check=False)
    dependency_snapshot = "\n".join(sorted(line.strip() for line in freeze.stdout.splitlines() if line.strip()))
    status = _git_value("status", "--porcelain=v1", "--untracked-files=all")
    return {
        "captured_at": datetime.now(UTC).isoformat(),
        "git_commit": _git_value("rev-parse", "HEAD"),
        "git_branch": _git_value("branch", "--show-current"),
        "git_dirty": bool(status and status != "UNAVAILABLE"),
        "git_status_sha256": _sha256_bytes(status.encode("utf-8")),
        "source_tree_root_sha256": source_tree_root,
        "python_executable": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "dependency_snapshot_sha256": _sha256_bytes(dependency_snapshot.encode("utf-8")),
        "dependency_snapshot_count": len(dependency_snapshot.splitlines()) if dependency_snapshot else 0,
        "test_profile": "local-deterministic-no-external-hardware-or-credentials",
    }


def _junit_counts(path: Path) -> tuple[int, int, int, int]:
    if not path.exists():
        return 0, 0, 0, 0
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))

    def total(key: str) -> int:
        return sum(int(float(item.attrib.get(key, "0"))) for item in suites)

    return total("tests"), total("failures"), total("errors"), total("skipped")


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_lock_owner(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _lease_owner_is_active(owner: dict[str, Any] | None, *, lease_dir: Path) -> bool:
    now = time.time()
    try:
        age = max(0.0, now - lease_dir.stat().st_mtime)
    except OSError:
        return False
    # A contender may observe the directory during the tiny window before the
    # owner record is atomically published. Never reclaim that fresh lease.
    if owner is None:
        return age < 2.0
    hostname = str(owner.get("hostname", ""))
    try:
        pid = int(owner.get("pid", 0))
    except (TypeError, ValueError):
        pid = 0
    if hostname == socket.gethostname() and _pid_is_alive(pid):
        return True
    try:
        acquired_epoch = float(owner.get("acquired_epoch", lease_dir.stat().st_mtime))
    except (TypeError, ValueError, OSError):
        acquired_epoch = now - age
    lease_ttl = float(os.environ.get("SIP_TEST_MATRIX_LEASE_TTL_SECONDS", "21600"))
    # A remote-host lease cannot be checked by PID. Honor it until its explicit
    # maximum lifetime expires; local dead owners can be reclaimed immediately.
    return hostname not in {"", socket.gethostname()} and now - acquired_epoch < lease_ttl


@contextmanager
def _exclusive_matrix_controller_lock():
    """Prevent complete matrix controllers from interleaving evidence.

    Suite-level leases protect individual staging areas.  A separate process-wide
    lock is still required because two controllers could otherwise execute
    different suites concurrently and assemble a mixed report set.  The lock
    lives outside generated repository trees so cleanup cannot replace its inode.
    """

    lock_path = _matrix_controller_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("SIP test matrix is already running for this worktree") from exc
        handle.seek(0)
        handle.truncate()
        handle.write(
            json.dumps(
                {
                    "schema": "sip.test-matrix-controller-lock/v1",
                    "pid": os.getpid(),
                    "worktree": str(ROOT.resolve()),
                    "started_at": datetime.now(UTC).isoformat(),
                },
                sort_keys=True,
            )
            + "\n"
        )
        handle.flush()
        os.fsync(handle.fileno())
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def _directory_writer_lease(name: str):
    """Acquire a filesystem-atomic writer lease resilient to lock-file replacement.

    ``flock`` remains the fast path, while this directory lease protects
    evidence on filesystems or operational paths where a lock file is deleted
    and recreated. Dead local owners are reclaimed without accepting stale
    writers.
    """

    LOCK_ROOT.mkdir(parents=True, exist_ok=True)
    lease_dir = LOCK_ROOT / f"{name}.writer.lock"
    token = uuid.uuid4().hex
    timeout_seconds = float(os.environ.get("SIP_TEST_MATRIX_LOCK_TIMEOUT_SECONDS", "3600"))
    deadline = time.monotonic() + timeout_seconds
    owner_payload = {
        "schema": "sip.test-matrix-writer-lease/v1",
        "token": token,
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "acquired_at": datetime.now(UTC).isoformat(),
        "acquired_epoch": time.time(),
    }
    while True:
        try:
            lease_dir.mkdir()
        except FileExistsError:
            owner = _read_lock_owner(lease_dir / "owner.json")
            if not _lease_owner_is_active(owner, lease_dir=lease_dir):
                stale = lease_dir.with_name(f"{lease_dir.name}.stale.{os.getpid()}.{uuid.uuid4().hex}")
                try:
                    lease_dir.replace(stale)
                except FileNotFoundError:
                    continue
                except OSError:
                    time.sleep(0.05)
                    continue
                shutil.rmtree(stale, ignore_errors=True)
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out waiting for test-matrix writer lease: {name}")
            time.sleep(0.05)
            continue
        owner_tmp = lease_dir / f".owner.{token}.tmp"
        owner_tmp.write_text(json.dumps(owner_payload, sort_keys=True) + "\n", encoding="utf-8")
        owner_tmp.replace(lease_dir / "owner.json")
        break
    try:
        yield owner_payload
    finally:
        owner = _read_lock_owner(lease_dir / "owner.json")
        if owner and owner.get("token") == token:
            released = lease_dir.with_name(f"{lease_dir.name}.released.{os.getpid()}.{token}")
            try:
                lease_dir.replace(released)
            except FileNotFoundError:
                pass
            else:
                shutil.rmtree(released, ignore_errors=True)


@contextmanager
def _suite_lock(name: str):
    """Serialize suite writers with advisory and filesystem-atomic locks."""
    LOCK_ROOT.mkdir(parents=True, exist_ok=True)
    lock_path = LOCK_ROOT / f"{name}.flock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            with _directory_writer_lease(name) as lease:
                handle.seek(0)
                handle.truncate()
                handle.write(json.dumps(lease, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
                yield lease
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _sidecar_path(name: str) -> Path:
    return REPORT_ROOT / f"{name}.evidence.json"


def _write_sidecar(result: SuiteResult) -> None:
    payload = {
        "schema": "sip.test-suite-evidence/v1",
        "result": asdict(result),
    }
    path = _sidecar_path(result.name)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _test_files(paths: Sequence[str]) -> list[Path]:
    files: set[Path] = set()
    for configured in paths:
        candidate = ROOT / configured
        if candidate.is_file() and candidate.name.startswith("test_") and candidate.suffix == ".py":
            files.add(candidate)
        elif candidate.is_dir():
            files.update(candidate.rglob("test_*.py"))
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def _safe_shard_name(path: Path) -> str:
    return path.relative_to(ROOT).as_posix().replace("/", "__").removesuffix(".py")


def _suite_staging_paths(name: str) -> tuple[Path, Path, Path]:
    """Return controller-private staging paths outside published evidence.

    Published report directories are intentionally separate from in-progress
    state.  Cleanup of a prior publication therefore cannot delete JUnit, logs,
    or shard records that a live controller is still producing.  The suite
    writer lease serializes access to this resumable staging area.
    """

    staging_root = LOCK_ROOT / "staging" / name
    return (
        staging_root / f"{name}.next.xml",
        staging_root / f"{name}.next.log",
        staging_root / "shards",
    )


def _stage_owner_path(staged_shard_root: Path) -> Path:
    return staged_shard_root / ".writer-token"


def _write_stage_owner(staged_shard_root: Path, writer_token: str) -> None:
    staged_shard_root.mkdir(parents=True, exist_ok=True)
    temporary = staged_shard_root / f".writer-token.{os.getpid()}.tmp"
    temporary.write_text(writer_token + "\n", encoding="utf-8")
    temporary.replace(_stage_owner_path(staged_shard_root))


def _assert_stage_owner(staged_shard_root: Path, writer_token: str) -> None:
    try:
        retained = _stage_owner_path(staged_shard_root).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError("test-matrix staging ownership was lost") from exc
    if retained != writer_token:
        raise RuntimeError("test-matrix staging ownership changed during shard execution")


def _shard_runtime_environment(
    *,
    environment: dict[str, str],
    writer_token: str,
    shard_name: str,
) -> tuple[Path, dict[str, str]]:
    """Return a process-private runtime and environment for one pytest shard.

    Parallel shards must never import the API against the repository-level
    ``runtime/sip.sqlite3``.  The writer token separates matrix controllers and
    the safe shard name separates every test file within one controller.
    """

    runtime_root = ROOT / "build" / "runtime" / "test-matrix" / writer_token / shard_name
    shard_environment = dict(environment)
    shard_environment.update(
        {
            "SIP_ENV": "test",
            "SIP_ALLOW_DEVELOPMENT_AUTH": "true",
            "SIP_DATABASE_URL": f"sqlite:///{runtime_root / 'sip.sqlite3'}",
            "SIP_OBJECT_STORE_BACKEND": "local",
            "SIP_OBJECT_STORE_ROOT": str(runtime_root / "objects"),
            "SIP_MULTIPART_ROOT": str(runtime_root / "multipart"),
            "SIP_MASTER_KEY_ID": "test-matrix-shard-v1",
        }
    )
    return runtime_root, shard_environment


def _write_synthetic_junit(
    destination: Path,
    *,
    shard_path: str,
    status: str,
    message: str,
    elapsed_seconds: float,
) -> None:
    """Retain machine-readable failure evidence when pytest cannot emit JUnit.

    A timed-out or catastrophically terminated pytest process may never reach its
    JUnit writer.  The matrix must still publish a failed shard atomically rather
    than crashing while finalizing evidence.  This synthetic document records one
    controller error and can never be interpreted as a passing test result.
    """

    suite = ET.Element(
        "testsuite",
        {
            "name": "pytest-shard-controller",
            "tests": "1",
            "failures": "0",
            "errors": "1",
            "skipped": "0",
            "time": f"{elapsed_seconds:.6f}",
            "timestamp": datetime.now(UTC).isoformat(),
            "hostname": platform.node(),
        },
    )
    case = ET.SubElement(
        suite,
        "testcase",
        {
            "classname": "sip.test_matrix",
            "name": f"{status}::{shard_path}",
            "time": f"{elapsed_seconds:.6f}",
        },
    )
    ET.SubElement(case, "error", {"message": message}).text = status
    root = ET.Element("testsuites", {"name": "pytest tests"})
    root.append(suite)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    destination.parent.mkdir(parents=True, exist_ok=True)
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def _run_pytest_shard(
    *,
    name: str,
    path: Path,
    staged_shard_root: Path,
    timeout_seconds: int,
    environment: dict[str, str],
    source_tree_root: str,
    writer_token: str,
) -> dict[str, Any]:
    _assert_stage_owner(staged_shard_root, writer_token)
    shard_name = _safe_shard_name(path)
    runtime_root, shard_environment = _shard_runtime_environment(
        environment=environment,
        writer_token=writer_token,
        shard_name=shard_name,
    )
    shutil.rmtree(runtime_root, ignore_errors=True)
    runtime_root.mkdir(parents=True, exist_ok=True)
    junit = staged_shard_root / f"{shard_name}.xml"
    log = staged_shard_root / f"{shard_name}.log"
    command = [
        sys.executable,
        str(ROOT / "tools" / "run_pytest_isolated.py"),
        "-q",
        str(path.relative_to(ROOT)),
        "-p",
        "no:cacheprovider",
        f"--junitxml={junit}",
    ]
    started = time.perf_counter()
    with log.open("wb") as output:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=shard_environment,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            exit_code = process.wait(timeout=timeout_seconds)
            status = "passed" if exit_code == 0 else "failed"
        except subprocess.TimeoutExpired:
            _terminate_process_group(process)
            exit_code = 124
            status = "timeout"
            output.write(f"\nTIMEOUT after {timeout_seconds}s\n".encode("utf-8"))
    elapsed = round(time.perf_counter() - started, 6)
    if not junit.is_file():
        _write_synthetic_junit(
            junit,
            shard_path=str(path.relative_to(ROOT)),
            status=status,
            message=(
                f"pytest shard exceeded {timeout_seconds}s"
                if status == "timeout"
                else f"pytest shard exited with code {exit_code} without JUnit evidence"
            ),
            elapsed_seconds=elapsed,
        )
    shutil.rmtree(runtime_root, ignore_errors=True)
    _assert_stage_owner(staged_shard_root, writer_token)
    declared_inputs = _declared_generated_inputs(path)
    result: dict[str, Any] = {
        "schema": "sip.pytest-shard-result/v2",
        "name": shard_name,
        "path": str(path.relative_to(ROOT)),
        "command": command,
        "status": status,
        "exit_code": exit_code,
        "elapsed_seconds": elapsed,
        "input_sha256": _sha256_file(path),
        "declared_generated_inputs": list(declared_inputs),
        "declared_generated_input_root_sha256": _hash_declared_input_roots(declared_inputs),
        "bootstrap_excluded_inputs": list(_bootstrap_excluded_inputs(path)),
        "source_tree_root_sha256": source_tree_root,
        "junit_path": str(junit),
        "log_path": str(log),
        "junit_sha256": _sha256_file(junit),
        "log_sha256": _sha256_file(log),
    }
    _assert_stage_owner(staged_shard_root, writer_token)
    result_path = staged_shard_root / f"{shard_name}.result.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _load_staged_shard(
    *,
    path: Path,
    staged_shard_root: Path,
    source_tree_root: str,
) -> dict[str, Any] | None:
    shard_name = _safe_shard_name(path)
    result_path = staged_shard_root / f"{shard_name}.result.json"
    if not result_path.is_file():
        return None
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    expected = {
        "schema": "sip.pytest-shard-result/v2",
        "name": shard_name,
        "path": str(path.relative_to(ROOT)),
        "input_sha256": _sha256_file(path),
        "declared_generated_inputs": list(_declared_generated_inputs(path)),
        "declared_generated_input_root_sha256": _shard_declared_input_root(path),
        "bootstrap_excluded_inputs": list(_bootstrap_excluded_inputs(path)),
        "source_tree_root_sha256": source_tree_root,
    }
    if any(result.get(key) != value for key, value in expected.items()):
        return None
    # A resumable record is valid only when its evidence is physically retained
    # in the staging directory that will be atomically published.  Accepting a
    # result record that points at a previously published final directory can
    # make the record appear valid until that directory is replaced, leaving
    # the new publication without the referenced JUnit/log files.
    expected_junit = staged_shard_root / f"{shard_name}.xml"
    expected_log = staged_shard_root / f"{shard_name}.log"
    junit = Path(str(result.get("junit_path", "")))
    log = Path(str(result.get("log_path", "")))
    if junit != expected_junit or log != expected_log:
        return None
    if not expected_junit.is_file() or not expected_log.is_file():
        return None
    if (
        _sha256_file(expected_junit) != result.get("junit_sha256")
        or _sha256_file(expected_log) != result.get("log_sha256")
    ):
        return None
    return result


def _merge_junit(shards: Sequence[dict[str, Any]], destination: Path, *, suite_name: str) -> None:
    combined = ET.Element(
        "testsuite",
        {
            "name": f"pytest-{suite_name}",
            "tests": "0",
            "failures": "0",
            "errors": "0",
            "skipped": "0",
            "time": "0.000000",
            "timestamp": datetime.now(UTC).isoformat(),
            "hostname": platform.node(),
        },
    )
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    elapsed = 0.0
    for shard in shards:
        path = Path(shard["junit_path"])
        if not path.is_file():
            totals["tests"] += 1
            totals["errors"] += 1
            case = ET.SubElement(
                combined,
                "testcase",
                {"classname": "sip.test_matrix", "name": f"missing_junit::{shard['path']}", "time": "0"},
            )
            ET.SubElement(case, "error", {"message": "pytest shard did not produce JUnit evidence"}).text = str(
                shard["status"]
            )
            continue
        root = ET.parse(path).getroot()
        suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
        for suite in suites:
            for key in totals:
                totals[key] += int(float(suite.attrib.get(key, "0")))
            elapsed += float(suite.attrib.get("time", "0"))
            for case in suite.findall("testcase"):
                combined.append(case)
    for key, value in totals.items():
        combined.set(key, str(value))
    combined.set("time", f"{elapsed:.6f}")
    root = ET.Element("testsuites", {"name": "pytest tests"})
    root.append(combined)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def _write_merged_log(shards: Sequence[dict[str, Any]], destination: Path, *, suite_name: str) -> None:
    with destination.open("wb") as output:
        output.write(f"SIP sharded pytest suite: {suite_name}\n".encode("utf-8"))
        for shard in shards:
            output.write(
                (
                    f"\n=== {shard['path']} status={shard['status']} "
                    f"exit_code={shard['exit_code']} elapsed={shard['elapsed_seconds']}s ===\n"
                ).encode("utf-8")
            )
            log_path = Path(shard["log_path"])
            if log_path.is_file():
                output.write(log_path.read_bytes())


def _portable_shard_command(command: Sequence[str], *, junit_path: str) -> list[str]:
    portable: list[str] = []
    for index, argument in enumerate(command):
        if argument.startswith("--junitxml="):
            portable.append(f"--junitxml={junit_path}")
            continue
        candidate = Path(argument)
        if index == 0 and candidate.name.startswith("python"):
            portable.append("python")
            continue
        if candidate.is_absolute():
            try:
                portable.append(candidate.relative_to(ROOT).as_posix())
                continue
            except ValueError:
                pass
        portable.append(argument)
    return portable


def _finalize_shard_records(
    shards: Sequence[dict[str, Any]],
    *,
    final_shard_root: Path,
) -> list[dict[str, Any]]:
    """Publish portable shard records after the staging directory is committed.

    Staged result files intentionally contain absolute paths so an interrupted
    controller can validate and resume them before publication.  Those staging
    paths cease to exist after the atomic rename, so retained evidence must be
    rewritten to repository-relative final paths and re-serialized.
    """

    finalized: list[dict[str, Any]] = []
    for shard in shards:
        record = dict(shard)
        junit = final_shard_root / Path(str(shard["junit_path"])).name
        log = final_shard_root / Path(str(shard["log_path"])).name
        if not junit.is_file() or not log.is_file():
            raise FileNotFoundError(f"final shard artifacts missing for {shard['path']}")
        record["junit_path"] = junit.relative_to(ROOT).as_posix()
        record["log_path"] = log.relative_to(ROOT).as_posix()
        record["portable_command"] = _portable_shard_command(
            list(record.get("command", [])),
            junit_path=record["junit_path"],
        )
        record["junit_sha256"] = _sha256_file(junit)
        record["log_sha256"] = _sha256_file(log)
        result_path = final_shard_root / f"{record['name']}.result.json"
        result_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        finalized.append(record)
    return finalized


def _shard_manifest_payload(
    *,
    name: str,
    timeout_seconds: int,
    shard_jobs: int,
    files: Sequence[Path],
    shards: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": "sip.pytest-shard-manifest/v2",
        "suite": name,
        "timeout_seconds_per_shard": timeout_seconds,
        "shard_jobs": min(max(1, shard_jobs), len(files)),
        "shards": [
            {
                **{key: value for key, value in shard.items() if key not in {"junit_path", "log_path"}},
                "junit_path": Path(str(shard["junit_path"])).name,
                "log_path": Path(str(shard["log_path"])).name,
            }
            for shard in shards
        ],
    }


def _suite_unlocked(
    name: str,
    paths: Sequence[str],
    *,
    timeout_seconds: int,
    source_tree_root: str,
    shard_jobs: int,
    writer_token: str,
) -> SuiteResult:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    junit = REPORT_ROOT / f"{name}.xml"
    log = REPORT_ROOT / f"{name}.log"
    staged_junit, staged_log, staged_shard_root = _suite_staging_paths(name)
    final_shard_root = REPORT_ROOT / f"{name}-shards"
    staged_junit.parent.mkdir(parents=True, exist_ok=True)
    staged_junit.unlink(missing_ok=True)
    staged_log.unlink(missing_ok=True)
    staged_shard_root.mkdir(parents=True, exist_ok=True)
    _write_stage_owner(staged_shard_root, writer_token)
    files = _test_files(paths)
    if not files:
        raise ValueError(f"suite {name} has no test files")
    environment = dict(os.environ)
    environment.update(
        {
            "PYTHONPATH": f"{ROOT / 'src'}:{ROOT}",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "SIP_TEST_MATRIX_PARENT_PID": str(os.getpid()),
        }
    )
    conceptual_command = [
        sys.executable,
        str(ROOT / "tools" / "run_pytest_isolated.py"),
        "-q",
        *paths,
        "-p",
        "no:cacheprovider",
        "--sharded-by-test-file",
    ]
    started = time.perf_counter()
    print(
        f"[test-matrix] starting {name}: files={len(files)} shard_jobs={min(max(1, shard_jobs), len(files))}",
        flush=True,
    )
    shards: list[dict[str, Any]] = []
    pending: list[Path] = []
    for path in files:
        resumed = _load_staged_shard(
            path=path,
            staged_shard_root=staged_shard_root,
            source_tree_root=source_tree_root,
        )
        if resumed is None:
            shard_name = _safe_shard_name(path)
            for stale in staged_shard_root.glob(f"{shard_name}.*"):
                stale.unlink(missing_ok=True)
            pending.append(path)
        else:
            shards.append(resumed)
    if shards:
        print(f"[test-matrix] {name}: resuming {len(shards)} completed file shard(s)", flush=True)
    if pending:
        shard_worker_count = min(max(1, shard_jobs), len(pending))
        if shard_worker_count == 1:
            # Popen from nested ThreadPoolExecutor workers can deadlock during
            # interpreter startup on some libc/Python combinations.  A caller
            # that explicitly requests one shard worker is asking for the
            # deterministic serial path, so execute it in the suite controller
            # thread rather than creating another worker thread.
            for path in pending:
                shards.append(
                    _run_pytest_shard(
                        name=name,
                        path=path,
                        staged_shard_root=staged_shard_root,
                        timeout_seconds=timeout_seconds,
                        environment=environment,
                        source_tree_root=source_tree_root,
                        writer_token=writer_token,
                    )
                )
        else:
            with ThreadPoolExecutor(max_workers=shard_worker_count) as executor:
                futures = {
                    executor.submit(
                        _run_pytest_shard,
                        name=name,
                        path=path,
                        staged_shard_root=staged_shard_root,
                        timeout_seconds=timeout_seconds,
                        environment=environment,
                        source_tree_root=source_tree_root,
                        writer_token=writer_token,
                    ): path
                    for path in pending
                }
                for future in as_completed(futures):
                    shards.append(future.result())
    shards.sort(key=lambda item: item["path"])
    _assert_stage_owner(staged_shard_root, writer_token)
    _merge_junit(shards, staged_junit, suite_name=name)
    _write_merged_log(shards, staged_log, suite_name=name)
    _assert_stage_owner(staged_shard_root, writer_token)
    _stage_owner_path(staged_shard_root).unlink()
    shutil.rmtree(final_shard_root, ignore_errors=True)
    staged_shard_root.replace(final_shard_root)
    finalized_shards = _finalize_shard_records(shards, final_shard_root=final_shard_root)
    manifest = _shard_manifest_payload(
        name=name,
        timeout_seconds=timeout_seconds,
        shard_jobs=shard_jobs,
        files=files,
        shards=finalized_shards,
    )
    final_manifest = final_shard_root / "manifest.json"
    final_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    staged_junit.replace(junit)
    staged_log.replace(log)
    elapsed = time.perf_counter() - started
    tests, failures, errors, skipped = _junit_counts(junit)
    status = "passed" if all(shard["status"] == "passed" for shard in shards) else "failed"
    if any(shard["status"] == "timeout" for shard in shards):
        status = "timeout"
    exit_code = 0 if status == "passed" else (124 if status == "timeout" else 1)
    result = SuiteResult(
        name=name,
        command=conceptual_command,
        status=status,
        exit_code=exit_code,
        elapsed_seconds=round(elapsed, 6),
        tests=tests,
        failures=failures,
        errors=errors,
        skipped=skipped,
        junit_path=str(junit.relative_to(ROOT)),
        log_path=str(log.relative_to(ROOT)),
        input_root_sha256=_hash_path_set(paths),
        source_tree_root_sha256=source_tree_root,
        junit_sha256=_sha256_file(junit),
        log_sha256=_sha256_file(log),
        captured_at=datetime.now(UTC).isoformat(),
        shard_count=len(shards),
        shard_commands=[list(shard["portable_command"]) for shard in finalized_shards],
        shard_manifest_path=str(final_manifest.relative_to(ROOT)),
        shard_manifest_sha256=_sha256_file(final_manifest),
    )
    _write_sidecar(result)
    print(
        f"[test-matrix] {name}: {status}; files={len(shards)}; tests={tests}; failures={failures}; "
        f"errors={errors}; skipped={skipped}; elapsed={elapsed:.2f}s",
        flush=True,
    )
    return result

def _suite(
    name: str,
    paths: Sequence[str],
    *,
    timeout_seconds: int,
    source_tree_root: str,
    shard_jobs: int,
) -> SuiteResult:
    with _suite_lock(name) as lease:
        return _suite_unlocked(
            name,
            paths,
            timeout_seconds=timeout_seconds,
            source_tree_root=source_tree_root,
            shard_jobs=shard_jobs,
            writer_token=str(lease["token"]),
        )


def _load_sidecar(name: str, paths: Sequence[str], *, source_tree_root: str) -> tuple[SuiteResult | None, list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    sidecar = _sidecar_path(name)
    if not sidecar.is_file():
        return None, [{"code": "SUITE_EVIDENCE_MISSING", "suite": name, "detail": str(sidecar.relative_to(ROOT))}]
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        if payload.get("schema") != "sip.test-suite-evidence/v1":
            raise ValueError("unsupported schema")
        result = SuiteResult(**payload["result"])
    except Exception as exc:
        return None, [{"code": "SUITE_EVIDENCE_INVALID", "suite": name, "detail": str(exc)}]
    if result.name != name:
        findings.append({"code": "SUITE_NAME_MISMATCH", "suite": name, "detail": result.name})
    expected_input = _hash_path_set(paths)
    if result.input_root_sha256 != expected_input:
        findings.append({"code": "SUITE_INPUT_STALE", "suite": name, "detail": "test/configuration input root changed"})
    if result.source_tree_root_sha256 != source_tree_root:
        findings.append({"code": "SUITE_SOURCE_STALE", "suite": name, "detail": "executable source tree changed"})
    junit = ROOT / result.junit_path
    log = ROOT / result.log_path
    if _sha256_file(junit) != result.junit_sha256:
        findings.append({"code": "SUITE_JUNIT_HASH_MISMATCH", "suite": name, "detail": result.junit_path})
    if _sha256_file(log) != result.log_sha256:
        findings.append({"code": "SUITE_LOG_HASH_MISMATCH", "suite": name, "detail": result.log_path})
    if result.shard_manifest_path:
        shard_manifest = ROOT / result.shard_manifest_path
        if _sha256_file(shard_manifest) != result.shard_manifest_sha256:
            findings.append(
                {
                    "code": "SUITE_SHARD_MANIFEST_HASH_MISMATCH",
                    "suite": name,
                    "detail": result.shard_manifest_path,
                }
            )
    counts = _junit_counts(junit)
    if counts != (result.tests, result.failures, result.errors, result.skipped):
        findings.append({"code": "SUITE_JUNIT_COUNT_MISMATCH", "suite": name, "detail": str(counts)})
    if result.status == "passed" and (result.exit_code != 0 or result.failures or result.errors):
        findings.append({"code": "SUITE_PASS_CLAIM_INVALID", "suite": name, "detail": "nonzero result retained as passed"})
    return result, findings


def _active_suites() -> list[tuple[str, tuple[str, ...]]]:
    return [
        (name, paths)
        for name, paths in CONFIGURED_SUITES
        if any((ROOT / path).rglob("test_*.py") for path in paths)
    ]


def run_selected(
    selected_names: set[str], *, timeout_seconds: int = 180, jobs: int = 5, shard_jobs: int = 3
) -> dict[str, object]:
    suites = [(name, paths) for name, paths in _active_suites() if name in selected_names]
    unknown = sorted(selected_names - {name for name, _ in _active_suites()})
    if unknown:
        raise ValueError(f"unknown or empty test suites: {unknown}")
    source_tree_root = _source_tree_root()
    by_name: dict[str, SuiteResult] = {}
    suite_worker_count = max(1, min(jobs, len(suites)))
    if suite_worker_count == 1:
        # Keep the deterministic serial controller on the main thread.  This
        # avoids a second layer of thread-to-process spawning and gives the
        # parent-death watchdog an unambiguous controller PID.
        for name, paths in suites:
            result = _suite(
                name,
                paths,
                timeout_seconds=timeout_seconds,
                source_tree_root=source_tree_root,
                shard_jobs=shard_jobs,
            )
            by_name[result.name] = result
    else:
        with ThreadPoolExecutor(max_workers=suite_worker_count) as executor:
            futures = {
                executor.submit(
                    _suite,
                    name,
                    paths,
                    timeout_seconds=timeout_seconds,
                    source_tree_root=source_tree_root,
                    shard_jobs=shard_jobs,
                ): name
                for name, paths in suites
            }
            for future in as_completed(futures):
                result = future.result()
                by_name[result.name] = result
    results = [by_name[name] for name, _ in suites]
    status = "passed" if all(item.status == "passed" for item in results) else "failed"
    return {
        "schema": "sip.test-suite-run/v1",
        "source_tree_root_sha256": source_tree_root,
        "status": status,
        "results": [asdict(item) for item in results],
        "totals": {
            "tests": sum(item.tests for item in results),
            "failures": sum(item.failures for item in results),
            "errors": sum(item.errors for item in results),
            "skipped": sum(item.skipped for item in results),
        },
    }


def assemble() -> dict[str, object]:
    source_tree_root = _source_tree_root()
    findings: list[dict[str, str]] = []
    results: list[SuiteResult] = []
    for name, paths in _active_suites():
        result, suite_findings = _load_sidecar(name, paths, source_tree_root=source_tree_root)
        findings.extend(suite_findings)
        if result is not None:
            results.append(result)
    all_names = {name for name, _ in _active_suites()}
    retained_names = {result.name for result in results}
    if retained_names != all_names:
        findings.append(
            {
                "code": "SUITE_SET_INCOMPLETE",
                "suite": "matrix",
                "detail": f"missing={sorted(all_names - retained_names)} extra={sorted(retained_names - all_names)}",
            }
        )
    status = (
        "passed"
        if not findings
        and all(result.status == "passed" and result.exit_code == 0 and result.failures == 0 and result.errors == 0 for result in results)
        else "failed"
    )
    payload: dict[str, object] = {
        "schema": "sip.test-matrix/v2",
        "evidence": _environment_evidence(source_tree_root),
        "verification_policy": {
            "required_exit_code": 0,
            "maximum_failures": 0,
            "maximum_errors": 0,
            "manual_reviewer": None,
        },
        "status": status,
        "python": sys.version,
        "plugin_autoload_disabled": True,
        "suite_process_isolation": True,
        "test_file_process_isolation": True,
        "resumable_suite_evidence": True,
        "suite_parallelism": None,
        "findings": findings,
        "results": [asdict(result) for result in results],
        "totals": {
            "tests": sum(result.tests for result in results),
            "failures": sum(result.failures for result in results),
            "errors": sum(result.errors for result in results),
            "skipped": sum(result.skipped for result in results),
            "elapsed_seconds": round(sum(result.elapsed_seconds for result in results), 6),
        },
    }
    contract_findings = _matrix_contract_findings(payload)
    if contract_findings:
        payload["findings"] = [*findings, *contract_findings]
        payload["status"] = "failed"
    MATRIX_PATH.parent.mkdir(parents=True, exist_ok=True)
    MATRIX_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload



def _matrix_contract_findings(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Validate a retained matrix without making it an input to its own test run.

    This is deliberately a pure payload check.  ``assemble`` separately validates
    every sidecar against current source, declared generated inputs, JUnit, logs,
    and shard manifests before it constructs the payload.
    """

    findings: list[dict[str, str]] = []

    def add(code: str, detail: str) -> None:
        findings.append({"code": code, "suite": "matrix", "detail": detail})

    if payload.get("schema") != "sip.test-matrix/v2":
        add("MATRIX_SCHEMA_INVALID", str(payload.get("schema")))
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        add("MATRIX_EVIDENCE_INVALID", "evidence must be an object")
    else:
        for field in ("git_commit", "source_tree_root_sha256", "dependency_snapshot_sha256"):
            value = evidence.get(field)
            expected_length = 40 if field == "git_commit" else 64
            if not isinstance(value, str) or len(value) != expected_length:
                add("MATRIX_EVIDENCE_FIELD_INVALID", field)
        for field in ("python_version", "platform"):
            if not evidence.get(field):
                add("MATRIX_EVIDENCE_FIELD_INVALID", field)
    expected_policy = {
        "required_exit_code": 0,
        "maximum_failures": 0,
        "maximum_errors": 0,
        "manual_reviewer": None,
    }
    if payload.get("verification_policy") != expected_policy:
        add("MATRIX_VERIFICATION_POLICY_INVALID", "verification policy differs from fail-closed baseline")
    results = payload.get("results")
    if not isinstance(results, list):
        add("MATRIX_RESULTS_INVALID", "results must be an array")
        results = []
    for item in results:
        if not isinstance(item, dict):
            add("MATRIX_RESULT_INVALID", "suite result must be an object")
            continue
        name = str(item.get("name", "unknown"))
        for field in ("input_root_sha256", "source_tree_root_sha256", "junit_sha256", "log_sha256"):
            value = item.get(field)
            if not isinstance(value, str) or len(value) != 64:
                findings.append({"code": "MATRIX_RESULT_HASH_INVALID", "suite": name, "detail": field})
        passed = (
            item.get("status") == "passed"
            and item.get("exit_code") == 0
            and item.get("failures") == 0
            and item.get("errors") == 0
        )
        if item.get("status") == "passed" and not passed:
            findings.append({"code": "MATRIX_RESULT_PASS_CLAIM_INVALID", "suite": name, "detail": "nonzero result retained as passed"})
        if item.get("status") != "passed" and item.get("exit_code") == 0:
            findings.append({"code": "MATRIX_RESULT_FAILURE_CLAIM_INVALID", "suite": name, "detail": "failed result retained with zero exit code"})
    retained_findings = payload.get("findings")
    if not isinstance(retained_findings, list):
        add("MATRIX_FINDINGS_INVALID", "findings must be an array")
        retained_findings = []
    suites_passed = bool(results) and all(
        isinstance(item, dict)
        and item.get("status") == "passed"
        and item.get("exit_code") == 0
        and item.get("failures") == 0
        and item.get("errors") == 0
        for item in results
    )
    expected_status = "passed" if suites_passed and not retained_findings else "failed"
    if payload.get("status") != expected_status:
        add("MATRIX_STATUS_INCONSISTENT", f"expected {expected_status}, found {payload.get('status')}")
    return findings

def run(*, timeout_seconds: int = 180, jobs: int = 5, shard_jobs: int = 3) -> dict[str, object]:
    selected = {name for name, _ in _active_suites()}
    run_result = run_selected(
        selected,
        timeout_seconds=timeout_seconds,
        jobs=jobs,
        shard_jobs=shard_jobs,
    )
    if run_result["status"] != "passed":
        # Still assemble all retained attempts so the failure is auditable.
        return assemble()
    return assemble()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SIP test categories in isolated, resumable pytest processes.")
    parser.add_argument("--timeout", type=int, default=180, help="per-suite timeout in seconds")
    parser.add_argument("--jobs", type=int, default=5, help="number of selected suites to execute concurrently")
    parser.add_argument(
        "--shard-jobs",
        type=int,
        default=3,
        help="number of test-file processes to execute concurrently within each suite",
    )
    parser.add_argument(
        "--suite",
        action="append",
        choices=[name for name, _ in CONFIGURED_SUITES],
        help="run only this suite and retain a source-bound sidecar; repeatable",
    )
    parser.add_argument("--assemble", action="store_true", help="assemble only current source-bound suite sidecars")
    args = parser.parse_args()
    if args.assemble and args.suite:
        parser.error("--assemble cannot be combined with --suite")
    with _exclusive_matrix_controller_lock():
        if args.assemble:
            result = assemble()
        elif args.suite:
            result = run_selected(
                set(args.suite),
                timeout_seconds=args.timeout,
                jobs=args.jobs,
                shard_jobs=args.shard_jobs,
            )
        else:
            result = run(
                timeout_seconds=args.timeout,
                jobs=args.jobs,
                shard_jobs=args.shard_jobs,
            )
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
