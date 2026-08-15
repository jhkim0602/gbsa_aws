from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from interview_evidence.company_management.adapters.applicant_session import (
    ApplicantSessionAdapter,
    IssuedInvitationToken,
)
from interview_evidence.company_management.domain.hiring import Campaign, Invitation
from interview_evidence.company_management.repositories.postgres import CompanyRepository
from interview_evidence.shared.idempotency import (
    InMemoryResourceIdempotencyStore,
    ResourceIdempotencyStore,
)
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
        idempotency: ResourceIdempotencyStore | None = None,
    ) -> None:
        self._repository = repository
        self._sessions = sessions
        self._clock = clock
        self._idempotency = idempotency or InMemoryResourceIdempotencyStore()

    def create_campaign(
        self,
        context: TenantContext,
        *,
        position_id: UUID,
        competency_model_version_id: UUID,
        name: str,
        candidate_instructions: str,
        idempotency_key: str,
    ) -> Campaign:
        existing_id = self._idempotency.get(
            context,
            operation="campaign.create",
            idempotency_key=idempotency_key,
        )
        if existing_id is not None:
            return self._repository.get_campaign(context, existing_id)
        version = self._repository.get_criterion_version(context, competency_model_version_id)
        campaign = Campaign.create(
            campaign_id=new_uuid7(self._clock.now()),
            company_id=context.company_id,
            position_id=position_id,
            competency_model_version=version,
            name=name,
            candidate_instructions=candidate_instructions,
        )
        self._repository.save_campaign(context, campaign)
        self._idempotency.put(
            context,
            operation="campaign.create",
            idempotency_key=idempotency_key,
            resource_id=campaign.campaign_id,
        )
        return campaign

    def publish_campaign(
        self,
        context: TenantContext,
        *,
        campaign_id: UUID,
        expected_version: int,
    ) -> Campaign:
        current = self._repository.get_campaign(context, campaign_id)
        published = current.publish(
            expected_version=expected_version,
            published_at=self._clock.now(),
        )
        return self._repository.save_campaign(context, published)

    def issue_invitations(
        self,
        context: TenantContext,
        *,
        campaign_id: UUID,
        applicants: tuple[ApplicantInvitationInput, ...],
        expires_at: datetime,
    ) -> tuple[InvitationIssuance, ...]:
        campaign = self._repository.get_campaign(context, campaign_id)
        if campaign.status != "published":
            raise ValueError("invitations require a published campaign")
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
                campaign_id=campaign_id,
                applicant_id=applicant_id,
                applicant_email=applicant.email,
                applicant_display_name=applicant.display_name,
                token_hash=token.token_hash,
                expires_at=expires_at,
            )
            self._repository.save_invitation(context, invitation)
            issuances.append(InvitationIssuance(invitation=invitation, token=token))
        return tuple(issuances)

    def list_invitations(self, context: TenantContext, campaign_id: UUID) -> tuple[Invitation, ...]:
        return self._repository.list_invitations(context, campaign_id)
