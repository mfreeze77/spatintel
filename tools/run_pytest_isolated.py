#!/usr/bin/env python3
"""Run pytest and terminate the isolated evidence process deterministically.

Some optional libraries register interpreter-shutdown hooks or non-daemon helper
threads after their tests have already completed.  A normal Python shutdown can
therefore hang after pytest has written its terminal summary and JUnit report.
The SIP test matrix runs every category in its own process, so after
``pytest.main`` returns we flush the two standard streams and use ``os._exit``
to preserve pytest's exact status without executing unrelated process-global
shutdown hooks.
"""
from __future__ import annotations

import os
import signal
import sys
import threading
import time
import traceback

import pytest


def _start_parent_watchdog() -> None:
    """Terminate the isolated process group if its matrix controller dies."""

    raw_parent = os.environ.get("SIP_TEST_MATRIX_PARENT_PID")
    if not raw_parent:
        return
    try:
        expected_parent = int(raw_parent)
    except ValueError:
        os._exit(125)

    def monitor() -> None:
        while True:
            if os.getppid() != expected_parent:
                # Matrix children are started in their own process sessions.
                # Kill that complete group when possible so test-launched helper
                # processes cannot outlive the evidence controller.
                try:
                    if hasattr(os, "killpg") and os.getpgrp() == os.getpid():
                        os.killpg(os.getpgrp(), signal.SIGTERM)
                except (OSError, ProcessLookupError):
                    pass
                os._exit(125)
            time.sleep(0.1)

    threading.Thread(target=monitor, name="sip-matrix-parent-watchdog", daemon=True).start()


def main(argv: list[str] | None = None) -> int:
    try:
        return int(pytest.main(list(sys.argv[1:] if argv is None else argv)))
    except BaseException:  # pragma: no cover - catastrophic runner path
        traceback.print_exc()
        return 3


def _flush_standard_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:
            pass


if __name__ == "__main__":
    _start_parent_watchdog()
    status = main()
    _flush_standard_streams()
    os._exit(status)
