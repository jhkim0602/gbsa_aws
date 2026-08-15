from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ErrorCode(StrEnum):
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    TENANT_SCOPE_DENIED = "TENANT_SCOPE_DENIED"
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    STALE_VERSION = "STALE_VERSION"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    INCOMPATIBLE_VERSION = "INCOMPATIBLE_VERSION"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"


class ErrorItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    code: str


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str = "about:blank"
    title: str
    status: int = Field(ge=400, le=599)
    code: str
    detail: str | None = None
    request_id: UUID
    retryable: bool
    current_version: int | None = Field(default=None, ge=0)
    errors: tuple[ErrorItem, ...] | None = None


class DomainError(Exception):
    def __init__(
        self,
        *,
        status: int,
        code: str,
        title: str,
        request_id: UUID,
        retryable: bool = False,
        detail: str | None = None,
        current_version: int | None = None,
        errors: tuple[ErrorItem, ...] | None = None,
        error_type: str = "about:blank",
    ) -> None:
        super().__init__(title)
        self.envelope = ErrorEnvelope(
            type=error_type,
            title=title,
            status=status,
            code=code,
            detail=detail,
            request_id=request_id,
            retryable=retryable,
            current_version=current_version,
            errors=errors,
        )

    def as_dict(self) -> dict[str, Any]:
        return self.envelope.model_dump(mode="json", exclude_none=True)
