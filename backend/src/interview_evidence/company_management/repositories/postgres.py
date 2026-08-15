from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Protocol, TypeVar
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Uuid,
    delete,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from interview_evidence.company_management.domain.applicant_access import (
    ApplicantProfile,
    ConsentRecord,
    ProcessingPurpose,
)
from interview_evidence.company_management.domain.company import (
    Company,
    CompanyUser,
    CompanyUserStatus,
    Position,
    PositionStatus,
)
from interview_evidence.company_management.domain.criteria import (
    CompetencyModelStatus,
    CompetencyModelVersion,
    EvaluationCriterion,
)
from interview_evidence.company_management.domain.hiring import (
    Campaign,
    CampaignStatus,
    Invitation,
    InvitationStateChange,
    InvitationStatus,
)
from interview_evidence.shared.tenant import TenantContext, require_tenant_context


class TenantScopedResourceNotFound(LookupError):
    """Raised without disclosing whether another tenant owns the identifier."""


class TenantOwned(Protocol):
    @property
    def company_id(self) -> UUID: ...


TenantOwnedT = TypeVar("TenantOwnedT", bound=TenantOwned)


class Base(DeclarativeBase):
    pass


class CompanyRow(Base):
    __tablename__ = "companies"

    company_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    brand_config: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    default_retention_days: Mapped[int] = mapped_column(Integer, default=180)
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CompanyUserRow(Base):
    __tablename__ = "company_users"

    company_user_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("companies.company_id"), index=True)
    identity_subject: Mapped[str] = mapped_column(String(512))
    email_normalized: Mapped[str] = mapped_column(String(320))
    role_code: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PositionRow(Base):
    __tablename__ = "positions"

    position_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("companies.company_id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(20_000))
    created_by: Mapped[UUID] = mapped_column(Uuid)
    status: Mapped[str] = mapped_column(String(30))
    row_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CompetencyModelVersionRow(Base):
    __tablename__ = "competency_model_versions"

    competency_model_version_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    position_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("positions.position_id"))
    version_number: Mapped[int] = mapped_column(Integer)
    prohibited_topics: Mapped[list[str]] = mapped_column(JSON)
    interview_duration_minutes: Mapped[int] = mapped_column(Integer)
    persona_definition: Mapped[dict[str, object]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30))
    row_version: Mapped[int] = mapped_column(Integer)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluationCriterionRow(Base):
    __tablename__ = "evaluation_criteria"

    criterion_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    competency_model_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("competency_model_versions.competency_model_version_id"),
        index=True,
    )
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(4000))
    weight: Mapped[float] = mapped_column(Float)
    good_evidence: Mapped[dict[str, object]] = mapped_column(JSON)
    weak_evidence: Mapped[dict[str, object]] = mapped_column(JSON)
    abstain_guidance: Mapped[str] = mapped_column(String(4000))
    common_questions: Mapped[list[str]] = mapped_column(JSON)
    required: Mapped[bool] = mapped_column(Boolean)


class CampaignRow(Base):
    __tablename__ = "campaigns"

    campaign_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    position_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("positions.position_id"))
    competency_model_version_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("competency_model_versions.competency_model_version_id")
    )
    name: Mapped[str] = mapped_column(String(200))
    candidate_instructions: Mapped[str] = mapped_column(String(10_000))
    status: Mapped[str] = mapped_column(String(30))
    row_version: Mapped[int] = mapped_column(Integer)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InvitationRow(Base):
    __tablename__ = "invitations"

    invitation_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    campaign_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("campaigns.campaign_id"))
    applicant_id: Mapped[UUID] = mapped_column(Uuid, unique=True)
    applicant_email_normalized: Mapped[str] = mapped_column(String(320))
    applicant_display_name: Mapped[str] = mapped_column(String(200))
    token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(40))
    identity_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_state_actor_type: Mapped[str] = mapped_column(String(30))
    row_version: Mapped[int] = mapped_column(Integer)


class InvitationStateHistoryRow(Base):
    __tablename__ = "invitation_state_history"

    invitation_state_change_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    invitation_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("invitations.invitation_id"))
    from_status: Mapped[str] = mapped_column(String(40))
    to_status: Mapped[str] = mapped_column(String(40))
    actor_type: Mapped[str] = mapped_column(String(30))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    aggregate_version: Mapped[int] = mapped_column(Integer)


class ApplicantProfileRow(Base):
    __tablename__ = "applicant_profiles"

    applicant_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    invitation_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("invitations.invitation_id"), unique=True
    )
    display_name: Mapped[str] = mapped_column(String(200))
    verification_method: Mapped[str] = mapped_column(String(50))
    technology_tags: Mapped[list[str]] = mapped_column(JSON)


class ConsentRecordRow(Base):
    __tablename__ = "consent_records"

    consent_record_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    invitation_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("invitations.invitation_id"))
    policy_version: Mapped[str] = mapped_column(String(100))
    purposes: Mapped[list[str]] = mapped_column(JSON)
    retention_days: Mapped[int] = mapped_column(Integer)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_digest: Mapped[str] = mapped_column(String(64))


class RetentionPolicyRow(Base):
    __tablename__ = "retention_policies"

    retention_policy_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    retention_days: Mapped[int] = mapped_column(Integer)
    policy_version: Mapped[int] = mapped_column(Integer)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CompanyRepository(Protocol):
    def save_company(self, context: TenantContext, company: Company) -> Company: ...
    def save_company_user(
        self, context: TenantContext, company_user: CompanyUser
    ) -> CompanyUser: ...
    def get_company_user(self, context: TenantContext, company_user_id: UUID) -> CompanyUser: ...
    def save_position(self, context: TenantContext, position: Position) -> Position: ...
    def get_position(self, context: TenantContext, position_id: UUID) -> Position: ...
    def list_positions(self, context: TenantContext) -> tuple[Position, ...]: ...
    def save_criterion_version(
        self, context: TenantContext, version: CompetencyModelVersion
    ) -> CompetencyModelVersion: ...
    def get_criterion_version(
        self, context: TenantContext, version_id: UUID
    ) -> CompetencyModelVersion: ...
    def list_criterion_versions(
        self, context: TenantContext, position_id: UUID
    ) -> tuple[CompetencyModelVersion, ...]: ...
    def save_campaign(self, context: TenantContext, campaign: Campaign) -> Campaign: ...
    def get_campaign(self, context: TenantContext, campaign_id: UUID) -> Campaign: ...
    def save_invitation(self, context: TenantContext, invitation: Invitation) -> Invitation: ...
    def get_invitation(self, context: TenantContext, invitation_id: UUID) -> Invitation: ...
    def list_invitations(
        self, context: TenantContext, campaign_id: UUID
    ) -> tuple[Invitation, ...]: ...
    def append_invitation_state_change(
        self, context: TenantContext, change: InvitationStateChange
    ) -> None: ...
    def save_applicant_profile(
        self, context: TenantContext, profile: ApplicantProfile
    ) -> ApplicantProfile: ...
    def save_consent(self, context: TenantContext, consent: ConsentRecord) -> ConsentRecord: ...
    def get_latest_consent(
        self, context: TenantContext, invitation_id: UUID
    ) -> ConsentRecord | None: ...


class InMemoryCompanyRepository:
    def __init__(self) -> None:
        self.companies: dict[UUID, Company] = {}
        self.company_users: dict[UUID, CompanyUser] = {}
        self.positions: dict[UUID, Position] = {}
        self.criterion_versions: dict[UUID, CompetencyModelVersion] = {}
        self.campaigns: dict[UUID, Campaign] = {}
        self.invitations: dict[UUID, Invitation] = {}
        self.invitation_history: list[InvitationStateChange] = []
        self.applicant_profiles: dict[UUID, ApplicantProfile] = {}
        self.consents: dict[UUID, ConsentRecord] = {}

    @staticmethod
    def _tenant(context: TenantContext, resource_company_id: UUID) -> TenantContext:
        tenant = require_tenant_context(context)
        tenant.assert_company(resource_company_id)
        return tenant

    @staticmethod
    def _scoped(
        context: TenantContext,
        resources: Mapping[UUID, TenantOwnedT],
        resource_id: UUID,
    ) -> TenantOwnedT:
        tenant = require_tenant_context(context)
        resource = resources.get(resource_id)
        if resource is None or getattr(resource, "company_id", None) != tenant.company_id:
            raise TenantScopedResourceNotFound("tenant-scoped resource not found")
        return resource

    def save_company(self, context: TenantContext, company: Company) -> Company:
        self._tenant(context, company.company_id)
        self.companies[company.company_id] = company
        return company

    def save_company_user(self, context: TenantContext, company_user: CompanyUser) -> CompanyUser:
        self._tenant(context, company_user.company_id)
        self.company_users[company_user.company_user_id] = company_user
        return company_user

    def get_company_user(self, context: TenantContext, company_user_id: UUID) -> CompanyUser:
        return self._scoped(context, self.company_users, company_user_id)

    def save_position(self, context: TenantContext, position: Position) -> Position:
        self._tenant(context, position.company_id)
        self.positions[position.position_id] = position
        return position

    def get_position(self, context: TenantContext, position_id: UUID) -> Position:
        return self._scoped(context, self.positions, position_id)

    def list_positions(self, context: TenantContext) -> tuple[Position, ...]:
        tenant = require_tenant_context(context)
        return tuple(
            position
            for position in self.positions.values()
            if position.company_id == tenant.company_id
        )

    def save_criterion_version(
        self, context: TenantContext, version: CompetencyModelVersion
    ) -> CompetencyModelVersion:
        self._tenant(context, version.company_id)
        self.get_position(context, version.position_id)
        self.criterion_versions[version.competency_model_version_id] = version
        return version

    def get_criterion_version(
        self, context: TenantContext, version_id: UUID
    ) -> CompetencyModelVersion:
        return self._scoped(context, self.criterion_versions, version_id)

    def list_criterion_versions(
        self, context: TenantContext, position_id: UUID
    ) -> tuple[CompetencyModelVersion, ...]:
        tenant = require_tenant_context(context)
        self.get_position(context, position_id)
        return tuple(
            version
            for version in self.criterion_versions.values()
            if version.company_id == tenant.company_id and version.position_id == position_id
        )

    def save_campaign(self, context: TenantContext, campaign: Campaign) -> Campaign:
        self._tenant(context, campaign.company_id)
        self.get_position(context, campaign.position_id)
        self.get_criterion_version(context, campaign.competency_model_version_id)
        self.campaigns[campaign.campaign_id] = campaign
        return campaign

    def get_campaign(self, context: TenantContext, campaign_id: UUID) -> Campaign:
        return self._scoped(context, self.campaigns, campaign_id)

    def save_invitation(self, context: TenantContext, invitation: Invitation) -> Invitation:
        self._tenant(context, invitation.company_id)
        self.get_campaign(context, invitation.campaign_id)
        self.invitations[invitation.invitation_id] = invitation
        return invitation

    def get_invitation(self, context: TenantContext, invitation_id: UUID) -> Invitation:
        return self._scoped(context, self.invitations, invitation_id)

    def list_invitations(self, context: TenantContext, campaign_id: UUID) -> tuple[Invitation, ...]:
        tenant = require_tenant_context(context)
        self.get_campaign(context, campaign_id)
        return tuple(
            invitation
            for invitation in self.invitations.values()
            if invitation.company_id == tenant.company_id and invitation.campaign_id == campaign_id
        )

    def append_invitation_state_change(
        self, context: TenantContext, change: InvitationStateChange
    ) -> None:
        self._tenant(context, change.company_id)
        self.get_invitation(context, change.invitation_id)
        self.invitation_history.append(change)

    def save_applicant_profile(
        self, context: TenantContext, profile: ApplicantProfile
    ) -> ApplicantProfile:
        self._tenant(context, profile.company_id)
        self.get_invitation(context, profile.invitation_id)
        self.applicant_profiles[profile.applicant_id] = profile
        return profile

    def save_consent(self, context: TenantContext, consent: ConsentRecord) -> ConsentRecord:
        self._tenant(context, consent.company_id)
        self.get_invitation(context, consent.invitation_id)
        self.consents[consent.consent_record_id] = consent
        return consent

    def get_latest_consent(
        self, context: TenantContext, invitation_id: UUID
    ) -> ConsentRecord | None:
        tenant = require_tenant_context(context)
        self.get_invitation(context, invitation_id)
        matches = [
            consent
            for consent in self.consents.values()
            if consent.company_id == tenant.company_id and consent.invitation_id == invitation_id
        ]
        return max(matches, key=lambda consent: consent.accepted_at, default=None)


class SqlAlchemyCompanyRepository:
    """PostgreSQL-compatible repository with mandatory tenant predicates."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _tenant(context: TenantContext) -> TenantContext:
        return require_tenant_context(context)

    def save_company(self, context: TenantContext, company: Company) -> Company:
        self._tenant(context).assert_company(company.company_id)
        self._session.merge(
            CompanyRow(
                company_id=company.company_id,
                name=company.name,
                brand_config=company.brand_config,
                default_retention_days=company.default_retention_days,
                status=company.status.value,
                created_at=company.created_at,
                updated_at=company.updated_at,
            )
        )
        self._session.flush()
        return company

    def save_company_user(self, context: TenantContext, company_user: CompanyUser) -> CompanyUser:
        self._tenant(context).assert_company(company_user.company_id)
        self._session.merge(
            CompanyUserRow(
                company_user_id=company_user.company_user_id,
                company_id=company_user.company_id,
                identity_subject=company_user.identity_subject,
                email_normalized=company_user.email_normalized,
                role_code=company_user.role_code,
                status=company_user.status.value,
                created_at=company_user.created_at,
                last_seen_at=company_user.last_seen_at,
            )
        )
        self._session.flush()
        return company_user

    def get_company_user(self, context: TenantContext, company_user_id: UUID) -> CompanyUser:
        tenant = self._tenant(context)
        row = self._session.scalar(
            select(CompanyUserRow).where(
                CompanyUserRow.company_id == tenant.company_id,
                CompanyUserRow.company_user_id == company_user_id,
            )
        )
        if row is None:
            raise TenantScopedResourceNotFound("tenant-scoped resource not found")
        return CompanyUser(
            company_user_id=row.company_user_id,
            company_id=row.company_id,
            identity_subject=row.identity_subject,
            email_normalized=row.email_normalized,
            role_code=row.role_code,
            status=CompanyUserStatus(row.status),
            created_at=row.created_at,
            last_seen_at=row.last_seen_at,
        )

    def save_position(self, context: TenantContext, position: Position) -> Position:
        self._tenant(context).assert_company(position.company_id)
        self._session.merge(
            PositionRow(
                position_id=position.position_id,
                company_id=position.company_id,
                title=position.title,
                description=position.description,
                created_by=position.created_by,
                status=position.status.value,
                row_version=position.row_version,
                created_at=position.created_at,
            )
        )
        self._session.flush()
        return position

    def get_position(self, context: TenantContext, position_id: UUID) -> Position:
        tenant = self._tenant(context)
        row = self._session.scalar(
            select(PositionRow).where(
                PositionRow.company_id == tenant.company_id,
                PositionRow.position_id == position_id,
            )
        )
        if row is None:
            raise TenantScopedResourceNotFound("tenant-scoped resource not found")
        return Position(
            position_id=row.position_id,
            company_id=row.company_id,
            title=row.title,
            description=row.description,
            created_by=row.created_by,
            status=PositionStatus(row.status),
            row_version=row.row_version,
            created_at=row.created_at,
        )

    def list_positions(self, context: TenantContext) -> tuple[Position, ...]:
        tenant = self._tenant(context)
        rows: Sequence[PositionRow] = self._session.scalars(
            select(PositionRow).where(PositionRow.company_id == tenant.company_id)
        ).all()
        return tuple(self.get_position(context, row.position_id) for row in rows)

    def save_criterion_version(
        self, context: TenantContext, version: CompetencyModelVersion
    ) -> CompetencyModelVersion:
        self._tenant(context).assert_company(version.company_id)
        self._session.merge(
            CompetencyModelVersionRow(
                competency_model_version_id=version.competency_model_version_id,
                company_id=version.company_id,
                position_id=version.position_id,
                version_number=version.version_number,
                prohibited_topics=list(version.prohibited_topics),
                interview_duration_minutes=version.interview_duration_minutes,
                persona_definition=version.persona_definition,
                status=version.status.value,
                row_version=version.row_version,
                published_at=version.published_at,
            )
        )
        self._session.execute(
            delete(EvaluationCriterionRow).where(
                EvaluationCriterionRow.company_id == version.company_id,
                EvaluationCriterionRow.competency_model_version_id
                == version.competency_model_version_id,
            )
        )
        self._session.add_all(
            [
                EvaluationCriterionRow(
                    criterion_id=criterion.criterion_id,
                    company_id=version.company_id,
                    competency_model_version_id=version.competency_model_version_id,
                    code=criterion.code,
                    name=criterion.name,
                    description=criterion.description,
                    weight=criterion.weight,
                    good_evidence=criterion.good_evidence,
                    weak_evidence=criterion.weak_evidence,
                    abstain_guidance=criterion.abstain_guidance,
                    common_questions=list(criterion.common_questions),
                    required=criterion.required,
                )
                for criterion in version.criteria
            ]
        )
        self._session.flush()
        return version

    def get_criterion_version(
        self, context: TenantContext, version_id: UUID
    ) -> CompetencyModelVersion:
        tenant = self._tenant(context)
        row = self._session.scalar(
            select(CompetencyModelVersionRow).where(
                CompetencyModelVersionRow.company_id == tenant.company_id,
                CompetencyModelVersionRow.competency_model_version_id == version_id,
            )
        )
        if row is None:
            raise TenantScopedResourceNotFound("tenant-scoped resource not found")
        criterion_rows = self._session.scalars(
            select(EvaluationCriterionRow)
            .where(
                EvaluationCriterionRow.company_id == tenant.company_id,
                EvaluationCriterionRow.competency_model_version_id == version_id,
            )
            .order_by(EvaluationCriterionRow.code)
        ).all()
        return CompetencyModelVersion(
            competency_model_version_id=row.competency_model_version_id,
            company_id=row.company_id,
            position_id=row.position_id,
            version_number=row.version_number,
            criteria=tuple(
                EvaluationCriterion(
                    criterion_id=criterion.criterion_id,
                    code=criterion.code,
                    name=criterion.name,
                    description=criterion.description,
                    weight=criterion.weight,
                    good_evidence=criterion.good_evidence,
                    weak_evidence=criterion.weak_evidence,
                    abstain_guidance=criterion.abstain_guidance,
                    common_questions=tuple(criterion.common_questions),
                    required=criterion.required,
                )
                for criterion in criterion_rows
            ),
            prohibited_topics=tuple(row.prohibited_topics),
            interview_duration_minutes=row.interview_duration_minutes,
            persona_definition=row.persona_definition,
            status=CompetencyModelStatus(row.status),
            row_version=row.row_version,
            published_at=row.published_at,
        )

    def list_criterion_versions(
        self, context: TenantContext, position_id: UUID
    ) -> tuple[CompetencyModelVersion, ...]:
        tenant = self._tenant(context)
        rows = self._session.scalars(
            select(CompetencyModelVersionRow).where(
                CompetencyModelVersionRow.company_id == tenant.company_id,
                CompetencyModelVersionRow.position_id == position_id,
            )
        ).all()
        return tuple(
            self.get_criterion_version(context, row.competency_model_version_id) for row in rows
        )

    def save_campaign(self, context: TenantContext, campaign: Campaign) -> Campaign:
        self._tenant(context).assert_company(campaign.company_id)
        self._session.merge(
            CampaignRow(
                campaign_id=campaign.campaign_id,
                company_id=campaign.company_id,
                position_id=campaign.position_id,
                competency_model_version_id=campaign.competency_model_version_id,
                name=campaign.name,
                candidate_instructions=campaign.candidate_instructions,
                status=campaign.status.value,
                row_version=campaign.row_version,
                published_at=campaign.published_at,
            )
        )
        self._session.flush()
        return campaign

    def get_campaign(self, context: TenantContext, campaign_id: UUID) -> Campaign:
        tenant = self._tenant(context)
        row = self._session.scalar(
            select(CampaignRow).where(
                CampaignRow.company_id == tenant.company_id,
                CampaignRow.campaign_id == campaign_id,
            )
        )
        if row is None:
            raise TenantScopedResourceNotFound("tenant-scoped resource not found")
        return Campaign(
            campaign_id=row.campaign_id,
            company_id=row.company_id,
            position_id=row.position_id,
            competency_model_version_id=row.competency_model_version_id,
            name=row.name,
            candidate_instructions=row.candidate_instructions,
            status=CampaignStatus(row.status),
            row_version=row.row_version,
            published_at=row.published_at,
        )

    def save_invitation(self, context: TenantContext, invitation: Invitation) -> Invitation:
        self._tenant(context).assert_company(invitation.company_id)
        self._session.merge(
            InvitationRow(
                invitation_id=invitation.invitation_id,
                company_id=invitation.company_id,
                campaign_id=invitation.campaign_id,
                applicant_id=invitation.applicant_id,
                applicant_email_normalized=invitation.applicant_email_normalized,
                applicant_display_name=invitation.applicant_display_name,
                token_hash=invitation.token_hash,
                expires_at=invitation.expires_at,
                status=invitation.status.value,
                identity_verified_at=invitation.identity_verified_at,
                last_state_actor_type=invitation.last_state_actor_type,
                row_version=invitation.row_version,
            )
        )
        self._session.flush()
        return invitation

    def get_invitation(self, context: TenantContext, invitation_id: UUID) -> Invitation:
        tenant = self._tenant(context)
        row = self._session.scalar(
            select(InvitationRow).where(
                InvitationRow.company_id == tenant.company_id,
                InvitationRow.invitation_id == invitation_id,
            )
        )
        if row is None:
            raise TenantScopedResourceNotFound("tenant-scoped resource not found")
        return Invitation(
            invitation_id=row.invitation_id,
            company_id=row.company_id,
            campaign_id=row.campaign_id,
            applicant_id=row.applicant_id,
            applicant_email_normalized=row.applicant_email_normalized,
            applicant_display_name=row.applicant_display_name,
            token_hash=row.token_hash,
            expires_at=row.expires_at,
            status=InvitationStatus(row.status),
            identity_verified_at=row.identity_verified_at,
            last_state_actor_type=row.last_state_actor_type,
            row_version=row.row_version,
        )

    def list_invitations(self, context: TenantContext, campaign_id: UUID) -> tuple[Invitation, ...]:
        tenant = self._tenant(context)
        rows = self._session.scalars(
            select(InvitationRow).where(
                InvitationRow.company_id == tenant.company_id,
                InvitationRow.campaign_id == campaign_id,
            )
        ).all()
        return tuple(self.get_invitation(context, row.invitation_id) for row in rows)

    def append_invitation_state_change(
        self, context: TenantContext, change: InvitationStateChange
    ) -> None:
        self._tenant(context).assert_company(change.company_id)
        self._session.add(
            InvitationStateHistoryRow(
                invitation_state_change_id=change.invitation_state_change_id,
                company_id=change.company_id,
                invitation_id=change.invitation_id,
                from_status=change.from_status.value,
                to_status=change.to_status.value,
                actor_type=change.actor_type,
                occurred_at=change.occurred_at,
                aggregate_version=change.aggregate_version,
            )
        )
        self._session.flush()

    def save_applicant_profile(
        self, context: TenantContext, profile: ApplicantProfile
    ) -> ApplicantProfile:
        self._tenant(context).assert_company(profile.company_id)
        self._session.merge(
            ApplicantProfileRow(
                applicant_id=profile.applicant_id,
                company_id=profile.company_id,
                invitation_id=profile.invitation_id,
                display_name=profile.display_name,
                verification_method=profile.verification_method.value,
                technology_tags=list(profile.technology_tags),
            )
        )
        self._session.flush()
        return profile

    def save_consent(self, context: TenantContext, consent: ConsentRecord) -> ConsentRecord:
        self._tenant(context).assert_company(consent.company_id)
        self._session.merge(
            ConsentRecordRow(
                consent_record_id=consent.consent_record_id,
                company_id=consent.company_id,
                invitation_id=consent.invitation_id,
                policy_version=consent.policy_version,
                purposes=sorted(purpose.value for purpose in consent.purposes),
                retention_days=consent.retention_days,
                accepted_at=consent.accepted_at,
                withdrawn_at=consent.withdrawn_at,
                evidence_digest=consent.evidence_digest,
            )
        )
        self._session.flush()
        return consent

    def get_latest_consent(
        self, context: TenantContext, invitation_id: UUID
    ) -> ConsentRecord | None:
        tenant = self._tenant(context)
        row = self._session.scalar(
            select(ConsentRecordRow)
            .where(
                ConsentRecordRow.company_id == tenant.company_id,
                ConsentRecordRow.invitation_id == invitation_id,
            )
            .order_by(ConsentRecordRow.accepted_at.desc())
            .limit(1)
        )
        if row is None:
            return None
        return ConsentRecord(
            consent_record_id=row.consent_record_id,
            company_id=row.company_id,
            invitation_id=row.invitation_id,
            policy_version=row.policy_version,
            purposes=frozenset(ProcessingPurpose(item) for item in row.purposes),
            retention_days=row.retention_days,
            accepted_at=row.accepted_at,
            withdrawn_at=row.withdrawn_at,
            evidence_digest=row.evidence_digest,
        )
