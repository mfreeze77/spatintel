#!/usr/bin/env python3
"""Static infrastructure integrity and release-readiness validation.

This validator is intentionally dependency-light. It validates deterministic
properties that can be proven without cloud credentials, Docker, Terraform, or
kubectl. Account-backed plan/apply and runtime probes remain external evidence.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]
K8S = ROOT / "infrastructure/kubernetes"
TERRAFORM = ROOT / "infrastructure/terraform"
COMPOSE = ROOT / "infrastructure/compose/docker-compose.yml"
EXPECTED_NAMESPACE = "sip-system"
ZERO_DIGEST = "0" * 64
API_SERVICE_ACCOUNTS = {
    "control-api",
    "identity-policy",
    "capture-service",
    "workflow-service",
    "scene-service",
    "evidence-service",
    "search-service",
    "export-service",
    "notification-service",
    "audit-service",
    "security-ops",
    "representation-api",
    "provider-registry",
    "representation-publisher",
}
def _load_worker_manifests() -> dict[str, dict[str, Any]]:
    manifests: dict[str, dict[str, Any]] = {}
    for path in sorted((ROOT / "workers").glob("*/worker-manifest.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        name = str(raw.get("name", ""))
        if not name or name in manifests:
            raise RuntimeError(f"invalid or duplicate worker manifest name in {path}")
        manifests[name] = raw
    if not manifests:
        raise RuntimeError("no immutable worker manifests found")
    return manifests


WORKER_MANIFESTS = _load_worker_manifests()
WORKER_SERVICE_ACCOUNTS = {f"worker-{name}" for name in WORKER_MANIFESTS}
REQUIRED_SERVICE_ACCOUNTS = API_SERVICE_ACCOUNTS | WORKER_SERVICE_ACCOUNTS | {"sip-migrator", "sip-web"}


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: str
    message: str


def _finding(findings: list[Finding], severity: str, code: str, path: Path | str, message: str) -> None:
    findings.append(Finding(severity, code, str(path), message))


def _yaml_documents(path: Path) -> list[dict[str, Any]]:
    docs = []
    for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if doc is not None:
            if not isinstance(doc, dict):
                raise TypeError(f"{path}: YAML document is not an object")
            docs.append(doc)
    return docs


def _iter_yaml(root: Path) -> Iterable[tuple[Path, dict[str, Any]]]:
    for path in sorted(root.rglob("*.yaml")):
        for doc in _yaml_documents(path):
            yield path, doc


def _containers(doc: dict[str, Any]) -> list[dict[str, Any]]:
    kind = doc.get("kind")
    spec: dict[str, Any] | None = None
    if kind in {"Deployment", "StatefulSet", "DaemonSet", "ReplicaSet"}:
        spec = doc.get("spec", {}).get("template", {}).get("spec")
    elif kind == "Job":
        spec = doc.get("spec", {}).get("template", {}).get("spec")
    elif kind == "CronJob":
        spec = doc.get("spec", {}).get("jobTemplate", {}).get("spec", {}).get("template", {}).get("spec")
    elif kind == "Pod":
        spec = doc.get("spec")
    if not spec:
        return []
    return [*spec.get("initContainers", []), *spec.get("containers", [])]


def _pod_spec(doc: dict[str, Any]) -> dict[str, Any] | None:
    kind = doc.get("kind")
    if kind in {"Deployment", "StatefulSet", "DaemonSet", "ReplicaSet"}:
        return doc.get("spec", {}).get("template", {}).get("spec")
    if kind == "Job":
        return doc.get("spec", {}).get("template", {}).get("spec")
    if kind == "CronJob":
        return doc.get("spec", {}).get("jobTemplate", {}).get("spec", {}).get("template", {}).get("spec")
    if kind == "Pod":
        return doc.get("spec")
    return None


def validate_kubernetes(findings: list[Finding], release: bool) -> dict[str, int]:
    counts = {"documents": 0, "workloads": 0, "service_accounts": 0}
    service_accounts: set[str] = set()
    workload_accounts: set[str] = set()
    referenced_secrets: set[str] = set()
    kustomized_files: set[Path] = set()
    worker_deployments_seen: set[str] = set()

    for kustomization in K8S.rglob("kustomization.yaml"):
        data = _yaml_documents(kustomization)[0]
        for resource in data.get("resources", []):
            if isinstance(resource, str) and not resource.startswith(("http://", "https://")):
                resolved = (kustomization.parent / resource).resolve()
                if resolved.is_file():
                    kustomized_files.add(resolved)
                elif not resolved.exists():
                    _finding(findings, "error", "K8S_RESOURCE_MISSING", kustomization, f"resource does not exist: {resource}")

    for path, doc in _iter_yaml(K8S):
        counts["documents"] += 1
        metadata = doc.get("metadata", {})
        kind = doc.get("kind", "")
        if kind != "Namespace" and metadata.get("namespace") not in {None, EXPECTED_NAMESPACE}:
            _finding(findings, "error", "K8S_NAMESPACE_MISMATCH", path, f"expected {EXPECTED_NAMESPACE}, got {metadata.get('namespace')}")
        annotations = metadata.get("annotations", {}) or {}
        if "eks.amazonaws.com/role-arn" in annotations:
            _finding(findings, "error", "K8S_IRSA_FORBIDDEN", path, "AWS profile uses EKS Pod Identity, not IRSA annotations")
        if kind == "ServiceAccount":
            name = metadata.get("name")
            if name:
                service_accounts.add(name)
                counts["service_accounts"] += 1
        pod_spec = _pod_spec(doc)
        if pod_spec is None:
            continue
        for container in [*pod_spec.get("initContainers", []), *pod_spec.get("containers", [])]:
            env_names = [item.get("name") for item in container.get("env", []) if isinstance(item, dict) and item.get("name")]
            duplicates = sorted({name for name in env_names if env_names.count(name) > 1})
            if duplicates:
                _finding(
                    findings,
                    "error",
                    "K8S_DUPLICATE_ENVIRONMENT_KEY",
                    path,
                    f"container {container.get('name')} repeats environment keys: {duplicates}",
                )
            mount_paths = [item.get("mountPath") for item in container.get("volumeMounts", []) if item.get("mountPath")]
            duplicate_mounts = sorted({name for name in mount_paths if mount_paths.count(name) > 1})
            if duplicate_mounts:
                _finding(
                    findings,
                    "error",
                    "K8S_DUPLICATE_VOLUME_MOUNT",
                    path,
                    f"container {container.get('name')} repeats mount paths: {duplicate_mounts}",
                )
        counts["workloads"] += 1
        service_account = pod_spec.get("serviceAccountName")
        if not service_account:
            _finding(findings, "error", "K8S_SERVICE_ACCOUNT_MISSING", path, "workload has no explicit serviceAccountName")
        else:
            workload_accounts.add(service_account)
        workload_name = str(metadata.get("name", ""))
        if kind == "Deployment" and workload_name.startswith("worker-"):
            worker_deployments_seen.add(workload_name)
            manifest_name = workload_name.removeprefix("worker-")
            manifest = WORKER_MANIFESTS.get(manifest_name)
            if manifest is None:
                _finding(findings, "error", "K8S_WORKER_MANIFEST_UNKNOWN", path, f"no immutable manifest for {workload_name}")
            else:
                if service_account != workload_name:
                    _finding(findings, "error", "K8S_WORKER_IDENTITY_MISMATCH", path, f"{workload_name} must use its own service account")
                if pod_spec.get("automountServiceAccountToken") is not False:
                    _finding(findings, "error", "K8S_WORKER_TOKEN_AUTOMOUNT", path, "worker service-account token must not be automounted")
                containers = pod_spec.get("containers", [])
                if len(containers) != 1:
                    _finding(findings, "error", "K8S_WORKER_CONTAINER_COUNT", path, "worker deployment must have exactly one execution container")
                else:
                    container = containers[0]
                    expected_args = ["python", manifest["entrypoint"]]
                    if container.get("args") != expected_args:
                        _finding(findings, "error", "K8S_WORKER_ENTRYPOINT_DRIFT", path, f"expected {expected_args}, got {container.get('args')}")
                    env = {item.get("name"): item.get("value") for item in container.get("env", []) if isinstance(item, dict) and "value" in item}
                    expected_identity = manifest["workload_identity"]
                    if env.get("SIP_WORKLOAD_IDENTITY") != expected_identity:
                        _finding(findings, "error", "K8S_WORKER_WORKLOAD_IDENTITY_DRIFT", path, f"expected {expected_identity}")
                    if env.get("SIP_WORKER_MANIFEST_SHA256") != manifest["manifest_sha256"]:
                        _finding(findings, "error", "K8S_WORKER_MANIFEST_DIGEST_DRIFT", path, "runtime manifest digest differs from immutable source manifest")
                    if env.get("SIP_WORKER_PUBLICATION_PERMISSION") != "false":
                        _finding(findings, "error", "K8S_WORKER_RUNTIME_PUBLICATION_PERMISSION", path, "worker runtime must receive publication denial")
                    if env.get("SIP_WORKER_COMPUTE_NETWORK_ACCESS") != "denied":
                        _finding(findings, "error", "K8S_WORKER_RUNTIME_NETWORK_POLICY", path, "worker runtime must receive compute-network denial")
                    object_mounts = [mount for mount in container.get("volumeMounts", []) if mount.get("name") == "objects"]
                    if not object_mounts or object_mounts[0].get("readOnly") is not True:
                        _finding(findings, "error", "K8S_WORKER_EVIDENCE_MOUNT_WRITABLE", path, "worker evidence mount must be read-only")
                    runtime_mounts = [mount for mount in container.get("volumeMounts", []) if mount.get("mountPath") == "/var/lib/sip/runtime"]
                    volume_by_name = {volume.get("name"): volume for volume in pod_spec.get("volumes", [])}
                    if len(runtime_mounts) != 1:
                        _finding(findings, "error", "K8S_WORKER_STAGING_MOUNT_INVALID", path, "worker must have exactly one private runtime staging mount")
                    else:
                        runtime_volume = volume_by_name.get(runtime_mounts[0].get("name"), {})
                        if "emptyDir" not in runtime_volume:
                            _finding(findings, "error", "K8S_WORKER_STAGING_NOT_EPHEMERAL", path, "worker staging must be a pod-private emptyDir")
                        if runtime_mounts[0].get("readOnly") is True:
                            _finding(findings, "error", "K8S_WORKER_STAGING_READ_ONLY", path, "worker staging must be writable")
                    gpu_count = int(manifest.get("resource_limits", {}).get("gpu_count", 0))
                    gpu_limit = container.get("resources", {}).get("limits", {}).get("nvidia.com/gpu")
                    if gpu_count and str(gpu_limit) != str(gpu_count):
                        _finding(findings, "error", "K8S_WORKER_GPU_LIMIT_DRIFT", path, f"expected nvidia.com/gpu={gpu_count}")
                template_annotations = doc.get("spec", {}).get("template", {}).get("metadata", {}).get("annotations", {}) or {}
                if template_annotations.get("sip.platform/worker-manifest-sha256") != manifest["manifest_sha256"]:
                    _finding(findings, "error", "K8S_WORKER_ANNOTATION_DIGEST_DRIFT", path, "pod manifest annotation is stale")
                if template_annotations.get("sip.platform/publication-permission") != "denied":
                    _finding(findings, "error", "K8S_WORKER_PUBLICATION_PERMISSION", path, "worker must be explicitly denied publication")
                if template_annotations.get("sip.platform/network-during-compute") != "denied":
                    _finding(findings, "error", "K8S_WORKER_COMPUTE_NETWORK_POLICY", path, "worker computation network access must be denied")

        if pod_spec.get("hostNetwork") or pod_spec.get("hostPID") or pod_spec.get("hostIPC"):
            _finding(findings, "error", "K8S_HOST_NAMESPACE_FORBIDDEN", path, "host network/PID/IPC is forbidden")
        for env_from_owner in [*pod_spec.get("initContainers", []), *pod_spec.get("containers", [])]:
            for source in env_from_owner.get("envFrom", []):
                if "secretRef" in source:
                    referenced_secrets.add(source["secretRef"].get("name", ""))
        for container in _containers(doc):
            image = str(container.get("image", ""))
            if not image:
                _finding(findings, "error", "K8S_IMAGE_MISSING", path, f"container {container.get('name')} has no image")
            elif "ghcr.io/spatial-intelligence-platform/" in image:
                if f"@sha256:{ZERO_DIGEST}" in image:
                    severity = "error" if release else "warning"
                    _finding(findings, severity, "K8S_IMAGE_SENTINEL", path, "application image digest has not been replaced by CI")
                elif "@sha256:" not in image and release:
                    _finding(findings, "error", "K8S_IMAGE_UNPINNED", path, f"release application image is not digest-pinned: {image}")
            elif "@sha256:" not in image:
                _finding(findings, "error", "K8S_DEPENDENCY_IMAGE_UNPINNED", path, f"dependency image is not digest-pinned: {image}")
            security = container.get("securityContext", {})
            if security.get("allowPrivilegeEscalation") is not False:
                _finding(findings, "error", "K8S_PRIVILEGE_ESCALATION", path, f"container {container.get('name')} must deny privilege escalation")
            dropped = set(security.get("capabilities", {}).get("drop", []))
            if "ALL" not in dropped:
                _finding(findings, "error", "K8S_CAPABILITIES_NOT_DROPPED", path, f"container {container.get('name')} must drop ALL capabilities")
            if security.get("seccompProfile", {}).get("type") != "RuntimeDefault":
                _finding(findings, "error", "K8S_SECCOMP_MISSING", path, f"container {container.get('name')} must use RuntimeDefault seccomp")
            resources = container.get("resources", {})
            if not resources.get("requests") or not resources.get("limits"):
                _finding(findings, "error", "K8S_RESOURCES_MISSING", path, f"container {container.get('name')} lacks requests/limits")

    missing_worker_deployments = WORKER_SERVICE_ACCOUNTS - worker_deployments_seen
    unexpected_worker_deployments = worker_deployments_seen - WORKER_SERVICE_ACCOUNTS
    if missing_worker_deployments:
        _finding(findings, "error", "K8S_WORKER_DEPLOYMENTS_MISSING", K8S, f"missing: {sorted(missing_worker_deployments)}")
    if unexpected_worker_deployments:
        _finding(findings, "error", "K8S_WORKER_DEPLOYMENTS_UNDECLARED", K8S, f"undeclared: {sorted(unexpected_worker_deployments)}")
    unexpected_worker_accounts = {name for name in service_accounts if name.startswith("worker-")} - WORKER_SERVICE_ACCOUNTS
    if unexpected_worker_accounts:
        _finding(findings, "error", "K8S_WORKER_SERVICE_ACCOUNTS_UNDECLARED", K8S, f"undeclared: {sorted(unexpected_worker_accounts)}")

    missing_accounts = REQUIRED_SERVICE_ACCOUNTS - service_accounts
    extra_workload_accounts = workload_accounts - service_accounts
    if missing_accounts:
        _finding(findings, "error", "K8S_REQUIRED_SERVICE_ACCOUNTS_MISSING", K8S, f"missing: {sorted(missing_accounts)}")
    if extra_workload_accounts:
        _finding(findings, "error", "K8S_WORKLOAD_ACCOUNT_UNDECLARED", K8S, f"undeclared: {sorted(extra_workload_accounts)}")
    if "sip-runtime-secrets" not in referenced_secrets:
        _finding(findings, "error", "K8S_RUNTIME_SECRET_NOT_REFERENCED", K8S, "workloads do not reference sip-runtime-secrets")
    example = (K8S / "base/runtime-secrets.example.yaml").resolve()
    if example in kustomized_files:
        _finding(findings, "error", "K8S_EXAMPLE_SECRET_APPLIED", example, "example secret must never be included in Kustomize")

    aws_config = K8S / "overlays/aws/aws-config.patch.yaml"
    if release and aws_config.exists():
        text = aws_config.read_text(encoding="utf-8")
        if "REPLACE_WITH_" in text:
            _finding(findings, "error", "K8S_AWS_OUTPUT_PLACEHOLDER", aws_config, "Terraform outputs have not been rendered into the release overlay")
    return counts


def validate_compose(findings: list[Finding], release: bool) -> dict[str, int]:
    del release  # Local application images are built from this repository.
    data = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        _finding(findings, "error", "COMPOSE_INVALID", COMPOSE, "root must be a mapping")
        return {"services": 0, "images": 0, "workers": 0}
    services = data.get("services", {})
    networks = data.get("networks", {})
    counts = {"services": len(services), "images": 0, "workers": 0}
    if not networks.get("backend", {}).get("internal"):
        _finding(findings, "error", "COMPOSE_BACKEND_NOT_INTERNAL", COMPOSE, "backend network must be internal")

    application_services = API_SERVICE_ACCOUNTS | WORKER_SERVICE_ACCOUNTS | {"migrate", "web"}
    compose_workers = {name for name in services if name.startswith("worker-")}
    counts["workers"] = len(compose_workers)
    missing_workers = WORKER_SERVICE_ACCOUNTS - compose_workers
    unexpected_workers = compose_workers - WORKER_SERVICE_ACCOUNTS
    if missing_workers:
        _finding(findings, "error", "COMPOSE_WORKERS_MISSING", COMPOSE, f"missing: {sorted(missing_workers)}")
    if unexpected_workers:
        _finding(findings, "error", "COMPOSE_WORKERS_UNDECLARED", COMPOSE, f"undeclared: {sorted(unexpected_workers)}")

    worker_runtime_sources: dict[str, str] = {}
    declared_volumes = set((data.get("volumes") or {}).keys())

    def compose_mount_parts(value: object) -> tuple[str, str, set[str]] | None:
        if not isinstance(value, str):
            return None
        parts = value.split(":")
        if len(parts) < 2:
            return None
        source, target = parts[0], parts[1]
        modes = set(parts[2].split(",")) if len(parts) > 2 else set()
        return source, target, modes

    for name, service in services.items():
        image = service.get("image")
        if image:
            counts["images"] += 1
            if name not in application_services and name != "object-store-init" and "@sha256:" not in image:
                _finding(findings, "error", "COMPOSE_DEPENDENCY_IMAGE_UNPINNED", COMPOSE, f"{name} image is not digest-pinned: {image}")
        for port in service.get("ports", []) or []:
            rendered = str(port)
            if not rendered.startswith(("127.0.0.1:", "${SIP_API_BIND:-127.0.0.1}:")):
                _finding(findings, "error", "COMPOSE_NON_LOOPBACK_PORT", COMPOSE, f"{name} exposes a non-loopback host port: {rendered}")
        if name not in {"postgres", "valkey", "valkey-config", "minio", "web", "object-store-init"}:
            if service.get("read_only") is not True:
                _finding(findings, "error", "COMPOSE_READ_ONLY_MISSING", COMPOSE, f"{name} must use a read-only root filesystem")
            if "ALL" not in set(service.get("cap_drop", [])):
                _finding(findings, "error", "COMPOSE_CAPABILITIES_NOT_DROPPED", COMPOSE, f"{name} must drop ALL capabilities")
        secrets = set(service.get("secrets", []) or [])
        if name in application_services - {"web"} and "sip_master_key_b64" not in secrets:
            _finding(findings, "error", "COMPOSE_SECRET_MISSING", COMPOSE, f"{name} does not receive the runtime encryption key secret")
        if name != "minio" and {"sip_minio_root_user", "sip_minio_root_password"} & secrets:
            _finding(findings, "error", "COMPOSE_MINIO_ADMIN_SECRET_EXPOSED", COMPOSE, f"{name} receives MinIO administrator credentials")

        if name in WORKER_SERVICE_ACCOUNTS:
            manifest_name = name.removeprefix("worker-")
            manifest = WORKER_MANIFESTS[manifest_name]
            if service.get("command") != ["python", manifest["entrypoint"]]:
                _finding(findings, "error", "COMPOSE_WORKER_ENTRYPOINT_DRIFT", COMPOSE, f"{name} entrypoint does not match immutable manifest")
            environment = service.get("environment", {}) or {}
            expected = {
                "SIP_WORKLOAD_IDENTITY": manifest["workload_identity"],
                "SIP_WORKER_MANIFEST_SHA256": manifest["manifest_sha256"],
                "SIP_WORKER_PUBLICATION_PERMISSION": "false",
                "SIP_WORKER_COMPUTE_NETWORK_ACCESS": "denied",
            }
            for key, value in expected.items():
                if environment.get(key) != value:
                    _finding(findings, "error", "COMPOSE_WORKER_ENV_DRIFT", COMPOSE, f"{name} {key} must be {value}")
            if any("--capability" in str(item) for item in service.get("command", [])):
                _finding(findings, "error", "COMPOSE_WORKER_CAPABILITY_OVERRIDE", COMPOSE, f"{name} overrides immutable capabilities")
            parsed_mounts = [
                parsed
                for item in service.get("volumes", []) or []
                if (parsed := compose_mount_parts(item)) is not None
            ]
            object_mounts = [item for item in parsed_mounts if item[1] == "/var/lib/sip/objects"]
            if len(object_mounts) != 1 or "ro" not in object_mounts[0][2]:
                _finding(findings, "error", "COMPOSE_WORKER_EVIDENCE_MOUNT_WRITABLE", COMPOSE, f"{name} evidence mount must be unique and read-only")
            runtime_mounts = [item for item in parsed_mounts if item[1] == "/var/lib/sip/runtime"]
            expected_runtime_source = f"{name}-runtime"
            if len(runtime_mounts) != 1 or runtime_mounts[0][0] != expected_runtime_source:
                _finding(
                    findings,
                    "error",
                    "COMPOSE_WORKER_STAGING_NOT_PRIVATE",
                    COMPOSE,
                    f"{name} must use its private {expected_runtime_source} staging volume",
                )
            else:
                worker_runtime_sources[name] = runtime_mounts[0][0]
                if runtime_mounts[0][0] not in declared_volumes:
                    _finding(findings, "error", "COMPOSE_WORKER_STAGING_UNDECLARED", COMPOSE, f"{name} staging volume is not declared")
                if "ro" in runtime_mounts[0][2]:
                    _finding(findings, "error", "COMPOSE_WORKER_STAGING_READ_ONLY", COMPOSE, f"{name} staging volume must be writable")
            if not service.get("mem_limit") or not service.get("cpus"):
                _finding(findings, "error", "COMPOSE_WORKER_RESOURCE_LIMIT_MISSING", COMPOSE, f"{name} lacks CPU or memory limits")

    duplicate_staging = {
        source: sorted(name for name, candidate in worker_runtime_sources.items() if candidate == source)
        for source in set(worker_runtime_sources.values())
        if sum(candidate == source for candidate in worker_runtime_sources.values()) > 1
    }
    if duplicate_staging:
        _finding(findings, "error", "COMPOSE_WORKER_STAGING_SHARED", COMPOSE, f"worker staging volumes are shared: {duplicate_staging}")

    common_env = data.get("x-common-environment", {})
    if common_env.get("SIP_OBJECT_STORE_BACKEND") != "${SIP_OBJECT_STORE_BACKEND:-local}":
        _finding(findings, "error", "COMPOSE_OBJECT_BACKEND_NOT_EXPLICIT", COMPOSE, "default object-store backend must be explicitly local")
    if "SIP_MULTIPART_ROOT" not in common_env:
        _finding(findings, "error", "COMPOSE_MULTIPART_ROOT_MISSING", COMPOSE, "multipart root is not configured")
    return counts


def _balanced_hcl(text: str) -> bool:
    # Remove quoted strings and comments before a conservative brace check.
    scrubbed = re.sub(r'"(?:\\.|[^"\\])*"', '""', text)
    scrubbed = re.sub(r"#.*$|//.*$", "", scrubbed, flags=re.MULTILINE)
    depth = 0
    for char in scrubbed:
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _terraform_set(text: str, name: str) -> set[str]:
    match = re.search(rf"{re.escape(name)}\s*=\s*toset\(\[(.*?)\]\)", text, re.S)
    if not match:
        return set()
    return set(re.findall(r'"([a-z0-9-]+)"', match.group(1)))


def validate_terraform(findings: list[Finding], release: bool) -> dict[str, int]:
    tf_files = sorted(TERRAFORM.rglob("*.tf"))
    counts = {"files": len(tf_files), "resources": 0}
    combined = "\n".join(path.read_text(encoding="utf-8") for path in tf_files)
    for path in tf_files:
        text = path.read_text(encoding="utf-8")
        if not _balanced_hcl(text):
            _finding(findings, "error", "TERRAFORM_UNBALANCED_HCL", path, "conservative brace validation failed")
        counts["resources"] += len(re.findall(r'(?m)^resource\s+"', text))
        if re.search(r'(?m)^\s*(access_key|secret_key)\s*=\s*"[^$]', text):
            _finding(findings, "error", "TERRAFORM_STATIC_CREDENTIAL", path, "static cloud credential appears in Terraform source")
    required_pins = [
        'required_version = "= 1.15.5"',
        'version = "= 6.55.0"',
    ]
    for pin in required_pins:
        if pin not in combined:
            _finding(findings, "error", "TERRAFORM_VERSION_PIN_MISSING", TERRAFORM, f"missing exact pin: {pin}")
    required_controls = [
        "aws_eks_pod_identity_association",
        "object_lock_enabled = true",
        "storage_encrypted",
        "deletion_protection",
        "manage_master_user_password",
        "prevent_destroy",
        "scan_on_push",
        "image_tag_mutability = \"IMMUTABLE\"",
    ]
    for token in required_controls:
        if token not in combined:
            _finding(findings, "error", "TERRAFORM_CONTROL_MISSING", TERRAFORM, f"required control is absent: {token}")

    locals_text = (TERRAFORM / "modules/aws-platform/locals.tf").read_text(encoding="utf-8")
    tf_api = _terraform_set(locals_text, "api_service_accounts")
    tf_workers = _terraform_set(locals_text, "worker_service_accounts")
    tf_migrators = _terraform_set(locals_text, "migration_service_accounts")
    if tf_api != API_SERVICE_ACCOUNTS:
        _finding(findings, "error", "TERRAFORM_API_IDENTITY_DRIFT", TERRAFORM, f"Terraform APIs differ: {sorted(tf_api ^ API_SERVICE_ACCOUNTS)}")
    if tf_workers != WORKER_SERVICE_ACCOUNTS:
        _finding(findings, "error", "TERRAFORM_WORKER_IDENTITY_DRIFT", TERRAFORM, f"Terraform workers differ: {sorted(tf_workers ^ WORKER_SERVICE_ACCOUNTS)}")
    if tf_migrators != {"sip-migrator"}:
        _finding(findings, "error", "TERRAFORM_MIGRATOR_IDENTITY_DRIFT", TERRAFORM, f"Terraform migrators differ: {sorted(tf_migrators)}")
    iam = (TERRAFORM / "modules/aws-platform/iam.tf").read_text(encoding="utf-8")
    if 'namespace       = var.kubernetes_namespace' not in iam:
        _finding(findings, "error", "TERRAFORM_NAMESPACE_NOT_PARAMETERIZED", TERRAFORM, "Pod Identity namespace is not parameterized")
    variables = (TERRAFORM / "modules/aws-platform/variables.tf").read_text(encoding="utf-8")
    if 'default     = "sip-system"' not in variables:
        _finding(findings, "error", "TERRAFORM_NAMESPACE_DEFAULT_DRIFT", TERRAFORM, "module namespace default must be sip-system")
    if release:
        example = TERRAFORM / "profiles/aws/terraform.tfvars.example"
        if example.exists() and "REPLACE_WITH_" in example.read_text(encoding="utf-8"):
            _finding(findings, "warning", "TERRAFORM_EXAMPLE_PLACEHOLDERS", example, "example variables intentionally contain placeholders; a release plan must use a separate reviewed tfvars file")
    return counts


def validate_entrypoint(findings: list[Finding]) -> dict[str, int]:
    path = ROOT / "infrastructure/containers/entrypoint.sh"
    text = path.read_text(encoding="utf-8")
    for secret in ["SIP_MASTER_KEY_B64", "SIP_SIGNING_KEY_B64", "SIP_POSTGRES_PASSWORD", "SIP_VALKEY_PASSWORD"]:
        if f"read_secret {secret}" not in text:
            _finding(findings, "error", "ENTRYPOINT_SECRET_NOT_READ", path, f"{secret} is not loaded from a mounted secret")
    if "postgresql+psycopg://" not in text or "redis://:" not in text:
        _finding(findings, "error", "ENTRYPOINT_CONNECTION_URL_MISSING", path, "database/cache URLs are not assembled from secrets")
    return {"secret_reads": text.count("read_secret ") - 1}


def run(*, release: bool = False) -> dict[str, Any]:
    findings: list[Finding] = []
    counts = {
        "kubernetes": validate_kubernetes(findings, release),
        "compose": validate_compose(findings, release),
        "terraform": validate_terraform(findings, release),
        "entrypoint": validate_entrypoint(findings),
    }
    errors = sum(item.severity == "error" for item in findings)
    warnings = sum(item.severity == "warning" for item in findings)
    return {
        "status": ("failed" if errors else ("blocked" if release else "passed_with_external_gaps")),
        "mode": "release" if release else "structural",
        "errors": errors,
        "warnings": warnings,
        "counts": counts,
        "findings": [asdict(item) for item in findings],
        "external_validation_required": [
            "terraform init/validate/plan against the target account",
            "kubectl/kustomize server-side dry-run against the target cluster version",
            "docker compose build and health rehearsal",
            "managed PostgreSQL, Valkey, KMS, S3, and backup/restore integration",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", action="store_true", help="fail on unreplaced application digests and deployment placeholders")
    parser.add_argument("--output", type=Path, default=ROOT / "build/reports/infrastructure-validation.json")
    args = parser.parse_args()
    report = run(release=args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["status"] == "passed_with_external_gaps" else 1)


if __name__ == "__main__":
    main()
