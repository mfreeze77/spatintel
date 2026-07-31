from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_progress09_service_openapi_and_event_contracts_are_owned_by_deployment_control() -> None:
    """REQ: OPSHYB-001, OPSAWS-006 deployment-control owns provider-neutral profile, portability, edge, migration, and admission contracts."""
    service = _json("services/deployment-control/service.json")
    assert service["service_name"] == "deployment-control"
    operations = {item["path"] for item in service["operations"]}
    assert "/v1/deployment/profiles" in operations
    assert any("/deployment/migrations" in path for path in operations)
    assert any("/deployment/edge-nodes" in path for path in operations)
    openapi = _json("schemas/openapi/deployment-control.openapi.json")
    public = {path for path in operations if path not in {"/health/live", "/health/ready", "/metrics"}}
    assert public <= set(openapi["paths"])
    catalog = _json("schemas/events/event-catalog.json")
    owned = {item["type"] for item in catalog["events"] if item.get("owner") == "deployment-control"}
    assert {"deployment.profile.registered", "deployment.residency.registered", "deployment.edge.enrolled", "deployment.migration.completed", "deployment.worker.shutdown_verified"} <= owned


def test_progress09_compose_and_kubernetes_are_nonroot_digest_pinned_and_default_deny() -> None:
    """REQ: ARCDEP-002, OPSHYB-003 production-shaped Compose/Kubernetes definitions use digest-pinned images, secret references, least privilege, resource limits, health checks, and default-deny networking."""
    compose = yaml.safe_load((ROOT / "infrastructure/compose/docker-compose.yml").read_text(encoding="utf-8"))
    service = compose["services"]["deployment-control"]
    assert service["environment"]["SIP_PRODUCTION_AUTHORIZED"] == "false"
    assert service["environment"]["SIP_DEFAULT_EGRESS"] == "denied"
    assert service["networks"] == ["backend"]

    deployment = yaml.safe_load((ROOT / "infrastructure/kubernetes/base/deployments/deployment-control.yaml").read_text(encoding="utf-8"))
    pod = deployment["spec"]["template"]["spec"]
    container = pod["containers"][0]
    assert "@sha256:" in container["image"]
    assert pod["securityContext"]["runAsNonRoot"] is True
    assert pod["automountServiceAccountToken"] is False
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert container["securityContext"]["allowPrivilegeEscalation"] is False
    assert container["resources"]["limits"]
    assert container["readinessProbe"] and container["livenessProbe"]
    policies = list(yaml.safe_load_all((ROOT / "infrastructure/kubernetes/base/network-policies.yaml").read_text(encoding="utf-8")))
    assert any(item and item.get("metadata", {}).get("name") in {"default-deny", "default-deny-all"} for item in policies)
    for overlay in ("local", "edge", "hybrid", "aws"):
        assert (ROOT / f"infrastructure/kubernetes/overlays/{overlay}/kustomization.yaml").is_file()
    edge_policy = yaml.safe_load((ROOT / "infrastructure/kubernetes/overlays/edge/edge-egress.yaml").read_text(encoding="utf-8"))
    assert edge_policy["spec"]["policyTypes"] == ["Egress"]


def test_progress09_aws_terraform_is_environment_scoped_private_and_replacement_documented() -> None:
    """REQ: OPSAWS-001, OPSAWS-002, OPSAWS-003, OPSAWS-004, OPSAWS-005, OPSAWS-006 Terraform and deployment manifests retain environment boundaries, private encrypted stores, queue controls, signed CDN policy, least-privilege keys/secrets, and provider exit paths."""
    module = (ROOT / "infrastructure/terraform/modules/aws-platform").read_text(encoding="utf-8") if (ROOT / "infrastructure/terraform/modules/aws-platform").is_file() else ""
    combined = "\n".join(path.read_text(encoding="utf-8") for path in sorted((ROOT / "infrastructure/terraform/modules/aws-platform").glob("*.tf")))
    for marker in ("environment", "private", "kms", "dead_letter", "quota", "budget"):
        assert marker.lower() in combined.lower()
    profile = _json("infrastructure/deployment/profiles/aws-reference.json")
    assert profile["production_authorized"] is False
    assert profile["network_policy"]["default_deny_egress"] is True
    assert profile["database"]["private"] is True and profile["database"]["encrypted"] is True
    assert profile["object_store"]["private"] is True and profile["object_store"]["encrypted"] is True
    assert profile["queue"]["dead_letter_enabled"] is True
    assert profile["cdn"]["raw_asset_origin"] is False
    assert profile["kms"]["least_privilege"] is True and profile["secrets"]["least_privilege"] is True
    assert len(profile["provider_replacement_paths"]) >= 8
    for relative in profile["provider_replacement_paths"].values():
        assert (ROOT / relative).is_file()
