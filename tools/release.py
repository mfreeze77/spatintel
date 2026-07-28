#!/usr/bin/env python3
"""Create deterministic SIP release artifacts and enforce fail-closed promotion gates."""
import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT / "build" / "release"
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
EXPECTED_SPEC_SHA256 = "84b570464b98b1baf3107789af22edad2a14086e5420df35a961f5fb16980bb8"

SOURCE_EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".swiftpm",
    ".build",
    ".next",
    "__pycache__",
    "node_modules",
    "runtime",
}
SOURCE_EXCLUDED_PREFIXES = ("build/",)
EVIDENCE_PREFIXES = ("build/evidence/", "build/reports/", "requirements/")


@dataclass(frozen=True)
class FileRecord:
    path: str
    bytes: int
    sha256: str
    mode: str


@dataclass(frozen=True)
class Blocker:
    code: str
    message: str
    evidence: str | None = None


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*arguments: str, default: str = "unknown") -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 and completed.stdout.strip() else default


def _source_date() -> str:
    raw = _git("show", "-s", "--format=%cI", "HEAD", default="1970-01-01T00:00:00+00:00")
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        value = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _project_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def _is_source_file(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    if any(relative == prefix.rstrip("/") or relative.startswith(prefix) for prefix in SOURCE_EXCLUDED_PREFIXES):
        return False
    if any(part in SOURCE_EXCLUDED_PARTS for part in path.relative_to(ROOT).parts):
        return False
    return path.is_file() and not path.is_symlink()


def _source_files() -> list[Path]:
    return [path for path in sorted(ROOT.rglob("*")) if _is_source_file(path)]


def _evidence_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(ROOT).as_posix()
        if any(relative.startswith(prefix) for prefix in EVIDENCE_PREFIXES):
            if relative.startswith("build/release/"):
                continue
            files.append(path)
    return files


def _file_records(paths: Iterable[Path]) -> list[FileRecord]:
    records: list[FileRecord] = []
    for path in paths:
        mode = oct(path.stat().st_mode & 0o777)
        records.append(
            FileRecord(
                path=path.relative_to(ROOT).as_posix(),
                bytes=path.stat().st_size,
                sha256=_sha256_file(path),
                mode=mode,
            )
        )
    return records


def _write_zip(destination: Path, paths: Sequence[Path], prefix: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(paths, key=lambda item: item.relative_to(ROOT).as_posix()):
            relative = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(f"{prefix}/{relative}", date_time=FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = ((path.stat().st_mode & 0o777) or 0o644) << 16
            info.flag_bits |= 0x800
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    temporary.replace(destination)


def _python_components(pyproject: Mapping[str, object]) -> list[dict[str, object]]:
    components: list[dict[str, object]] = []
    project = pyproject.get("project", {})
    if not isinstance(project, Mapping):
        return components
    groups: list[tuple[str, object]] = [("runtime", project.get("dependencies", []))]
    optional = project.get("optional-dependencies", {})
    if isinstance(optional, Mapping):
        groups.extend((str(group), values) for group, values in optional.items())
    pattern = re.compile(r"^([A-Za-z0-9_.-]+)==([^;\s]+)")
    seen: set[tuple[str, str]] = set()
    for group, values in groups:
        if not isinstance(values, list):
            continue
        for dependency in values:
            match = pattern.match(str(dependency))
            if not match:
                continue
            name, version = match.groups()
            key = (name.lower(), version)
            if key in seen:
                continue
            seen.add(key)
            components.append(
                {
                    "type": "library",
                    "bom-ref": f"pkg:pypi/{name}@{version}",
                    "name": name,
                    "version": version,
                    "purl": f"pkg:pypi/{name}@{version}",
                    "properties": [{"name": "sip:dependency-group", "value": group}],
                }
            )
    return components


def _node_components() -> list[dict[str, object]]:
    payload = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))
    components: list[dict[str, object]] = []
    for group in ("dependencies", "devDependencies"):
        for name, version in sorted(payload.get(group, {}).items()):
            encoded = name.replace("@", "%40").replace("/", "%2F") if name.startswith("@") else name
            components.append(
                {
                    "type": "library",
                    "bom-ref": f"pkg:npm/{encoded}@{version}",
                    "name": name,
                    "version": version,
                    "purl": f"pkg:npm/{encoded}@{version}",
                    "properties": [{"name": "sip:dependency-group", "value": f"web:{group}"}],
                }
            )
    return components


def _container_components() -> list[dict[str, object]]:
    path = ROOT / "build/manifests/container-images.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    components: list[dict[str, object]] = []
    for image in data.get("images", []):
        reference = str(image.get("reference", ""))
        name = str(image.get("name", reference))
        components.append(
            {
                "type": "container",
                "bom-ref": f"urn:sip:container:{name}",
                "name": name,
                "version": reference,
                "properties": [
                    {"name": "sip:reference", "value": reference},
                    {"name": "sip:production-allowed", "value": str(bool(image.get("production_allowed"))).lower()},
                ],
            }
        )
    return components


def _worker_components() -> list[dict[str, object]]:
    components: list[dict[str, object]] = []
    for path in sorted((ROOT / "workers").glob("*/worker-manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        name = str(manifest.get("worker_id", path.parent.name))
        digest = _sha256_file(path)
        components.append(
            {
                "type": "application",
                "bom-ref": f"urn:sip:worker:{name}:{digest}",
                "name": name,
                "version": digest,
                "hashes": [{"alg": "SHA-256", "content": digest}],
                "properties": [
                    {"name": "sip:capability", "value": str(manifest.get("capability", "unknown"))},
                    {"name": "sip:manifest-path", "value": path.relative_to(ROOT).as_posix()},
                ],
            }
        )
    return components


def _governance_components() -> list[dict[str, object]]:
    components: list[dict[str, object]] = []
    for directory, component_type in (
        (ROOT / "third_party/models", "machine-learning-model"),
        (ROOT / "third_party/providers", "service"),
        (ROOT / "third_party/sources", "data"),
        (ROOT / "third_party/data", "data"),
    ):
        for path in sorted(directory.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            name = str(payload.get("name") or payload.get("id") or path.stem)
            digest = _sha256_file(path)
            components.append(
                {
                    "type": component_type,
                    "bom-ref": f"urn:sip:governance:{directory.name}:{name}:{digest}",
                    "name": name,
                    "version": str(payload.get("version") or payload.get("commit") or digest),
                    "hashes": [{"alg": "SHA-256", "content": digest}],
                    "properties": [
                        {"name": "sip:manifest", "value": path.relative_to(ROOT).as_posix()},
                        {"name": "sip:approval-status", "value": str(payload.get("approval_status", payload.get("status", "unknown")))},
                    ],
                }
            )
    return components


def _sbom(version: str, commit: str, generated_at: str) -> dict[str, object]:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    components = (
        _python_components(pyproject)
        + _node_components()
        + _container_components()
        + _worker_components()
        + _governance_components()
    )
    components = sorted(components, key=lambda item: str(item["bom-ref"]))
    root_ref = f"pkg:generic/spatial-intelligence-platform@{version}?commit={commit}"
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{hashlib.md5(root_ref.encode('utf-8'), usedforsecurity=False).hexdigest()}",
        "version": 1,
        "metadata": {
            "timestamp": generated_at,
            "tools": {"components": [{"type": "application", "name": "tools/release.py", "version": "1"}]},
            "component": {
                "type": "application",
                "bom-ref": root_ref,
                "name": "spatial-intelligence-platform",
                "version": version,
                "properties": [
                    {"name": "sip:git-commit", "value": commit},
                    {"name": "sip:spec-sha256", "value": EXPECTED_SPEC_SHA256},
                ],
            },
        },
        "components": components,
        "dependencies": [{"ref": root_ref, "dependsOn": [str(item["bom-ref"]) for item in components]}],
    }


def _load_json(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


def _report_blockers() -> list[Blocker]:
    blockers: list[Blocker] = []
    required_reports = {
        "test-matrix": ROOT / "build/reports/test-matrix.json",
        "typecheck": ROOT / "build/reports/typecheck-report.json",
        "security": ROOT / "build/reports/security-report.json",
        "license": ROOT / "build/reports/license-gate.json",
        "benchmark": ROOT / "build/reports/benchmark-report.json",
        "infrastructure": ROOT / "build/reports/infrastructure-static-validation.json",
        "static-checks": ROOT / "build/reports/static-checks.json",
    }
    for name, path in required_reports.items():
        report = _load_json(path)
        if report is None:
            blockers.append(Blocker("RELEASE_REPORT_MISSING", f"required {name} report is missing or invalid", path.relative_to(ROOT).as_posix()))
            continue
        status = report.get("status")
        if status not in {"passed", None} or (name == "infrastructure" and int(report.get("errors", 1)) != 0):
            blockers.append(Blocker("RELEASE_REPORT_FAILED", f"required {name} report is not passing", path.relative_to(ROOT).as_posix()))
        external = report.get("external_validation_required")
        if isinstance(external, list) and external:
            blockers.append(
                Blocker(
                    "RELEASE_EXTERNAL_VALIDATION_OPEN",
                    f"{name} report has {len(external)} unresolved external validations",
                    path.relative_to(ROOT).as_posix(),
                )
            )
    for name in ("foundation", "hybrid", "construction", "liveforever"):
        path = ROOT / f"build/evidence/demos/{name}.json"
        report = _load_json(path)
        if report is None or report.get("status") != "passed":
            blockers.append(Blocker("RELEASE_DEMO_MISSING", f"retained {name} demonstration is missing or not passing", path.relative_to(ROOT).as_posix()))
    return blockers


def _requirements_blockers() -> list[Blocker]:
    path = ROOT / "requirements/requirements-ledger.json"
    payload = _load_json(path)
    if payload is None:
        return [Blocker("REQUIREMENTS_LEDGER_INVALID", "requirements ledger is missing or invalid", path.relative_to(ROOT).as_posix())]
    records = payload.get("requirements", payload.get("records", []))
    if not isinstance(records, list):
        return [Blocker("REQUIREMENTS_LEDGER_INVALID", "requirements ledger has no requirement records", path.relative_to(ROOT).as_posix())]
    complete_statuses = {"VERIFIED", "WAIVED_WITH_EXPIRATION", "NOT_APPLICABLE_WITH_RATIONALE"}
    incomplete = [
        item
        for item in records
        if isinstance(item, dict)
        and item.get("priority") in {"P0", "P1"}
        and item.get("implementation_status", item.get("status")) not in complete_statuses
    ]
    return [] if not incomplete else [
        Blocker(
            "REQUIREMENTS_RELEASE_GATES_OPEN",
            f"{len(incomplete)} P0/P1 requirements are not verified, validly waived, or not applicable",
            path.relative_to(ROOT).as_posix(),
        )
    ]


def _environment_blockers(version: str, *, signing_available: bool) -> list[Blocker]:
    blockers: list[Blocker] = []
    status = _git("status", "--porcelain", default="")
    if status:
        blockers.append(Blocker("WORKTREE_DIRTY", "release promotion requires a clean Git working tree"))
    exact_tag = _git("describe", "--tags", "--exact-match", "HEAD", default="")
    if exact_tag != f"v{version}":
        blockers.append(Blocker("RELEASE_TAG_MISSING", f"HEAD must carry exact tag v{version}"))
    if not (ROOT / "pnpm-lock.yaml").is_file():
        blockers.append(Blocker("WEB_LOCKFILE_MISSING", "pnpm-lock.yaml is required for a frozen web dependency graph"))
    if not signing_available:
        blockers.append(Blocker("RELEASE_SIGNING_KEY_MISSING", "an Ed25519 release signing key is required for promotion"))
    spec_zip = ROOT / "spec/source/Spatial-Intelligence-Platform-Spec-v1.1.zip"
    if not spec_zip.is_file() or _sha256_file(spec_zip) != EXPECTED_SPEC_SHA256:
        blockers.append(Blocker("SPEC_ARCHIVE_HASH_MISMATCH", "authoritative specification archive hash does not match", spec_zip.relative_to(ROOT).as_posix()))
    images = _load_json(ROOT / "build/manifests/container-images.json")
    if images:
        blocked = [
            item
            for item in images.get("images", [])
            if isinstance(item, dict)
            and not bool(item.get("production_allowed"))
            and "local-only" not in str(item.get("name", ""))
        ]
        if blocked:
            blockers.append(
                Blocker(
                    "PRODUCTION_IMAGE_BLOCKED",
                    "production-required image manifests remain denied: " + ", ".join(str(item.get("name")) for item in blocked),
                    "build/manifests/container-images.json",
                )
            )
    return blockers


def _signing_key() -> tuple[object | None, str | None]:
    encoded = os.environ.get("SIP_RELEASE_SIGNING_KEY_B64", "").strip()
    key_path = os.environ.get("SIP_RELEASE_SIGNING_KEY_FILE", "").strip()
    if not encoded and key_path:
        encoded = Path(key_path).read_text(encoding="utf-8").strip()
    if not encoded:
        return None, None
    try:
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) != 32:
            return None, "release signing key must decode to exactly 32 raw Ed25519 private-key bytes"
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        return Ed25519PrivateKey.from_private_bytes(raw), None
    except (ValueError, OSError) as exc:
        return None, f"release signing key could not be loaded: {exc}"


def _write_checksums(directory: Path) -> None:
    lines: list[str] = []
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS":
            lines.append(f"{_sha256_file(path)}  {path.name}")
    (directory / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(*, mode: str) -> dict[str, object]:
    version = _project_version()
    commit = _git("rev-parse", "HEAD")
    branch = _git("branch", "--show-current", default="detached")
    generated_at = _source_date()
    tree_status = _git("status", "--porcelain", default="")
    tree_clean = not bool(tree_status)
    source_files = _source_files()
    evidence_files = _evidence_files()
    source_records = _file_records(source_files)
    source_root = _sha256_bytes(_canonical_json([asdict(item) for item in source_records]))
    candidate_id = f"sip-v{version}-{commit[:12]}-{source_root[:12]}"
    output = RELEASE_ROOT / candidate_id
    output.mkdir(parents=True, exist_ok=True)

    source_manifest = {
        "schema": "sip.source-manifest/v1",
        "version": version,
        "git_commit": commit,
        "git_branch": branch,
        "working_tree_clean": tree_clean,
        "generated_at": generated_at,
        "source_root_sha256": source_root,
        "file_count": len(source_records),
        "total_bytes": sum(item.bytes for item in source_records),
        "files": [asdict(item) for item in source_records],
    }
    (output / "source-manifest.json").write_bytes(_canonical_json(source_manifest))

    source_archive = output / f"spatial-intelligence-platform-{version}-source.zip"
    evidence_archive = output / f"spatial-intelligence-platform-{version}-evidence.zip"
    _write_zip(source_archive, source_files, f"spatial-intelligence-platform-{version}")
    _write_zip(evidence_archive, evidence_files, f"spatial-intelligence-platform-{version}-evidence")

    sbom = _sbom(version, commit, generated_at)
    sbom_path = output / "sbom.cdx.json"
    sbom_path.write_bytes(_canonical_json(sbom))

    key, key_error = _signing_key()
    blockers = _requirements_blockers() + _report_blockers() + _environment_blockers(version, signing_available=key is not None)
    if key_error:
        blockers.append(Blocker("RELEASE_SIGNING_KEY_INVALID", key_error))
    blockers = sorted({(item.code, item.message, item.evidence): item for item in blockers}.values(), key=lambda item: (item.code, item.message))

    artifact_records = {
        source_archive.name: {"sha256": _sha256_file(source_archive), "bytes": source_archive.stat().st_size},
        evidence_archive.name: {"sha256": _sha256_file(evidence_archive), "bytes": evidence_archive.stat().st_size},
        "source-manifest.json": {"sha256": _sha256_file(output / "source-manifest.json"), "bytes": (output / "source-manifest.json").stat().st_size},
        "sbom.cdx.json": {"sha256": _sha256_file(sbom_path), "bytes": sbom_path.stat().st_size},
    }
    readiness = {
        "schema": "sip.release-readiness/v1",
        "mode": mode,
        "status": "ready" if not blockers else "blocked",
        "candidate_id": candidate_id,
        "blocker_count": len(blockers),
        "blockers": [asdict(item) for item in blockers],
        "promotion_rule": "Promotion is denied whenever any blocker is present.",
    }
    readiness_path = output / "release-readiness.json"
    readiness_path.write_bytes(_canonical_json(readiness))
    artifact_records[readiness_path.name] = {"sha256": _sha256_file(readiness_path), "bytes": readiness_path.stat().st_size}

    reports: dict[str, object] = {}
    for path in sorted((ROOT / "build/reports").glob("*.json")):
        reports[path.name] = {"sha256": _sha256_file(path), "bytes": path.stat().st_size}
    demos: dict[str, object] = {}
    for path in sorted((ROOT / "build/evidence/demos").glob("*.json")):
        demos[path.stem] = {"sha256": _sha256_file(path), "bytes": path.stat().st_size}

    record = {
        "schema": "sip.release-record/v1",
        "candidate_id": candidate_id,
        "product": "Spatial Intelligence Platform",
        "version": version,
        "generated_at": generated_at,
        "git": {
            "commit": commit,
            "branch": branch,
            "exact_tag": _git("describe", "--tags", "--exact-match", "HEAD", default=None),
            "working_tree_clean": tree_clean,
        },
        "specification": {
            "path": "spec/source/Spatial-Intelligence-Platform-Spec-v1.1.zip",
            "sha256": _sha256_file(ROOT / "spec/source/Spatial-Intelligence-Platform-Spec-v1.1.zip"),
            "expected_sha256": EXPECTED_SPEC_SHA256,
        },
        "source_root_sha256": source_root,
        "artifacts": artifact_records,
        "reports": reports,
        "demonstrations": demos,
        "requirements_ledger_sha256": _sha256_file(ROOT / "requirements/requirements-ledger.json"),
        "worker_manifest_root_sha256": _sha256_bytes(
            _canonical_json(
                [
                    {"path": path.relative_to(ROOT).as_posix(), "sha256": _sha256_file(path)}
                    for path in sorted((ROOT / "workers").glob("*/worker-manifest.json"))
                ]
            )
        ),
        "readiness": {"status": readiness["status"], "blocker_count": len(blockers)},
        "signature": {"algorithm": "Ed25519", "present": key is not None},
    }
    record_path = output / "release-record.json"
    record_bytes = _canonical_json(record)
    record_path.write_bytes(record_bytes)

    if key is not None:
        from cryptography.hazmat.primitives import serialization

        signature = key.sign(record_bytes)
        public = key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        (output / "release-record.sig").write_text(base64.b64encode(signature).decode("ascii") + "\n", encoding="ascii")
        (output / "release-public-key.txt").write_text(base64.b64encode(public).decode("ascii") + "\n", encoding="ascii")

    _write_checksums(output)
    latest = {
        "schema": "sip.release-latest/v1",
        "candidate_id": candidate_id,
        "path": output.relative_to(ROOT).as_posix(),
        "readiness": readiness["status"],
        "record_sha256": _sha256_file(record_path),
    }
    RELEASE_ROOT.mkdir(parents=True, exist_ok=True)
    (RELEASE_ROOT / "latest.json").write_bytes(_canonical_json(latest))
    result = {
        "schema": "sip.release-build/v1",
        "mode": mode,
        "status": "passed" if mode == "candidate" or not blockers else "failed",
        "readiness": readiness["status"],
        "candidate_id": candidate_id,
        "output": output.relative_to(ROOT).as_posix(),
        "source_files": len(source_files),
        "evidence_files": len(evidence_files),
        "blockers": [asdict(item) for item in blockers],
    }
    (ROOT / "build/reports/release-report.json").write_bytes(_canonical_json(result))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("candidate", "release"), default="candidate")
    args = parser.parse_args()
    result = build(mode=args.mode)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
