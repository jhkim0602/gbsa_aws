from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from interview_evidence.company_management.domain.company import Position
from interview_evidence.company_management.domain.hiring import (
    InvitationStateChange,
)
from interview_evidence.company_management.repositories.postgres import CompanyRepository
from interview_evidence.shared.ids import Clock, CommandMeta, new_uuid7
from interview_evidence.shared.security.principals import CompanyPrincipal
from interview_evidence.shared.tenant import TenantContext


class CompanyUserSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    company_user_id: UUID
    company_id: UUID
    email: str
    status: str


class CriterionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    criterion_id: UUID
    code: str
    name: str
    description: str
    weight: float
    good_evidence: dict[str, object]
    weak_evidence: dict[str, object]
    abstain_guidance: str
    common_questions: tuple[str, ...]
    required: bool


class CriterionVersionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    company_id: UUID
    competency_model_version_id: UUID
    position_id: UUID
    version_number: int
    criteria: tuple[CriterionSnapshot, ...]
    prohibited_topics: tuple[str, ...]
    interview_duration_minutes: int
    persona_definition: dict[str, object]
    published_at: datetime


class CampaignSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    company_id: UUID
    campaign_id: UUID
    position_id: UUID
    competency_model_version_id: UUID
    prohibited_topics: tuple[str, ...]
    interview_duration_minutes: int
    persona_definition: dict[str, object]


class InvitationAuthorization(BaseModel):
    model_config = ConfigDict(frozen=True)

    company_id: UUID
    invitation_id: UUID
    applicant_id: UUID
    campaign_id: UUID
    state: str
    expires_at: datetime
    authorized: bool


class ConsentAuthorizationSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    company_id: UUID
    invitation_id: UUID
    consent_record_id: UUID | None
    policy_version: str | None
    accepted_purposes: frozenset[str]
    withdrawn_at: datetime | None
    retention_days: int | None
    authorized: bool


class InvitationStateSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    company_id: UUID
    invitation_id: UUID
    state: str
    row_version: int


class CompanyService:
    def __init__(self, repository: CompanyRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock
        self._idempotent_positions: dict[tuple[UUID, str], UUID] = {}

    def get_current_user(
        self,
        context: TenantContext,
        principal: CompanyPrincipal,
    ) -> CompanyUserSnapshot:
        context.assert_company(principal.company_id)
        return CompanyUserSnapshot(
            company_user_id=principal.company_user_id,
            company_id=principal.company_id,
            email=f"{principal.company_user_id}@tenant.local",
            status="active",
        )

    def create_position(
        self,
        context: TenantContext,
        principal: CompanyPrincipal,
        *,
        title: str,
        description: str,
        idempotency_key: str,
    ) -> Position:
        context.assert_company(principal.company_id)
        existing_id = self._idempotent_positions.get((context.company_id, idempotency_key))
        if existing_id is not None:
            return self._repository.get_position(context, existing_id)
        position = Position(
            position_id=new_uuid7(self._clock.now()),
            company_id=context.company_id,
            title=title,
            description=description,
            created_by=principal.company_user_id,
            created_at=self._clock.now(),
        )
        self._repository.save_position(context, position)
        self._idempotent_positions[(context.company_id, idempotency_key)] = position.position_id
        return position

    def list_positions(self, context: TenantContext) -> tuple[Position, ...]:
        return self._repository.list_positions(context)


class CompanyManagementPublic:
    """Only the frozen Lane A application contract exposed to other lanes."""

    def __init__(self, repository: CompanyRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    def get_campaign_snapshot(
        self,
        context: TenantContext,
        campaign_id: UUID,
    ) -> CampaignSnapshot:
        campaign = self._repository.get_campaign(context, campaign_id)
        criterion = self.get_criterion_version(context, campaign.competency_model_version_id)
        return CampaignSnapshot(
            company_id=context.company_id,
            campaign_id=campaign.campaign_id,
            position_id=campaign.position_id,
            competency_model_version_id=criterion.competency_model_version_id,
            prohibited_topics=criterion.prohibited_topics,
            interview_duration_minutes=criterion.interview_duration_minutes,
            persona_definition=criterion.persona_definition,
        )

    def get_criterion_version(
        self,
        context: TenantContext,
        version_id: UUID,
    ) -> CriterionVersionSnapshot:
        version = self._repository.get_criterion_version(context, version_id)
        if version.published_at is None or version.status != "published":
            raise PermissionError("only published criterion versions are exportable")
        return CriterionVersionSnapshot(
            company_id=context.company_id,
            competency_model_version_id=version.competency_model_version_id,
            position_id=version.position_id,
            version_number=version.version_number,
            criteria=tuple(
                CriterionSnapshot.model_validate(criterion.model_dump())
                for criterion in version.criteria
            ),
            prohibited_topics=version.prohibited_topics,
            interview_duration_minutes=version.interview_duration_minutes,
            persona_definition=version.persona_definition,
            published_at=version.published_at,
        )

    def authorize_invitation(
        self,
        context: TenantContext,
        invitation_id: UUID,
        *,
        required_state: str,
    ) -> InvitationAuthorization:
        invitation = self._repository.get_invitation(context, invitation_id)
        return InvitationAuthorization(
            company_id=context.company_id,
            invitation_id=invitation.invitation_id,
            applicant_id=invitation.applicant_id,
            campaign_id=invitation.campaign_id,
            state=invitation.status.value,
            expires_at=invitation.expires_at,
            authorized=(
                invitation.status.value == required_state
                and self._clock.now() < invitation.expires_at
            ),
        )

    def get_consent_authorization(
        self,
        context: TenantContext,
        invitation_id: UUID,
        *,
        required_purposes: frozenset[str],
    ) -> ConsentAuthorizationSnapshot:
        consent = self._repository.get_latest_consent(context, invitation_id)
        if consent is None:
            return ConsentAuthorizationSnapshot(
                company_id=context.company_id,
                invitation_id=invitation_id,
                consent_record_id=None,
                policy_version=None,
                accepted_purposes=frozenset(),
                withdrawn_at=None,
                retention_days=None,
                authorized=False,
            )
        return ConsentAuthorizationSnapshot(
            company_id=context.company_id,
            invitation_id=invitation_id,
            consent_record_id=consent.consent_record_id,
            policy_version=consent.policy_version,
            accepted_purposes=frozenset(purpose.value for purpose in consent.purposes),
            withdrawn_at=consent.withdrawn_at,
            retention_days=consent.retention_days,
            authorized=(
                consent.withdrawn_at is None
                and required_purposes.issubset(purpose.value for purpose in consent.purposes)
            ),
        )

    def advance_invitation_state(
        self,
        context: TenantContext,
        invitation_id: UUID,
        *,
        from_state: str,
        to_state: str,
        meta: CommandMeta,
    ) -> InvitationStateSnapshot:
        current = self._repository.get_invitation(context, invitation_id)
        if current.status.value != from_state:
            raise ValueError("invitation state does not match the requested transition")
        if meta.expected_version is None:
            raise ValueError("expected_version is required")
        updated = current.transition(
            to_state,
            actor_type=context.actor_type.value,
            occurred_at=meta.occurred_at,
            expected_version=meta.expected_version,
        )
        self._repository.save_invitation(context, updated)
        self._repository.append_invitation_state_change(
            context,
            InvitationStateChange(
                invitation_state_change_id=new_uuid7(self._clock.now()),
                company_id=context.company_id,
                invitation_id=invitation_id,
                from_status=current.status,
                to_status=updated.status,
                actor_type=context.actor_type.value,
                occurred_at=meta.occurred_at,
                aggregate_version=updated.row_version,
            ),
        )
        return InvitationStateSnapshot(
            company_id=context.company_id,
            invitation_id=invitation_id,
            state=updated.status.value,
            row_version=updated.row_version,
        )
