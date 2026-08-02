from __future__ import annotations

from pathlib import Path

import pytest

from sip.errors import AuthorizationError, NotFoundError, ValidationError
from tests.progress11_helpers import bootstrap_release, campaign_body, complete_campaign, create_campaign


def test_progress11_cross_tenant_release_evidence_is_denied(tmp_path: Path) -> None:
    """REQ: TSTSEC-001, TSTGATE-009 cross-tenant campaign and release-candidate reads fail closed without confirming resource existence."""
    env = bootstrap_release(tmp_path, name="p11-cross-tenant")
    completed = complete_campaign(env)
    foreign = env["context"].tenancy.create_tenant("foreign", tenant_id="p11-foreign-tenant", actor_id="bootstrap")
    service = env["context"].release_assurance
    with pytest.raises(NotFoundError):
        service.campaign(tenant_id=foreign, campaign_id=completed["campaign"]["campaign_id"])
    with pytest.raises(NotFoundError):
        service.candidate(tenant_id=foreign, release_candidate_id=completed["candidate"]["release_candidate_id"])


def test_progress11_external_evidence_cannot_be_labeled_complete(tmp_path: Path) -> None:
    """REQ: TSTGATE-002, TSTGATE-004, TSTGATE-007 unavailable browser, device, GPU, cloud, or external-review evidence cannot be represented as passed complete."""
    env = bootstrap_release(tmp_path, name="p11-external")
    campaign = create_campaign(env)
    with pytest.raises(ValidationError) as error:
        env["context"].release_assurance.record_gate(
            campaign_id=campaign["campaign_id"],
            tenant_id=env["tenant"],
            gate_type="accessibility",
            required=True,
            execution_status="not_executed",
            control_status="passed_complete",
            thresholds={"failures": 0},
            result={"profile": "unavailable"},
            findings=[],
            evidence=[],
            external_gap=True,
            actor_id="qa-reviewer",
        )
    assert error.value.code == "QA_GATE_PASS_OVERCLAIM"


def test_progress11_signed_manifest_never_authorizes_production(tmp_path: Path) -> None:
    """REQ: TSTGATE-003, TSTGATE-011, TSTGATE-012 a valid signed candidate remains non-authorizing and production admission retains True North and external-gap blockers."""
    env = bootstrap_release(tmp_path, name="p11-prod")
    candidate = complete_campaign(env)["candidate"]
    assert candidate["production_authorized"] is False
    decision = env["context"].release_assurance.production_admission(
        tenant_id=env["tenant"],
        release_candidate_id=candidate["release_candidate_id"],
        actor_id="release-manager",
    )
    assert decision["admitted"] is False
    assert decision["production_authorized"] is False
    assert decision["progress_12_authorized"] is False
    assert any(item["code"] == "TRUE_NORTH_PRODUCTION_AUTHORIZATION_MISSING" for item in decision["blockers"])


def test_progress11_test_data_must_be_synthetic_or_documented_consent(tmp_path: Path) -> None:
    """REQ: TSTSEC-001, LIFTEST-006 customer, confidential-facility, or human-subject data cannot enter a bounded bounded release campaign without separate authorization."""
    env = bootstrap_release(tmp_path, name="p11-data")
    body = campaign_body(env["project"])
    body["test_data"] = {"classification": "private_family", "customer_data": False, "human_subjects": False}
    with pytest.raises(ValidationError) as error:
        env["context"].release_assurance.create_campaign(tenant_id=env["tenant"], actor_id="release-manager", **body)
    assert error.value.code == "QA_TEST_DATA_POLICY_INVALID"

    body = campaign_body(env["project"])
    body["test_data"] = {"classification": "consented", "customer_data": False, "human_subjects": True}
    with pytest.raises(AuthorizationError) as error:
        env["context"].release_assurance.create_campaign(tenant_id=env["tenant"], actor_id="release-manager", **body)
    assert error.value.code == "QA_LIVE_DATA_DENIED"
