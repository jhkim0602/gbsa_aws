from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from interview_evidence.company_management.application.company_service import (
    CompanyManagementPublic,
)
from interview_evidence.company_management.domain.hiring import (
    Invitation,
    InvitationStateChange,
    InvitationStatus,
)
from interview_evidence.company_management.repositories.postgres import CompanyRepository
from interview_evidence.shared.ids import CommandMeta, FrozenClock
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 20, 8, 30, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000002")


class LockedInvitationRepository:
    def __init__(self, invitation: Invitation) -> None:
        self.invitation = invitation
        self.saved_invitations: list[Invitation] = []
        self.state_changes: list[InvitationStateChange] = []

    def get_invitation_for_update(self, _context: TenantContext, invitation_id: UUID) -> Invitation:
        assert invitation_id == self.invitation.invitation_id
        return self.invitation

    def save_invitation(self, _context: TenantContext, invitation: Invitation) -> Invitation:
        self.saved_invitations.append(invitation)
        self.invitation = invitation
        return invitation

    def append_invitation_state_change(
        self, _context: TenantContext, change: InvitationStateChange
    ) -> None:
        self.state_changes.append(change)


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=UUID("00000000-0000-7000-8000-000000000003"),
        request_id=INVITATION_ID,
        trace_id="invitation-state-idempotency",
    )


def test_advancing_to_the_current_state_is_idempotent() -> None:
    repository = LockedInvitationRepository(
        Invitation(
            invitation_id=INVITATION_ID,
            company_id=COMPANY_ID,
            position_id=UUID("00000000-0000-7000-8000-000000000004"),
            competency_model_version_id=UUID("00000000-0000-7000-8000-000000000005"),
            applicant_id=UUID("00000000-0000-7000-8000-000000000006"),
            applicant_email_normalized="candidate@example.com",
            applicant_display_name="지원자",
            token_hash="a" * 64,
            expires_at=NOW + timedelta(days=1),
            status=InvitationStatus.ANALYZING,
            last_state_actor_type="system",
            row_version=5,
        )
    )
    service = CompanyManagementPublic(
        cast(CompanyRepository, repository),
        FrozenClock(NOW),
    )

    snapshot = service.advance_invitation_state(
        context(),
        INVITATION_ID,
        from_state="materials_submitted",
        to_state="analyzing",
        meta=CommandMeta.create("analysis-started", expected_version=4),
    )

    assert snapshot.state == "analyzing"
    assert snapshot.row_version == 5
    assert repository.saved_invitations == []
    assert repository.state_changes == []
