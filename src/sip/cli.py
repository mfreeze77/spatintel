from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .capture import CapturePackage
from .spec_lint import run as run_spec_lint

ROOT = Path(__file__).resolve().parents[2]


def _version(command: list[str]) -> str | None:
    if shutil.which(command[0]) is None:
        return None
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=10)
        return (result.stdout or result.stderr).strip().splitlines()[0]
    except Exception:
        return "present-but-version-query-failed"



def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _nvidia_report() -> dict[str, Any]:
    if shutil.which("nvidia-smi") is None:
        return {"available": False, "devices": [], "error": "nvidia-smi not installed"}
    command = [
        "nvidia-smi",
        "--query-gpu=name,driver_version,memory.total,compute_cap",
        "--format=csv,noheader,nounits",
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=15)
    except Exception as exc:
        return {"available": False, "devices": [], "error": f"nvidia-smi probe failed: {type(exc).__name__}"}
    devices = []
    for line in result.stdout.splitlines():
        fields = [part.strip() for part in line.split(",")]
        if len(fields) >= 4:
            devices.append({"name": fields[0], "driver_version": fields[1], "memory_mib": fields[2], "compute_capability": fields[3]})
    return {"available": bool(devices), "devices": devices, "error": None if devices else "no CUDA device reported"}


def _probe_torch_cuda() -> dict[str, Any]:
    try:
        import torch
    except Exception as exc:
        return {"installed": False, "available": False, "error": f"torch import failed: {type(exc).__name__}"}
    report: dict[str, Any] = {
        "installed": True,
        "version": str(torch.__version__),
        "compiled_cuda": str(torch.version.cuda) if torch.version.cuda else None,
        "available": bool(torch.cuda.is_available()),
        "device_count": int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,
        "error": None,
    }
    if not report["available"]:
        report["error"] = "torch CUDA runtime is unavailable"
        return report
    try:
        value = torch.tensor([1.0], device="cuda") * 2
        torch.cuda.synchronize()
        report["smoke_result"] = float(value.cpu().item())
    except Exception as exc:
        report["available"] = False
        report["error"] = f"CUDA smoke operation failed: {type(exc).__name__}"
    return report


def _approved_local_checkpoints(manifest_root: Path | None = None) -> dict[str, Any]:
    root = manifest_root or ROOT / "third_party/models"
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for manifest_path in sorted(root.glob("*.json")) if root.is_dir() else []:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            rejected.append({"manifest": str(manifest_path), "reason": "invalid_json"})
            continue
        if manifest.get("approval_state") != "approved":
            rejected.append({"manifest": str(manifest_path), "model_id": manifest.get("model_id"), "reason": "not_approved"})
            continue
        checkpoint_hash = str(manifest.get("checkpoint_hash", "")).lower()
        checkpoint_path_value = manifest.get("local_path")
        if not checkpoint_path_value or not __import__("re").fullmatch(r"[0-9a-f]{64}", checkpoint_hash):
            rejected.append({"manifest": str(manifest_path), "model_id": manifest.get("model_id"), "reason": "approved_manifest_missing_local_path_or_hash"})
            continue
        checkpoint_path = Path(str(checkpoint_path_value)).expanduser()
        if not checkpoint_path.is_absolute():
            checkpoint_path = (ROOT / checkpoint_path).resolve()
        if not checkpoint_path.is_file():
            rejected.append({"manifest": str(manifest_path), "model_id": manifest.get("model_id"), "reason": "checkpoint_missing"})
            continue
        actual = _sha256(checkpoint_path)
        if actual != checkpoint_hash:
            rejected.append({"manifest": str(manifest_path), "model_id": manifest.get("model_id"), "reason": "checkpoint_hash_mismatch", "actual_sha256": actual})
            continue
        accepted.append({"manifest": str(manifest_path), "model_id": manifest.get("model_id"), "checkpoint_path": str(checkpoint_path), "checkpoint_sha256": actual})
    return {"approved": accepted, "rejected": rejected, "implicit_downloads_allowed": False}


def gpu_doctor(manifest_root: Path | None = None) -> dict[str, Any]:
    nvidia = _nvidia_report()
    torch = _probe_torch_cuda()
    checkpoints = _approved_local_checkpoints(manifest_root)
    runtime_ready = bool(nvidia.get("available")) and bool(torch.get("available"))
    checkpoint_ready = bool(checkpoints["approved"])
    if runtime_ready and checkpoint_ready:
        status = "ready"
        reasons: list[str] = []
    elif not runtime_ready:
        status = "unavailable"
        reasons = [str(nvidia.get("error") or torch.get("error") or "GPU runtime unavailable")]
    else:
        status = "blocked"
        reasons = ["no approved, content-addressed local checkpoint is available"]
    return {
        "status": status,
        "runtime_compatible": runtime_ready,
        "nvidia": nvidia,
        "torch": torch,
        "checkpoints": checkpoints,
        "reasons": reasons,
        "production_execution_allowed": status == "ready",
    }

def doctor() -> dict[str, Any]:
    tools = {
        "python": platform.python_version(),
        "git": _version(["git", "--version"]),
        "node": _version(["node", "--version"]),
        "npm": _version(["npm", "--version"]),
        "pnpm": _version(["pnpm", "--version"]),
        "swift": _version(["swift", "--version"]),
        "docker": _version(["docker", "--version"]),
        "terraform": _version(["terraform", "version"]),
        "kubectl": _version(["kubectl", "version", "--client"]),
        "just": _version(["just", "--version"]),
    }
    required_local = ["python", "git"]
    return {
        "status": "healthy" if all(tools[name] for name in required_local) else "missing-required-tool",
        "platform": platform.platform(),
        "tools": tools,
        "profiles": {
            "cpu_reference": tools["python"] is not None,
            "web": tools["node"] is not None and tools["npm"] is not None,
            "swift_fixture": tools["swift"] is not None,
            "containers": tools["docker"] is not None,
            "terraform": tools["terraform"] is not None,
            "kubernetes": tools["kubectl"] is not None,
        },
        "gpu": gpu_doctor(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="sip", description="Spatial Intelligence Platform developer and operator CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    spec = sub.add_parser("spec-check")
    spec.add_argument("--release", action="store_true")
    capture = sub.add_parser("validate-capture")
    capture.add_argument("path", type=Path)
    args = parser.parse_args()

    if args.command == "doctor":
        result = doctor()
    elif args.command == "spec-check":
        result = run_spec_lint(release=args.release)
    elif args.command == "validate-capture":
        result = CapturePackage.validate(args.path)
    else:
        parser.error("unknown command")
        return
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if result.get("status") == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
