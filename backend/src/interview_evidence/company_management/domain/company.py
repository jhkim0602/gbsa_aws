from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CompanyStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class CompanyUserStatus(StrEnum):
    INVITED = "invited"
    ACTIVE = "active"
    DISABLED = "disabled"


class PositionStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


class Company(BaseModel):
    model_config = ConfigDict(frozen=True)

    company_id: UUID
    name: str = Field(min_length=1, max_length=200)
    brand_config: dict[str, str] = Field(default_factory=dict)
    default_retention_days: int = Field(default=180, ge=1, le=3650)
    status: CompanyStatus = CompanyStatus.ACTIVE
    created_at: datetime
    updated_at: datetime


class CompanyUser(BaseModel):
    model_config = ConfigDict(frozen=True)

    company_user_id: UUID
    company_id: UUID
    identity_subject: str = Field(min_length=1, max_length=512)
    email_normalized: str = Field(min_length=3, max_length=320)
    role_code: str = Field(default="hiring_manager", min_length=1, max_length=100)
    status: CompanyUserStatus = CompanyUserStatus.ACTIVE
    created_at: datetime
    last_seen_at: datetime | None = None

    @field_validator("email_normalized")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class Position(BaseModel):
    model_config = ConfigDict(frozen=True)

    position_id: UUID
    company_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=20_000)
    created_by: UUID
    status: PositionStatus = PositionStatus.DRAFT
    row_version: int = Field(default=1, ge=1)
    created_at: datetime

    def activate(self, *, expected_version: int) -> Position:
        if expected_version != self.row_version:
            raise ValueError("stale position version")
        return self.model_copy(
            update={"status": PositionStatus.ACTIVE, "row_version": self.row_version + 1}
        )
