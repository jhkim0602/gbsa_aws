from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from interview_evidence.shared.security.principals import ApplicantPrincipal
from interview_evidence.shared.submission_materials import SubmissionRequirement
from interview_evidence.shared.tenant import TenantContext


class SubmissionAuthorizationDenied(PermissionError):
    """Raised before any storage or analysis work begins."""


@dataclass(frozen=True, slots=True)
class SubmissionAuthorization:
    company_id: UUID
    invitation_id: UUID
    applicant_id: UUID
    position_id: UUID
    position_title: str
    requirements: tuple[SubmissionRequirement, ...]
    policy_version: str
    retention_days: int


class SubmissionAuthorizationPort(Protocol):
    def authorize(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
    ) -> SubmissionAuthorization: ...

    def mark_required_materials_submitted(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
    ) -> None: ...
