from __future__ import annotations

import socket
import subprocess

import pytest

from sip.errors import AuthorizationError, ValidationError
from sip.worker_manifest import WorkerResourceLimits
from sip.worker_sandbox import ExecutionSandbox


@pytest.mark.security
def test_worker_sandbox_denies_network_and_shell_but_allows_trusted_control_io() -> None:
    """REQ: PLTSDK-003 and TSTLAY-004."""
    sandbox = ExecutionSandbox(WorkerResourceLimits(max_memory_bytes=4_294_967_296))
    with sandbox:
        with pytest.raises(AuthorizationError) as network:
            socket.socket()
        assert network.value.code == "WORKER_NETWORK_DENIED"
        with pytest.raises(AuthorizationError) as shell:
            subprocess.run(["true"], check=False)
        assert shell.value.code == "WORKER_SHELL_DENIED"
        with sandbox.trusted_control_io():
            handle = socket.socket()
            handle.close()


@pytest.mark.security
def test_worker_sandbox_enforces_output_staging_limit() -> None:
    sandbox = ExecutionSandbox(
        WorkerResourceLimits(max_output_bytes=32, max_memory_bytes=4_294_967_296)
    )
    with sandbox:
        with pytest.raises(ValidationError) as exc:
            sandbox.validate_output({"payload": "x" * 128})
    assert exc.value.code == "WORKER_OUTPUT_LIMIT_EXCEEDED"
