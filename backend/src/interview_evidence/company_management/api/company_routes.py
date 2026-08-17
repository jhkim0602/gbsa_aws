from datetime import date, datetime
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from interview_evidence.company_management.adapters.company_auth import CompanyAuthAdapter
from interview_evidence.company_management.application.company_service import CompanyService
from interview_evidence.company_management.application.criteria_service import CriteriaService
from interview_evidence.company_management.application.hiring_service import (
    ApplicantInvitationInput,
    HiringService,
)
from interview_evidence.company_management.application.interviewer_service import (
    InterviewerProfileService,
)
from interview_evidence.company_management.application.invitation_template_service import (
    InvitationTemplateService,
    LogoTooLargeError,
    UnsupportedLogoTypeError,
)
from interview_evidence.company_management.domain.company import (
    InterviewerProfile,
    InterviewerTone,
    Position,
    PositionStatus,
    StalePositionVersionError,
)
from interview_evidence.company_management.domain.criteria import (
    CompetencyModelVersion,
    PublishedVersionImmutableError,
    StaleCriterionVersionError,
)
from interview_evidence.company_management.domain.hiring import Invitation
from interview_evidence.company_management.repositories.postgres import (
    TenantScopedResourceNotFound,
)
from interview_evidence.company_management.workers.invitation_email import (
    InvitationEmailCommand,
    InvitationEmailHandler,
    format_deadline,
)
from interview_evidence.shared.audit import AuditAppender
from interview_evidence.shared.email_templates import (
    MAX_GUIDE_LINES,
    InvitationEmailTemplate,
)
from interview_evidence.shared.interview_level import (
    DEFAULT_INTERVIEW_LEVEL,
    InterviewLevel,
)
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
    role_type: str | None = Field(default=None, max_length=100)
    headcount: int | None = Field(default=None, ge=1, le=10_000)
    recruitment_start_at: date | None = None
    recruitment_end_at: date | None = None


class PositionView(PositionCreate):
    position_id: UUID
    status: str
    row_version: int
    created_at: datetime


class PositionUpdate(PositionCreate):
    status: PositionStatus


class PositionPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PositionView]
    next_cursor: str | None = None


class InterviewerProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    tone: InterviewerTone
    voice_id: str = Field(min_length=1, max_length=100)


class InterviewerProfileView(InterviewerProfileCreate):
    interviewer_profile_id: UUID
    row_version: int
    created_at: datetime


class InterviewerProfilePage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[InterviewerProfileView]
    next_cursor: str | None = None


class EvaluationCriterionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^[A-Z0-9_-]{2,40}$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    weight: float = Field(ge=0)
    verification_guide: "CriterionVerificationGuideInput"
    abstain_guidance: str = Field(min_length=1)
    common_questions: tuple[str, ...] = ()
    required: bool


class JobRequirementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_type: str = Field(pattern=r"^(required|preferred)$")
    statement: str = Field(min_length=1, max_length=4000)
    priority: int = Field(ge=1, le=5)
    criterion_code: str = Field(pattern=r"^[A-Z0-9_-]{2,40}$")


class CriterionVerificationGuideInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observable_dimensions: tuple[str, ...] = Field(min_length=1, max_length=12)
    strong_answer_signals: tuple[str, ...] = Field(min_length=1, max_length=12)
    weak_answer_signals: tuple[str, ...] = Field(min_length=1, max_length=12)
    follow_up_directions: tuple[str, ...] = Field(min_length=1, max_length=8)
    max_follow_ups: int = Field(ge=0, le=3)
    time_budget_seconds: int = Field(ge=60, le=1800)


class CompetencyModelVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_requirements: tuple[JobRequirementInput, ...] = Field(min_length=1, max_length=50)
    criteria: tuple[EvaluationCriterionInput, ...] = Field(min_length=1)
    prohibited_topics: tuple[str, ...]
    interview_duration_minutes: int = Field(ge=10, le=120)
    interview_level: InterviewLevel = DEFAULT_INTERVIEW_LEVEL
    persona_definition: dict[str, object] | None = None


class CompetencyModelVersionView(CompetencyModelVersionCreate):
    job_requirements: tuple[JobRequirementInput, ...] = Field(max_length=50)
    competency_model_version_id: UUID
    position_id: UUID
    version_number: int
    status: str
    row_version: int
    published_at: datetime | None


class CompetencyModelVersionPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CompetencyModelVersionView]
    next_cursor: str | None = None


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
    position_id: UUID
    competency_model_version_id: UUID
    applicant_email: str
    applicant_display_name: str | None = None
    status: str
    expires_at: datetime
    row_version: int
    analysis_status: str | None = None
    interview_status: str | None = None
    report_status: str | None = None
    interview_session_id: UUID | None = None


class InvitationSessionSnapshot(Protocol):
    @property
    def interview_session_id(self) -> UUID: ...

    @property
    def state(self) -> str: ...


class InvitationSessionResolver(Protocol):
    def find_session_for_invitation(
        self,
        context: TenantContext,
        *,
        invitation_id: UUID,
    ) -> InvitationSessionSnapshot | None: ...


class InvitationReviewSnapshot(Protocol):
    @property
    def report_status(self) -> str: ...


class InvitationReviewResolver(Protocol):
    def get_invitation_review(
        self,
        context: TenantContext,
        *,
        invitation_id: UUID,
    ) -> InvitationReviewSnapshot | None: ...


class InvitationPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[InvitationView]
    next_cursor: str | None = None


class InvitationBatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted_count: int
    rejected_count: int
    invitations: list[InvitationView]


class InvitationEmailTemplateInput(BaseModel):
    """The editable template as the console sends it.

    ``logo_url`` is deliberately absent: the server derives it from the uploaded logo so
    a client cannot point every invitation at a host it controls.
    """

    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1, max_length=200)
    headline: str = Field(min_length=1, max_length=200)
    intro: str = Field(min_length=1, max_length=2_000)
    guides: tuple[str, ...] = Field(default=(), max_length=MAX_GUIDE_LINES)
    cta_label: str = Field(min_length=1, max_length=40)
    outro: str = Field(default="", max_length=1_000)
    footer: str = Field(default="", max_length=300)
    brand_color: str = Field(default="#5966ce", pattern=r"^#[0-9a-fA-F]{6}$")
    use_applicant_name: bool = True
    emphasize_deadline: bool = True
    show_security_notice: bool = True

    def to_template(self) -> InvitationEmailTemplate:
        return InvitationEmailTemplate.model_validate(self.model_dump())


class InvitationEmailTemplateView(InvitationEmailTemplateInput):
    logo_url: str | None = None
    #: False when this position inherits the company-wide template.
    is_position_override: bool = False


class InvitationEmailPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    html_body: str


class CompanyLogoView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logo_url: str
    content_type: str
    byte_size: int


class CompanyRequestScope(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    principal: CompanyPrincipal
    context: TenantContext


def create_company_router(
    *,
    auth: CompanyAuthAdapter,
    company_service: CompanyService,
    criteria_service: CriteriaService,
    interviewer_service: InterviewerProfileService,
    hiring_service: HiringService,
    template_service: InvitationTemplateService,
    audit: AuditAppender,
    invitation_email: InvitationEmailHandler | None = None,
    applicant_access_base_url: str = "https://applicant.local/access",
    interview_sessions: InvitationSessionResolver | None = None,
    invitation_reviews: InvitationReviewResolver | None = None,
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
            role_type=body.role_type,
            headcount=body.headcount,
            recruitment_start_at=body.recruitment_start_at,
            recruitment_end_at=body.recruitment_end_at,
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

    @router.get(
        "/positions/{position_id}",
        response_model=PositionView,
        operation_id="getPosition",
    )
    def get_position(position_id: UUID, scope: Scope) -> PositionView:
        try:
            position = company_service.get_position(scope.context, position_id)
        except TenantScopedResourceNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        return _position_view(position)

    @router.patch(
        "/positions/{position_id}",
        response_model=PositionView,
        operation_id="updatePosition",
    )
    def update_position(
        position_id: UUID,
        body: PositionUpdate,
        scope: Scope,
        if_match_version: IfMatchVersion,
    ) -> PositionView:
        try:
            position = company_service.update_position(
                scope.context,
                position_id=position_id,
                expected_version=if_match_version,
                title=body.title,
                description=body.description,
                role_type=body.role_type,
                headcount=body.headcount,
                recruitment_start_at=body.recruitment_start_at,
                recruitment_end_at=body.recruitment_end_at,
                status=body.status,
            )
        except TenantScopedResourceNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        except StalePositionVersionError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
            ) from error
        audit.append(
            scope.context,
            action="position.updated",
            resource_type="position",
            resource_id=position.position_id,
            result="success",
            metadata={
                "row_version": position.row_version,
                "status": position.status.value,
            },
        )
        return _position_view(position)

    @router.get(
        "/interviewer-profiles",
        response_model=InterviewerProfilePage,
        operation_id="listInterviewerProfiles",
    )
    def list_interviewer_profiles(
        scope: Scope,
        cursor: Annotated[str | None, Query(max_length=512)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> InterviewerProfilePage:
        del cursor
        profiles = interviewer_service.list(scope.context)[:limit]
        return InterviewerProfilePage(
            items=[_interviewer_profile_view(profile) for profile in profiles]
        )

    @router.post(
        "/interviewer-profiles",
        response_model=InterviewerProfileView,
        status_code=status.HTTP_201_CREATED,
        operation_id="createInterviewerProfile",
    )
    def create_interviewer_profile(
        body: InterviewerProfileCreate,
        scope: Scope,
        idempotency_key: IdempotencyKey,
    ) -> InterviewerProfileView:
        profile = interviewer_service.create(
            scope.context,
            name=body.name,
            tone=body.tone,
            voice_id=body.voice_id,
            idempotency_key=idempotency_key,
        )
        audit.append(
            scope.context,
            action="interviewer_profile.created",
            resource_type="interviewer_profile",
            resource_id=profile.interviewer_profile_id,
            result="success",
            metadata={"row_version": profile.row_version, "tone": profile.tone.value},
        )
        return _interviewer_profile_view(profile)

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
                job_requirements=tuple(item.model_dump() for item in body.job_requirements),
                criteria=tuple(item.model_dump() for item in body.criteria),
                prohibited_topics=body.prohibited_topics,
                interview_duration_minutes=body.interview_duration_minutes,
                interview_level=body.interview_level,
                idempotency_key=idempotency_key,
            )
        except TenantScopedResourceNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
            ) from error
        audit.append(
            scope.context,
            action="criterion_version.created",
            resource_type="competency_model_version",
            resource_id=version.competency_model_version_id,
            result="success",
            metadata={"row_version": version.row_version},
        )
        return _criterion_view(version)

    @router.get(
        "/positions/{position_id}/competency-model-versions",
        response_model=CompetencyModelVersionPage,
        operation_id="listCompetencyModelVersions",
    )
    def list_competency_model_versions(
        position_id: UUID,
        scope: Scope,
        cursor: Annotated[str | None, Query(max_length=512)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> CompetencyModelVersionPage:
        del cursor
        try:
            versions = criteria_service.list_versions(scope.context, position_id)[:limit]
        except TenantScopedResourceNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        return CompetencyModelVersionPage(items=[_criterion_view(version) for version in versions])

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
        except (StaleCriterionVersionError, PublishedVersionImmutableError) as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        audit.append(
            scope.context,
            action="criterion_version.published",
            resource_type="competency_model_version",
            resource_id=version.competency_model_version_id,
            result="success",
            metadata={"row_version": version.row_version},
        )
        return _criterion_view(version)

    @router.get(
        "/positions/{position_id}/invitations",
        response_model=InvitationPage,
        operation_id="listInvitations",
    )
    def list_invitations(
        position_id: UUID,
        scope: Scope,
        cursor: Annotated[str | None, Query(max_length=512)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> InvitationPage:
        del cursor
        try:
            invitations = hiring_service.list_invitations(scope.context, position_id)[:limit]
        except TenantScopedResourceNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        return InvitationPage(
            items=[
                _invitation_view(
                    invitation,
                    interview_sessions=interview_sessions,
                    invitation_reviews=invitation_reviews,
                    context=scope.context,
                )
                for invitation in invitations
            ]
        )

    @router.post(
        "/positions/{position_id}/invitations",
        response_model=InvitationBatchResult,
        status_code=status.HTTP_202_ACCEPTED,
        operation_id="createInvitations",
    )
    def create_invitations(
        position_id: UUID,
        body: InvitationBatchCreate,
        scope: Scope,
        idempotency_key: IdempotencyKey,
    ) -> InvitationBatchResult:
        del idempotency_key
        try:
            issuances = hiring_service.issue_invitations(
                scope.context,
                position_id=position_id,
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
            resource_type="position",
            resource_id=position_id,
            result="success",
            metadata={"accepted_count": len(issuances), "rejected_count": 0},
        )
        if invitation_email is not None:
            position = company_service.get_position(scope.context, position_id)
            template = template_service.resolve_for_sending(scope.context, position_id)
            company_name = template_service.company_name(scope.context)
            for issuance in issuances:
                invitation_email.handle(
                    scope.context,
                    InvitationEmailCommand(
                        invitation_id=issuance.invitation.invitation_id,
                        applicant_ref=issuance.invitation.applicant_id,
                        company_name=company_name,
                        position_title=position.title,
                        deadline_text=format_deadline(issuance.invitation.expires_at),
                        template=template,
                        recipient_address=issuance.invitation.applicant_email,
                        invitation_url=(
                            f"{applicant_access_base_url}?token={issuance.token.raw_token}"
                        ),
                        applicant_display_name=issuance.invitation.applicant_display_name,
                    ),
                )
        return InvitationBatchResult(
            accepted_count=len(issuances),
            rejected_count=0,
            invitations=[
                _invitation_view(
                    issuance.invitation,
                    interview_sessions=interview_sessions,
                    invitation_reviews=invitation_reviews,
                    context=scope.context,
                )
                for issuance in issuances
            ],
        )

    @router.get(
        "/invitation-email-template",
        response_model=InvitationEmailTemplateView,
        operation_id="getInvitationEmailTemplate",
    )
    def get_invitation_email_template(scope: Scope) -> InvitationEmailTemplateView:
        try:
            template = template_service.get_company_template(scope.context)
        except TenantScopedResourceNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        return _template_view(template, is_position_override=False)

    @router.put(
        "/invitation-email-template",
        response_model=InvitationEmailTemplateView,
        operation_id="replaceInvitationEmailTemplate",
    )
    def replace_invitation_email_template(
        body: InvitationEmailTemplateInput,
        scope: Scope,
    ) -> InvitationEmailTemplateView:
        try:
            template = template_service.save_company_template(
                scope.context,
                body.to_template(),
            )
        except TenantScopedResourceNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        audit.append(
            scope.context,
            action="invitation_email_template.updated",
            resource_type="company",
            resource_id=scope.principal.company_id,
            result="success",
            metadata={"scope": "company"},
        )
        return _template_view(template, is_position_override=False)

    @router.delete(
        "/invitation-email-template",
        response_model=InvitationEmailTemplateView,
        operation_id="deleteInvitationEmailTemplate",
    )
    def delete_invitation_email_template(scope: Scope) -> InvitationEmailTemplateView:
        """Drop the company's edits so it tracks the platform default copy again.

        The console needs this to offer "revert to default" without shipping its own
        copy of the Korean wording, which would drift from the renderer.
        """
        try:
            template = template_service.clear_company_template(scope.context)
        except TenantScopedResourceNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        audit.append(
            scope.context,
            action="invitation_email_template.reverted",
            resource_type="company",
            resource_id=scope.principal.company_id,
            result="success",
            metadata={"scope": "company"},
        )
        return _template_view(template, is_position_override=False)

    @router.get(
        "/positions/{position_id}/invitation-email-template",
        response_model=InvitationEmailTemplateView,
        operation_id="getPositionInvitationEmailTemplate",
    )
    def get_position_invitation_email_template(
        position_id: UUID,
        scope: Scope,
    ) -> InvitationEmailTemplateView:
        try:
            resolved = template_service.get_position_template(scope.context, position_id)
        except TenantScopedResourceNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        return _template_view(
            resolved.template,
            is_position_override=resolved.is_position_override,
        )

    @router.put(
        "/positions/{position_id}/invitation-email-template",
        response_model=InvitationEmailTemplateView,
        operation_id="replacePositionInvitationEmailTemplate",
    )
    def replace_position_invitation_email_template(
        position_id: UUID,
        body: InvitationEmailTemplateInput,
        scope: Scope,
    ) -> InvitationEmailTemplateView:
        try:
            resolved = template_service.save_position_template(
                scope.context,
                position_id,
                body.to_template(),
            )
        except TenantScopedResourceNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        audit.append(
            scope.context,
            action="invitation_email_template.updated",
            resource_type="position",
            resource_id=position_id,
            result="success",
            metadata={"scope": "position"},
        )
        return _template_view(
            resolved.template,
            is_position_override=resolved.is_position_override,
        )

    @router.delete(
        "/positions/{position_id}/invitation-email-template",
        response_model=InvitationEmailTemplateView,
        operation_id="deletePositionInvitationEmailTemplate",
    )
    def delete_position_invitation_email_template(
        position_id: UUID,
        scope: Scope,
    ) -> InvitationEmailTemplateView:
        """Drop the position override so the position inherits the company template."""
        try:
            resolved = template_service.save_position_template(scope.context, position_id, None)
        except TenantScopedResourceNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        audit.append(
            scope.context,
            action="invitation_email_template.reverted",
            resource_type="position",
            resource_id=position_id,
            result="success",
            metadata={"scope": "position"},
        )
        return _template_view(
            resolved.template,
            is_position_override=resolved.is_position_override,
        )

    @router.post(
        "/invitation-email-template/preview",
        response_model=InvitationEmailPreview,
        operation_id="previewInvitationEmailTemplate",
    )
    def preview_invitation_email_template(
        body: InvitationEmailTemplateInput,
        scope: Scope,
    ) -> InvitationEmailPreview:
        """Render unsaved edits against sample data so the console can show a live preview."""
        rendered = template_service.preview(scope.context, body.to_template())
        return InvitationEmailPreview(subject=rendered.subject, html_body=rendered.html_body)

    @router.put(
        "/invitation-email-template/logo",
        response_model=CompanyLogoView,
        operation_id="replaceCompanyLogo",
    )
    async def replace_company_logo(request: Request, scope: Scope) -> CompanyLogoView:
        content_type = request.headers.get("content-type", "")
        body = await request.body()
        try:
            logo = template_service.upload_logo(
                scope.context,
                content=body,
                content_type=content_type,
            )
        except TenantScopedResourceNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        except LogoTooLargeError as error:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=str(error),
            ) from error
        except UnsupportedLogoTypeError as error:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=str(error),
            ) from error
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            ) from error
        audit.append(
            scope.context,
            action="company_logo.replaced",
            resource_type="company",
            resource_id=logo.company_id,
            result="success",
            metadata={"byte_size": logo.byte_size, "content_type": logo.content_type},
        )
        return CompanyLogoView(
            logo_url=template_service.logo_url(logo.company_id),
            content_type=logo.content_type,
            byte_size=logo.byte_size,
        )

    @router.delete(
        "/invitation-email-template/logo",
        status_code=status.HTTP_204_NO_CONTENT,
        operation_id="deleteCompanyLogo",
    )
    def delete_company_logo(scope: Scope) -> None:
        template_service.delete_logo(scope.context)
        audit.append(
            scope.context,
            action="company_logo.deleted",
            resource_type="company",
            resource_id=scope.principal.company_id,
            result="success",
            metadata={},
        )

    @router.get(
        "/public/companies/{company_id}/logo",
        response_class=Response,
        operation_id="getPublicCompanyLogo",
    )
    def get_public_company_logo(company_id: UUID) -> Response:
        """Serve the logo to unauthenticated mail clients rendering an invitation.

        A recipient's mail client fetches remote images with no credentials, so this
        route cannot require a tenant context. It exposes only the logo a company chose
        to embed in its outbound email, and nothing else about the tenant.
        """
        logo = template_service.find_public_logo(company_id)
        if logo is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return Response(
            content=logo.content,
            media_type=logo.content_type,
            headers={
                "Cache-Control": "public, max-age=3600",
                "ETag": f'"{logo.sha256}"',
            },
        )

    return router


def _template_view(
    template: InvitationEmailTemplate,
    *,
    is_position_override: bool,
) -> InvitationEmailTemplateView:
    return InvitationEmailTemplateView(
        **template.model_dump(exclude={"logo_url"}),
        logo_url=template.logo_url,
        is_position_override=is_position_override,
    )


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
        role_type=position.role_type,
        headcount=position.headcount,
        recruitment_start_at=position.recruitment_start_at,
        recruitment_end_at=position.recruitment_end_at,
        status=position.status.value,
        row_version=position.row_version,
        created_at=position.created_at,
    )


def _interviewer_profile_view(profile: InterviewerProfile) -> InterviewerProfileView:
    return InterviewerProfileView(
        interviewer_profile_id=profile.interviewer_profile_id,
        name=profile.name,
        tone=profile.tone,
        voice_id=profile.voice_id,
        row_version=profile.row_version,
        created_at=profile.created_at,
    )


def _criterion_view(version: CompetencyModelVersion) -> CompetencyModelVersionView:
    return CompetencyModelVersionView(
        competency_model_version_id=version.competency_model_version_id,
        position_id=version.position_id,
        version_number=version.version_number,
        job_requirements=[
            JobRequirementInput.model_validate(
                requirement.model_dump(exclude={"job_requirement_id"})
            )
            for requirement in version.job_requirements
        ],
        criteria=[
            EvaluationCriterionInput.model_validate(criterion.model_dump(exclude={"criterion_id"}))
            for criterion in version.criteria
        ],
        prohibited_topics=version.prohibited_topics,
        interview_duration_minutes=version.interview_duration_minutes,
        interview_level=version.interview_level,
        persona_definition=version.persona_definition,
        status=version.status.value,
        row_version=version.row_version,
        published_at=version.published_at,
    )


def _invitation_view(
    invitation: Invitation,
    *,
    interview_sessions: InvitationSessionResolver | None = None,
    invitation_reviews: InvitationReviewResolver | None = None,
    context: TenantContext | None = None,
) -> InvitationView:
    session = (
        interview_sessions.find_session_for_invitation(
            context,
            invitation_id=invitation.invitation_id,
        )
        if interview_sessions is not None and context is not None
        else None
    )
    # Absent until Lane D has a report for the invitation, which is what the console reads
    # to decide whether the analysis report can be opened at all.
    review = (
        invitation_reviews.get_invitation_review(
            context,
            invitation_id=invitation.invitation_id,
        )
        if invitation_reviews is not None and context is not None
        else None
    )
    return InvitationView(
        invitation_id=invitation.invitation_id,
        position_id=invitation.position_id,
        competency_model_version_id=invitation.competency_model_version_id,
        applicant_email=invitation.applicant_email,
        applicant_display_name=invitation.applicant_display_name,
        status=invitation.status.value,
        expires_at=invitation.expires_at,
        row_version=invitation.row_version,
        interview_status=session.state if session is not None else None,
        report_status=review.report_status if review is not None else None,
        interview_session_id=(session.interview_session_id if session is not None else None),
    )
