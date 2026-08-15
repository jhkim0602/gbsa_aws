from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from interview_evidence.submission_analysis.domain.source import (
    SourceReferenceCandidate,
)


class StrategyStatus(StrEnum):
    READY = "ready"
    PARTIAL = "partial"
    SUPERSEDED = "superseded"


class VerificationPoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    criterion_id: UUID
    prompt: str = Field(min_length=1, max_length=2000)
    source_ids: tuple[UUID, ...] = Field(min_length=1)


class InterviewStrategy(BaseModel):
    model_config = ConfigDict(frozen=True)

    interview_strategy_id: UUID
    company_id: UUID
    invitation_id: UUID
    applicant_id: UUID
    competency_model_version_id: UUID
    strategy_version: int = Field(ge=1)
    common_topics: tuple[str, ...]
    verification_points: tuple[VerificationPoint, ...]
    follow_up_directions: dict[str, list[str]]
    time_budget: dict[str, int]
    required_evidence_plan: dict[str, int]
    source_reference_candidates: tuple[SourceReferenceCandidate, ...]
    model_config_version: str
    status: StrategyStatus

    @model_validator(mode="after")
    def time_budget_is_positive(self) -> InterviewStrategy:
        if self.time_budget.get("total_seconds", 0) <= 0:
            raise ValueError("strategy total time budget must be positive")
        return self
