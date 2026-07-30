from __future__ import annotations

import json
from pathlib import Path

from tools.progress07_supply_chain_check import run

ROOT = Path(__file__).resolve().parents[2]


def test_progress07_security_policy_files_deny_runtime_models_and_repository_secrets() -> None:
    """REQ: OPSKEY-001, OPSSEC-003, OPSSEC-004, SECEXT-001, SECEXT-002, SECEXT-003 security policy files deny runtime model egress and repository secret material."""
    model = json.loads((ROOT / "infrastructure/security/model-egress-policy.json").read_text(encoding="utf-8"))
    secrets = json.loads((ROOT / "infrastructure/security/secret-material-policy.json").read_text(encoding="utf-8"))
    assert model["default"] == "deny"
    assert model["production_runtime_downloads"] == "denied"
    assert model["worker_public_internet_egress"] == "denied"
    assert secrets["default"] == "deny"
    assert set(secrets["forbidden_in_source"]) >= {"password", "token", "private_key", "passcode"}
    assert secrets["runtime_source"] == "external_secret_manager"


def test_progress07_supply_chain_contracts_are_pinned_and_fail_closed() -> None:
    """REQ: OPSCICD-001, OPSCICD-002, OPSCICD-003, OPSCICD-004, OPSCICD-005, OPSCICD-006, OPSSEC-004 dependency, action, image, evidence, and promotion controls are pinned and fail closed."""
    report = run()
    assert report["status"] in {"passed_complete", "passed_with_external_gaps"}
    assert report["findings"] == []
    assert report["production_authorized"] is False
    assert report["external_or_release_blockers"]
    workflow = (ROOT / ".github/workflows/progress07-security.yml").read_text(encoding="utf-8")
    all_workflows = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / ".github/workflows").glob("*.yml"))
    assert "progress07_supply_chain_check.py" in workflow
    assert "security_check.py --release" in all_workflows
    admission = json.loads((ROOT / "infrastructure/security/release-admission-policy.json").read_text(encoding="utf-8"))
    assert admission["default"] == "deny"
    assert admission["requires_signed_component_manifests"] is True
    assert admission["requires_production_environment_authorization"] is True
    assert admission["production_authorized"] is False


def test_progress07_supply_chain_adversarial_mutations_are_detected(tmp_path, monkeypatch) -> None:
    """REQ: OPSCICD-001, OPSCICD-002, OPSCICD-003, OPSCICD-004, OPSCICD-005, OPSCICD-006, OPSSEC-003, OPSSEC-004 unpinned actions, dependencies, images, model egress, repository secrets, mutable sources, and mutable audit policy fail closed."""
    import shutil
    import tools.progress07_supply_chain_check as checker

    root = tmp_path / "repo"
    for relative in [
        ".github/workflows",
        "apps/web",
        "build/manifests",
        "third_party",
        "infrastructure/security",
        "infrastructure/postgres",
    ]:
        source = ROOT / relative
        destination = root / relative
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    shutil.copy2(ROOT / "pyproject.toml", root / "pyproject.toml")
    monkeypatch.setattr(checker, "ROOT", root)

    baseline = checker.run()
    assert baseline["findings"] == []
    assert baseline["production_authorized"] is False

    def mutate(relative: str, transform, expected_code: str) -> None:
        path = root / relative
        original = path.read_text(encoding="utf-8")
        path.write_text(transform(original), encoding="utf-8")
        try:
            codes = {finding["code"] for finding in checker.run()["findings"]}
            assert expected_code in codes
        finally:
            path.write_text(original, encoding="utf-8")

    workflow = sorted((root / ".github/workflows").glob("*.yml"))[0]
    mutate(
        str(workflow.relative_to(root)),
        lambda text: __import__("re").sub(r"(@)[a-f0-9]{40}", r"\1main", text, count=1),
        "UNPINNED_GITHUB_ACTION",
    )
    mutate(
        "pyproject.toml",
        lambda text: text.replace("alembic==1.18.4", "alembic>=1.18.4", 1),
        "PYTHON_DEPENDENCY_NOT_EXACT",
    )

    container_path = root / "build/manifests/container-images.json"
    container_original = json.loads(container_path.read_text(encoding="utf-8"))
    mutated = json.loads(json.dumps(container_original))
    mutated["images"][0]["reference"] = "python:latest"
    container_path.write_text(json.dumps(mutated), encoding="utf-8")
    try:
        assert "CONTAINER_DIGEST_REQUIRED" in {item["code"] for item in checker.run()["findings"]}
    finally:
        container_path.write_text(json.dumps(container_original, indent=2) + "\n", encoding="utf-8")

    mutate(
        "infrastructure/security/model-egress-policy.json",
        lambda text: text.replace('"production_runtime_downloads": "denied"', '"production_runtime_downloads": "allowed"'),
        "MODEL_EGRESS_POLICY_NOT_FAIL_CLOSED",
    )
    mutate(
        "infrastructure/security/secret-policy.json",
        lambda text: text.replace('"repository_material": "prohibited"', '"repository_material": "allowed"'),
        "SECRET_POLICY_NOT_FAIL_CLOSED",
    )
    mutate(
        "infrastructure/postgres/audit-immutability.sql",
        lambda text: text.replace("REVOKE UPDATE, DELETE", "GRANT UPDATE, DELETE"),
        "AUDIT_IMMUTABILITY_SQL_MISSING",
    )

    lock_path = root / "third_party/manifest.lock.json"
    lock_original = json.loads(lock_path.read_text(encoding="utf-8"))
    lock_mutated = json.loads(json.dumps(lock_original))
    sources = lock_mutated.get("imported_sources", [])
    assert sources
    if "revision" in sources[0]:
        sources[0]["revision"] = "main"
    else:
        sources[0]["commit"] = "main"
    lock_path.write_text(json.dumps(lock_mutated), encoding="utf-8")
    try:
        assert "THIRD_PARTY_SOURCE_REVISION_MUTABLE" in {item["code"] for item in checker.run()["findings"]}
    finally:
        lock_path.write_text(json.dumps(lock_original, indent=2) + "\n", encoding="utf-8")

    lock_mutated = json.loads(json.dumps(lock_original))
    lock_mutated["imported_sources"][0]["repository"] = "https://unapproved.invalid/model"
    lock_path.write_text(json.dumps(lock_mutated), encoding="utf-8")
    try:
        assert "THIRD_PARTY_SOURCE_REPOSITORY_UNAPPROVED" in {item["code"] for item in checker.run()["findings"]}
    finally:
        lock_path.write_text(json.dumps(lock_original, indent=2) + "\n", encoding="utf-8")
