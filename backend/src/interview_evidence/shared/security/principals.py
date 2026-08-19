from __future__ import annotations

from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PrincipalNotFoundError(PermissionError):
    """Raised without exposing whether a credential once existed."""


class CompanyPrincipal(BaseModel):
    model_config = ConfigDict(frozen=True)

    company_id: UUID
    company_user_id: UUID
    identity_subject: str = Field(min_length=1, max_length=512)


class ApplicantPrincipal(BaseModel):
    model_config = ConfigDict(frozen=True)

    company_id: UUID
    invitation_id: UUID
    applicant_id: UUID
    session_id: UUID


class PrincipalProvider(Protocol):
    def get_company_principal(self, credential: str) -> CompanyPrincipal: ...

    def get_applicant_principal(self, credential: str) -> ApplicantPrincipal: ...
