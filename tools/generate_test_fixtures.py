#!/usr/bin/env python3
"""Generate the deterministic SIP adversarial and vertical test corpus.

The corpus contains only synthetic data. It is safe to distribute with the source
repository and is intentionally small enough for CI while retaining representative
integrity, policy, geometry, and provider-failure cases.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from sip.capture import CapturePackage, create_synthetic_room_capture
from sip.errors import ValidationError

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _deterministic_zip(path: Path, entries: dict[str, bytes], *, compression: int = zipfile.ZIP_DEFLATED) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=compression, compresslevel=9, allowZip64=True) as archive:
        for name, payload in sorted(entries.items()):
            info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
            info.compress_type = compression
            info.external_attr = 0o644 << 16
            archive.writestr(info, payload, compress_type=compression, compresslevel=9)


def _normalize_zip(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(source) as archive:
        entries = {info.filename: archive.read(info.filename) for info in archive.infolist()}
    _deterministic_zip(destination, entries)


def _expected_validation(path: Path) -> tuple[str, str | None]:
    try:
        CapturePackage.validate(path)
    except ValidationError as exc:
        return "rejected", exc.code
    return "accepted", None


def _build(root: Path) -> list[dict[str, Any]]:
    root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="sip-fixture-") as temporary:
        generated = Path(temporary) / "room.sipcapture"
        create_synthetic_room_capture(generated, seed=42, frame_count=8)
        canonical = root / "capture" / "canonical-room.sipcapture"
        _normalize_zip(generated, canonical)

    with zipfile.ZipFile(canonical) as archive:
        canonical_entries = {info.filename: archive.read(info.filename) for info in archive.infolist()}

    future_entries = dict(canonical_entries)
    future_manifest = json.loads(future_entries["manifest.json"])
    future_manifest["schema_version"] = "99.0.0"
    future_entries["manifest.json"] = _canonical_json(future_manifest)
    future = root / "capture" / "future-schema.sipcapture"
    _deterministic_zip(future, future_entries)

    tampered_entries = dict(canonical_entries)
    rgb_name = next(name for name in sorted(tampered_entries) if name.endswith("rgb.bin"))
    tampered_entries[rgb_name] += b"tampered"
    tampered = root / "capture" / "tampered-asset.sipcapture"
    _deterministic_zip(tampered, tampered_entries)

    truncated = root / "capture" / "truncated.sipcapture"
    data = canonical.read_bytes()
    _write(truncated, data[: max(64, len(data) // 3)])

    traversal = root / "security" / "path-traversal.zip"
    _deterministic_zip(traversal, {"../outside.txt": b"must never extract", "manifest.json": b"{}\n"})

    bomb = root / "security" / "compression-bomb.zip"
    _deterministic_zip(bomb, {"highly-compressible.bin": b"0" * (2 * 1024 * 1024)})

    embedded = root / "security" / "embedded-script-metadata.json"
    _write(embedded, _canonical_json({
        "filename": "drawing.svg",
        "media_type": "image/svg+xml",
        "metadata": {"title": "<script>alert('synthetic')</script>", "onload": "fetch('https://invalid.example')"},
        "expected_policy": "reject_or_sanitize_before_indexing_or_rendering",
    }))

    geometry_cases = {
        "known-transform.json": {
            "source_frame": "fixture-a",
            "target_frame": "fixture-b",
            "units": "meter",
            "transform": [[0.0, -1.0, 0.0, 2.0], [1.0, 0.0, 0.0, -3.0], [0.0, 0.0, 1.0, 1.25], [0.0, 0.0, 0.0, 1.0]],
            "expected_scale": 1.0,
            "expected_translation_m": [2.0, -3.0, 1.25],
        },
        "mixed-coordinate-frames.json": {
            "frames": [
                {"frame_id": "arkit-y-up", "units": "meter", "handedness": "right", "up": "+Y"},
                {"frame_id": "bim-z-up", "units": "millimeter", "handedness": "right", "up": "+Z"},
            ],
            "expected_behavior": "explicit_registered_transform_required",
        },
        "proxy-missing-surface.json": {
            "proxy_hit": {"position": [1.0, 0.8, 2.0], "primitive_id": 12},
            "metric_candidates": [],
            "expected_behavior": "unresolved_non_authoritative_hit",
        },
        "repeated-corridor-loop.json": {
            "scene": "synthetic_repeated_corridor",
            "loop_candidates": [[10, 110], [10, 210]],
            "geometric_verification": {"10-110": False, "10-210": True},
            "expected_behavior": "accept_only_geometrically_verified_loop",
        },
    }
    for name, payload in geometry_cases.items():
        _write(root / "geometry" / name, _canonical_json(payload))

    construction = {
        "schema": "sip.synthetic-construction-project/v1",
        "project_id": "synthetic-construction-demo",
        "classification": "internal",
        "hierarchy": {"site": "Demo Site", "building": "Building A", "level": "L1", "rooms": ["Electrical 101", "Corridor 102"]},
        "systems": [
            {"kind": "fire_alarm", "entity_id": "fa-panel-1", "state": "observed", "authority": "evidence"},
            {"kind": "access_control", "entity_id": "door-102a", "state": "design", "authority": "design_intent"},
            {"kind": "mechanical", "entity_id": "ahu-1", "state": "verified", "authority": "field_verified"},
        ],
        "measurement": {"value": 0.914, "units": "meter", "uncertainty": 0.003, "calibration_id": "tape-verified-1", "verifier": "synthetic-inspector", "verification_date": "2026-01-01"},
        "deficiency": {"id": "def-1", "state": "closed", "correction_evidence": ["photo-after-1"], "retest": "passed"},
        "warnings": ["phone-derived geometry is not survey-grade or fabrication-authoritative"],
    }
    _write(root / "construction" / "synthetic-project.json", _canonical_json(construction))

    liveforever = {
        "schema": "sip.synthetic-liveforever-project/v1",
        "project_id": "synthetic-liveforever-demo",
        "people": [{"person_id": "person-a", "name": "Alex Example"}, {"person_id": "person-b", "name": "Jordan Example"}],
        "place": {"place_id": "place-kitchen", "name": "Family Kitchen"},
        "event": {"event_id": "event-storm", "date": "1985-06-01", "label": "Summer storm"},
        "recollections": [
            {"assertion_id": "memory-a", "speaker": "person-a", "claim": "The lights failed before dinner", "label": "recollection", "confidence": 0.7},
            {"assertion_id": "memory-b", "speaker": "person-b", "claim": "The lights failed after dinner", "label": "recollection", "confidence": 0.65},
        ],
        "conflict": {"kind": "temporal_disagreement", "members": ["memory-a", "memory-b"], "resolution": "unresolved"},
        "generated_reconstruction": {"label": "generated_reconstruction_not_historical_fact", "model_id": "synthetic-denied-by-default", "prompt_hash": "0" * 64},
        "consent": {"grant_id": "grant-family-only", "audiences": ["private", "family"], "public": False, "revoked": False},
        "experience_controls": {"quiet_mode": True, "pause": True, "reset": True, "safe_exit": True},
    }
    _write(root / "liveforever" / "conflicting-recollections.json", _canonical_json(liveforever))

    _write(root / "security" / "cross-tenant-attempts.json", _canonical_json({
        "attempts": [
            {"operation": "asset_read", "actor_tenant": "tenant-a", "resource_tenant": "tenant-b", "expected": "deny_not_found"},
            {"operation": "hybrid_conversion", "actor_project": "project-a", "body_project": "project-b", "expected": "deny_scope_mismatch"},
            {"operation": "evidence_link", "assertion_tenant": "tenant-a", "evidence_tenant": "tenant-b", "expected": "deny"},
        ]
    }))

    _write(root / "providers" / "failure-matrix.json", _canonical_json({
        "cases": [
            {"code": "PROVIDER_OOM", "retryable": True, "cleanup_verified": True, "expected_state": "failed_retryable"},
            {"code": "PROVIDER_INVALID_OUTPUT", "retryable": False, "cleanup_verified": True, "expected_state": "failed_terminal"},
            {"code": "PROVIDER_CLEANUP_FAILED", "retryable": False, "cleanup_verified": False, "expected_state": "cleanup_quarantined"},
            {"code": "DUPLICATE_MESSAGE", "expected": "idempotent_replay_or_conflict_on_payload_change"},
            {"code": "CANCELLED", "expected": "no_publication_and_durable_audit"},
        ]
    }))

    archive_expectations = {
        "capture/canonical-room.sipcapture": ("accepted", None),
        "capture/future-schema.sipcapture": _expected_validation(future),
        "capture/tampered-asset.sipcapture": _expected_validation(tampered),
        "capture/truncated.sipcapture": _expected_validation(truncated),
        "security/path-traversal.zip": _expected_validation(traversal),
        "security/compression-bomb.zip": _expected_validation(bomb),
    }
    descriptions = {
        "capture/canonical-room.sipcapture": "Valid deterministic canonical room capture with RGB, depth, confidence, poses, and calibration.",
        "capture/future-schema.sipcapture": "Structurally valid archive declaring an unsupported future major schema.",
        "capture/tampered-asset.sipcapture": "Canonical package with one content byte stream changed without updating its hash.",
        "capture/truncated.sipcapture": "Truncated ZIP for parser and recovery rejection.",
        "security/path-traversal.zip": "Archive containing a parent-directory member.",
        "security/compression-bomb.zip": "Highly compressible entry exceeding the configured compression-ratio guard.",
    }
    for relative, (expected, code) in archive_expectations.items():
        path = root / relative
        records.append({
            "path": relative,
            "sha256": _sha(path),
            "byte_count": path.stat().st_size,
            "category": relative.split("/", 1)[0],
            "description": descriptions[relative],
            "expected_result": expected,
            "expected_error_code": code,
        })

    for path in sorted(root.rglob("*.json")):
        if path.name == "manifest.json":
            continue
        relative = path.relative_to(root).as_posix()
        records.append({
            "path": relative,
            "sha256": _sha(path),
            "byte_count": path.stat().st_size,
            "category": relative.split("/", 1)[0],
            "description": "Synthetic structured fixture; see file content for expected behavior.",
            "expected_result": "controlled_fixture",
            "expected_error_code": None,
        })
    return sorted(records, key=lambda item: item["path"])


def generate(destination: Path) -> dict[str, Any]:
    if destination.exists():
        shutil.rmtree(destination)
    records = _build(destination)
    manifest = {
        "schema": "sip.test-fixture-corpus/v1",
        "generated_by": "tools/generate_test_fixtures.py",
        "synthetic_only": True,
        "fixture_count": len(records),
        "fixtures": records,
    }
    _write(destination / "manifest.json", _canonical_json(manifest))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        with tempfile.TemporaryDirectory(prefix="sip-fixtures-check-") as temporary:
            candidate = Path(temporary) / "fixtures"
            generate(candidate)
            current_files = sorted(path.relative_to(FIXTURES).as_posix() for path in FIXTURES.rglob("*") if path.is_file()) if FIXTURES.exists() else []
            candidate_files = sorted(path.relative_to(candidate).as_posix() for path in candidate.rglob("*") if path.is_file())
            if current_files != candidate_files:
                raise SystemExit("fixture corpus file set drift detected; run tools/generate_test_fixtures.py")
            for relative in candidate_files:
                if (FIXTURES / relative).read_bytes() != (candidate / relative).read_bytes():
                    raise SystemExit(f"fixture corpus drift detected: {relative}; run tools/generate_test_fixtures.py")
        print(json.dumps({"check": True, "path": str(FIXTURES.relative_to(ROOT))}, sort_keys=True))
        return 0
    manifest = generate(FIXTURES)
    print(json.dumps({"check": False, "path": str(FIXTURES.relative_to(ROOT)), "fixtures": manifest["fixture_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
