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
