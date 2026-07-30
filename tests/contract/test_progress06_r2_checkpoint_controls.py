from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path

from tools.verify_progress06_r2_checkpoint import (
    EXPECTED_BASE_COMMIT,
    EXPECTED_BASE_OUTER_SHA256,
    EXPECTED_BASE_ZIP_SHA256,
    EXPECTED_BASE_SOURCE_ROOT,
)

ROOT = Path(__file__).resolve().parents[2]


def test_progress06_r2_predecessor_record_identifies_exact_accepted_r1_checkpoint() -> None:
    """CONTROL: Progress 06-R2 provenance is bound to the accepted R1 commit and packages."""

    predecessor = json.loads((ROOT / "PREDECESSOR_CHECKPOINT.json").read_text(encoding="utf-8"))
    record = predecessor["accepted_progress_06_r1_checkpoint"]
    assert record["checkpoint_id"] == "sip-v1.1.0-progress-06-r1"
    assert record["commit"] == EXPECTED_BASE_COMMIT
    assert record["project_zip_sha256"] == EXPECTED_BASE_ZIP_SHA256
    assert record["outer_delivery_zip_sha256"] == EXPECTED_BASE_OUTER_SHA256
    assert record["source_tree_root_sha256"] == EXPECTED_BASE_SOURCE_ROOT


def test_progress06_r2_acceptance_cli_rejects_concurrent_evidence_writers(tmp_path: Path) -> None:
    """CONTROL: concurrent checkpoint acceptance cannot overwrite immutable gate snapshots."""

    lock_path = ROOT / "build/locks/progress-06-r2-acceptance.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        acquired_here = False
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired_here = True
        except BlockingIOError:
            # The outer clean-source acceptance runner owns the lock while this
            # test executes in the complete matrix. That state is equally valid
            # for proving that a second process is rejected.
            pass
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from tools.run_progress06_r2_checkpoint_acceptance import _exclusive_acceptance_lock; "
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
