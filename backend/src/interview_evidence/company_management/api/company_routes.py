from datetime import date, datetime
from typing import Annotated, Protocol
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
from interview_evidence.company_management.application.interviewer_service import (
    InterviewerProfileService,
)
from interview_evidence.company_management.domain.company import (
    InterviewerProfile,
    InterviewerTone,
    Position,
    PositionStatus,
)
from interview_evidence.company_management.domain.criteria import CompetencyModelVersion
from interview_evidence.company_management.domain.hiring import Invitation
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
    good_evidence: dict[str, object] = Field(default_factory=dict)
    weak_evidence: dict[str, object] = Field(default_factory=dict)
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
    interviewer_service: InterviewerProfileService,
    hiring_service: HiringService,
    audit: AuditAppender,
    invitation_email: InvitationEmailHandler | None = None,
    applicant_access_base_url: str = "https://applicant.local/access",
    interview_sessions: InvitationSessionResolver | None = None,
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
        except ValueError as error:
            code = (
                status.HTTP_409_CONFLICT
                if "stale" in str(error)
                else status.HTTP_422_UNPROCESSABLE_ENTITY
            )
            raise HTTPException(status_code=code, detail=str(error)) from error
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
            invitations=[
                _invitation_view(
                    issuance.invitation,
                    interview_sessions=interview_sessions,
                    context=scope.context,
                )
                for issuance in issuances
            ],
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
        persona_definition=version.persona_definition,
        status=version.status.value,
        row_version=version.row_version,
        published_at=version.published_at,
    )


def _invitation_view(
    invitation: Invitation,
    *,
    interview_sessions: InvitationSessionResolver | None = None,
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
        interview_session_id=(session.interview_session_id if session is not None else None),
    )
