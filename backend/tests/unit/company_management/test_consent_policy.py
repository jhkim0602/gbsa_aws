from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from interview_evidence.company_management.domain.applicant_access import (
    DEFAULT_CONSENT_POLICY,
    ConsentRecord,
    ConsentRequiredError,
    ProcessingPurpose,
    require_processing_authorization,
)

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000002")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def accepted_consent() -> ConsentRecord:
    return ConsentRecord.accept(
        consent_record_id=UUID("00000000-0000-7000-8000-000000000003"),
        company_id=COMPANY_ID,
        invitation_id=INVITATION_ID,
        policy_version="2026-08-v1",
        purposes=(
            ProcessingPurpose.DOCUMENT_ANALYSIS,
            ProcessingPurpose.RECORDING,
            ProcessingPurpose.AI_ASSESSMENT,
        ),
        retention_days=180,
        accepted_at=NOW,
        evidence_digest="a" * 64,
    )


def test_each_processing_purpose_requires_active_consent() -> None:
    consent = accepted_consent()

    for purpose in ProcessingPurpose:
        authorization = require_processing_authorization(consent, purpose, at=NOW)
        assert authorization.company_id == COMPANY_ID
        assert authorization.invitation_id == INVITATION_ID
        assert authorization.purpose == purpose
        assert authorization.expires_at == NOW + timedelta(days=180)


def test_missing_or_withdrawn_consent_blocks_processing() -> None:
    with pytest.raises(ConsentRequiredError):
        require_processing_authorization(None, ProcessingPurpose.DOCUMENT_ANALYSIS, at=NOW)

    withdrawn = accepted_consent().withdraw(at=NOW + timedelta(minutes=1))
    with pytest.raises(ConsentRequiredError):
        require_processing_authorization(
            withdrawn,
            ProcessingPurpose.AI_ASSESSMENT,
            at=NOW + timedelta(minutes=2),
        )


def test_consent_policy_digest_changes_with_displayed_content() -> None:
    policy = DEFAULT_CONSENT_POLICY
    changed = policy.model_copy(update={"retention_days": policy.retention_days + 1})

    assert len(policy.content_digest) == 64
    assert changed.content_digest != policy.content_digest
    assert policy.required_purposes == frozenset(ProcessingPurpose)
