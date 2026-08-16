from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from interview_evidence.company_management.adapters.applicant_session import (
    ApplicantSessionAdapter,
    InvitationTokenAlreadyUsedError,
    InvitationTokenExpiredError,
    InvitationTokenNotFoundError,
)
from interview_evidence.company_management.application.applicant_access_service import (
    ApplicantAccessService,
)
from interview_evidence.company_management.domain.applicant_access import ProcessingPurpose
from interview_evidence.shared.ids import Clock, SystemClock
from interview_evidence.shared.security.principals import (
    ApplicantPrincipal,
    PrincipalNotFoundError,
)
from interview_evidence.shared.tenant import ActorType, TenantContext


class ApplicantTokenExchange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invitation_token: str = Field(min_length=32, max_length=4096)


class ApplicantIdentityVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=200)
    verification_value: str = Field(min_length=1, max_length=500)


class ApplicantAccessState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invitation_id: UUID
    state: str
    expires_at: datetime
    required_actions: list[str]


class ConsentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_version: str = Field(min_length=1, max_length=100)
    accepted_purposes: tuple[ProcessingPurpose, ...] = Field(min_length=1)
    consent_content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class ConsentPolicyPurposeView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: ProcessingPurpose
    title: str
    description: str


class ConsentPolicyView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_version: str
    ai_role: str
    recording_notice: str
    processing_purposes: list[ConsentPolicyPurposeView]
    retention_days: int
    deletion_method: str
    required_purposes: list[ProcessingPurpose]
    content_digest: str


class ConsentView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consent_record_id: UUID
    policy_version: str
    accepted_purposes: list[str]
    retention_days: int
    accepted_at: datetime


def create_applicant_router(
    *,
    sessions: ApplicantSessionAdapter,
    access_service: ApplicantAccessService,
    clock: Clock | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/v1")
    active_clock = clock or SystemClock()

    def applicant_scope(
        request: Request,
        session_cookie: Annotated[
            str | None,
            Cookie(alias="iep_applicant_session"),
        ] = None,
    ) -> tuple[ApplicantPrincipal, TenantContext]:
        if session_cookie is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        try:
            principal = sessions.get_applicant_principal(session_cookie)
        except PrincipalNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED) from error
        request_id = _optional_uuid(request.headers.get("x-request-id"))
        effective_request_id = request_id or principal.session_id
        return principal, TenantContext(
            company_id=principal.company_id,
            actor_type=ActorType.APPLICANT,
            actor_id=principal.applicant_id,
            request_id=effective_request_id,
            trace_id=request.headers.get("x-trace-id") or str(effective_request_id),
        )

    IdempotencyKey = Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=16, max_length=128),
    ]

    @router.post(
        "/applicant/access/exchange",
        status_code=status.HTTP_204_NO_CONTENT,
        operation_id="exchangeApplicantInvitationToken",
    )
    def exchange_applicant_invitation_token(
        body: ApplicantTokenExchange,
        response: Response,
        idempotency_key: IdempotencyKey,
    ) -> None:
        del idempotency_key
        try:
            _, cookie = sessions.exchange(body.invitation_token)
        except (
            InvitationTokenNotFoundError,
            InvitationTokenExpiredError,
            InvitationTokenAlreadyUsedError,
        ) as error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED) from error
        max_age = max(
            0,
            int((cookie.expires_at - active_clock.now()).total_seconds()),
        )
        response.set_cookie(
            key="iep_applicant_session",
            value=cookie.raw_value,
            max_age=max_age,
            expires=cookie.expires_at,
            secure=True,
            httponly=True,
            samesite="strict",
            path="/v1/applicant",
        )

    @router.post(
        "/applicant/access/revoke",
        status_code=status.HTTP_204_NO_CONTENT,
        operation_id="revokeApplicantSession",
    )
    def revoke_applicant_session(
        request: Request,
        response: Response,
        session_cookie: Annotated[
            str | None,
            Cookie(alias="iep_applicant_session"),
        ] = None,
    ) -> None:
        applicant_scope(request, session_cookie)
        assert session_cookie is not None
        sessions.revoke(session_cookie)
        response.delete_cookie(
            key="iep_applicant_session",
            secure=True,
            httponly=True,
            samesite="strict",
            path="/v1/applicant",
        )

    @router.post(
        "/applicant/identity-verifications",
        response_model=ApplicantAccessState,
        operation_id="verifyApplicantIdentity",
    )
    def verify_applicant_identity(
        body: ApplicantIdentityVerification,
        request: Request,
        idempotency_key: IdempotencyKey,
        session_cookie: Annotated[
            str | None,
            Cookie(alias="iep_applicant_session"),
        ] = None,
    ) -> ApplicantAccessState:
        del idempotency_key
        principal, context = applicant_scope(request, session_cookie)
        try:
            _, invitation = access_service.verify_identity(
                context,
                principal,
                display_name=body.display_name,
                verification_value=body.verification_value,
            )
        except PermissionError as error:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN) from error
        return ApplicantAccessState(
            invitation_id=invitation.invitation_id,
            state=invitation.status.value,
            expires_at=invitation.expires_at,
            required_actions=["consent"],
        )

    @router.get(
        "/applicant/consents",
        response_model=ConsentPolicyView,
        operation_id="getApplicantConsentPolicy",
    )
    def get_applicant_consent_policy(
        request: Request,
        session_cookie: Annotated[
            str | None,
            Cookie(alias="iep_applicant_session"),
        ] = None,
    ) -> ConsentPolicyView:
        applicant_scope(request, session_cookie)
        policy = access_service.get_consent_policy()
        return ConsentPolicyView(
            policy_version=policy.policy_version,
            ai_role=policy.ai_role,
            recording_notice=policy.recording_notice,
            processing_purposes=[
                ConsentPolicyPurposeView.model_validate(item.model_dump())
                for item in policy.processing_purposes
            ],
            retention_days=policy.retention_days,
            deletion_method=policy.deletion_method,
            required_purposes=sorted(
                policy.required_purposes,
                key=lambda purpose: purpose.value,
            ),
            content_digest=policy.content_digest,
        )

    @router.post(
        "/applicant/consents",
        response_model=ConsentView,
        status_code=status.HTTP_201_CREATED,
        operation_id="recordApplicantConsent",
    )
    def record_applicant_consent(
        body: ConsentCreate,
        request: Request,
        idempotency_key: IdempotencyKey,
        session_cookie: Annotated[
            str | None,
            Cookie(alias="iep_applicant_session"),
        ] = None,
    ) -> ConsentView:
        del idempotency_key
        principal, context = applicant_scope(request, session_cookie)
        try:
            consent = access_service.record_consent(
                context,
                principal,
                policy_version=body.policy_version,
                accepted_purposes=body.accepted_purposes,
                consent_content_digest=body.consent_content_digest,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
            ) from error
        return ConsentView(
            consent_record_id=consent.consent_record_id,
            policy_version=consent.policy_version,
            accepted_purposes=sorted(purpose.value for purpose in consent.purposes),
            retention_days=consent.retention_days,
            accepted_at=consent.accepted_at,
        )

    return router


def _optional_uuid(value: str | None) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None
