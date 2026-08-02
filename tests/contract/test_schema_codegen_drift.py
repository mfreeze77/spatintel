from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


@pytest.mark.contract
def test_schema_codegen_check_has_no_drift() -> None:
    """Run code generation in its own process-bound shard.

    Keeping this check separate prevents a previously created application
    context from leaking threads or file descriptors into the generator
    subprocess while retaining the exact command used by CI and operators.
    """
    result = subprocess.run(
        [sys.executable, "tools/schema_codegen/generate.py", "--root", ".", "--check"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
