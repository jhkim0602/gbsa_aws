from __future__ import annotations

from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from interview_evidence.shared.security.principals import ApplicantPrincipal
from interview_evidence.shared.tenant import TenantContext


class InterviewAuthorizationDenied(PermissionError):
    pass


class InterviewAuthorization(BaseModel):
    model_config = ConfigDict(frozen=True)

    company_id: UUID
    invitation_id: UUID
    applicant_id: UUID
    strategy_id: UUID
    competency_model_version_id: UUID
    partial_analysis: bool


class InterviewAuthorizationPort(Protocol):
    def authorize_start(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        *,
        strategy_id: UUID,
        acknowledged_partial_analysis: bool,
    ) -> InterviewAuthorization: ...


class FakeInterviewAuthorization:
    def __init__(
        self,
        authorization: InterviewAuthorization | None,
        *,
        reason: str = "interview_not_authorized",
    ) -> None:
        self._authorization = authorization
        self._reason = reason

    def authorize_start(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        *,
        strategy_id: UUID,
        acknowledged_partial_analysis: bool,
    ) -> InterviewAuthorization:
        authorization = self._authorization
        if (
            authorization is None
            or authorization.company_id != context.company_id
            or authorization.company_id != principal.company_id
            or authorization.invitation_id != principal.invitation_id
            or authorization.applicant_id != principal.applicant_id
            or authorization.strategy_id != strategy_id
            or (authorization.partial_analysis and not acknowledged_partial_analysis)
        ):
            raise InterviewAuthorizationDenied(self._reason)
        return authorization

    @classmethod
    def denied(cls, *, reason: str) -> FakeInterviewAuthorization:
        return cls(None, reason=reason)
