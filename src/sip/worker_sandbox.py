from __future__ import annotations

import asyncio
import contextlib
import os
import resource
import signal
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator
from unittest.mock import patch

from .canonical import canonical_json
from .errors import AuthorizationError, ValidationError
from .worker_manifest import WorkerResourceLimits


class WorkerDeadlineExceeded(ValidationError):
    def __init__(self) -> None:
        super().__init__("WORKER_DEADLINE_EXCEEDED", "worker exceeded its declared wall-time limit")


@dataclass(frozen=True)
class ResourceUsage:
    elapsed_wall_seconds: float
    elapsed_cpu_seconds: float
    maximum_rss_bytes: int


class ExecutionSandbox:
    """Best-effort in-process guard backed by container and network policy controls.

    Production isolation is layered: this guard blocks common Python network and shell
    APIs during provider computation, while containers enforce seccomp, dropped Linux
    capabilities, read-only filesystems, cgroup budgets, and restricted egress. Trusted
    control-plane callbacks temporarily leave the in-process guard so heartbeats and
    checkpoints can be delivered.
    """

    _guard_lock = threading.RLock()

    def __init__(self, limits: WorkerResourceLimits) -> None:
        self.limits = limits
        self._patches: list[Any] = []
        self._active = False
        self._started_wall = 0.0
        self._started_cpu = 0.0
        self._previous_signal_handler: Any = None
        self._timer_enabled = False
        self._lock_acquired = False

    def __enter__(self) -> "ExecutionSandbox":
        self._guard_lock.acquire()
        self._lock_acquired = True
        try:
            self._started_wall = time.monotonic()
            self._started_cpu = time.process_time()
            self._activate_guards()
            self._activate_deadline()
        except Exception:
            self._lock_acquired = False
            self._guard_lock.release()
            raise
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        try:
            self._deactivate_deadline()
            self._deactivate_guards()
        finally:
            if self._lock_acquired:
                self._lock_acquired = False
                self._guard_lock.release()

    @contextlib.contextmanager
    def trusted_control_io(self) -> Iterator[None]:
        """Allow only the runtime's narrow control gateway to perform transport I/O."""
        was_active = self._active
        if was_active:
            self._deactivate_guards()
        try:
            yield
        finally:
            if was_active:
                self._activate_guards()

    def usage(self) -> ResourceUsage:
        maximum_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux reports KiB; macOS reports bytes. The repository's reference and
        # production Linux profiles use KiB. Avoid understating on either platform.
        maximum_rss_bytes = int(maximum_rss * 1024 if maximum_rss < 10**12 else maximum_rss)
        return ResourceUsage(
            elapsed_wall_seconds=max(0.0, time.monotonic() - self._started_wall),
            elapsed_cpu_seconds=max(0.0, time.process_time() - self._started_cpu),
            maximum_rss_bytes=maximum_rss_bytes,
        )

    def validate_output(self, output: dict[str, Any]) -> None:
        byte_count = len(canonical_json(output))
        if byte_count > self.limits.max_output_bytes:
            raise ValidationError(
                "WORKER_OUTPUT_LIMIT_EXCEEDED",
                "worker output exceeds its declared staging limit",
                {"actual_bytes": byte_count, "maximum_bytes": self.limits.max_output_bytes},
            )
        usage = self.usage()
        if usage.elapsed_cpu_seconds > self.limits.max_cpu_seconds:
            raise ValidationError(
                "WORKER_CPU_LIMIT_EXCEEDED",
                "worker exceeded its declared CPU-time limit",
                {"actual_seconds": usage.elapsed_cpu_seconds, "maximum_seconds": self.limits.max_cpu_seconds},
            )
        if usage.maximum_rss_bytes > self.limits.max_memory_bytes:
            raise ValidationError(
                "WORKER_MEMORY_LIMIT_EXCEEDED",
                "worker exceeded its declared memory envelope",
                {"actual_bytes": usage.maximum_rss_bytes, "maximum_bytes": self.limits.max_memory_bytes},
            )

    def validate_input(
        self,
        input_manifest: dict[str, Any],
        *,
        filesystem_read_scopes: list[str],
        filesystem_write_scopes: list[str],
    ) -> int:
        byte_count = len(canonical_json(input_manifest))
        if byte_count > self.limits.max_input_bytes:
            raise ValidationError(
                "WORKER_INPUT_LIMIT_EXCEEDED",
                "worker input manifest exceeds its declared limit",
                {"actual_bytes": byte_count, "maximum_bytes": self.limits.max_input_bytes},
            )
        for key, value in _walk_values(input_manifest):
            if key.endswith("_path") and isinstance(value, str):
                mode = "write" if _is_write_path_key(key) else "read"
                scopes = filesystem_write_scopes if mode == "write" else filesystem_read_scopes
                _validate_scoped_path(value, scopes=scopes, mode=mode)
            elif key.endswith("_paths") and isinstance(value, list):
                mode = "write" if _is_write_path_key(key) else "read"
                scopes = filesystem_write_scopes if mode == "write" else filesystem_read_scopes
                for item in value:
                    if not isinstance(item, str):
                        raise ValidationError(
                            "WORKER_PATH_INVALID",
                            "declared path list contains a non-string value",
                            {"field": key},
                        )
                    _validate_scoped_path(item, scopes=scopes, mode=mode)
        return byte_count

    def _activate_guards(self) -> None:
        if self._active:
            return

        def deny_network(*_: Any, **__: Any) -> Any:
            raise AuthorizationError("WORKER_NETWORK_DENIED", "worker capability does not permit network access")

        def deny_shell(*_: Any, **__: Any) -> Any:
            raise AuthorizationError("WORKER_SHELL_DENIED", "worker capability does not permit shell or subprocess access")

        targets: list[tuple[str, Callable[..., Any]]] = [
            ("socket.socket", deny_network),
            ("socket.create_connection", deny_network),
            ("socket.getaddrinfo", deny_network),
            ("socket.gethostbyname", deny_network),
            ("socket.gethostbyname_ex", deny_network),
            ("subprocess.Popen", deny_shell),
            ("subprocess.run", deny_shell),
            ("subprocess.call", deny_shell),
            ("subprocess.check_call", deny_shell),
            ("subprocess.check_output", deny_shell),
            ("os.system", deny_shell),
            ("os.popen", deny_shell),
            ("asyncio.create_subprocess_exec", deny_shell),
            ("asyncio.create_subprocess_shell", deny_shell),
        ]
        self._patches = [patch(target, replacement) for target, replacement in targets]
        for active_patch in self._patches:
            active_patch.start()
        self._active = True

    def _deactivate_guards(self) -> None:
        if not self._active:
            return
        for active_patch in reversed(self._patches):
            active_patch.stop()
        self._patches.clear()
        self._active = False

    def _activate_deadline(self) -> None:
        if threading.current_thread() is not threading.main_thread() or not hasattr(signal, "setitimer"):
            return

        def deadline_handler(signum: int, frame: Any) -> None:
            del signum, frame
            raise WorkerDeadlineExceeded()

        self._previous_signal_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, deadline_handler)
        signal.setitimer(signal.ITIMER_REAL, float(self.limits.max_wall_seconds))
        self._timer_enabled = True

    def _deactivate_deadline(self) -> None:
        if not self._timer_enabled:
            return
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, self._previous_signal_handler)
        self._timer_enabled = False


def _walk_values(value: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            name = str(key)
            yield name, child
            yield from _walk_values(child, f"{prefix}.{name}" if prefix else name)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_values(child, prefix)


def _is_write_path_key(key: str) -> bool:
    return key.startswith(("destination_", "output_", "staging_", "scratch_", "temporary_"))


def _validate_scoped_path(value: str, *, scopes: list[str], mode: str) -> None:
    path = Path(value)
    if not path.is_absolute():
        raise AuthorizationError(
            "WORKER_FILESYSTEM_PATH_RELATIVE",
            "worker filesystem paths must be absolute",
            {"path": value, "mode": mode},
        )
    # Resolve existing ancestors so a symlink cannot escape the declared mount.
    resolved = path.resolve(strict=False)
    allowed = False
    normalized_scopes: list[str] = []
    for raw_scope in scopes:
        scope = Path(raw_scope).resolve(strict=False)
        normalized_scopes.append(str(scope))
        if resolved == scope or scope in resolved.parents:
            allowed = True
            break
    if not allowed:
        raise AuthorizationError(
            "WORKER_FILESYSTEM_SCOPE_DENIED",
            "worker path is outside its declared filesystem scope",
            {"path": str(resolved), "mode": mode, "allowed_scopes": normalized_scopes},
        )
