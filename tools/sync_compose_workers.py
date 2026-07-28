#!/usr/bin/env python3
"""Synchronize immutable worker manifests into Docker Compose without expanding YAML anchors."""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "infrastructure/compose/docker-compose.yml"


def _cpu_limit(manifest: dict[str, object]) -> str:
    limits = manifest["resource_limits"]
    assert isinstance(limits, dict)
    if int(limits.get("gpu_count", 0)) > 0:
        return "8.0"
    if int(limits["max_memory_bytes"]) >= 8 * 1024**3:
        return "4.0"
    return "2.0"


def _memory_limit(manifest: dict[str, object]) -> str:
    limits = manifest["resource_limits"]
    assert isinstance(limits, dict)
    value = int(limits["max_memory_bytes"])
    return f"{math.ceil(value / 1024**3)}g"


def render(current: str) -> str:
    text = current
    manifests: dict[str, dict[str, object]] = {}
    for path in sorted((ROOT / "workers").glob("*/worker-manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifests[str(manifest["name"])] = manifest
    if not manifests:
        raise RuntimeError("no worker manifests found")

    for worker_name, manifest in manifests.items():
        service = f"worker-{worker_name}"
        pattern = rf"(?ms)(^  {re.escape(service)}:\n.*?)(?=^  [a-z0-9][a-z0-9-]*:\n|^secrets:\n)"
        match = re.search(pattern, text)
        if not match:
            raise RuntimeError(f"Compose is missing {service}")
        block = match.group(1)
        if "SIP_WORKER_METRICS_PORT:" not in block:
            marker = "      SIP_WORKER_COMPUTE_NETWORK_ACCESS: denied\n"
            if marker not in block:
                raise RuntimeError(f"{service} is missing its compute-network policy")
            block = block.replace(marker, marker + '      SIP_WORKER_METRICS_PORT: "9100"\n', 1)
        if "\n    expose:\n      - \"9100\"\n" not in block:
            marker = "    stop_grace_period: 30s\n"
            if marker not in block:
                raise RuntimeError(f"{service} is missing stop_grace_period")
            block = block.replace(marker, marker + '    expose:\n      - "9100"\n', 1)

        replacements = {
            r"(?m)^    command: .*?$": f"    command: [python, {manifest['entrypoint']}]",
            r"(?m)^      SIP_SERVICE_NAME: .*?$": f"      SIP_SERVICE_NAME: {service}",
            r"(?m)^      SIP_WORKLOAD_IDENTITY: .*?$": f"      SIP_WORKLOAD_IDENTITY: {manifest['workload_identity']}",
            r"(?m)^      SIP_WORKER_MANIFEST_SHA256: .*?$": f"      SIP_WORKER_MANIFEST_SHA256: {manifest['manifest_sha256']}",
            r"(?m)^      SIP_WORKER_PUBLICATION_PERMISSION: .*?$": '      SIP_WORKER_PUBLICATION_PERMISSION: "false"',
            r"(?m)^      SIP_WORKER_COMPUTE_NETWORK_ACCESS: .*?$": "      SIP_WORKER_COMPUTE_NETWORK_ACCESS: denied",
            r"(?m)^      SIP_WORKER_METRICS_PORT: .*?$": '      SIP_WORKER_METRICS_PORT: "9100"',
            r"(?m)^    cpus: .*?$": f'    cpus: "{_cpu_limit(manifest)}"',
            r"(?m)^    mem_limit: .*?$": f"    mem_limit: {_memory_limit(manifest)}",
        }
        for expression, replacement in replacements.items():
            block, count = re.subn(expression, replacement, block, count=1)
            if count != 1:
                raise RuntimeError(f"{service} is missing field matching {expression}")
        block = re.sub(
            r"(?m)^      - [a-z0-9_-]+:/var/lib/sip/objects(?::[a-z,]+)?$",
            "      - sip_objects:/var/lib/sip/objects:ro",
            block,
            count=1,
        )
        block, count = re.subn(
            r"(?m)^      - [a-z0-9_-]+:/var/lib/sip/runtime(?::[a-z,]+)?$",
            f"      - {service}-runtime:/var/lib/sip/runtime",
            block,
            count=1,
        )
        if count != 1:
            raise RuntimeError(f"{service} is missing its runtime mount")
        text = text[: match.start(1)] + block + text[match.end(1) :]

    # Reconcile generated worker volumes while preserving human-maintained volumes.
    text = re.sub(r"(?m)^  worker-[a-z0-9-]+-runtime: \{\}\n", "", text)
    marker = "  sip_runtime: {}\n"
    if marker not in text:
        raise RuntimeError("Compose named-volume section is missing sip_runtime")
    generated = "".join(f"  worker-{name}-runtime: {{}}\n" for name in sorted(manifests))
    text = text.replace(marker, marker + generated, 1)
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    current = COMPOSE.read_text(encoding="utf-8")
    rendered = render(current)
    if args.check:
        if rendered != current:
            raise SystemExit("Docker Compose worker definitions are stale; run tools/sync_compose_workers.py")
        print("Docker Compose worker definitions are synchronized")
        return
    COMPOSE.write_text(rendered, encoding="utf-8")
    print(f"synchronized {len(list((ROOT / 'workers').glob('*/worker-manifest.json')))} workers")


if __name__ == "__main__":
    main()
