from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sip.canonical import canonical_sha256
from sip.errors import AuthorizationError
from tests.progress11_helpers import bootstrap_release, complete_campaign, create_campaign, release_artifact_manifest


def test_progress11_critical_p0_truth_consent_authority_and_security_requirements_are_nonwaivable(tmp_path: Path) -> None:
    """REQ: TSTGATE-008, TSTGATE-009, TSTGATE-010 P0, truth, consent, authority, tenant-isolation, provenance, and security stop-lines cannot be waived."""
    env = bootstrap_release(tmp_path, name="p11-nonwaivable")
    campaign = create_campaign(env)
    service = env["context"].release_assurance
    for requirement_id, priority in [
        ("TSTGATE-009", "P0"),
        ("TSTSEC-001", "P1"),
        ("CONAUTH-001", "P1"),
        ("LIFCONS-001", "P1"),
    ]:
        with pytest.raises(AuthorizationError) as error:
            service.approve_waiver(
                campaign_id=campaign["campaign_id"],
                tenant_id=env["tenant"],
                requirement_id=requirement_id,
                priority=priority,
                reason="adversarial waiver",
                compensating_control={"control": "review", "verification": "manual"},
                owner="release-manager",
                expires_at=datetime.now(timezone.utc) + timedelta(days=1),
                actor_id="release-manager",
            )
        assert error.value.code in {"QA_WAIVER_PROHIBITED", "QA_WAIVER_REQUIREMENT_OUT_OF_SCOPE"}


def test_progress11_release_artifact_manifest_rejects_stale_incomplete_unsigned_and_unsafe_evidence(tmp_path: Path) -> None:
    """REQ: TSTGATE-003, TSTGATE-007, TSTGATE-011 stale, partial, mismatched, unchecked, unsigned, unsafe, or source-unbound release manifests are blocked."""
    env = bootstrap_release(tmp_path, name="p11-manifest")
    completed = complete_campaign(env, sign_candidate=False)
    manifest = release_artifact_manifest(marker="unsafe")
    manifest["artifacts"].append(
        {
            "path": "../escape.txt",
            "sha256": canonical_sha256({"unsafe": True}),
            "byte_count": 1,
            "media_type": "text/plain",
        }
    )
    manifest["signed"] = False
    manifest["signature_reference"] = ""
    manifest["content_root_sha256"] = "0" * 64
    candidate = env["context"].release_assurance.evaluate_and_sign_candidate(
        campaign_id=completed["campaign"]["campaign_id"],
        tenant_id=env["tenant"],
        source_commit="d" * 40,
        source_root_sha256="e" * 64,
        release_manifest=manifest,
        signer_key_id="adversarial-key",
        actor_id="release-manager",
    )
    codes = {item["code"] for item in candidate["blockers"]}
    assert {
        "QA_RELEASE_ARTIFACT_PATH_UNSAFE",
        "QA_RELEASE_ARTIFACT_MANIFEST_UNSIGNED",
        "QA_RELEASE_SIGNATURE_REFERENCE_MISSING",
        "QA_RELEASE_CONTENT_ROOT_MISMATCH",
    } <= codes
    assert candidate["status"] == "blocked"


def test_progress11_production_admission_fails_closed_even_for_valid_candidate(tmp_path: Path) -> None:
    """REQ: TSTGATE-011, TSTGATE-012 a fully valid local candidate cannot authorize production or Progress 12 while external evidence and independent True North approval are absent."""
    env = bootstrap_release(tmp_path, name="p11-admission")
    candidate = complete_campaign(env, external_gates=set())["candidate"]
    assert candidate["status"] == "passed_complete"
    decision = env["context"].release_assurance.production_admission(
        tenant_id=env["tenant"],
        release_candidate_id=candidate["release_candidate_id"],
        actor_id="release-manager",
    )
    assert decision["admitted"] is False
    assert decision["production_authorized"] is False
    assert decision["progress_12_authorized"] is False
    codes = {item["code"] for item in decision["blockers"]}
    assert "TRUE_NORTH_PRODUCTION_AUTHORIZATION_MISSING" in codes
    assert "NON_PRODUCTION_ENVIRONMENT" in codes
