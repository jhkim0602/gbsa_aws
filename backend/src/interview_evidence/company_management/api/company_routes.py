from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from interview_evidence.company_management.adapters.company_auth import CompanyAuthAdapter
from interview_evidence.company_management.application.company_service import CompanyService
from interview_evidence.company_management.application.criteria_service import CriteriaService
from interview_evidence.company_management.application.hiring_service import (
    ApplicantInvitationInput,
    HiringService,
)
from interview_evidence.company_management.domain.company import Position
from interview_evidence.company_management.domain.criteria import CompetencyModelVersion
from interview_evidence.company_management.domain.hiring import Campaign, Invitation
from interview_evidence.company_management.repositories.postgres import (
    TenantScopedResourceNotFound,
)
from interview_evidence.company_management.workers.invitation_email import (
    InvitationEmailCommand,
    InvitationEmailHandler,
)
from interview_evidence.shared.audit import AuditAppender
from interview_evidence.shared.security.principals import (
    CompanyPrincipal,
    PrincipalNotFoundError,
)
from interview_evidence.shared.tenant import TenantContext


class CompanyUserView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_user_id: UUID
    company_id: UUID
    email: str
    status: str


class PositionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=20_000)


class PositionView(PositionCreate):
    position_id: UUID
    status: str
    row_version: int
    created_at: datetime


class PositionPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PositionView]
    next_cursor: str | None = None


class EvaluationCriterionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^[A-Z0-9_-]{2,40}$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    weight: float = Field(ge=0)
    good_evidence: dict[str, object]
    weak_evidence: dict[str, object]
    abstain_guidance: str = Field(min_length=1)
    common_questions: tuple[str, ...] = ()
    required: bool


class CompetencyModelVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criteria: tuple[EvaluationCriterionInput, ...] = Field(min_length=1)
    prohibited_topics: tuple[str, ...]
    interview_duration_minutes: int = Field(ge=10, le=120)
    persona_definition: dict[str, object]


class CompetencyModelVersionView(CompetencyModelVersionCreate):
    competency_model_version_id: UUID
    position_id: UUID
    version_number: int
    status: str
    row_version: int
    published_at: datetime | None


class CampaignCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position_id: UUID
    competency_model_version_id: UUID
    name: str = Field(min_length=1, max_length=200)
    candidate_instructions: str = Field(min_length=1, max_length=10_000)


class CampaignView(CampaignCreate):
    campaign_id: UUID
    status: str
    row_version: int
    published_at: datetime | None


class ApplicantInvitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=200)


class InvitationBatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    applicants: tuple[ApplicantInvitationRequest, ...] = Field(min_length=1, max_length=1000)
    expires_at: datetime


class InvitationView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invitation_id: UUID
    campaign_id: UUID
    applicant_email: str
    status: str
    expires_at: datetime
    row_version: int
    analysis_status: str | None = None
    interview_status: str | None = None
    report_status: str | None = None


class InvitationPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[InvitationView]
    next_cursor: str | None = None


class InvitationBatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted_count: int
    rejected_count: int
    invitations: list[InvitationView]


class CompanyRequestScope(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    principal: CompanyPrincipal
    context: TenantContext


def create_company_router(
    *,
    auth: CompanyAuthAdapter,
    company_service: CompanyService,
    criteria_service: CriteriaService,
    hiring_service: HiringService,
    audit: AuditAppender,
    invitation_email: InvitationEmailHandler | None = None,
    applicant_access_base_url: str = "https://applicant.local/access",
) -> APIRouter:
    router = APIRouter(prefix="/v1")

    def company_scope(
        request: Request,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> CompanyRequestScope:
        if authorization is None or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        request_id = _optional_uuid(request.headers.get("x-request-id"))
        try:
            principal, context = auth.authenticate(
                authorization.removeprefix("Bearer ").strip(),
                request_id=request_id,
                trace_id=request.headers.get("x-trace-id"),
            )
        except PrincipalNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED) from error
        return CompanyRequestScope(principal=principal, context=context)

    Scope = Annotated[CompanyRequestScope, Depends(company_scope)]
    IdempotencyKey = Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=16, max_length=128),
    ]
    IfMatchVersion = Annotated[
        int,
        Header(alias="If-Match-Version", ge=1),
    ]

    @router.get("/me", response_model=CompanyUserView, operation_id="getCurrentCompanyUser")
    def get_current_company_user(scope: Scope) -> CompanyUserView:
        snapshot = company_service.get_current_user(scope.context, scope.principal)
        return CompanyUserView.model_validate(snapshot.model_dump())

    @router.get(
        "/positions",
        response_model=PositionPage,
        operation_id="listPositions",
    )
    def list_positions(
        scope: Scope,
        cursor: Annotated[str | None, Query(max_length=512)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> PositionPage:
        del cursor
        positions = company_service.list_positions(scope.context)[:limit]
        return PositionPage(items=[_position_view(position) for position in positions])

    @router.post(
        "/positions",
        response_model=PositionView,
        status_code=status.HTTP_201_CREATED,
        operation_id="createPosition",
    )
    def create_position(
        body: PositionCreate,
        scope: Scope,
        idempotency_key: IdempotencyKey,
    ) -> PositionView:
        position = company_service.create_position(
            scope.context,
            scope.principal,
            title=body.title,
            description=body.description,
            idempotency_key=idempotency_key,
        )
        audit.append(
            scope.context,
            action="position.created",
            resource_type="position",
            resource_id=position.position_id,
            result="success",
            metadata={"row_version": position.row_version},
        )
        return _position_view(position)

    @router.post(
        "/positions/{position_id}/competency-model-versions",
        response_model=CompetencyModelVersionView,
        status_code=status.HTTP_201_CREATED,
        operation_id="createCompetencyModelVersion",
    )
    def create_competency_model_version(
        position_id: UUID,
        body: CompetencyModelVersionCreate,
        scope: Scope,
        idempotency_key: IdempotencyKey,
    ) -> CompetencyModelVersionView:
        try:
            version = criteria_service.create_version(
                scope.context,
                position_id=position_id,
                criteria=tuple(item.model_dump() for item in body.criteria),
                prohibited_topics=body.prohibited_topics,
                interview_duration_minutes=body.interview_duration_minutes,
                persona_definition=body.persona_definition,
                idempotency_key=idempotency_key,
            )
        except TenantScopedResourceNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        audit.append(
            scope.context,
            action="criterion_version.created",
            resource_type="competency_model_version",
            resource_id=version.competency_model_version_id,
            result="success",
            metadata={"row_version": version.row_version},
        )
        return _criterion_view(version)

    @router.post(
        "/competency-model-versions/{version_id}/publish",
        response_model=CompetencyModelVersionView,
        operation_id="publishCompetencyModelVersion",
    )
    def publish_competency_model_version(
        version_id: UUID,
        scope: Scope,
        idempotency_key: IdempotencyKey,
        if_match_version: IfMatchVersion,
    ) -> CompetencyModelVersionView:
        del idempotency_key
        try:
            version = criteria_service.publish_version(
                scope.context,
                version_id=version_id,
                expected_version=if_match_version,
            )
        except TenantScopedResourceNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        audit.append(
            scope.context,
            action="criterion_version.published",
            resource_type="competency_model_version",
            resource_id=version.competency_model_version_id,
            result="success",
            metadata={"row_version": version.row_version},
        )
        return _criterion_view(version)

    @router.post(
        "/campaigns",
        response_model=CampaignView,
        status_code=status.HTTP_201_CREATED,
        operation_id="createCampaign",
    )
    def create_campaign(
        body: CampaignCreate,
        scope: Scope,
        idempotency_key: IdempotencyKey,
    ) -> CampaignView:
        try:
            campaign = hiring_service.create_campaign(
                scope.context,
                position_id=body.position_id,
                competency_model_version_id=body.competency_model_version_id,
                name=body.name,
                candidate_instructions=body.candidate_instructions,
                idempotency_key=idempotency_key,
            )
        except TenantScopedResourceNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        audit.append(
            scope.context,
            action="campaign.created",
            resource_type="campaign",
            resource_id=campaign.campaign_id,
            result="success",
            metadata={"row_version": campaign.row_version},
        )
        return _campaign_view(campaign)

    @router.post(
        "/campaigns/{campaign_id}/publish",
        response_model=CampaignView,
        operation_id="publishCampaign",
    )
    def publish_campaign(
        campaign_id: UUID,
        scope: Scope,
        idempotency_key: IdempotencyKey,
        if_match_version: IfMatchVersion,
    ) -> CampaignView:
        del idempotency_key
        try:
            campaign = hiring_service.publish_campaign(
                scope.context,
                campaign_id=campaign_id,
                expected_version=if_match_version,
            )
        except TenantScopedResourceNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        audit.append(
            scope.context,
            action="campaign.published",
            resource_type="campaign",
            resource_id=campaign.campaign_id,
            result="success",
            metadata={"row_version": campaign.row_version},
        )
        return _campaign_view(campaign)

    @router.get(
        "/campaigns/{campaign_id}/invitations",
        response_model=InvitationPage,
        operation_id="listInvitations",
    )
    def list_invitations(
        campaign_id: UUID,
        scope: Scope,
        cursor: Annotated[str | None, Query(max_length=512)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> InvitationPage:
        del cursor
        try:
            invitations = hiring_service.list_invitations(scope.context, campaign_id)[:limit]
        except TenantScopedResourceNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        return InvitationPage(items=[_invitation_view(invitation) for invitation in invitations])

    @router.post(
        "/campaigns/{campaign_id}/invitations",
        response_model=InvitationBatchResult,
        status_code=status.HTTP_202_ACCEPTED,
        operation_id="createInvitations",
    )
    def create_invitations(
        campaign_id: UUID,
        body: InvitationBatchCreate,
        scope: Scope,
        idempotency_key: IdempotencyKey,
    ) -> InvitationBatchResult:
        del idempotency_key
        try:
            issuances = hiring_service.issue_invitations(
                scope.context,
                campaign_id=campaign_id,
                applicants=tuple(
                    ApplicantInvitationInput(
                        email=applicant.email,
                        display_name=applicant.display_name,
                    )
                    for applicant in body.applicants
                ),
                expires_at=body.expires_at,
            )
        except TenantScopedResourceNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        audit.append(
            scope.context,
            action="invitation.batch_created",
            resource_type="campaign",
            resource_id=campaign_id,
            result="success",
            metadata={"accepted_count": len(issuances), "rejected_count": 0},
        )
        if invitation_email is not None:
            for issuance in issuances:
                invitation_email.handle(
                    scope.context,
                    InvitationEmailCommand(
                        invitation_id=issuance.invitation.invitation_id,
                        applicant_ref=issuance.invitation.applicant_id,
                        recipient_address=issuance.invitation.applicant_email,
                        invitation_url=(
                            f"{applicant_access_base_url}?token={issuance.token.raw_token}"
                        ),
                    ),
                )
        return InvitationBatchResult(
            accepted_count=len(issuances),
            rejected_count=0,
            invitations=[_invitation_view(issuance.invitation) for issuance in issuances],
        )

    return router


def _optional_uuid(value: str | None) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def _position_view(position: Position) -> PositionView:
    return PositionView(
        position_id=position.position_id,
        title=position.title,
        description=position.description,
        status=position.status.value,
        row_version=position.row_version,
        created_at=position.created_at,
    )


def _criterion_view(version: CompetencyModelVersion) -> CompetencyModelVersionView:
    return CompetencyModelVersionView(
        competency_model_version_id=version.competency_model_version_id,
        position_id=version.position_id,
        version_number=version.version_number,
        criteria=[
            EvaluationCriterionInput.model_validate(criterion.model_dump(exclude={"criterion_id"}))
            for criterion in version.criteria
        ],
        prohibited_topics=version.prohibited_topics,
        interview_duration_minutes=version.interview_duration_minutes,
        persona_definition=version.persona_definition,
        status=version.status.value,
        row_version=version.row_version,
        published_at=version.published_at,
    )


def _campaign_view(campaign: Campaign) -> CampaignView:
    return CampaignView(
        campaign_id=campaign.campaign_id,
        position_id=campaign.position_id,
        competency_model_version_id=campaign.competency_model_version_id,
        name=campaign.name,
        candidate_instructions=campaign.candidate_instructions,
        status=campaign.status.value,
        row_version=campaign.row_version,
        published_at=campaign.published_at,
    )


def _invitation_view(invitation: Invitation) -> InvitationView:
    return InvitationView(
        invitation_id=invitation.invitation_id,
        campaign_id=invitation.campaign_id,
        applicant_email=invitation.applicant_email,
        status=invitation.status.value,
        expires_at=invitation.expires_at,
        row_version=invitation.row_version,
    )
