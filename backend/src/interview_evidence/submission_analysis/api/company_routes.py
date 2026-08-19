from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from interview_evidence.shared.security.principals import (
    CompanyPrincipal,
    PrincipalNotFoundError,
    PrincipalProvider,
)
from interview_evidence.shared.submission_materials import SubmissionMaterialType
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.domain.submission import SourceType
from interview_evidence.submission_analysis.repositories.postgres import (
    SubmissionRepository,
)


class CompanySubmissionView(BaseModel):
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


@dataclass(frozen=True, slots=True)
class CompanySubmissionScope:
    principal: CompanyPrincipal
    context: TenantContext


class SubmissionObjectPresigner(Protocol):
    def create_playback_url(
        self,
        context: TenantContext,
        *,
        object_key: str,
        expires_in_seconds: int,
    ) -> str: ...


def create_company_submission_router(
    *,
    principal_provider: PrincipalProvider,
    repository: SubmissionRepository,
    presigner: SubmissionObjectPresigner | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/v1")

    def company_scope(
        request: Request,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> CompanySubmissionScope:
        if authorization is None or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        try:
            principal = principal_provider.get_company_principal(
                authorization.removeprefix("Bearer ").strip()
            )
        except PrincipalNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED) from error
        request_id_text = request.headers.get("x-request-id")
        request_id = UUID(request_id_text) if request_id_text else UUID(int=0)
        return CompanySubmissionScope(
            principal=principal,
            context=TenantContext(
                company_id=principal.company_id,
                actor_type=ActorType.COMPANY_USER,
                actor_id=principal.company_user_id,
                request_id=request_id,
                trace_id=request.headers.get("x-trace-id", "trace-company-submission"),
            ),
        )

    Scope = Annotated[CompanySubmissionScope, Depends(company_scope)]

    @router.get(
        "/company/invitations/{invitation_id}/submissions",
        response_model=list[CompanySubmissionView],
        operation_id="listCompanyApplicantSubmissions",
    )
    def list_company_applicant_submissions(
        invitation_id: UUID,
        scope: Scope,
    ) -> list[CompanySubmissionView]:
        submissions = repository.list_submissions_for_invitation(
            scope.context,
            invitation_id,
        )
        return [
            CompanySubmissionView(
                submission_id=submission.submission_id,
                material_type=submission.material_type,
                source_type=submission.source_type.value,
                original_filename=submission.original_filename,
                source_url=_source_url(scope.context, submission, presigner),
                status=submission.status.value,
                failure_code=submission.failure_code,
                impact_summary=submission.impact_summary,
                created_at=submission.created_at,
            )
            for submission in submissions
        ]

    return router


def _source_url(
    context: TenantContext,
    submission: object,
    presigner: SubmissionObjectPresigner | None,
) -> str | None:
    source_type = submission.source_type
    source_uri = str(submission.source_uri)
    if source_type in {SourceType.PUBLIC_GIT, SourceType.PUBLIC_URL}:
        return source_uri
    if presigner is None:
        return None
    return presigner.create_playback_url(
        context,
        object_key=source_uri,
        expires_in_seconds=300,
    )
