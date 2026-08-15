from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ActorType(StrEnum):
    COMPANY_USER = "company_user"
    APPLICANT = "applicant"
    SYSTEM = "system"


class TenantScopeError(PermissionError):
    """Raised before a missing or mismatched tenant can reach storage."""


class TenantContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    company_id: UUID
    actor_type: ActorType
    actor_id: UUID
    request_id: UUID
    trace_id: str = Field(min_length=1, max_length=200)

    def assert_company(self, resource_company_id: UUID) -> None:
        if resource_company_id != self.company_id:
            raise TenantScopeError("resource is outside the active tenant")


def require_tenant_context(context: TenantContext | None) -> TenantContext:
    if context is None:
        raise TenantScopeError("tenant context is required")
    return context
