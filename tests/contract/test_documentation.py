from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_required_documentation_and_readme_links_exist() -> None:
    """REQ: DELDOD-001 required product, operator, developer, security, privacy, and release documentation is retained."""
    required = {
        "docs/architecture/OVERVIEW.md",
        "docs/developer/GETTING_STARTED.md",
        "docs/developer/CONTRACTS_AND_MIGRATIONS.md",
        "docs/operator/DEPLOYMENT.md",
        "docs/operator/WORKERS.md",
        "docs/operator/BACKUP_RESTORE.md",
        "docs/operator/INCIDENT_RESPONSE.md",
        "docs/operator/PROVIDER_GOVERNANCE.md",
        "docs/runbooks/OPERATIONS_INCIDENTS.md",
        "docs/runbooks/CONTROLLED_DELETION.md",
        "docs/runbooks/KEY_ROTATION.md",
        "docs/security/THREAT_MODEL.md",
        "docs/privacy/PRIVACY_AND_CONSENT.md",
        "docs/user/CONSTRUCTION.md",
        "docs/user/LIVEFOREVER.md",
        "docs/release/RELEASE_PROCESS.md",
        "docs/release/KNOWN_LIMITATIONS.md",
    }
    assert all((ROOT / path).is_file() for path in required)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    markdown_paths = set(re.findall(r"`((?:docs|requirements|build|spec|third_party)/[^`\n]+)`", readme))
    broken = sorted(path for path in markdown_paths if not (ROOT / path.rstrip("/.")).exists())
    assert broken == []


def test_operations_runbooks_cover_required_incident_classes_and_procedure_fields() -> None:
    """REQ: OPSSRE-001, OPSSRE-002 incident runbooks cover mandated failures with complete control fields."""
    text = (ROOT / "docs/runbooks/OPERATIONS_INCIDENTS.md").read_text(encoding="utf-8").lower()
    incidents = {
        "database outage",
        "object corruption",
        "queue backlog",
        "gpu or reconstruction-worker failure",
        "model or quality regression",
        "suspected cross-tenant access",
        "leaked share link",
        "consent, audience, or third-party protection failure",
        "bad redaction",
        "destructive deletion error",
        "backup, restore, or disaster-recovery failure",
    }
    for incident in incidents:
        assert incident in text, incident
    for field in {
        "trigger and severity",
        "roles",
        "controls and decisions",
        "evidence and validation",
        "rollback and communications",
    }:
        assert text.count(field) >= 10, field


def test_threat_model_enumerates_specified_attack_classes() -> None:
    """REQ: OPSTHREA-001, OPSTHR-007 threat model covers device, parser, provider, tenant, authority, derivative, and immersive threats."""
    text = (ROOT / "docs/security/THREAT_MODEL.md").read_text(encoding="utf-8").lower()
    threats = {
        "capture-device compromise",
        "upload tampering",
        "archive bomb",
        "parser exploit",
        "gpu escape",
        "cross-tenant",
        "signed-url",
        "viewer scraping",
        "model or source-data exfiltration",
        "prompt injection",
        "insider abuse",
        "destructive deletion",
        "geometry or splat payload exploit",
        "external-provider egress",
        "topology disclosure",
        "derivative redaction",
        "authority spoofing",
        "immersive collision/navigation failure",
    }
    for threat in threats:
        assert threat in text, threat


def test_contributor_documentation_defines_ownership_adr_review_and_release_gates() -> None:
    """REQ: DELDEV-006 contributor documentation states code owners, review, ADR, and release gates."""
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8").lower()
    for phrase in {"codeowners", "code owner", "adr process", "reviewers", "release gates", "fail closed"}:
        assert phrase in text
