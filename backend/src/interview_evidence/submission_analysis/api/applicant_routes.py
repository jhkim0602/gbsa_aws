from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from interview_evidence.shared.audit import AuditAppender
from interview_evidence.shared.security.principals import (
    ApplicantPrincipal,
    PrincipalNotFoundError,
    PrincipalProvider,
)
from interview_evidence.shared.submission_materials import (
    SubmissionMaterialType,
    SubmissionRequirement,
)
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.application.authorization import (
    SubmissionAuthorization,
    SubmissionAuthorizationDenied,
    SubmissionAuthorizationPort,
)
from interview_evidence.submission_analysis.application.submission_service import (
    SubmissionService,
)
from interview_evidence.submission_analysis.application.submission_validator import (
    SubmissionValidationError,
)
from interview_evidence.submission_analysis.domain.submission import (
    SourceType,
    Submission,
)


class UploadIntentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: SourceType
    filename: str = Field(min_length=1, max_length=255)
    media_type: str
    byte_size: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class UploadIntentView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_id: UUID
    method: str
    url: str
    required_headers: dict[str, str]
    expires_at: datetime


class SubmissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_type: SubmissionMaterialType
    source_type: SourceType
    upload_id: UUID | None = None
    public_url: str | None = None
    candidate_identity_inputs: dict[str, object] | None = None

    @model_validator(mode="after")
    def source_reference_matches_type(self) -> "SubmissionCreate":
        is_file = self.source_type in {
            SourceType.COVER_LETTER,
            SourceType.RESUME,
            SourceType.PDF,
        }
        if is_file and (self.upload_id is None or self.public_url is not None):
            raise ValueError("file submissions require upload_id only")
        if not is_file and (self.public_url is None or self.upload_id is not None):
            raise ValueError("public submissions require public_url only")
        return self


class SubmissionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_id: UUID
    material_type: SubmissionMaterialType
    source_type: str
    original_filename: str | None
    source_url: str | None
    status: str
    failure_code: str | None
    impact_summary: str | None
    created_at: datetime


class AnalysisReadinessView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_status: str
    submissions: list[SubmissionView]
    interview_ready: bool
    strategy_id: UUID | None = None
    strategy_version: int | None = None
    impact_summary: str | None = None


class SubmissionWorkspaceView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position_id: UUID
    position_title: str
    requirements: list[SubmissionRequirement]
    submissions: list[SubmissionView]


class ApplicantScope(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    principal: ApplicantPrincipal
    context: TenantContext
    authorization: SubmissionAuthorization


def create_applicant_submission_router(
    *,
    principal_provider: PrincipalProvider,
    authorization: SubmissionAuthorizationPort,
    service: SubmissionService,
    audit: AuditAppender,
) -> APIRouter:
    router = APIRouter(prefix="/v1")

    def applicant_scope(
        request: Request,
        session_cookie: Annotated[
            str | None,
            Cookie(alias="iep_applicant_session"),
        ] = None,
    ) -> ApplicantScope:
        if session_cookie is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        try:
            principal = principal_provider.get_applicant_principal(session_cookie)
        except PrincipalNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED) from error
        request_id = _optional_uuid(request.headers.get("x-request-id"))
        effective_request_id = request_id or principal.session_id
        context = TenantContext(
            company_id=principal.company_id,
            actor_type=ActorType.APPLICANT,
            actor_id=principal.applicant_id,
            request_id=effective_request_id,
            trace_id=request.headers.get("x-trace-id") or str(effective_request_id),
        )
        try:
            submission_authorization = authorization.authorize(context, principal)
        except SubmissionAuthorizationDenied as error:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN) from error
        return ApplicantScope(
            principal=principal,
            context=context,
            authorization=submission_authorization,
        )

    IdempotencyKey = Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=16, max_length=128),
    ]
    Scope = Annotated[ApplicantScope, Depends(applicant_scope)]

    @router.post(
        "/applicant/submissions/upload-intents",
        response_model=UploadIntentView,
        status_code=status.HTTP_201_CREATED,
        operation_id="createSubmissionUploadIntent",
    )
    def create_upload_intent(
        body: UploadIntentCreate,
        scope: Scope,
        idempotency_key: IdempotencyKey,
    ) -> UploadIntentView:
        del idempotency_key
        try:
            intent = service.create_upload_intent(
                scope.context,
                scope.principal,
                source_type=body.source_type,
                filename=body.filename,
                media_type=body.media_type,
                byte_size=body.byte_size,
                sha256=body.sha256,
            )
        except SubmissionValidationError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
            ) from error
        audit.append(
            scope.context,
            action="submission.upload_intent_created",
            resource_type="upload_intent",
            resource_id=intent.upload_id,
            result="success",
            metadata={"byte_size": intent.byte_size, "source_type": intent.source_type},
        )
        return UploadIntentView(
            upload_id=intent.upload_id,
            method=intent.method,
            url=intent.url,
            required_headers=intent.required_headers,
            expires_at=intent.expires_at,
        )

    @router.get(
        "/applicant/submission-workspace",
        response_model=SubmissionWorkspaceView,
        operation_id="getApplicantSubmissionWorkspace",
    )
    def get_submission_workspace(scope: Scope) -> SubmissionWorkspaceView:
        submissions = service.list_submissions(
            scope.context,
            scope.principal.applicant_id,
        )
        return SubmissionWorkspaceView(
            position_id=scope.authorization.position_id,
            position_title=scope.authorization.position_title,
            requirements=list(scope.authorization.requirements),
            submissions=[_submission_view(submission) for submission in submissions],
        )

    @router.get(
        "/applicant/submissions",
        response_model=list[SubmissionView],
        operation_id="listApplicantSubmissions",
    )
    def list_submissions(scope: Scope) -> list[SubmissionView]:
        return [
            _submission_view(submission)
            for submission in service.list_submissions(scope.context, scope.principal.applicant_id)
        ]

    @router.post(
        "/applicant/submissions",
        response_model=SubmissionView,
        status_code=status.HTTP_202_ACCEPTED,
        operation_id="registerApplicantSubmission",
    )
    def register_submission(
        body: SubmissionCreate,
        scope: Scope,
        idempotency_key: IdempotencyKey,
    ) -> SubmissionView:
        try:
            if body.upload_id is not None:
                submission = service.register_file_submission(
                    scope.context,
                    scope.principal,
                    material_type=body.material_type,
                    source_type=body.source_type,
                    upload_id=body.upload_id,
                    requirements=scope.authorization.requirements,
                    idempotency_key=idempotency_key,
                )
            else:
                assert body.public_url is not None
                submission = service.register_public_submission(
                    scope.context,
                    scope.principal,
                    material_type=body.material_type,
                    source_type=body.source_type,
                    public_url=body.public_url,
                    candidate_identity_inputs=body.candidate_identity_inputs,
                    requirements=scope.authorization.requirements,
                    idempotency_key=idempotency_key,
                )
        except (SubmissionValidationError, ValueError) as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
            ) from error
        audit.append(
            scope.context,
            action="submission.registered",
            resource_type="submission",
            resource_id=submission.submission_id,
            result="accepted",
            metadata={
                "source_type": submission.source_type.value,
                "material_type": submission.material_type.value,
            },
        )
        if service.required_materials_submitted(
            scope.context,
            scope.principal,
            scope.authorization.requirements,
        ):
            authorization.mark_required_materials_submitted(
                scope.context,
                scope.principal,
            )
        return _submission_view(submission)

    @router.get(
        "/applicant/analysis-status",
        response_model=AnalysisReadinessView,
        operation_id="getApplicantAnalysisStatus",
    )
    def get_analysis_status(scope: Scope) -> AnalysisReadinessView:
        readiness = service.readiness(
            scope.context,
            scope.principal,
            scope.authorization.requirements,
        )
        return AnalysisReadinessView(
            overall_status=readiness.overall_status,
            submissions=[_submission_view(submission) for submission in readiness.submissions],
            interview_ready=readiness.interview_ready,
            strategy_id=readiness.strategy_id,
            strategy_version=readiness.strategy_version,
            impact_summary=readiness.impact_summary,
        )

    return router


def _submission_view(submission: Submission) -> SubmissionView:
    return SubmissionView(
        submission_id=submission.submission_id,
        material_type=submission.material_type,
        source_type=submission.source_type.value,
        original_filename=submission.original_filename,
        source_url=(
            submission.source_uri
            if submission.source_type in {SourceType.PUBLIC_GIT, SourceType.PUBLIC_URL}
            else None
        ),
        status=submission.status.value,
        failure_code=submission.failure_code,
        impact_summary=submission.impact_summary,
        created_at=submission.created_at,
    )


def _optional_uuid(value: str | None) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None
