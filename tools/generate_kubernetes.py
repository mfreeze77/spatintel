#!/usr/bin/env python3
"""Generate deterministic, production-shaped Kubernetes manifests for SIP.

The generator is authoritative for infrastructure/kubernetes.  It deliberately
uses an impossible all-zero image digest until CI substitutes a built and signed
release digest.  Secrets are never generated into source control.
"""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
K8S_ROOT = ROOT / "infrastructure/kubernetes"
BASE = K8S_ROOT / "base"
OVERLAYS = K8S_ROOT / "overlays"
NAMESPACE = "sip-system"
VERSION = "1.1.0"
SENTINEL_DIGEST = "0" * 64
PYTHON_IMAGE = f"ghcr.io/spatial-intelligence-platform/sip-python:{VERSION}@sha256:{SENTINEL_DIGEST}"
WEB_IMAGE = f"ghcr.io/spatial-intelligence-platform/sip-web:{VERSION}@sha256:{SENTINEL_DIGEST}"

API_SERVICES = [
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
    "representation-api",
    "provider-registry",
    "representation-publisher",
]
def load_workers() -> dict[str, dict[str, Any]]:
    workers: dict[str, dict[str, Any]] = {}
    for path in sorted((ROOT / "workers").glob("*/worker-manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        deployment_name = f"worker-{manifest['name']}"
        workers[deployment_name] = {
            "service_account": deployment_name,
            "entrypoint": manifest["entrypoint"],
            "workload_identity": manifest["workload_identity"],
            "manifest_sha256": manifest["manifest_sha256"],
            "capabilities": manifest["capabilities"],
            "resource_limits": manifest["resource_limits"],
        }
    if not workers:
        raise RuntimeError("no immutable worker manifests found")
    return workers


WORKERS = load_workers()
SERVICE_ACCOUNTS = [*API_SERVICES, *sorted(WORKERS), "sip-migrator", "sip-web"]


def dump(path: Path, *docs: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump_all(docs, sort_keys=False), encoding="utf-8")


def labels(component: str, name: str) -> dict[str, str]:
    return {
        "app.kubernetes.io/name": name,
        "app.kubernetes.io/part-of": "spatial-intelligence-platform",
        "app.kubernetes.io/component": component,
        "app.kubernetes.io/version": VERSION,
    }


def security_context() -> dict[str, Any]:
    return {
        "allowPrivilegeEscalation": False,
        "readOnlyRootFilesystem": True,
        "runAsNonRoot": True,
        "runAsUser": 10001,
        "runAsGroup": 10001,
        "capabilities": {"drop": ["ALL"]},
        "seccompProfile": {"type": "RuntimeDefault"},
    }


def pod_security_context() -> dict[str, Any]:
    return {
        "runAsNonRoot": True,
        "runAsUser": 10001,
        "runAsGroup": 10001,
        "fsGroup": 10001,
        "fsGroupChangePolicy": "OnRootMismatch",
        "seccompProfile": {"type": "RuntimeDefault"},
    }


def env_from() -> list[dict[str, Any]]:
    return [
        {"configMapRef": {"name": "sip-runtime-config"}},
        {"secretRef": {"name": "sip-runtime-secrets"}},
    ]


def runtime_volumes(size: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mounts = [
        {"name": "tmp", "mountPath": "/tmp"},
        {"name": "runtime", "mountPath": "/var/lib/sip/runtime"},
        {"name": "objects", "mountPath": "/var/lib/sip/objects"},
    ]
    volumes = [
        {"name": "tmp", "emptyDir": {"sizeLimit": "256Mi"}},
        {"name": "runtime", "emptyDir": {"sizeLimit": size}},
        {"name": "objects", "emptyDir": {"sizeLimit": size}},
    ]
    return mounts, volumes


def api_deployment(name: str) -> dict[str, Any]:
    pod_labels = labels("api", name)
    replicas = 2 if name in {"control-api", "identity-policy", "scene-service", "evidence-service"} else 1
    mounts, volumes = runtime_volumes("2Gi")
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": name, "namespace": NAMESPACE, "labels": pod_labels},
        "spec": {
            "replicas": replicas,
            "revisionHistoryLimit": 5,
            "strategy": {"type": "RollingUpdate", "rollingUpdate": {"maxUnavailable": 0, "maxSurge": 1}},
            "selector": {"matchLabels": {"app.kubernetes.io/name": name}},
            "template": {
                "metadata": {
                    "labels": pod_labels,
                    "annotations": {
                        "prometheus.io/scrape": "true",
                        "prometheus.io/port": "8080",
                        "prometheus.io/path": "/metrics",
                    },
                },
                "spec": {
                    "serviceAccountName": name,
                    "automountServiceAccountToken": True,
                    "securityContext": pod_security_context(),
                    "terminationGracePeriodSeconds": 30,
                    "topologySpreadConstraints": [
                        {
                            "maxSkew": 1,
                            "topologyKey": "kubernetes.io/hostname",
                            "whenUnsatisfiable": "ScheduleAnyway",
                            "labelSelector": {"matchLabels": {"app.kubernetes.io/name": name}},
                        }
                    ],
                    "containers": [
                        {
                            "name": "api",
                            "image": PYTHON_IMAGE,
                            "imagePullPolicy": "IfNotPresent",
                            "args": [
                                "uvicorn",
                                "sip.api:app",
                                "--host",
                                "0.0.0.0",
                                "--port",
                                "8080",
                                "--proxy-headers",
                                "--no-server-header",
                            ],
                            "env": [{"name": "SIP_SERVICE_NAME", "value": name}],
                            "envFrom": env_from(),
                            "ports": [{"name": "http", "containerPort": 8080, "protocol": "TCP"}],
                            "securityContext": security_context(),
                            "resources": {
                                "requests": {"cpu": "100m", "memory": "256Mi"},
                                "limits": {"cpu": "2", "memory": "2Gi"},
                            },
                            "startupProbe": {
                                "httpGet": {"path": "/health/live", "port": "http"},
                                "failureThreshold": 30,
                                "periodSeconds": 2,
                            },
                            "livenessProbe": {
                                "httpGet": {"path": "/health/live", "port": "http"},
                                "periodSeconds": 15,
                                "timeoutSeconds": 3,
                            },
                            "readinessProbe": {
                                "httpGet": {"path": "/health/ready", "port": "http"},
                                "periodSeconds": 5,
                                "timeoutSeconds": 3,
                            },
                            "volumeMounts": mounts,
                        }
                    ],
                    "volumes": volumes,
                },
            },
        },
    }


def service(name: str, component: str = "api", port: int = 8080) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": name, "namespace": NAMESPACE, "labels": labels(component, name)},
        "spec": {
            "type": "ClusterIP",
            "selector": {"app.kubernetes.io/name": name},
            "ports": [{"name": "http", "port": port, "targetPort": "http"}],
        },
    }


def _memory_quantity(byte_count: int) -> str:
    gib = max(1, math.ceil(byte_count / (1024**3)))
    return f"{gib}Gi"


def worker_deployment(name: str, config: dict[str, Any]) -> dict[str, Any]:
    pod_labels = labels("worker", name)
    limits = config["resource_limits"]
    memory_limit = _memory_quantity(int(limits["max_memory_bytes"]))
    ephemeral_limit = _memory_quantity(max(int(limits["max_output_bytes"]), 1024**3))
    cpu_limit = max(1, min(16, math.ceil(int(limits["max_cpu_seconds"]) / max(1, int(limits["max_wall_seconds"])) * 4)))
    resources: dict[str, Any] = {
        "requests": {"cpu": "250m", "memory": "512Mi", "ephemeral-storage": "1Gi"},
        "limits": {"cpu": str(cpu_limit), "memory": memory_limit, "ephemeral-storage": ephemeral_limit},
    }
    if int(limits.get("gpu_count", 0)):
        resources["limits"]["nvidia.com/gpu"] = str(limits["gpu_count"])
        resources["requests"]["nvidia.com/gpu"] = str(limits["gpu_count"])
    mounts, volumes = runtime_volumes(ephemeral_limit)
    # Workers may read immutable evidence but never mutate the evidence mount.
    # All handler outputs are staged under the separate runtime volume and only
    # the representation publisher can bind an approved candidate to a scene.
    for mount in mounts:
        if mount.get("name") == "objects":
            mount["readOnly"] = True
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": name, "namespace": NAMESPACE, "labels": pod_labels},
        "spec": {
            "replicas": 1,
            "revisionHistoryLimit": 3,
            "strategy": {"type": "Recreate"},
            "selector": {"matchLabels": {"app.kubernetes.io/name": name}},
            "template": {
                "metadata": {
                    "labels": pod_labels,
                    "annotations": {
                        "sip.platform/worker-manifest-sha256": config["manifest_sha256"],
                        "sip.platform/publication-permission": "denied",
                        "sip.platform/network-during-compute": "denied",
                        "prometheus.io/scrape": "true",
                        "prometheus.io/port": "9100",
                        "prometheus.io/path": "/metrics",
                    },
                },
                "spec": {
                    "serviceAccountName": config["service_account"],
                    "automountServiceAccountToken": False,
                    "securityContext": pod_security_context(),
                    "terminationGracePeriodSeconds": 60,
                    "containers": [
                        {
                            "name": "worker",
                            "image": PYTHON_IMAGE,
                            "imagePullPolicy": "IfNotPresent",
                            "args": ["python", config["entrypoint"]],
                            "env": [
                                {"name": "SIP_WORKER_ID", "valueFrom": {"fieldRef": {"fieldPath": "metadata.name"}}},
                                {"name": "SIP_WORKLOAD_IDENTITY", "value": config["workload_identity"]},
                                {"name": "SIP_WORKER_MANIFEST_SHA256", "value": config["manifest_sha256"]},
                                {"name": "SIP_WORKER_PUBLICATION_PERMISSION", "value": "false"},
                                {"name": "SIP_WORKER_COMPUTE_NETWORK_ACCESS", "value": "denied"},
                                {"name": "SIP_WORKER_METRICS_PORT", "value": "9100"},
                            ],
                            "envFrom": env_from(),
                            "ports": [{"name": "metrics", "containerPort": 9100}],
                            "securityContext": security_context(),
                            "resources": resources,
                            "volumeMounts": mounts,
                        }
                    ],
                    "volumes": volumes,
                },
            },
        },
    }

def web_deployment() -> dict[str, Any]:
    pod_labels = labels("web", "web")
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "web", "namespace": NAMESPACE, "labels": pod_labels},
        "spec": {
            "replicas": 2,
            "revisionHistoryLimit": 5,
            "selector": {"matchLabels": {"app.kubernetes.io/name": "web"}},
            "template": {
                "metadata": {"labels": pod_labels},
                "spec": {
                    "serviceAccountName": "sip-web",
                    "automountServiceAccountToken": False,
                    "securityContext": pod_security_context(),
                    "containers": [
                        {
                            "name": "web",
                            "image": WEB_IMAGE,
                            "imagePullPolicy": "IfNotPresent",
                            "env": [{"name": "SIP_INTERNAL_API_BASE", "value": "http://control-api:8080"}],
                            "ports": [{"name": "http", "containerPort": 3000}],
                            "securityContext": security_context(),
                            "resources": {
                                "requests": {"cpu": "100m", "memory": "256Mi"},
                                "limits": {"cpu": "1", "memory": "1Gi"},
                            },
                            "livenessProbe": {"httpGet": {"path": "/api/health", "port": "http"}, "periodSeconds": 15},
                            "readinessProbe": {"httpGet": {"path": "/api/health", "port": "http"}, "periodSeconds": 5},
                            "volumeMounts": [{"name": "tmp", "mountPath": "/tmp"}],
                        }
                    ],
                    "volumes": [{"name": "tmp", "emptyDir": {"sizeLimit": "128Mi"}}],
                },
            },
        },
    }


def migration_job() -> dict[str, Any]:
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": "sip-migrate", "namespace": NAMESPACE, "labels": labels("migration", "sip-migrate")},
        "spec": {
            "backoffLimit": 3,
            "ttlSecondsAfterFinished": 86400,
            "template": {
                "metadata": {"labels": labels("migration", "sip-migrate")},
                "spec": {
                    "restartPolicy": "OnFailure",
                    "serviceAccountName": "sip-migrator",
                    "automountServiceAccountToken": True,
                    "securityContext": pod_security_context(),
                    "containers": [
                        {
                            "name": "migrate",
                            "image": PYTHON_IMAGE,
                            "args": ["alembic", "upgrade", "head"],
                            "envFrom": env_from(),
                            "securityContext": security_context(),
                            "resources": {
                                "requests": {"cpu": "100m", "memory": "256Mi"},
                                "limits": {"cpu": "1", "memory": "1Gi"},
                            },
                            "volumeMounts": [{"name": "tmp", "mountPath": "/tmp"}],
                        }
                    ],
                    "volumes": [{"name": "tmp", "emptyDir": {"sizeLimit": "128Mi"}}],
                },
            },
        },
    }


def network_policies() -> list[dict[str, Any]]:
    app_selector = {
        "matchExpressions": [
            {"key": "app.kubernetes.io/component", "operator": "In", "values": ["api", "worker", "migration"]}
        ]
    }
    return [
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": "default-deny", "namespace": NAMESPACE},
            "spec": {"podSelector": {}, "policyTypes": ["Ingress", "Egress"]},
        },
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": "allow-dns", "namespace": NAMESPACE},
            "spec": {
                "podSelector": {},
                "policyTypes": ["Egress"],
                "egress": [
                    {
                        "to": [{"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kube-system"}}}],
                        "ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}],
                    }
                ],
            },
        },
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": "web-to-control-api", "namespace": NAMESPACE},
            "spec": {
                "podSelector": {"matchLabels": {"app.kubernetes.io/name": "control-api"}},
                "policyTypes": ["Ingress"],
                "ingress": [
                    {
                        "from": [{"podSelector": {"matchLabels": {"app.kubernetes.io/name": "web"}}}],
                        "ports": [{"protocol": "TCP", "port": 8080}],
                    }
                ],
            },
        },
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": "platform-internal-api", "namespace": NAMESPACE},
            "spec": {
                "podSelector": {"matchLabels": {"app.kubernetes.io/component": "api"}},
                "policyTypes": ["Ingress"],
                "ingress": [
                    {
                        "from": [
                            {
                                "podSelector": {
                                    "matchExpressions": [
                                        {
                                            "key": "app.kubernetes.io/component",
                                            "operator": "In",
                                            "values": ["api", "worker", "migration"],
                                        }
                                    ]
                                }
                            }
                        ],
                        "ports": [{"protocol": "TCP", "port": 8080}],
                    }
                ],
            },
        },
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": "observability-scrape", "namespace": NAMESPACE},
            "spec": {
                "podSelector": {
                    "matchExpressions": [
                        {"key": "app.kubernetes.io/component", "operator": "In", "values": ["api", "worker"]}
                    ]
                },
                "policyTypes": ["Ingress"],
                "ingress": [
                    {
                        "from": [
                            {
                                "namespaceSelector": {
                                    "matchLabels": {"kubernetes.io/metadata.name": "sip-observability"}
                                }
                            }
                        ],
                        "ports": [
                            {"protocol": "TCP", "port": 8080},
                            {"protocol": "TCP", "port": 9100},
                        ],
                    }
                ],
            },
        },
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": "application-to-local-dependencies", "namespace": NAMESPACE},
            "spec": {
                "podSelector": app_selector,
                "policyTypes": ["Egress"],
                "egress": [
                    {
                        "to": [{"podSelector": {"matchLabels": {"app.kubernetes.io/name": "postgres"}}}],
                        "ports": [{"protocol": "TCP", "port": 5432}],
                    },
                    {
                        "to": [{"podSelector": {"matchLabels": {"app.kubernetes.io/name": "valkey"}}}],
                        "ports": [{"protocol": "TCP", "port": 6379}],
                    },
                ],
            },
        },
    ]


def availability_resources() -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for name in ["control-api", "identity-policy", "scene-service", "evidence-service", "web"]:
        docs.append(
            {
                "apiVersion": "policy/v1",
                "kind": "PodDisruptionBudget",
                "metadata": {"name": name, "namespace": NAMESPACE},
                "spec": {"maxUnavailable": 1, "selector": {"matchLabels": {"app.kubernetes.io/name": name}}},
            }
        )
    docs.append(
        {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {"name": "control-api", "namespace": NAMESPACE},
            "spec": {
                "scaleTargetRef": {"apiVersion": "apps/v1", "kind": "Deployment", "name": "control-api"},
                "minReplicas": 2,
                "maxReplicas": 10,
                "behavior": {"scaleDown": {"stabilizationWindowSeconds": 300}},
                "metrics": [
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "cpu",
                            "target": {"type": "Utilization", "averageUtilization": 65},
                        },
                    }
                ],
            },
        }
    )
    return docs


def local_dependencies() -> list[dict[str, Any]]:
    postgis_image = "postgis/postgis:18-3.6@sha256:f248a10d133f63d01aefab324f3462d7e1002e9cc1b65c6585626f6cb7a3d85c"
    valkey_image = "valkey/valkey:9.1.1-alpine3.24@sha256:ee91f7a174ac4d6a6b0685b3a60e321f0a9dbbb691f9b0e285be2ba1d1be8328"
    dependency_security = {
        "allowPrivilegeEscalation": False,
        "capabilities": {"drop": ["ALL"]},
        "seccompProfile": {"type": "RuntimeDefault"},
    }
    return [
        {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {"name": "sip-local-dependency", "namespace": NAMESPACE},
            "automountServiceAccountToken": False,
        },
        {
            "apiVersion": "apps/v1",
            "kind": "StatefulSet",
            "metadata": {"name": "postgres", "namespace": NAMESPACE},
            "spec": {
                "serviceName": "postgres",
                "replicas": 1,
                "selector": {"matchLabels": {"app.kubernetes.io/name": "postgres"}},
                "template": {
                    "metadata": {
                        "labels": {
                            "app.kubernetes.io/name": "postgres",
                            "app.kubernetes.io/component": "database",
                        }
                    },
                    "spec": {
                        "serviceAccountName": "sip-local-dependency",
                        "automountServiceAccountToken": False,
                        "securityContext": {"fsGroup": 999, "fsGroupChangePolicy": "OnRootMismatch"},
                        "containers": [
                            {
                                "name": "postgres",
                                "image": postgis_image,
                                "ports": [{"name": "postgres", "containerPort": 5432}],
                                "env": [
                                    {"name": "POSTGRES_DB", "value": "sip"},
                                    {"name": "POSTGRES_USER", "value": "sip"},
                                    {
                                        "name": "POSTGRES_PASSWORD",
                                        "valueFrom": {
                                            "secretKeyRef": {"name": "sip-runtime-secrets", "key": "POSTGRES_PASSWORD"}
                                        },
                                    },
                                    {
                                        "name": "POSTGRES_INITDB_ARGS",
                                        "value": "--data-checksums --auth-host=scram-sha-256 --auth-local=peer",
                                    },
                                ],
                                "securityContext": dependency_security,
                                "volumeMounts": [{"name": "data", "mountPath": "/var/lib/postgresql"}],
                                "resources": {
                                    "requests": {"cpu": "250m", "memory": "512Mi"},
                                    "limits": {"cpu": "2", "memory": "4Gi"},
                                },
                                "readinessProbe": {
                                    "exec": {"command": ["pg_isready", "-U", "sip", "-d", "sip"]},
                                    "periodSeconds": 5,
                                },
                            }
                        ],
                    },
                },
                "volumeClaimTemplates": [
                    {
                        "metadata": {"name": "data"},
                        "spec": {
                            "accessModes": ["ReadWriteOnce"],
                            "resources": {"requests": {"storage": "20Gi"}},
                        },
                    }
                ],
            },
        },
        {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": "postgres", "namespace": NAMESPACE},
            "spec": {
                "clusterIP": "None",
                "selector": {"app.kubernetes.io/name": "postgres"},
                "ports": [{"name": "postgres", "port": 5432}],
            },
        },
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "valkey", "namespace": NAMESPACE},
            "spec": {
                "replicas": 1,
                "selector": {"matchLabels": {"app.kubernetes.io/name": "valkey"}},
                "template": {
                    "metadata": {
                        "labels": {"app.kubernetes.io/name": "valkey", "app.kubernetes.io/component": "cache"}
                    },
                    "spec": {
                        "serviceAccountName": "sip-local-dependency",
                        "automountServiceAccountToken": False,
                        "securityContext": {"fsGroup": 999, "fsGroupChangePolicy": "OnRootMismatch"},
                        "initContainers": [
                            {
                                "name": "configure",
                                "image": valkey_image,
                                "command": [
                                    "/bin/sh",
                                    "-ec",
                                    "umask 077; printf '%s\\n' 'bind 0.0.0.0' 'protected-mode yes' 'appendonly yes' 'appendfsync everysec' 'save 900 1' > /generated/valkey.conf; printf 'requirepass %s\\n' \"$(cat /run/secrets/VALKEY_PASSWORD)\" >> /generated/valkey.conf; chown 999:999 /generated/valkey.conf; chmod 0600 /generated/valkey.conf",
                                ],
                                "securityContext": {**dependency_security, "runAsUser": 0},
                                "resources": {
                                    "requests": {"cpu": "10m", "memory": "16Mi"},
                                    "limits": {"cpu": "100m", "memory": "64Mi"},
                                },
                                "volumeMounts": [
                                    {"name": "config", "mountPath": "/generated"},
                                    {"name": "runtime-secrets", "mountPath": "/run/secrets", "readOnly": True},
                                ],
                            }
                        ],
                        "containers": [
                            {
                                "name": "valkey",
                                "image": valkey_image,
                                "args": ["valkey-server", "/usr/local/etc/valkey/valkey.conf"],
                                "ports": [{"name": "valkey", "containerPort": 6379}],
                                "securityContext": {**dependency_security, "runAsNonRoot": True, "runAsUser": 999, "runAsGroup": 999},
                                "volumeMounts": [
                                    {"name": "data", "mountPath": "/data"},
                                    {"name": "config", "mountPath": "/usr/local/etc/valkey", "readOnly": True},
                                ],
                                "resources": {
                                    "requests": {"cpu": "100m", "memory": "128Mi"},
                                    "limits": {"cpu": "1", "memory": "1Gi"},
                                },
                            }
                        ],
                        "volumes": [
                            {"name": "data", "emptyDir": {"sizeLimit": "2Gi"}},
                            {"name": "config", "emptyDir": {"sizeLimit": "1Mi"}},
                            {
                                "name": "runtime-secrets",
                                "secret": {
                                    "secretName": "sip-runtime-secrets",
                                    "items": [{"key": "VALKEY_PASSWORD", "path": "VALKEY_PASSWORD"}],
                                    "defaultMode": 256,
                                },
                            },
                        ],
                    },
                },
            },
        },
        {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": "valkey", "namespace": NAMESPACE},
            "spec": {
                "selector": {"app.kubernetes.io/name": "valkey"},
                "ports": [{"name": "valkey", "port": 6379}],
            },
        },
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": "local-dependency-ingress", "namespace": NAMESPACE},
            "spec": {
                "podSelector": {
                    "matchExpressions": [
                        {"key": "app.kubernetes.io/component", "operator": "In", "values": ["database", "cache"]}
                    ]
                },
                "policyTypes": ["Ingress"],
                "ingress": [
                    {
                        "from": [
                            {
                                "podSelector": {
                                    "matchExpressions": [
                                        {
                                            "key": "app.kubernetes.io/component",
                                            "operator": "In",
                                            "values": ["api", "worker", "migration"],
                                        }
                                    ]
                                }
                            }
                        ],
                        "ports": [{"protocol": "TCP", "port": 5432}, {"protocol": "TCP", "port": 6379}],
                    }
                ],
            },
        },
    ]


def generate() -> None:
    if K8S_ROOT.exists():
        for child in K8S_ROOT.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    BASE.mkdir(parents=True, exist_ok=True)

    dump(
        BASE / "namespace.yaml",
        {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": NAMESPACE,
                "labels": {
                    "pod-security.kubernetes.io/enforce": "restricted",
                    "pod-security.kubernetes.io/audit": "restricted",
                    "pod-security.kubernetes.io/warn": "restricted",
                },
            },
        },
    )
    dump(
        BASE / "serviceaccounts.yaml",
        *[
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {"name": name, "namespace": NAMESPACE},
                "automountServiceAccountToken": False,
            }
            for name in SERVICE_ACCOUNTS
        ],
    )
    dump(
        BASE / "configmap.yaml",
        {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "sip-runtime-config", "namespace": NAMESPACE},
            "data": {
                "SIP_ENV": "production",
                "SIP_ALLOW_DEVELOPMENT_AUTH": "false",
                "SIP_MASTER_KEY_ID": "external-kms-v1",
                "SIP_OBJECT_STORE_BACKEND": "s3",
                "SIP_OBJECT_STORE_ROOT": "/var/lib/sip/objects",
                "SIP_MULTIPART_ROOT": "/var/lib/sip/runtime/multipart",
                "SIP_MAX_API_BODY_BYTES": "67108864",
                "SIP_LOG_LEVEL": "info",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://otel-collector.sip-observability:4318",
            },
        },
    )
    dump(
        BASE / "runtime-secrets.example.yaml",
        {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": "sip-runtime-secrets",
                "namespace": NAMESPACE,
                "annotations": {"sip.example/never-apply": "replace-with-secret-manager-materialization"},
            },
            "type": "Opaque",
            "stringData": {
                "SIP_DATABASE_URL": "REPLACE_WITH_SECRET_MANAGER_VALUE",
                "SIP_VALKEY_URL": "REPLACE_WITH_SECRET_MANAGER_VALUE",
                "SIP_MASTER_KEY_B64": "REPLACE_WITH_32_BYTE_BASE64_KEY",
                "SIP_SIGNING_KEY_B64": "REPLACE_WITH_32_BYTE_BASE64_KEY",
                "POSTGRES_PASSWORD": "LOCAL_OVERLAY_ONLY_REPLACE",
                "VALKEY_PASSWORD": "LOCAL_OVERLAY_ONLY_REPLACE",
            },
        },
    )
    dump(BASE / "migration-job.yaml", migration_job())
    dump(BASE / "network-policies.yaml", *network_policies())
    dump(BASE / "availability.yaml", *availability_resources())

    resources = [
        "namespace.yaml",
        "serviceaccounts.yaml",
        "configmap.yaml",
        "migration-job.yaml",
        "network-policies.yaml",
        "availability.yaml",
    ]
    for name in API_SERVICES:
        rel = f"deployments/{name}.yaml"
        dump(BASE / rel, api_deployment(name))
        resources.append(rel)
        rel = f"services/{name}.yaml"
        dump(BASE / rel, service(name))
        resources.append(rel)
    for name, config in WORKERS.items():
        rel = f"deployments/{name}.yaml"
        dump(BASE / rel, worker_deployment(name, config))
        resources.append(rel)
    dump(BASE / "deployments/web.yaml", web_deployment())
    resources.append("deployments/web.yaml")
    dump(BASE / "services/web.yaml", service("web", "web", 3000))
    resources.append("services/web.yaml")
    dump(
        BASE / "kustomization.yaml",
        {"apiVersion": "kustomize.config.k8s.io/v1beta1", "kind": "Kustomization", "resources": resources},
    )

    local = OVERLAYS / "local"
    local.mkdir(parents=True, exist_ok=True)
    dump(
        local / "kustomization.yaml",
        {
            "apiVersion": "kustomize.config.k8s.io/v1beta1",
            "kind": "Kustomization",
            "resources": ["../../base", "stateful-dependencies.yaml"],
            "images": [
                {"name": "ghcr.io/spatial-intelligence-platform/sip-python", "newName": "sip/python", "newTag": f"{VERSION}-local"},
                {"name": "ghcr.io/spatial-intelligence-platform/sip-web", "newName": "sip/web", "newTag": f"{VERSION}-local"},
            ],
            "patches": [{"path": "local-config.patch.yaml"}],
        },
    )
    dump(
        local / "local-config.patch.yaml",
        {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "sip-runtime-config", "namespace": NAMESPACE},
            "data": {
                "SIP_ENV": "development",
                "SIP_ALLOW_DEVELOPMENT_AUTH": "true",
                "SIP_OBJECT_STORE_BACKEND": "local",
                "SIP_DEPLOYMENT_PROFILE": "local",
            },
        },
    )
    dump(local / "stateful-dependencies.yaml", *local_dependencies())

    hybrid = OVERLAYS / "hybrid"
    hybrid.mkdir(parents=True, exist_ok=True)
    dump(
        hybrid / "kustomization.yaml",
        {
            "apiVersion": "kustomize.config.k8s.io/v1beta1",
            "kind": "Kustomization",
            "resources": ["../../base"],
            "patches": [{"path": "hybrid-config.patch.yaml"}, {"path": "hybrid-egress.yaml"}],
        },
    )
    dump(
        hybrid / "hybrid-config.patch.yaml",
        {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "sip-runtime-config", "namespace": NAMESPACE},
            "data": {"SIP_DEPLOYMENT_PROFILE": "hybrid", "SIP_REQUIRE_PRIVATE_ENDPOINTS": "true"},
        },
    )
    dump(
        hybrid / "hybrid-egress.yaml",
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": "hybrid-managed-services-egress", "namespace": NAMESPACE},
            "spec": {
                "podSelector": {
                    "matchExpressions": [
                        {
                            "key": "app.kubernetes.io/component",
                            "operator": "In",
                            "values": ["api", "worker", "migration"],
                        }
                    ]
                },
                "policyTypes": ["Egress"],
                "egress": [
                    {"ports": [{"protocol": "TCP", "port": 443}]},
                    {"ports": [{"protocol": "TCP", "port": 5432}, {"protocol": "TCP", "port": 6379}]},
                ],
            },
        },
    )

    aws = OVERLAYS / "aws"
    aws.mkdir(parents=True, exist_ok=True)
    dump(
        aws / "kustomization.yaml",
        {
            "apiVersion": "kustomize.config.k8s.io/v1beta1",
            "kind": "Kustomization",
            "resources": ["../../base", "aws-egress.yaml"],
            "patches": [{"path": "aws-config.patch.yaml"}],
        },
    )
    dump(
        aws / "aws-config.patch.yaml",
        {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "sip-runtime-config", "namespace": NAMESPACE},
            "data": {
                "SIP_DEPLOYMENT_PROFILE": "aws",
                "SIP_OBJECT_STORE_BACKEND": "s3",
                "SIP_S3_PREFIX": "sip",
                "AWS_REGION": "REPLACE_WITH_TERRAFORM_REGION_OUTPUT",
                "SIP_S3_REGION": "REPLACE_WITH_TERRAFORM_REGION_OUTPUT",
                "SIP_S3_BUCKET": "REPLACE_WITH_TERRAFORM_EVIDENCE_BUCKET_OUTPUT",
                "SIP_S3_KMS_KEY_ID": "REPLACE_WITH_TERRAFORM_PLATFORM_KMS_OUTPUT",
                "SIP_REQUIRE_PRIVATE_ENDPOINTS": "true",
            },
        },
    )
    dump(
        aws / "aws-egress.yaml",
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": "aws-managed-services-egress", "namespace": NAMESPACE},
            "spec": {
                "podSelector": {
                    "matchExpressions": [
                        {
                            "key": "app.kubernetes.io/component",
                            "operator": "In",
                            "values": ["api", "worker", "migration"],
                        }
                    ]
                },
                "policyTypes": ["Egress"],
                "egress": [
                    {"to": [{"ipBlock": {"cidr": "10.42.0.0/16"}}], "ports": [{"protocol": "TCP", "port": 5432}, {"protocol": "TCP", "port": 6379}, {"protocol": "TCP", "port": 443}]},
                    {"ports": [{"protocol": "TCP", "port": 443}]},
                ],
            },
        },
    )

    (K8S_ROOT / "README.md").write_text(
        "# Kubernetes deployment\n\n"
        "All manifests are generated by `python tools/generate_kubernetes.py`. Do not edit generated YAML directly.\n\n"
        "The committed application image digest is deliberately all zeros. CI must replace it with the exact signed image digest before release.\n\n"
        "`sip-runtime-secrets` is never committed. Materialize it through the approved secret manager. For a disposable local cluster, run `python tools/bootstrap_kubernetes_secrets.py --apply-command` and review the emitted command before applying it. The example Secret is documentation only and is excluded from Kustomize.\n\n"
        "AWS uses EKS Pod Identity associations created by Terraform. Service-account annotations are intentionally absent. The Kubernetes namespace and Terraform associations are both `sip-system`.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    generate()
    print(f"Generated Kubernetes base and overlays under {K8S_ROOT}")
