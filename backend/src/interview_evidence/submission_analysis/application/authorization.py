from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from interview_evidence.shared.security.principals import ApplicantPrincipal
from interview_evidence.shared.tenant import TenantContext


class SubmissionAuthorizationDenied(PermissionError):
    """Raised before any storage or analysis work begins."""


@dataclass(frozen=True, slots=True)
class SubmissionAuthorization:
    company_id: UUID
    invitation_id: UUID
    applicant_id: UUID
    policy_version: str
    retention_days: int


class SubmissionAuthorizationPort(Protocol):
    def authorize(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
    ) -> SubmissionAuthorization: ...
