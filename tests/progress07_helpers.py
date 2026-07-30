from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sip.canonical import sha256_bytes
from sip.context import PlatformContext, temporary_settings

CRITICAL_THREATS = [
    "capture_device_compromise", "upload_tampering", "archive_bomb", "parser_exploit",
    "gpu_escape", "cross_tenant_access", "signed_url_leakage", "viewer_scraping",
    "model_exfiltration", "prompt_injection", "insider_abuse", "destructive_deletion",
    "geometry_payload_parsing", "provider_egress", "topology_disclosure",
    "derivative_redaction", "authority_spoofing", "immersive_safety_failure",
]


def bootstrap(tmp_path: Path, *, name: str = "p07") -> tuple[PlatformContext, str, str]:
    context = PlatformContext.create(temporary_settings(tmp_path / name))
    tenant = context.tenancy.create_tenant(f"{name} tenant", tenant_id=f"{name}-tenant", actor_id="bootstrap")
    project = context.tenancy.create_project(
        tenant, f"{name} project", vertical="platform", classification="internal",
        project_id=f"{name}-project", actor_id="bootstrap",
    )
    return context, tenant, project


def threat_payload() -> dict:
    return {
        "scope": "sip-platform",
        "threats": [
            {
                "threat_id": threat,
                "description": threat.replace("_", " "),
                "owner": "security-team",
                "test_ids": [f"test:{threat}"],
                "controls": {
                    "preventative": ["deny-by-default"],
                    "detective": ["audit"],
                    "recovery": ["revoke-and-restore"],
                },
            }
            for threat in CRITICAL_THREATS
        ],
        "misuse_cases": [
            {"domain": "sensitive_facility", "case": "topology inference", "control": "pre-match authorization"},
            {"domain": "private_family", "case": "relationship inference", "control": "consent-scoped graph"},
        ],
        "public_viewer_analysis": {
            "trusted_secrets": False,
            "scraping_controls": ["rate_limit", "watermark"],
            "cache_controls": ["policy_etag", "revoke"],
        },
        "residual_risks": [
            {"risk": "screen capture", "owner": "security-team", "release_disposition": "disclose-and-watermark"}
        ],
        "owner": "security-team",
        "review_trigger": "scheduled",
    }


def headers(tenant: str, project: str, *, subject: str = "security-admin", role: str = "security_admin", purposes: str = "security,incident_response,reconstruction,privacy,release") -> dict[str, str]:
    return {
        "X-SIP-Tenant": tenant,
        "X-SIP-Subject": subject,
        "X-SIP-Projects": project,
        "X-SIP-Roles": role,
        "X-SIP-Purposes": purposes,
        "X-SIP-Audience": "private",
    }


def register_provider(context: PlatformContext, *, provider_id: str = "p07-provider", tenant: str | None = None, project: str | None = None) -> str:
    del tenant, project
    context.providers.register(
        {
            "provider_id": provider_id,
            "version": "1.0.0",
            "source_url": f"local://{provider_id}",
            "source_revision": "a" * 40,
            "license_id": "Apache-2.0",
            "approval_state": "approved",
            "allowed_classifications": ["internal"],
            "allowed_purposes": ["reconstruction"],
            "allowed_regions": ["local"],
            "deployments": ["local"],
            "retention_days": 0,
            "output_rights": "commercial_derivatives_allowed",
        },
        actor_id="provider-governance",
    )
    return provider_id


def output_checks(payload: bytes = b"progress07-provider-output") -> tuple[str, dict]:
    output_hash = sha256_bytes(payload)
    checks = {
        name: {
            "passed": True,
            "tool": f"sip-{name}",
            "version": "1.0.0",
            "report_sha256": sha256_bytes(name.encode()),
        }
        for name in [
            "malware_scan", "resource_limits", "format_validation", "transform_validation",
            "content_policy", "hash_verified", "quarantine_write_only",
        ]
    }
    checks["hash_verified"]["observed_sha256"] = output_hash
    checks["quarantine_write_only"]["workspace_policy"] = "write_only_staging"
    return output_hash, checks


def valid_rights_outcomes() -> dict:
    result = {}
    for name in ["canonical", "derivatives", "indexes", "caches", "exports", "backups"]:
        result[name] = {"state": "completed" if name != "backups" else "expiry_tracked", "evidence_hash": sha256_bytes(name.encode())}
    return result


def fresh_now() -> datetime:
    return datetime.now(UTC)
