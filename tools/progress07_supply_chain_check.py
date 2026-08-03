#!/usr/bin/env python3
"""Verify Progress 07 supply-chain, secret, manifest, and fail-closed release controls."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ACTION_PIN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[a-f0-9]{40}$")
DIGEST_REF = re.compile(r"^[^\s@]+@sha256:[a-f0-9]{64}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _workflow_findings() -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    required_commands = {
        "make lint", "make spec-check", "make test", "make migrations",
        "make security", "make license-check", "make benchmark",
    }
    workflow_text = ""
    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        workflow_text += "\n" + text
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("uses:"):
                reference = stripped.split(":", 1)[1].strip()
                if not ACTION_PIN.fullmatch(reference):
                    findings.append({"code": "UNPINNED_GITHUB_ACTION", "path": str(path.relative_to(ROOT)), "line": line_number, "reference": reference})
    missing = sorted(command for command in required_commands if command not in workflow_text)
    if missing:
        findings.append({"code": "CI_REQUIRED_GATE_MISSING", "missing": missing})
    if "progress07_supply_chain_check.py" not in workflow_text:
        findings.append({"code": "CI_SUPPLY_CHAIN_CHECK_MISSING"})
    if "security_check.py --release" not in workflow_text:
        findings.append({"code": "CI_RELEASE_SECURITY_PROFILE_MISSING"})
    return findings


def _dependency_findings() -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    groups: list[tuple[str, list[str]]] = [("project.dependencies", list(pyproject["project"].get("dependencies", [])))]
    for name, values in pyproject["project"].get("optional-dependencies", {}).items():
        groups.append((f"project.optional-dependencies.{name}", list(values)))
    for group, values in groups:
        for dependency in values:
            value = str(dependency)
            if " @ " in value or "==" in value:
                continue
            findings.append({"code": "PYTHON_DEPENDENCY_NOT_EXACT", "group": group, "dependency": value})

    package = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))
    for group in ("dependencies", "devDependencies"):
        for name, version in package.get(group, {}).items():
            if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?", str(version)):
                findings.append({"code": "NODE_DEPENDENCY_NOT_EXACT", "group": group, "dependency": name, "version": version})
    return findings


def _container_findings() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    manifest = json.loads((ROOT / "build/manifests/container-images.json").read_text(encoding="utf-8"))
    for image in manifest.get("images", []):
        reference = str(image.get("reference", ""))
        if not DIGEST_REF.fullmatch(reference):
            findings.append({"code": "CONTAINER_DIGEST_REQUIRED", "image": image.get("name"), "reference": reference})
        if image.get("production_allowed") is not True:
            blockers.append({"code": "CONTAINER_PRODUCTION_BLOCKED", "image": image.get("name"), "reason": image.get("block_reason", "not approved")})
    return findings, blockers


def _third_party_findings() -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    lock_path = ROOT / "third_party/manifest.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if not lock.get("execution_policy"):
        findings.append({"code": "THIRD_PARTY_EXECUTION_POLICY_MISSING"})
    for image in lock.get("container_images", []):
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", str(image.get("digest", ""))):
            findings.append({"code": "THIRD_PARTY_CONTAINER_DIGEST_INVALID", "entry": image})
    for dependency in lock.get("dependencies", []):
        if not dependency.get("ecosystem") or not dependency.get("name") or not re.fullmatch(r"[0-9][A-Za-z0-9.+_-]*", str(dependency.get("version", ""))):
            findings.append({"code": "THIRD_PARTY_DEPENDENCY_PIN_INVALID", "entry": dependency})
    sources = [
        *lock.get("sources", []),
        *lock.get("source_repositories", []),
        *lock.get("imported_sources", []),
    ]
    for source in sources:
        revision = str(source.get("revision", source.get("commit", "")))
        if not revision or revision.lower() in {"main", "master", "latest", "head"}:
            findings.append({"code": "THIRD_PARTY_SOURCE_REVISION_MUTABLE", "entry": source})
        repository = str(source.get("repository", source.get("source_url", "")))
        if repository and not (repository.startswith("https://github.com/") or repository.startswith("local://")):
            findings.append({"code": "THIRD_PARTY_SOURCE_REPOSITORY_UNAPPROVED", "entry": source})
    if not lock.get("container_images") or not lock.get("dependencies"):
        findings.append({"code": "THIRD_PARTY_LOCK_INCOMPLETE"})
    return findings


def _policy_findings() -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    secret_path = ROOT / "infrastructure/security/secret-policy.json"
    model_path = ROOT / "infrastructure/security/model-egress-policy.json"
    transport_path = ROOT / "infrastructure/security/transport-policy.json"
    for path in (secret_path, model_path, transport_path):
        if not path.is_file():
            findings.append({"code": "SECURITY_POLICY_MISSING", "path": str(path.relative_to(ROOT))})
    if findings:
        return findings
    secret = json.loads(secret_path.read_text(encoding="utf-8"))
    model = json.loads(model_path.read_text(encoding="utf-8"))
    transport = json.loads(transport_path.read_text(encoding="utf-8"))
    if not secret.get("approved_backends") or secret.get("production_requirements", {}).get("repository_material") != "prohibited":
        findings.append({"code": "SECRET_POLICY_NOT_FAIL_CLOSED"})
    if model.get("production_runtime_downloads") != "denied" or model.get("worker_public_internet_egress") != "denied":
        findings.append({"code": "MODEL_EGRESS_POLICY_NOT_FAIL_CLOSED"})
    if transport.get("minimum_tls_version") not in {"TLSv1.2", "TLSv1.3"} or transport.get("certificate_validation_required") is not True:
        findings.append({"code": "TRANSPORT_POLICY_NOT_FAIL_CLOSED"})
    sql = ROOT / "infrastructure/postgres/audit-immutability.sql"
    if not sql.is_file() or "REVOKE UPDATE, DELETE" not in sql.read_text(encoding="utf-8").upper():
        findings.append({"code": "AUDIT_IMMUTABILITY_SQL_MISSING"})
    return findings


def run() -> dict[str, Any]:
    container_findings, blockers = _container_findings()
    findings = [
        *_workflow_findings(),
        *_dependency_findings(),
        *container_findings,
        *_third_party_findings(),
        *_policy_findings(),
    ]
    status = "failed" if findings else ("passed_with_external_gaps" if blockers else "passed_complete")
    return {
        "schema": "sip.progress07-supply-chain-report/v1",
        "status": status,
        "findings": findings,
        "external_or_release_blockers": blockers,
        "production_authorized": False,
        "limitations": [
            "Digest and source-policy checks do not replace registry signature verification, vulnerability scanning, or deployed admission controls.",
            "Production remains fail-closed while any production component or external review is blocked.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/reports/progress07-supply-chain-report.json")
    args = parser.parse_args()
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["status"] in {"passed_complete", "passed_with_external_gaps"} else 1)


if __name__ == "__main__":
    main()
