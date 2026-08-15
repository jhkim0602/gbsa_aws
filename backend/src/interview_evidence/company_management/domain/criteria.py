from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PublishedVersionImmutableError(ValueError):
    """Raised when a published competency model is edited."""


class StaleCriterionVersionError(ValueError):
    """Raised when optimistic concurrency detects a late write."""


class CompetencyModelStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


class EvaluationCriterion(BaseModel):
    model_config = ConfigDict(frozen=True)

    criterion_id: UUID
    code: str = Field(pattern=r"^[A-Z0-9_-]{2,40}$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    weight: float = Field(ge=0)
    good_evidence: dict[str, object]
    weak_evidence: dict[str, object]
    abstain_guidance: str = Field(min_length=1, max_length=4000)
    common_questions: tuple[str, ...] = ()
    required: bool


class CompetencyModelVersion(BaseModel):
    model_config = ConfigDict(frozen=True)

    competency_model_version_id: UUID
    company_id: UUID
    position_id: UUID
    version_number: int = Field(ge=1)
    criteria: tuple[EvaluationCriterion, ...] = Field(min_length=1)
    prohibited_topics: tuple[str, ...] = ()
    interview_duration_minutes: int = Field(ge=10, le=120)
    persona_definition: dict[str, object]
    status: CompetencyModelStatus = CompetencyModelStatus.DRAFT
    row_version: int = Field(default=1, ge=1)
    published_at: datetime | None = None

    @field_validator("criteria")
    @classmethod
    def criterion_codes_are_unique(
        cls, value: tuple[EvaluationCriterion, ...]
    ) -> tuple[EvaluationCriterion, ...]:
        codes = [criterion.code for criterion in value]
        if len(codes) != len(set(codes)):
            raise ValueError("criterion codes must be unique within a version")
        return value

    @model_validator(mode="after")
    def published_versions_have_a_timestamp(self) -> CompetencyModelVersion:
        if self.status is CompetencyModelStatus.PUBLISHED and self.published_at is None:
            raise ValueError("published competency versions require published_at")
        return self

    @classmethod
    def create(
        cls,
        *,
        competency_model_version_id: UUID,
        company_id: UUID,
        position_id: UUID,
        version_number: int,
        criteria: tuple[EvaluationCriterion, ...],
        prohibited_topics: tuple[str, ...],
        interview_duration_minutes: int,
        persona_definition: dict[str, object],
    ) -> CompetencyModelVersion:
        return cls(
            competency_model_version_id=competency_model_version_id,
            company_id=company_id,
            position_id=position_id,
            version_number=version_number,
            criteria=criteria,
            prohibited_topics=prohibited_topics,
            interview_duration_minutes=interview_duration_minutes,
            persona_definition=persona_definition,
        )

    def publish(
        self,
        *,
        expected_version: int,
        published_at: datetime,
    ) -> CompetencyModelVersion:
        if self.status is not CompetencyModelStatus.DRAFT:
            raise PublishedVersionImmutableError("only draft competency versions can be published")
        if expected_version != self.row_version:
            raise StaleCriterionVersionError("stale competency model version")
        return self.model_copy(
            update={
                "status": CompetencyModelStatus.PUBLISHED,
                "published_at": published_at,
                "row_version": self.row_version + 1,
            }
        )

    def replace_persona(
        self,
        persona_definition: dict[str, object],
    ) -> CompetencyModelVersion:
        if self.status is not CompetencyModelStatus.DRAFT:
            raise PublishedVersionImmutableError("published competency versions are immutable")
        return self.model_copy(
            update={
                "persona_definition": persona_definition,
                "row_version": self.row_version + 1,
            }
        )
