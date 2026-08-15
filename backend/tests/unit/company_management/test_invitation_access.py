from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from interview_evidence.company_management.adapters.applicant_session import (
    ApplicantSessionAdapter,
    InvitationTokenAlreadyUsedError,
    InvitationTokenExpiredError,
    InvitationTokenNotFoundError,
)
from interview_evidence.company_management.domain.hiring import (
    Invitation,
    InvitationStateError,
)
from interview_evidence.shared.ids import FrozenClock

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
CAMPAIGN_ID = UUID("00000000-0000-7000-8000-000000000002")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000003")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000004")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def invitation(token_hash: str, *, expires_at: datetime | None = None) -> Invitation:
    return Invitation.create(
        invitation_id=INVITATION_ID,
        company_id=COMPANY_ID,
        campaign_id=CAMPAIGN_ID,
        applicant_id=APPLICANT_ID,
        applicant_email="applicant@example.com",
        applicant_display_name="홍길동",
        token_hash=token_hash,
        expires_at=expires_at or NOW + timedelta(days=7),
    )


def test_invitation_tokens_are_high_entropy_hash_only_and_one_time() -> None:
    adapter = ApplicantSessionAdapter(clock=FrozenClock(NOW))
    first = adapter.issue_token(
        invitation_id=INVITATION_ID,
        company_id=COMPANY_ID,
        applicant_id=APPLICANT_ID,
        expires_at=NOW + timedelta(days=7),
    )
    second = adapter.issue_token(
        invitation_id=UUID("00000000-0000-7000-8000-000000000005"),
        company_id=COMPANY_ID,
        applicant_id=APPLICANT_ID,
        expires_at=NOW + timedelta(days=7),
    )

    assert len(first.raw_token) >= 43
    assert first.raw_token != second.raw_token
    assert first.raw_token not in first.token_hash
    assert adapter.persisted_token_hashes == (first.token_hash, second.token_hash)

    principal, session_cookie = adapter.exchange(first.raw_token)
    assert principal.invitation_id == INVITATION_ID
    assert session_cookie.raw_value not in repr(adapter)

    with pytest.raises(InvitationTokenAlreadyUsedError):
        adapter.exchange(first.raw_token)
    with pytest.raises(InvitationTokenNotFoundError):
        adapter.exchange("x" * 64)


def test_expired_invitation_token_is_rejected() -> None:
    adapter = ApplicantSessionAdapter(clock=FrozenClock(NOW))
    issued = adapter.issue_token(
        invitation_id=INVITATION_ID,
        company_id=COMPANY_ID,
        applicant_id=APPLICANT_ID,
        expires_at=NOW - timedelta(seconds=1),
    )

    with pytest.raises(InvitationTokenExpiredError):
        adapter.exchange(issued.raw_token)


def test_invitation_state_machine_rejects_skips_and_late_overwrites() -> None:
    current = invitation("a" * 64)
    verified = current.transition(
        "identity_verified",
        actor_type="applicant",
        occurred_at=NOW,
        expected_version=1,
    )
    consented = verified.transition(
        "consented",
        actor_type="applicant",
        occurred_at=NOW,
        expected_version=2,
    )

    assert consented.row_version == 3
    with pytest.raises(InvitationStateError):
        current.transition(
            "consented",
            actor_type="applicant",
            occurred_at=NOW,
            expected_version=1,
        )
    with pytest.raises(InvitationStateError):
        consented.transition(
            "identity_verified",
            actor_type="applicant",
            occurred_at=NOW,
            expected_version=1,
        )
