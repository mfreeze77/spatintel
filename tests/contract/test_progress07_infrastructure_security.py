from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_progress07_audit_database_role_is_append_only() -> None:
    """REQ: OPSAUDIT-001, OPSAUDIT-002, OPSAUDIT-003, OPSAUDIT-004, OPSSEC-006 audit storage privileges prohibit update and deletion while retaining verification access."""
    sql = (ROOT / "infrastructure/postgres/audit-immutability.sql").read_text(encoding="utf-8").upper()
    assert "REVOKE UPDATE, DELETE" in sql
    assert "AUDIT_EVENTS" in sql
    assert "GRANT SELECT" in sql
    assert "GRANT SELECT, INSERT" in sql


def test_progress07_secrets_and_transport_have_fail_closed_deployment_policies() -> None:
    """REQ: OPSKEY-001, OPSKEY-002, OPSSEC-003, OPSSEC-004 secret and transport policies deny repository material and plaintext or unverified transport."""
    secret = json.loads((ROOT / "infrastructure/security/secret-policy.json").read_text(encoding="utf-8"))
    material = json.loads((ROOT / "infrastructure/security/secret-material-policy.json").read_text(encoding="utf-8"))
    transport = json.loads((ROOT / "infrastructure/security/transport-policy.json").read_text(encoding="utf-8"))
    assert secret["default"] == "deny"
    assert secret["production_requirements"]["repository_material"] == "prohibited"
    assert material["default"] == "deny"
    assert material["runtime_source"] == "external_secret_manager"
    assert transport["minimum_tls_version"] == "TLSv1.3"
    assert transport["certificate_validation_required"] is True
    assert transport["plaintext_external_transport"] == "denied"
    assert transport["production_authorized"] is False


def test_progress07_security_ops_is_a_distinct_nonroot_service_boundary() -> None:
    """REQ: OPSCICD-001, OPSCICD-003, OPSSEC-001, OPSSEC-002 security operations are exposed through an isolated, least-privilege, non-root logical service boundary."""
    compose = yaml.safe_load((ROOT / "infrastructure/compose/docker-compose.yml").read_text(encoding="utf-8"))
    service = compose["services"]["security-ops"]
    assert service["user"] == "10001:10001"
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in service["security_opt"]
    assert service["environment"]["SIP_SERVICE_NAME"] == "security-ops"
    assert service["environment"]["SIP_MODEL_EGRESS_DEFAULT"] == "denied"
    deployment = yaml.safe_load((ROOT / "infrastructure/kubernetes/base/deployments/security-ops.yaml").read_text(encoding="utf-8"))
    pod = deployment["spec"]["template"]["spec"]
    container = pod["containers"][0]
    assert pod["serviceAccountName"] == "security-ops"
    assert pod["securityContext"]["runAsNonRoot"] is True
    assert container["securityContext"]["allowPrivilegeEscalation"] is False
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert container["securityContext"]["capabilities"]["drop"] == ["ALL"]


def test_progress07_worker_egress_and_runtime_model_downloads_fail_closed() -> None:
    """REQ: OPSSEC-003, SECEXT-001, SECEXT-002, SECEXT-003 worker public egress and production runtime model downloads are denied by policy."""
    model = json.loads((ROOT / "infrastructure/security/model-egress-policy.json").read_text(encoding="utf-8"))
    assert model["default"] == "deny"
    assert model["production_runtime_downloads"] == "denied"
    assert model["worker_public_internet_egress"] == "denied"
    assert model["allowed_destinations"] == []
    assert model["local_only_overrides_external"] is True
    deploy = (ROOT / "infrastructure/kubernetes/base/deployments/security-ops.yaml").read_text(encoding="utf-8")
    assert "SIP_SERVICE_NAME" in deploy
    assert "security-ops" in deploy
    assert "http://" not in deploy.lower()
