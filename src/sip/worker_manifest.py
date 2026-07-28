from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .canonical import canonical_sha256
from .errors import ValidationError


class WorkerResourceLimits(BaseModel):
    """Declared execution envelope enforced by runtime and deployment controls."""

    model_config = ConfigDict(extra="forbid")

    max_wall_seconds: int = Field(default=900, ge=1, le=86_400)
    max_cpu_seconds: int = Field(default=900, ge=1, le=86_400)
    max_memory_bytes: int = Field(default=2_147_483_648, ge=16_777_216)
    max_input_bytes: int = Field(default=1_073_741_824, ge=1)
    max_output_bytes: int = Field(default=268_435_456, ge=1)
    gpu_count: int = Field(default=0, ge=0, le=16)


class WorkerManifest(BaseModel):
    """Immutable, capability-scoped worker descriptor.

    The digest is calculated over every field except ``manifest_sha256``. File
    hashes bind the descriptor to the exact executable entry point and shared
    runtime source used for the release.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_id: Literal["sip.worker-manifest/v1"] = Field(default="sip.worker-manifest/v1", alias="schema")
    name: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    version: str = Field(min_length=1)
    entrypoint: str = Field(min_length=1)
    entrypoint_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    runtime_module: str = "src/sip/worker_runtime.py"
    runtime_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    protocol_module: str = "src/sip/worker_protocol.py"
    protocol_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    sandbox_module: str = "src/sip/worker_sandbox.py"
    sandbox_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    workload_identity: str = Field(min_length=1)
    capabilities: list[str] = Field(min_length=1)
    input_contract: str = "sip.worker-input/v1"
    output_contract: str = "sip.worker-result/v1"
    compatibility: str = ">=1.1.0,<2.0.0"
    governance: str = Field(min_length=1)
    durable: Literal[True] = True
    idempotent: Literal[True] = True
    cancellable: Literal[True] = True
    checkpointed: Literal[True] = True
    audited: Literal[True] = True
    least_privilege: Literal[True] = True
    shell_access: Literal[False] = False
    network_access: Literal[False] = False
    publication_permission: Literal[False] = False
    output_mode: Literal["quarantine_candidate"] = "quarantine_candidate"
    filesystem_read_scopes: list[str] = Field(default_factory=lambda: ["/var/lib/sip/objects"])
    filesystem_write_scopes: list[str] = Field(default_factory=lambda: ["/var/lib/sip/runtime/staging"])
    resource_limits: WorkerResourceLimits = Field(default_factory=WorkerResourceLimits)
    requirement_ids: list[str] = Field(default_factory=list)
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("capabilities")
    @classmethod
    def unique_capabilities(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("worker capabilities must be unique")
        if value != sorted(value):
            raise ValueError("worker capabilities must be sorted")
        return value

    @field_validator("filesystem_read_scopes", "filesystem_write_scopes")
    @classmethod
    def absolute_unique_scopes(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("worker filesystem scopes may not be empty")
        normalized = [str(Path(item)) for item in value]
        if any(not Path(item).is_absolute() for item in normalized):
            raise ValueError("worker filesystem scopes must be absolute paths")
        if len(normalized) != len(set(normalized)):
            raise ValueError("worker filesystem scopes must be unique")
        return sorted(normalized)

    @model_validator(mode="after")
    def verify_digest(self) -> "WorkerManifest":
        if self.manifest_sha256 != self.calculated_digest():
            raise ValueError("worker manifest digest does not match canonical contents")
        return self

    def calculated_digest(self) -> str:
        payload = self.model_dump(mode="json", by_alias=True, exclude={"manifest_sha256"})
        return canonical_sha256(payload)

    def verify_files(self, repository_root: Path) -> None:
        entrypoint = _resolve_repository_path(repository_root, self.entrypoint)
        runtime = _resolve_repository_path(repository_root, self.runtime_module)
        protocol = _resolve_repository_path(repository_root, self.protocol_module)
        sandbox = _resolve_repository_path(repository_root, self.sandbox_module)
        for path, expected, label in (
            (entrypoint, self.entrypoint_sha256, "entrypoint"),
            (runtime, self.runtime_sha256, "runtime"),
            (protocol, self.protocol_sha256, "protocol"),
            (sandbox, self.sandbox_sha256, "sandbox"),
        ):
            if not path.is_file():
                raise ValidationError("WORKER_MANIFEST_FILE_MISSING", f"worker {label} is missing", {"path": str(path)})
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected:
                raise ValidationError(
                    "WORKER_MANIFEST_FILE_HASH_MISMATCH",
                    f"worker {label} hash does not match immutable manifest",
                    {"path": str(path), "expected": expected, "actual": actual},
                )


def load_worker_manifest(path: Path, *, repository_root: Path | None = None, verify_files: bool = True) -> WorkerManifest:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        manifest = WorkerManifest.model_validate(raw)
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError("WORKER_MANIFEST_INVALID", "worker manifest is invalid", {"path": str(path)}) from exc
    if verify_files:
        manifest.verify_files(repository_root or _infer_repository_root(path))
    return manifest


def create_manifest_payload(
    *,
    repository_root: Path,
    name: str,
    version: str,
    entrypoint: str,
    capabilities: list[str],
    governance: str,
    resource_limits: WorkerResourceLimits | None = None,
    requirement_ids: list[str] | None = None,
    filesystem_read_scopes: list[str] | None = None,
    filesystem_write_scopes: list[str] | None = None,
) -> dict[str, object]:
    entrypoint_path = _resolve_repository_path(repository_root, entrypoint)
    runtime_path = repository_root / "src/sip/worker_runtime.py"
    protocol_path = repository_root / "src/sip/worker_protocol.py"
    sandbox_path = repository_root / "src/sip/worker_sandbox.py"
    payload: dict[str, object] = {
        "schema": "sip.worker-manifest/v1",
        "name": name,
        "version": version,
        "entrypoint": entrypoint,
        "entrypoint_sha256": hashlib.sha256(entrypoint_path.read_bytes()).hexdigest(),
        "runtime_module": "src/sip/worker_runtime.py",
        "runtime_sha256": hashlib.sha256(runtime_path.read_bytes()).hexdigest(),
        "protocol_module": "src/sip/worker_protocol.py",
        "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        "sandbox_module": "src/sip/worker_sandbox.py",
        "sandbox_sha256": hashlib.sha256(sandbox_path.read_bytes()).hexdigest(),
        "workload_identity": f"sip-worker:{name}",
        "capabilities": sorted(capabilities),
        "input_contract": "sip.worker-input/v1",
        "output_contract": "sip.worker-result/v1",
        "compatibility": ">=1.1.0,<2.0.0",
        "governance": governance,
        "durable": True,
        "idempotent": True,
        "cancellable": True,
        "checkpointed": True,
        "audited": True,
        "least_privilege": True,
        "shell_access": False,
        "network_access": False,
        "publication_permission": False,
        "output_mode": "quarantine_candidate",
        "filesystem_read_scopes": sorted(filesystem_read_scopes or ["/var/lib/sip/objects"]),
        "filesystem_write_scopes": sorted(filesystem_write_scopes or ["/var/lib/sip/runtime/staging"]),
        "resource_limits": (resource_limits or WorkerResourceLimits()).model_dump(mode="json"),
        "requirement_ids": sorted(requirement_ids or ["PLTGRPC-001", "PLTGRPC-006", "PLTSDK-003", "HYBAPI-003", "HYBAPI-004"]),
    }
    payload["manifest_sha256"] = canonical_sha256(payload)
    # Validate before writing so the generator cannot emit a malformed descriptor.
    WorkerManifest.model_validate(payload)
    return payload


def _resolve_repository_path(root: Path, relative: str) -> Path:
    root = root.resolve()
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValidationError("WORKER_MANIFEST_PATH_ESCAPE", "worker manifest path escapes repository root", {"path": relative})
    return candidate


def _infer_repository_root(path: Path) -> Path:
    resolved = path.resolve()
    for parent in [resolved.parent, *resolved.parents]:
        if (parent / "pyproject.toml").is_file() and (parent / "workers").is_dir():
            return parent
    raise ValidationError("WORKER_REPOSITORY_ROOT_UNKNOWN", "could not locate worker repository root", {"path": str(path)})
