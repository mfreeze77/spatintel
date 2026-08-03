from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from sip.failures import FailureCatalog
from tools.generate_service_catalog import generate as generate_service_catalog

ROOT = Path(__file__).resolve().parents[1]
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
MODEL_SUFFIXES = {".pt", ".pth", ".ckpt", ".safetensors", ".onnx", ".gguf", ".bin"}
VALID_APPROVALS = {"approved", "denied", "quarantined", "expired"}
INCOMPATIBLE_LICENSES = {"unknown", "research-only", "restricted-use", "proprietary-unapproved"}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be an object")
    return value


def validate(*, release: bool = False) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    def error(code: str, path: Path | str, message: str) -> None:
        errors.append({"code": code, "path": str(path), "message": message})

    def warning(code: str, path: Path | str, message: str) -> None:
        warnings.append({"code": code, "path": str(path), "message": message})

    source_lock = _load(ROOT / "third_party/sources/source-lock.json")
    names: set[str] = set()
    for source in source_lock.get("sources", []):
        name = str(source.get("name", ""))
        if not name or name in names:
            error("SOURCE_NAME_INVALID", "third_party/sources/source-lock.json", f"invalid/duplicate source name {name!r}")
        names.add(name)
        if not HEX40.fullmatch(str(source.get("revision", ""))):
            error("SOURCE_REVISION_UNPINNED", name, "source revision must be an exact 40-character Git commit")
        if not str(source.get("license", "")):
            error("SOURCE_LICENSE_MISSING", name, "source license is required")
        if not str(source.get("license_blob_sha", "")):
            error("SOURCE_LICENSE_EVIDENCE_MISSING", name, "license blob SHA is required")

    expected_lingbot = "1f480aeb8a47a24656090d46d053115b7fe60435"
    lingbot_lock = _load(ROOT / "adapters/lingbot-map/source.lock.json")
    if lingbot_lock.get("commit") != expected_lingbot:
        error("LINGBOT_REVISION_MISMATCH", "adapters/lingbot-map/source.lock.json", "authoritative LingBot commit changed")
    if lingbot_lock.get("checkpoint_status") != "not_configured":
        error("LINGBOT_CHECKPOINT_STATUS_INVALID", "adapters/lingbot-map/source.lock.json", "checkpoint must remain inactive until a local model is configured")
    dockerfile = (ROOT / "adapters/lingbot-map/Dockerfile").read_text()
    if expected_lingbot not in dockerfile:
        error("LINGBOT_DOCKER_REVISION_MISSING", "adapters/lingbot-map/Dockerfile", "Docker context does not enforce the pinned revision")
    if "@sha256:" not in dockerfile or re.search(r"@sha256:0{64}", dockerfile):
        error("LINGBOT_BASE_IMAGE_UNPINNED", "adapters/lingbot-map/Dockerfile", "base image must use a nonzero digest")
    warning(
        "LINGBOT_BASE_IMAGE_VULNERABILITIES_REQUIRE_RESCAN",
        "adapters/lingbot-map/Dockerfile",
        "the inactive adapter image must be rebuilt on a scan-clean CUDA/PyTorch baseline before local use",
    )

    provider_count = 0
    for path in sorted((ROOT / "third_party/providers").glob("*.json")):
        provider_count += 1
        manifest = _load(path)
        state = str(manifest.get("approval_state", ""))
        if state not in VALID_APPROVALS:
            error("PROVIDER_APPROVAL_INVALID", path, f"invalid approval state {state!r}")
        required = {
            "provider_id", "version", "source_url", "source_revision", "license_id", "approval_state",
            "allowed_classifications", "allowed_purposes", "allowed_regions", "retention_days",
        }
        missing = sorted(required - manifest.keys())
        if missing:
            error("PROVIDER_MANIFEST_INCOMPLETE", path, f"missing {missing}")
        if state == "approved":
            if manifest.get("license_id", "").lower() in INCOMPATIBLE_LICENSES | {"unknown"}:
                error("APPROVED_PROVIDER_LICENSE_INVALID", path, "approved provider has an unknown/incompatible license")
            if manifest.get("source_url") in {"UNRESOLVED", "", None}:
                error("APPROVED_PROVIDER_SOURCE_INVALID", path, "approved provider source must resolve")
        elif release and state != "denied":
            error("NONAPPROVED_PROVIDER_RELEASE", path, "release manifests must not contain executable quarantined/expired providers")

    model_count = 0
    for path in sorted((ROOT / "third_party/models").glob("*.json")):
        model_count += 1
        manifest = _load(path)
        state = str(manifest.get("approval_state", ""))
        if state not in VALID_APPROVALS:
            error("MODEL_APPROVAL_INVALID", path, f"invalid approval state {state!r}")
        required = {
            "model_id", "version", "checkpoint_hash", "code_revision", "code_license", "weights_license",
            "dataset_terms", "output_terms", "approval_state", "usage_scope", "allowed_purposes",
        }
        missing = sorted(required - manifest.keys())
        if missing:
            error("MODEL_MANIFEST_INCOMPLETE", path, f"missing {missing}")
        if manifest.get("usage_scope") != "local_internal":
            error("MODEL_USAGE_SCOPE_INVALID", path, "internal tooling accepts only the local_internal usage scope")
        if state == "approved":
            if not HEX64.fullmatch(str(manifest.get("checkpoint_hash", ""))):
                error("APPROVED_MODEL_HASH_INVALID", path, "approved model requires an exact SHA-256 checkpoint hash")
            if str(manifest.get("weights_license", "")).lower() in INCOMPATIBLE_LICENSES:
                error("APPROVED_MODEL_LICENSE_INVALID", path, "approved model has incompatible/unknown weights rights")
            if not manifest.get("dataset_terms") or manifest.get("output_terms") in {"", "unknown", None}:
                error("APPROVED_MODEL_RIGHTS_INCOMPLETE", path, "approved model requires dataset and output-rights review")
        if release and state != "approved" and path.name != "lingbot-map-checkpoint.json":
            error("NONAPPROVED_MODEL_RELEASE", path, "nonapproved models cannot enter a release execution path")

    forbidden_weight_files = [
        path for path in ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in MODEL_SUFFIXES and "spec/" not in path.as_posix()
    ]
    for path in forbidden_weight_files:
        error("UNMANIFESTED_MODEL_FILE", path.relative_to(ROOT), "model/checkpoint binaries are forbidden in source and release trees")

    required_notices = [
        ROOT / "LICENSES/Apache-2.0-SIP.txt",
        ROOT / "LICENSES/Apache-2.0-LingBot-Map.txt",
        ROOT / "LICENSES/MIT-Polyform.txt",
        ROOT / "THIRD_PARTY_NOTICES.md",
    ]
    for path in required_notices:
        if not path.is_file() or path.stat().st_size == 0:
            error("NOTICE_MISSING", path.relative_to(ROOT), "required license/notice file is missing")

    # Failure taxonomy, assumptions, risk, ownership, and ADR controls are part
    # of the same fail-closed governance gate as licenses/providers/models.
    try:
        failure_catalog = FailureCatalog.load()
        failure_count = len(failure_catalog.document.failures)
    except Exception as exc:
        failure_count = 0
        error("FAILURE_CATALOG_INVALID", "governance/failure-catalog.json", str(exc))

    open_register = _load(ROOT / "governance/open-questions.json")
    open_questions = open_register.get("questions", [])
    required_open = {
        "OQ-LINGBOT-CHECKPOINT-RIGHTS",
        "OQ-LINGBOT-HARDWARE-ENVELOPE",
        "OQ-LONG-BUILDING-DRIFT",
        "OQ-DYNAMIC-SCENE-BEHAVIOR",
        "OQ-CROSS-SESSION-REPEATABILITY",
    }
    question_ids = {str(item.get("id", "")) for item in open_questions}
    for missing in sorted(required_open - question_ids):
        error("OPEN_QUESTION_MISSING", "governance/open-questions.json", f"missing {missing}")
    unresolved_p0 = []
    for item in open_questions:
        path = f"governance/open-questions.json#{item.get('id')}"
        experiment = item.get("falsifiable_experiment", {})
        for field in ("owner", "policy_owner", "default_safe_behavior", "assumption"):
            if not item.get(field):
                error("OPEN_QUESTION_INCOMPLETE", path, f"missing {field}")
        for field in (
            "input_hashes_required", "environment_manifest_required", "exact_model_or_algorithm_required",
            "output_hashes_required", "analysis_required", "conclusion_required", "acceptance_threshold",
        ):
            if not experiment.get(field):
                error("OPEN_EXPERIMENT_INCOMPLETE", path, f"missing/false {field}")
        if item.get("priority") == "P0" and item.get("status") != "CLOSED":
            unresolved_p0.append(item.get("id"))
            if not item.get("release_blocking"):
                error("OPEN_P0_NOT_BLOCKING", path, "unresolved P0 assumptions must block release")
    if release:
        for question_id in unresolved_p0:
            error("OPEN_P0_RELEASE_BLOCKER", f"governance/open-questions.json#{question_id}", "unresolved P0 assumption blocks release")

    risk_register = _load(ROOT / "governance/risk-register.json")
    mandated_risks = {
        "RISK-PROXY-AUTHORITY-CONFUSION", "RISK-PROVIDER-DATA-EGRESS", "RISK-PROTECTED-GEOMETRY-LOSS",
        "RISK-ANCHOR-DRIFT", "RISK-IMMERSIVE-SAFETY", "RISK-DERIVATIVE-REDACTION", "RISK-PROVIDER-LOCK-IN",
    }
    risks = risk_register.get("risks", [])
    risk_ids = {str(item.get("id", "")) for item in risks}
    for missing in sorted(mandated_risks - risk_ids):
        error("CRITICAL_RISK_MISSING", "governance/risk-register.json", f"missing {missing}")
    if risk_register.get("critical_increase_policy", {}).get("review_deadline") != "one_business_day":
        error("CRITICAL_RISK_REVIEW_SLA_INVALID", "governance/risk-register.json", "critical increase review must be one business day")
    for item in risks:
        path = f"governance/risk-register.json#{item.get('id')}"
        for field in (
            "requirement_ids", "test_ids", "monitors", "incident_playbooks", "fail_safe_mode", "scene_classes",
            "intended_uses", "local_native_fallback", "impact_analysis_procedure", "owner", "reviewers",
        ):
            if not item.get(field):
                error("RISK_RECORD_INCOMPLETE", path, f"missing {field}")
        for playbook in item.get("incident_playbooks", []):
            if not (ROOT / playbook).is_file():
                error("RISK_PLAYBOOK_MISSING", path, f"missing playbook {playbook}")
        acceptance = item.get("risk_acceptance")
        if acceptance is not None and not acceptance.get("expires_at"):
            error("RISK_ACCEPTANCE_NO_EXPIRY", path, "risk acceptance requires expiry")
        if item.get("status") == "CLOSED" and (not item.get("closure_evidence") or not item.get("residual_risk")):
            error("RISK_CLOSURE_UNSUPPORTED", path, "closed risk requires evidence and residual-risk statement")

    service_catalog_path = ROOT / "governance/service-catalog.json"
    service_catalog = _load(service_catalog_path)
    generated_service_catalog = generate_service_catalog()
    if service_catalog != generated_service_catalog:
        error("SERVICE_CATALOG_DRIFT", service_catalog_path.relative_to(ROOT), "generated service/worker ownership catalog is stale")
    components = service_catalog.get("components", [])
    for item in components:
        path = f"governance/service-catalog.json#{item.get('name')}"
        for field in (
            "owner", "repository_path", "data_stores", "slo", "shutdown", "recovery_strategy", "blast_radius",
            "retry_safety", "rpo", "rto", "degraded_behavior", "dependency_controls",
        ):
            if not item.get(field):
                error("SERVICE_CATALOG_INCOMPLETE", path, f"missing {field}")
        if item.get("kind") == "worker" and item.get("publication_permission") is not False:
            error("WORKER_PUBLICATION_PERMISSION", path, "workers must have no publication permission")

    adr_index = _load(ROOT / "docs/adr/index.json")
    adr_ids: set[str] = set()
    required_sections = adr_index.get("required_sections", [])
    for item in adr_index.get("adrs", []):
        adr_id = str(item.get("id", ""))
        path = ROOT / str(item.get("path", ""))
        if not adr_id or adr_id in adr_ids:
            error("ADR_ID_INVALID", "docs/adr/index.json", f"invalid/duplicate ADR ID {adr_id!r}")
        adr_ids.add(adr_id)
        if not path.is_file():
            error("ADR_FILE_MISSING", path.relative_to(ROOT) if path.is_relative_to(ROOT) else path, "indexed ADR file is missing")
            continue
        text = path.read_text(encoding="utf-8")
        for section in required_sections:
            if f"## {section}" not in text:
                error("ADR_SECTION_MISSING", path.relative_to(ROOT), f"missing section {section}")
        for marker in (
            "- Requirements:", "- Risks:", "- Benchmarks:", "- Source evidence:",
            "- Exit/export strategy:", "- Security/privacy review:",
        ):
            if marker not in text:
                error("ADR_TRACEABILITY_MISSING", path.relative_to(ROOT), f"missing {marker}")

    if provider_count == 0:
        error("PROVIDER_MANIFESTS_MISSING", "third_party/providers", "at least one provider manifest is required")
    if model_count == 0:
        error("MODEL_MANIFESTS_MISSING", "third_party/models", "at least one model manifest is required")

    report = {
        "schema": "sip.governance-check/v1",
        "mode": "release" if release else "structural",
        "status": "passed" if not errors else "failed",
        "source_count": len(source_lock.get("sources", [])),
        "provider_count": provider_count,
        "model_count": model_count,
        "failure_count": failure_count,
        "open_question_count": len(open_questions),
        "unresolved_p0_question_count": len(unresolved_p0),
        "risk_count": len(risks),
        "service_component_count": len(components),
        "adr_count": len(adr_ids),
        "unmanifested_model_file_count": len(forbidden_weight_files),
        "errors": errors,
        "warnings": warnings,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Fail-closed SIP source/model/provider governance gate")
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "build/reports/governance-check.json")
    args = parser.parse_args()
    report = validate(release=args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
