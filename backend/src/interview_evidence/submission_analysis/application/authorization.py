from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from interview_evidence.shared.security.principals import ApplicantPrincipal
from interview_evidence.shared.submission_materials import (
    DEFAULT_SUBMISSION_REQUIREMENTS,
    SubmissionRequirement,
)
from interview_evidence.shared.tenant import TenantContext

FAKE_SUBMISSION_REQUIREMENTS = tuple(
    requirement.model_copy(
        update={"required": requirement.material_type.value == "resume"}
    )
    for requirement in DEFAULT_SUBMISSION_REQUIREMENTS
)


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


class FakeSubmissionAuthorization:
    def __init__(
        self,
        *,
        principal: ApplicantPrincipal,
        authorized: bool,
        reason: str | None = None,
        requirements: tuple[SubmissionRequirement, ...] = FAKE_SUBMISSION_REQUIREMENTS,
    ) -> None:
        self._principal = principal
        self._authorized = authorized
        self._reason = reason
        self._requirements = requirements
        self.calls: list[UUID] = []
        self.materials_submitted_calls: list[UUID] = []

    @classmethod
    def allowed(cls, principal: ApplicantPrincipal) -> FakeSubmissionAuthorization:
        return cls(principal=principal, authorized=True)

    @classmethod
    def denied(
        cls,
        principal: ApplicantPrincipal,
        *,
        reason: str,
    ) -> FakeSubmissionAuthorization:
        return cls(principal=principal, authorized=False, reason=reason)

    def authorize(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
    ) -> SubmissionAuthorization:
        context.assert_company(principal.company_id)
        self.calls.append(principal.invitation_id)
        if principal != self._principal or not self._authorized:
            raise SubmissionAuthorizationDenied(
                self._reason or "submission authorization denied"
            )
        return SubmissionAuthorization(
            company_id=principal.company_id,
            invitation_id=principal.invitation_id,
            applicant_id=principal.applicant_id,
            position_id=UUID(int=0),
            position_title="테스트 포지션",
            requirements=self._requirements,
            policy_version="2026-08-v1",
            retention_days=180,
        )

    def mark_required_materials_submitted(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
    ) -> None:
        context.assert_company(principal.company_id)
        self.materials_submitted_calls.append(principal.invitation_id)
