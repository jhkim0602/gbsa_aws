from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from interview_evidence.company_management.adapters.applicant_session import (
    ApplicantSessionAdapter,
    IssuedInvitationToken,
)
from interview_evidence.company_management.domain.hiring import Invitation
from interview_evidence.company_management.repositories.postgres import CompanyRepository
from interview_evidence.shared.idempotency import ResourceIdempotencyStore
from interview_evidence.shared.ids import Clock, new_uuid7
from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class ApplicantInvitationInput:
    email: str
    display_name: str


@dataclass(frozen=True, slots=True)
class InvitationIssuance:
    invitation: Invitation
    token: IssuedInvitationToken


class HiringService:
    def __init__(
        self,
        repository: CompanyRepository,
        sessions: ApplicantSessionAdapter,
        clock: Clock,
        idempotency: ResourceIdempotencyStore,
    ) -> None:
        self._repository = repository
        self._sessions = sessions
        self._clock = clock
        self._idempotency = idempotency

    def issue_invitations(
        self,
        context: TenantContext,
        *,
        position_id: UUID,
        applicants: tuple[ApplicantInvitationInput, ...],
        expires_at: datetime,
    ) -> tuple[InvitationIssuance, ...]:
        self._repository.get_position(context, position_id)
        versions = self._repository.list_criterion_versions(context, position_id)
        published = [version for version in versions if version.status == "published"]
        if not published:
            raise ValueError("invitations require a published competency model")
        version = max(published, key=lambda item: item.version_number)
        issuances: list[InvitationIssuance] = []
        for applicant in applicants:
            invitation_id = new_uuid7(self._clock.now())
            applicant_id = new_uuid7(self._clock.now())
            token = self._sessions.issue_token(
                invitation_id=invitation_id,
                company_id=context.company_id,
                applicant_id=applicant_id,
                expires_at=expires_at,
            )
            invitation = Invitation.create(
                invitation_id=invitation_id,
                company_id=context.company_id,
                position_id=position_id,
                competency_model_version_id=version.competency_model_version_id,
                applicant_id=applicant_id,
                applicant_email=applicant.email,
                applicant_display_name=applicant.display_name,
                token_hash=token.token_hash,
                expires_at=expires_at,
            )
            self._repository.save_invitation(context, invitation)
            issuances.append(InvitationIssuance(invitation=invitation, token=token))
        return tuple(issuances)

    def list_invitations(self, context: TenantContext, position_id: UUID) -> tuple[Invitation, ...]:
        self._repository.get_position(context, position_id)
        return self._repository.list_invitations(context, position_id)
