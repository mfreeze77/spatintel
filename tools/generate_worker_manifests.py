#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sip.worker_manifest import WorkerResourceLimits, create_manifest_payload

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.1.0"

# Limits are the application contract. Container cgroups must be equal or tighter.
LIMITS: dict[str, WorkerResourceLimits] = {
    "lingbot-adapter": WorkerResourceLimits(
        max_wall_seconds=3600,
        max_cpu_seconds=3600,
        max_memory_bytes=34_359_738_368,
        max_input_bytes=536_870_912_000,
        max_output_bytes=536_870_912_000,
        gpu_count=1,
    ),
    "fusion-tsdf": WorkerResourceLimits(max_wall_seconds=1800, max_cpu_seconds=1800, max_memory_bytes=8_589_934_592),
    "splat": WorkerResourceLimits(max_wall_seconds=3600, max_cpu_seconds=3600, max_memory_bytes=8_589_934_592, gpu_count=0),
}


def _render(directory: Path) -> tuple[str, str]:
    legacy_path = directory / "worker.json"
    if not legacy_path.is_file():
        raise SystemExit(f"missing worker.json source descriptor: {legacy_path}")
    legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
    name = str(legacy["name"])
    payload = create_manifest_payload(
        repository_root=ROOT,
        name=name,
        version=VERSION,
        entrypoint=f"workers/{name}/main.py",
        capabilities=list(legacy["capabilities"]),
        governance=str(legacy["governance"]),
        resource_limits=LIMITS.get(name),
        requirement_ids=[
            "PLTGRPC-001",
            "PLTGRPC-002",
            "PLTGRPC-004",
            "PLTGRPC-005",
            "PLTGRPC-006",
            "PLTSDK-003",
            "HYBAPI-003",
            "HYBAPI-004",
            "HYBAPI-009",
            "HYBAPI-010",
            "TSTLAY-004",
        ],
    )
    manifest_text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    # worker.json is a human-readable index only. The signed/hash-bound manifest
    # remains the execution authority.
    legacy["execution_manifest"] = f"workers/{name}/worker-manifest.json"
    legacy["manifest_sha256"] = payload["manifest_sha256"]
    legacy_text = json.dumps(legacy, indent=2, sort_keys=True) + "\n"
    return manifest_text, legacy_text


def generate(*, check: bool = False) -> list[str]:
    drift: list[str] = []
    for directory in sorted((ROOT / "workers").iterdir()):
        if not directory.is_dir():
            continue
        manifest_text, legacy_text = _render(directory)
        expected = {
            directory / "worker-manifest.json": manifest_text,
            directory / "worker.json": legacy_text,
        }
        for path, content in expected.items():
            if check:
                if not path.is_file() or path.read_text(encoding="utf-8") != content:
                    drift.append(str(path.relative_to(ROOT)))
            else:
                path.write_text(content, encoding="utf-8")
    return drift


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate immutable SIP worker manifests.")
    parser.add_argument("--check", action="store_true", help="fail if committed manifests differ from generated content")
    args = parser.parse_args()
    drift = generate(check=args.check)
    if drift:
        raise SystemExit("generated worker manifest drift:\n" + "\n".join(drift))
    print("Worker manifests are current" if args.check else "Generated worker manifests")


if __name__ == "__main__":
    main()
