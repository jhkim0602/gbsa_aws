from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


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


class InterviewerTone(StrEnum):
    CALM = "calm"
    FRIENDLY = "friendly"
    ANALYTICAL = "analytical"
    CONCISE = "concise"


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
    role_type: str | None = Field(default=None, max_length=100)
    headcount: int | None = Field(default=None, ge=1, le=10_000)
    recruitment_start_at: date | None = None
    recruitment_end_at: date | None = None
    created_by: UUID
    status: PositionStatus = PositionStatus.DRAFT
    row_version: int = Field(default=1, ge=1)
    created_at: datetime

    @field_validator("recruitment_end_at")
    @classmethod
    def validate_recruitment_period(
        cls,
        value: date | None,
        info: ValidationInfo,
    ) -> date | None:
        start = info.data.get("recruitment_start_at")
        if value is not None and start is not None and value < start:
            raise ValueError("recruitment_end_at must not be before recruitment_start_at")
        return value

    def activate(self, *, expected_version: int) -> Position:
        if expected_version != self.row_version:
            raise ValueError("stale position version")
        return self.model_copy(
            update={"status": PositionStatus.ACTIVE, "row_version": self.row_version + 1}
        )

    def revise(
        self,
        *,
        expected_version: int,
        title: str,
        description: str,
        role_type: str | None,
        headcount: int | None,
        recruitment_start_at: date | None,
        recruitment_end_at: date | None,
        status: PositionStatus,
    ) -> Position:
        if expected_version != self.row_version:
            raise ValueError("stale position version")
        if self.status is PositionStatus.CLOSED:
            raise ValueError("closed positions are immutable")
        allowed_statuses = {
            PositionStatus.DRAFT: {PositionStatus.DRAFT, PositionStatus.ACTIVE},
            PositionStatus.ACTIVE: {PositionStatus.ACTIVE, PositionStatus.CLOSED},
            PositionStatus.CLOSED: {PositionStatus.CLOSED},
        }
        if status not in allowed_statuses[self.status]:
            raise ValueError("invalid position status transition")
        return Position(
            **self.model_dump(
                exclude={
                    "title",
                    "description",
                    "role_type",
                    "headcount",
                    "recruitment_start_at",
                    "recruitment_end_at",
                    "status",
                    "row_version",
                }
            ),
            title=title,
            description=description,
            role_type=role_type,
            headcount=headcount,
            recruitment_start_at=recruitment_start_at,
            recruitment_end_at=recruitment_end_at,
            status=status,
            row_version=self.row_version + 1,
        )


class InterviewerProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    interviewer_profile_id: UUID
    company_id: UUID
    name: str = Field(min_length=1, max_length=80)
    tone: InterviewerTone
    voice_id: str = Field(min_length=1, max_length=100)
    row_version: int = Field(default=1, ge=1)
    created_at: datetime

    def snapshot(self) -> dict[str, object]:
        return {
            "interviewer_profile_id": str(self.interviewer_profile_id),
            "name": self.name,
            "tone": self.tone.value,
            "voice_id": self.voice_id,
        }
