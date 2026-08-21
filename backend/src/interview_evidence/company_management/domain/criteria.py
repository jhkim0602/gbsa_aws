from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from interview_evidence.shared.assessment_axes import ASSESSMENT_AXIS_KEY_SET
from interview_evidence.shared.interview_level import (
    DEFAULT_INTERVIEW_LEVEL,
    InterviewLevel,
)

#: Tolerance for a weight total. The weights are JSON floats redistributed by the console,
#: so an exact ``== 100`` would reject a set that sums to 99.99999999999999.
_WEIGHT_SUM_EPSILON = 0.001


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
    #: How much each of the five scoring axes counts toward a criterion's score, keyed by
    #: ``shared.assessment_axes``. An empty mapping means equal weight, which is what every
    #: version published before weights existed carries -- and what those reports were
    #: actually scored with, so it is the honest default rather than a migration.
    #:
    #: Not on ``AssessmentAxis``: that is a ``Final`` prompt constant, and a weight is a
    #: company's choice. Not per criterion either -- a recruiter setting five numbers per
    #: criterion is a form nobody fills in correctly, and the criterion already carries the
    #: company's judgement in *which* criteria exist and what they weigh against each other.
    axis_weights: dict[str, float] = Field(default_factory=dict)
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

    @classmethod
    def criterion_weights_total_100(
        cls, value: tuple[EvaluationCriterion, ...]
    ) -> tuple[EvaluationCriterion, ...]:
        """Criterion weights are percentages and must add up to 100.

        The alternative -- accept any positive sum and divide by it when scoring -- produces
        identical scores, so this is a decision about what the recruiter reads rather than
        about arithmetic. Requiring 100 means the number on the form *is* the percentage, and
        the console keeps it there by redistributing the others as one is dragged
        (``rebalanceWeights`` in ``EvaluationDesigner.tsx``, which preserves the untouched
        criteria's ratios). Accepting 30/25/20 would leave 30 on screen meaning 40%, which the
        UI would then have to keep explaining.

        This says nothing about the denominator a report divides by. A criterion the interview
        never reached is dropped at scoring time, so the weights that actually count can total
        0.75 even though the configured ones total 100 -- which is why the calculator still
        renders its divisor.

        ``EPSILON`` rather than ``==``: the weights arrive as JSON floats, and three values a
        UI rebalanced to 100 can land on 99.99999999999999.

        **Called from :meth:`create`, not registered as a validator.** A validator runs on
        every construction, and ``_criterion_versions_from_rows`` constructs this class to read
        a row back -- so as a validator this rule rejected versions stored before it existed
        and turned every read of them into a 500: the criteria list, applicant access, the
        hiring workspace, question generation, the interview and report generation. Nothing
        enforced a total before, and the wizard displayed ``합계 {totalWeight}`` without
        checking it, so those rows are the normal case rather than corruption.

        Reading them is safe: ``scoring.aggregate`` divides by whatever the weights total, so a
        version stored at 30/25/20 already scores as 40%/33%/27% -- the proportions the
        recruiter set. The rule buys clarity for what a recruiter *enters*, and that is a write
        concern. Enforcing it here still catches it before the version is stored, which is what
        the spec asked for: the publish request fails rather than aggregation failing after the
        interview is over. ``criteria`` cannot change afterwards -- only ``publish`` and
        ``replace_persona`` mutate a version -- so checking once at creation holds for the
        version's whole life.
        """
        if not value:
            return value
        total = sum(criterion.weight for criterion in value)
        if abs(total - 100) > _WEIGHT_SUM_EPSILON:
            raise ValueError(f"criterion weights must total 100, got {total:g}")
        return value

    @model_validator(mode="after")
    def axis_weights_name_every_scoring_axis(self) -> CompetencyModelVersion:
        """Reject an axis-weight mapping that cannot be read as the recruiter meant it.

        ``dict`` differs from the criteria tuple in two ways that both produce a wrong
        score without an error: a key can be misspelled, and only some keys can be given.

        * An unknown key (``{"correctnes": 40}``) matches no axis, is silently ignored, and
          leaves the recruiter believing they weighted 정확성 at 40.
        * A partial mapping (``{"depth": 40, "correctness": 30}``) has no defined meaning.
          Reading the absent keys as 0 drops three axes out of the score; reading them as 1
          adds 40 and 1 on the same scale. Both are wrong and neither shows on screen. So
          it is all or nothing: empty (equal weight) or every key named.
        * A negative weight would mean "doing well on this axis lowers the score", which
          inverts the ranking table rather than expressing a preference.

        This is checked here rather than in aggregation because ``CompetencyModelVersion``
        is frozen and locks on publish (``PublishedVersionImmutableError``), and the report
        freezes these numbers verbatim. Caught late, the interview is already over and there
        is nothing left to fix; caught here, the publish request simply fails.

        Still a validator, unlike ``criterion_weights_total_100``, because reading a stored row
        cannot trip it. ``axis_weights`` arrived in ``m_013`` as NOT NULL with an empty-object
        default, so every version written before this rule carries ``{}`` and returns on the
        line below. ``weight`` has existed since ``a_001`` with no total enforced anywhere, so
        stored criteria genuinely do total something other than 100.
        """
        if not self.axis_weights:
            return self
        unknown = sorted(set(self.axis_weights) - ASSESSMENT_AXIS_KEY_SET)
        if unknown:
            raise ValueError(f"unknown assessment axis weights: {unknown}")
        missing = sorted(ASSESSMENT_AXIS_KEY_SET - set(self.axis_weights))
        if missing:
            raise ValueError(
                f"axis weights must name every scoring axis or be empty; missing {missing}"
            )
        negative = sorted(key for key, weight in self.axis_weights.items() if weight < 0)
        if negative:
            raise ValueError(f"axis weights cannot be negative: {negative}")
        # Percentages, on the same rule as the criterion weights above: the number a recruiter
        # sets on a slider is the share that axis carries. A single axis at 0 is fine and means
        # "do not look at this one here"; the other four then have to make up the 100.
        total = sum(self.axis_weights.values())
        if abs(total - 100) > _WEIGHT_SUM_EPSILON:
            raise ValueError(f"axis weights must total 100, got {total:g}")
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
        axis_weights: dict[str, float] | None = None,
        persona_definition: dict[str, object] | None = None,
    ) -> CompetencyModelVersion:
        # The one place a version is built from what a recruiter entered. Reading a stored row
        # goes through `cls(...)` directly, and must not be held to a rule that did not exist
        # when the row was written -- see `criterion_weights_total_100`.
        cls.criterion_weights_total_100(criteria)
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
            axis_weights=dict(axis_weights or {}),
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
