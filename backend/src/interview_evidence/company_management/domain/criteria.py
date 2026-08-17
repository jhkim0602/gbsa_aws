from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from interview_evidence.shared.interview_level import (
    DEFAULT_INTERVIEW_LEVEL,
    InterviewLevel,
)


class PublishedVersionImmutableError(ValueError):
    """Raised when a published competency model is edited."""


class StaleCriterionVersionError(ValueError):
    """Raised when optimistic concurrency detects a late write."""


class CompetencyModelStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


def _system_persona_definition() -> dict[str, object]:
    return {
        "mode": "system_managed",
        "tone": "neutral",
        "voice_id": "Seoyeon",
    }


class RequirementType(StrEnum):
    REQUIRED = "required"
    PREFERRED = "preferred"


class JobRequirement(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_requirement_id: UUID
    requirement_type: RequirementType
    statement: str = Field(min_length=1, max_length=4000)
    priority: int = Field(ge=1, le=5)
    criterion_code: str = Field(pattern=r"^[A-Z0-9_-]{2,40}$")


class CriterionVerificationGuide(BaseModel):
    model_config = ConfigDict(frozen=True)

    observable_dimensions: tuple[str, ...] = Field(min_length=1, max_length=12)
    strong_answer_signals: tuple[str, ...] = Field(min_length=1, max_length=12)
    weak_answer_signals: tuple[str, ...] = Field(min_length=1, max_length=12)
    follow_up_directions: tuple[str, ...] = Field(min_length=1, max_length=8)
    max_follow_ups: int = Field(ge=0, le=3)
    time_budget_seconds: int = Field(ge=60, le=1800)

    @field_validator(
        "observable_dimensions",
        "strong_answer_signals",
        "weak_answer_signals",
        "follow_up_directions",
    )
    @classmethod
    def entries_are_non_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(item.strip() for item in value)
        if any(not item for item in normalized):
            raise ValueError("verification guide entries must not be blank")
        return normalized


class EvaluationCriterion(BaseModel):
    model_config = ConfigDict(frozen=True)

    criterion_id: UUID
    code: str = Field(pattern=r"^[A-Z0-9_-]{2,40}$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    weight: float = Field(ge=0)
    verification_guide: CriterionVerificationGuide = Field(
        default_factory=lambda: CriterionVerificationGuide(
            observable_dimensions=("구체적인 상황", "본인 행동", "결과"),
            strong_answer_signals=("본인 행동과 판단 근거가 구체적이다.",),
            weak_answer_signals=("팀 활동 또는 결과만 언급한다.",),
            follow_up_directions=("본인이 직접 수행한 행동",),
            max_follow_ups=1,
            time_budget_seconds=300,
        )
    )
    abstain_guidance: str = Field(min_length=1, max_length=4000)
    common_questions: tuple[str, ...] = ()
    required: bool


class CompetencyModelVersion(BaseModel):
    model_config = ConfigDict(frozen=True)

    competency_model_version_id: UUID
    company_id: UUID
    position_id: UUID
    version_number: int = Field(ge=1)
    job_requirements: tuple[JobRequirement, ...] = ()
    criteria: tuple[EvaluationCriterion, ...] = Field(min_length=1)
    prohibited_topics: tuple[str, ...] = ()
    interview_duration_minutes: int = Field(ge=10, le=120)
    #: How deep the interview digs. Versioned with the criteria rather than stored on
    #: the position, so changing it produces a new published version and every report
    #: stays traceable to the level its interview was conducted at.
    interview_level: InterviewLevel = DEFAULT_INTERVIEW_LEVEL
    persona_definition: dict[str, object] = Field(default_factory=_system_persona_definition)
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

    @model_validator(mode="after")
    def requirements_reference_known_criteria(self) -> CompetencyModelVersion:
        criterion_codes = {criterion.code for criterion in self.criteria}
        unknown = {
            requirement.criterion_code
            for requirement in self.job_requirements
            if requirement.criterion_code not in criterion_codes
        }
        if unknown:
            raise ValueError("job requirement criterion must exist in the same version")
        return self

    @classmethod
    def create(
        cls,
        *,
        competency_model_version_id: UUID,
        company_id: UUID,
        position_id: UUID,
        version_number: int,
        job_requirements: tuple[JobRequirement, ...] = (),
        criteria: tuple[EvaluationCriterion, ...],
        prohibited_topics: tuple[str, ...],
        interview_duration_minutes: int,
        interview_level: InterviewLevel = DEFAULT_INTERVIEW_LEVEL,
        persona_definition: dict[str, object] | None = None,
    ) -> CompetencyModelVersion:
        return cls(
            competency_model_version_id=competency_model_version_id,
            company_id=company_id,
            position_id=position_id,
            version_number=version_number,
            job_requirements=job_requirements,
            criteria=criteria,
            prohibited_topics=prohibited_topics,
            interview_duration_minutes=interview_duration_minutes,
            interview_level=interview_level,
            persona_definition=persona_definition
            or {
                "mode": "system_managed",
                "tone": "neutral",
                "voice_id": "Seoyeon",
            },
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
