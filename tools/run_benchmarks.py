#!/usr/bin/env python3
"""Run deterministic SIP CPU-reference geometry and package benchmarks."""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np

from sip.canonical import sha256_file
from sip.capture import CapturePackage, create_synthetic_room_capture
from sip.geometry import interaction_proxy, mesh_to_splats, ransac_similarity

ROOT = Path(__file__).resolve().parents[1]


def _git_state() -> dict[str, Any]:
    def command(*args: str) -> str | None:
        completed = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
        return completed.stdout.strip() if completed.returncode == 0 else None

    commit = command("rev-parse", "HEAD")
    status = command("status", "--porcelain")
    return {"commit": commit, "working_tree_clean": status == "", "dirty_paths": len(status.splitlines()) if status else 0}


def _measure(call: Callable[[], Any], samples: int) -> tuple[dict[str, float | int], Any]:
    durations: list[float] = []
    result: Any = None
    call()
    for _ in range(samples):
        started = time.perf_counter_ns()
        result = call()
        durations.append((time.perf_counter_ns() - started) / 1_000_000)
    ordered = sorted(durations)
    p95_index = max(0, min(len(ordered) - 1, int(np.ceil(len(ordered) * 0.95)) - 1))
    return {
        "samples": samples,
        "min_ms": min(durations),
        "median_ms": statistics.median(durations),
        "p95_ms": ordered[p95_index],
        "max_ms": max(durations),
    }, result


def _fixture_mesh() -> tuple[np.ndarray, np.ndarray]:
    vertices = np.array(
        [
            [0, 0, 0], [4, 0, 0], [4, 3, 0], [0, 3, 0],
            [0, 0, 2.7], [4, 0, 2.7], [4, 3, 2.7], [0, 3, 2.7],
        ],
        dtype=float,
    )
    faces = np.array(
        [
            [0, 1, 2], [0, 2, 3], [4, 6, 5], [4, 7, 6],
            [0, 4, 5], [0, 5, 1], [1, 5, 6], [1, 6, 2],
            [2, 6, 7], [2, 7, 3], [3, 7, 4], [3, 4, 0],
        ],
        dtype=int,
    )
    return vertices, faces


def _budget_result(name: str, measured: dict[str, Any], budget: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    if "p95_ms_max" in budget:
        checks.append({"metric": "p95_ms", "operator": "<=", "threshold": budget["p95_ms_max"], "actual": measured["p95_ms"], "passed": measured["p95_ms"] <= budget["p95_ms_max"]})
    if "rmse_max" in budget:
        checks.append({"metric": "rmse", "operator": "<=", "threshold": budget["rmse_max"], "actual": measured["rmse"], "passed": measured["rmse"] <= budget["rmse_max"]})
    if "minimum_inliers" in budget:
        checks.append({"metric": "inliers", "operator": ">=", "threshold": budget["minimum_inliers"], "actual": measured["inliers"], "passed": measured["inliers"] >= budget["minimum_inliers"]})
    return {"benchmark": name, "status": "passed" if all(item["passed"] for item in checks) else "failed", "checks": checks}


def run(*, budget_path: Path) -> dict[str, Any]:
    budgets_document = json.loads(budget_path.read_text(encoding="utf-8"))
    budgets = budgets_document["budgets"]
    rng = np.random.default_rng(2104)
    source = rng.normal(size=(500, 3))
    angle = 0.22
    rotation = np.array([[np.cos(angle), 0, np.sin(angle)], [0, 1, 0], [-np.sin(angle), 0, np.cos(angle)]])
    target = (1.25 * (rotation @ source.T)).T + np.array([2.0, -0.5, 1.0])
    target[:25] += np.array([10.0, 8.0, -9.0])

    registration_metrics, registration = _measure(
        lambda: ransac_similarity(source, target, threshold_m=0.02, iterations=400, seed=7), 5
    )
    transform, mask = registration
    registration_metrics.update({"inliers": int(mask.sum()), "rmse": transform.rmse, "scale": transform.scale})

    vertices, faces = _fixture_mesh()
    proxy_metrics, proxy = _measure(lambda: interaction_proxy(vertices, faces, target_faces=8), 20)
    proxy_metrics.update({"input_faces": len(faces), "output_faces": len(proxy["faces"])})

    splat_metrics, splats = _measure(lambda: mesh_to_splats(vertices, faces, samples=96, seed=11), 10)
    splat_metrics.update({"input_faces": len(faces), "output_splats": len(splats["positions"]), "lossy": bool(splats["lossy"])})

    with tempfile.TemporaryDirectory(prefix="sip-benchmark-") as temporary:
        archive = Path(temporary) / "room.sipcapture"
        package = create_synthetic_room_capture(archive, seed=42, frame_count=16)
        capture_metrics, validation = _measure(lambda: CapturePackage.validate(archive), 5)
        capture_metrics.update({"archive_sha256": sha256_file(archive), "root_hash": package["root_hash"], "validated_frames": validation["frame_count"]})

    benchmarks = {
        "sim3_ransac_500_points_25_outliers": registration_metrics,
        "interaction_proxy_12_to_8_faces": proxy_metrics,
        "mesh_to_splats_12_faces_x8": splat_metrics,
        "cscp_validate_16_frames": capture_metrics,
    }
    budget_checks = [_budget_result(name, result, budgets[name]) for name, result in benchmarks.items()]
    git = _git_state()
    return {
        "schema": "sip.benchmark-report/v2",
        "status": "passed" if all(item["status"] == "passed" for item in budget_checks) else "failed",
        "profile": {
            "name": "cpu-reference",
            "execution": "single-process deterministic CPU path",
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "git": git,
        },
        "budget_manifest": {"path": str(budget_path.relative_to(ROOT)), "sha256": sha256_file(budget_path)},
        "benchmarks": benchmarks,
        "budget_checks": budget_checks,
        "claims": budgets_document["claims"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budgets", type=Path, default=ROOT / "benchmarks/reference-budgets.json")
    parser.add_argument("--output", type=Path, default=ROOT / "build/reports/benchmark-report.json")
    args = parser.parse_args()
    report = run(budget_path=args.budgets.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
