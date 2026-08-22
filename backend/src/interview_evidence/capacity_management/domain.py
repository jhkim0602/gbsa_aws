from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CapacityServiceRole(StrEnum):
    API = "api"
    WORKER = "worker"


class CapacityReservationStatus(StrEnum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


class CapacityReservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    position_id: UUID
    company_id: UUID
    source_version: int = Field(ge=1)
    status: CapacityReservationStatus
    expected_concurrency: int | None = Field(default=None, ge=1, le=10_000)
    interview_at: datetime | None = None
    interview_duration_minutes: int = Field(default=30, ge=30, le=30)
    updated_at: datetime

    @field_validator("interview_at", "updated_at")
    @classmethod
    def timestamps_must_include_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("capacity timestamps must include a timezone")
        return value

    @property
    def is_schedulable(self) -> bool:
        return (
            self.status is CapacityReservationStatus.ACTIVE
            and self.expected_concurrency is not None
            and self.interview_at is not None
        )


class CapacityTarget(BaseModel):
    model_config = ConfigDict(frozen=True)

    service_role: CapacityServiceRole
    min_capacity: int = Field(ge=0)
    max_capacity: int = Field(ge=1)
    expected_load: int = Field(ge=0)
    saturated: bool = False


class ScheduledCapacityAction(BaseModel):
    model_config = ConfigDict(frozen=True)

    action_name: str = Field(min_length=1, max_length=256)
    service_role: CapacityServiceRole
    effective_at: datetime
    min_capacity: int = Field(ge=0)
    max_capacity: int = Field(ge=1)
    expected_load: int = Field(ge=0)
    plan_hash: str = Field(min_length=64, max_length=64)

    @field_validator("effective_at")
    @classmethod
    def effective_time_must_include_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("scheduled action time must include a timezone")
        return value


class CapacityPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: datetime
    current_targets: tuple[CapacityTarget, ...]
    scheduled_actions: tuple[ScheduledCapacityAction, ...]
    saturated_services: tuple[CapacityServiceRole, ...] = ()
