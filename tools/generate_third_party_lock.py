#!/usr/bin/env python3
"""Generate the deterministic third-party manifest lock from governed source records."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tomllib
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "third_party/manifest.lock.json"
GOVERNED_DIRS = (
    ROOT / "third_party/sources",
    ROOT / "third_party/models",
    ROOT / "third_party/providers",
    ROOT / "third_party/data",
)


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for directory in GOVERNED_DIRS:
        for path in sorted(directory.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            relative = path.relative_to(ROOT).as_posix()
            identity = (
                payload.get("provider_id")
                or payload.get("model_id")
                or payload.get("dataset_id")
                or path.stem
            )
            records.append(
                {
                    "path": relative,
                    "sha256": _sha256(path.read_bytes()),
                    "schema": payload.get("schema"),
                    "identity": identity,
                    "approval_state": payload.get("approval_state", "recorded"),
                    "source_revision": payload.get("source_revision") or payload.get("code_revision"),
                    "license": payload.get("license_id") or payload.get("license") or payload.get("code_license"),
                    "runtime_download": False,
                }
            )
    return records


def _python_dependencies() -> list[dict[str, str]]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    groups: dict[str, list[str]] = {"runtime": list(project.get("dependencies", []))}
    groups.update({key: list(value) for key, value in project.get("optional-dependencies", {}).items()})
    records: list[dict[str, str]] = []
    for group, values in sorted(groups.items()):
        for value in sorted(values):
            match = re.fullmatch(r"([A-Za-z0-9_.-]+)(?:\[([A-Za-z0-9_,.-]+)\])?==([^;\s]+)", value)
            if not match:
                raise ValueError(f"Python dependency is not exactly pinned: {value}")
            records.append({"ecosystem": "pypi", "name": match.group(1).lower(), "version": match.group(3), "group": group, **({"extras": match.group(2)} if match.group(2) else {})})
    return records


def _web_dependencies() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    root_package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    package_manager = str(root_package.get("packageManager", ""))
    if not re.fullmatch(r"pnpm@\d+\.\d+\.\d+", package_manager):
        raise ValueError("packageManager must be an exact pnpm version")
    records.append({"ecosystem": "npm", "name": "pnpm", "version": package_manager.split("@", 1)[1], "group": "toolchain"})
    package = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))
    for group in ("dependencies", "devDependencies"):
        for name, version in sorted(package.get(group, {}).items()):
            if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9_.-]+)?", str(version)):
                raise ValueError(f"npm dependency is not exactly pinned: {name}={version}")
            records.append({"ecosystem": "npm", "name": name, "version": str(version), "group": group})
    return records


def _container_images() -> list[dict[str, str]]:
    compose = yaml.safe_load((ROOT / "infrastructure/compose/docker-compose.yml").read_text(encoding="utf-8"))
    records: dict[str, dict[str, str]] = {}
    for service, definition in sorted(compose.get("services", {}).items()):
        image = str(definition.get("image", ""))
        if not image or image.startswith("sip/"):
            continue
        if "@sha256:" not in image or re.search(r"@sha256:0{64}$", image):
            raise ValueError(f"container image is not digest pinned: {service}={image}")
        records.setdefault(image, {"ecosystem": "oci", "name": image.split("@", 1)[0], "digest": image.split("@", 1)[1]})
    return [records[key] for key in sorted(records)]


def build() -> dict[str, Any]:
    source_lock = json.loads((ROOT / "third_party/sources/source-lock.json").read_text(encoding="utf-8"))
    imported_sources = []
    for source in sorted(source_lock.get("sources", []), key=lambda item: str(item["name"])):
        imported_sources.append(
            {
                "name": source["name"],
                "repository": source["repository"],
                "revision": source["revision"],
                "license": source["license"],
                "license_blob_sha": source["license_blob_sha"],
                "patches": [],
                "build_image": "none-format-reference" if source["name"] == "polyform" else "adapters/lingbot-map/Dockerfile",
                "runtime_state": source["runtime_state"],
                "model_dataset_relationship": (
                    "checkpoint governed independently by third_party/models/lingbot-map-checkpoint.json"
                    if source["name"] == "lingbot-map"
                    else "none; published export-format reference only"
                ),
            }
        )
    payload: dict[str, Any] = {
        "schema": "sip.third-party-manifest-lock/v1",
        "specification_version": "1.1.0",
        "runtime_downloads_allowed": False,
        "imported_sources": imported_sources,
        "governance_manifests": _manifest_records(),
        "dependencies": _python_dependencies() + _web_dependencies(),
        "container_images": _container_images(),
        "approval_policy": "deny_by_default_exact_hash_purpose_classification_region_retention",
    }
    payload["lock_root_sha256"] = _sha256(_canonical(payload))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = build()
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not DESTINATION.is_file() or DESTINATION.read_text(encoding="utf-8") != serialized:
            raise SystemExit("third-party manifest lock drift detected; run tools/generate_third_party_lock.py")
        print(json.dumps({"status": "passed", "path": str(DESTINATION.relative_to(ROOT)), "root": payload["lock_root_sha256"]}, sort_keys=True))
        return
    DESTINATION.write_text(serialized, encoding="utf-8")
    print(json.dumps({"status": "generated", "path": str(DESTINATION.relative_to(ROOT)), "root": payload["lock_root_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
