from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from interview_evidence.reporting.domain.scoring import (
    Aggregate,
    Entry,
    aggregate,
    weights_for,
)
from interview_evidence.shared.assessment_axes import AssessmentAxisKey

COMMUNICATION_SEPARATED_CONFIG_VERSION = "report-config-v2-communication-separated"


class AssessmentState(StrEnum):
    CONFIRMED = "confirmed"
    PARTIALLY_CONFIRMED = "partially_confirmed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NEEDS_FOLLOW_UP = "needs_follow_up"


class Sufficiency(StrEnum):
    DIRECT = "direct"
    SUPPORTING = "supporting"
    WEAK = "weak"


class ReportKind(StrEnum):
    AI_ORIGINAL = "ai_original"


class ReportStatus(StrEnum):
    GENERATING = "generating"
    READY = "ready"
    PARTIAL = "partial"
    FAILED = "failed"


class EvidenceRangeError(ValueError):
    """Raised when an Evidence interval is unavailable or assessment-ineligible."""


def _overlaps(start_ms: int, end_ms: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(start_ms < range_end and end_ms > range_start for range_start, range_end in ranges)


@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: UUID
    company_id: UUID
    report_item_id: UUID
    criterion_id: UUID
    competency_model_version_id: UUID
    answer_turn_id: UUID
    transcript_segment_id: UUID
    video_start_ms: int
    video_end_ms: int
    observation: str
    rationale: str
    sufficiency: Sufficiency
    generation_version: str
    created_at: datetime

    def __post_init__(self) -> None:
        if self.video_start_ms < 0 or self.video_end_ms <= self.video_start_ms:
            raise EvidenceRangeError("Evidence requires a valid ordered video range")
        if not self.observation.strip() or not self.rationale.strip():
            raise ValueError("Evidence observation and rationale are required")

    @classmethod
    def from_source_reference(cls, **_: object) -> Evidence:
        raise TypeError("Evidence must reference a final applicant answer, not a SourceReference")

    def validate_timeline(
        self,
        *,
        answer_turn_id: UUID,
        transcript_start_ms: int,
        transcript_end_ms: int,
        missing_ranges: tuple[tuple[int, int], ...],
        technical_failure_ranges: tuple[tuple[int, int], ...],
    ) -> None:
        if self.answer_turn_id != answer_turn_id:
            raise EvidenceRangeError("Evidence must reference the validated final answer Turn")
        if self.video_start_ms < transcript_start_ms or self.video_end_ms > transcript_end_ms:
            raise EvidenceRangeError("Evidence range must fall inside its transcript segment")
        if _overlaps(self.video_start_ms, self.video_end_ms, missing_ranges):
            raise EvidenceRangeError("Evidence overlaps a missing recording range")
        if _overlaps(self.video_start_ms, self.video_end_ms, technical_failure_ranges):
            raise EvidenceRangeError("Evidence overlaps a technical failure interval")


@dataclass(frozen=True, slots=True)
class AxisAssessment:
    """One evaluation axis as the model judged it, with what it cited.

    The score is the model's, not a formula's: what separates a 40 from an 80 on depth is
    a judgement about an answer, which is why ``rationale`` travels with it. A reviewer who
    disagrees reads the rationale, plays the cited Evidence and overrules -- which only
    works because ``quoted_evidence_ids`` was verified to resolve before this was stored.

    ``score`` is None when the answers gave no basis to judge this axis. It is never zero
    for that case: zero says the candidate was wrong, and treating "never asked" as wrong
    would reject people for gaps in our own interview.
    """

    axis: str
    label: str
    score: int | None
    rationale: str
    quoted_evidence_ids: tuple[UUID, ...] = ()

    def __post_init__(self) -> None:
        if self.score is not None and not 0 <= self.score <= 100:
            raise ValueError("axis score must fall between 0 and 100")
        if self.score is not None and not self.quoted_evidence_ids:
            raise ValueError("a scored axis must cite the Evidence it rests on")
        if not self.rationale.strip():
            raise ValueError("axis rationale is required")


@dataclass(frozen=True, slots=True)
class ReportItem:
    report_item_id: UUID
    company_id: UUID
    report_id: UUID
    criterion_id: UUID
    competency_model_version_id: UUID
    assessment_state: AssessmentState
    observation: str
    rationale: str
    sufficiency: str
    uncertainty: str
    evidence: tuple[Evidence, ...]
    #: Snapshot of the criterion name so a reviewer never reads a bare UUID, and so
    #: the report stays readable after the criterion version it came from is deleted.
    criterion_name: str = ""
    follow_up_question: str | None = None
    #: How the model scored each axis. Empty for reports generated before scoring
    #: existed, which the reviewer UI reads as "no scores on this report".
    axis_assessments: tuple[AxisAssessment, ...] = ()
    #: What this criterion counted for in the report score, snapshotted from the published
    #: version. Frozen here rather than read back from the version, so a company changing its
    #: weights cannot silently restate a report a reviewer has already acted on.
    criterion_weight: float = 1.0
    #: What each axis counted for within this criterion, keyed by ``shared.assessment_axes``.
    #: Empty means equal weight -- which is what reports generated before weights existed were
    #: actually scored with, so reading it that way reproduces their numbers rather than
    #: rewriting them.
    axis_weights: Mapping[str, float] = field(default_factory=dict)

    @property
    def axis_aggregate(self) -> Aggregate:
        """The criterion's score with its divisor and per-axis arithmetic.

        Callers that only want the number use :attr:`average_score`; the reviewer's calculator
        needs the rest, because "78" and "78 out of the 70% we could judge" are different
        claims and only one of them is honest.
        """
        keys = [axis.axis for axis in self.axis_assessments]
        weights = weights_for(keys, self.axis_weights)
        return aggregate(
            [
                Entry(key=axis.axis, score=axis.score, weight=weight)
                for axis, weight in zip(self.axis_assessments, weights, strict=True)
            ]
        )

    @property
    def competency_axis_assessments(self) -> tuple[AxisAssessment, ...]:
        return tuple(
            axis
            for axis in self.axis_assessments
            if axis.axis != AssessmentAxisKey.COMMUNICATION.value
        )

    @property
    def competency_axis_aggregate(self) -> Aggregate:
        keys = [axis.axis for axis in self.competency_axis_assessments]
        weights = weights_for(keys, self.axis_weights)
        return aggregate(
            [
                Entry(key=axis.axis, score=axis.score, weight=weight)
                for axis, weight in zip(
                    self.competency_axis_assessments,
                    weights,
                    strict=True,
                )
            ]
        )

    @property
    def competency_score(self) -> int | None:
        return self.competency_axis_aggregate.score

    @property
    def communication_assessment(self) -> AxisAssessment | None:
        return next(
            (
                axis
                for axis in self.axis_assessments
                if axis.axis == AssessmentAxisKey.COMMUNICATION.value
            ),
            None,
        )

    @property
    def average_score(self) -> int | None:
        """Weighted mean of the axes that could be judged, or None when none could.

        Kept under this name because it is published as ``score`` on the report item and read
        by the console; only the arithmetic changed. Unscored axes are left out of both the
        numerator and the divisor rather than counted as zero, so a criterion where only one
        axis was observable reports that axis honestly instead of being dragged toward a
        failure by the four the interview never reached.
        """
        return self.axis_aggregate.score

    def __post_init__(self) -> None:
        if (
            self.assessment_state
            in {
                AssessmentState.CONFIRMED,
                AssessmentState.PARTIALLY_CONFIRMED,
            }
            and not self.evidence
        ):
            raise ValueError("confirmed assessments require at least one valid Evidence")
        for item in self.evidence:
            if (
                item.company_id != self.company_id
                or item.report_item_id != self.report_item_id
                or item.criterion_id != self.criterion_id
                or item.competency_model_version_id != self.competency_model_version_id
            ):
                raise ValueError("Evidence scope must match its ReportItem")


@dataclass(frozen=True, slots=True)
class Report:
    report_id: UUID
    company_id: UUID
    interview_session_id: UUID
    invitation_id: UUID
    version: int
    kind: ReportKind
    model_version: str
    prompt_version: str
    config_version: str
    status: ReportStatus
    summary: str
    created_at: datetime
    items: tuple[ReportItem, ...] = ()

    @property
    def scored_items(self) -> tuple[ReportItem, ...]:
        return tuple(item for item in self.items if self.score_for(item) is not None)

    def axis_aggregate_for(self, item: ReportItem) -> Aggregate:
        if self.config_version == COMMUNICATION_SEPARATED_CONFIG_VERSION:
            return item.competency_axis_aggregate
        return item.axis_aggregate

    def score_for(self, item: ReportItem) -> int | None:
        return self.axis_aggregate_for(item).score

    @property
    def criterion_aggregate(self) -> Aggregate:
        """The report's score with its divisor and per-criterion arithmetic.

        Keyed by criterion id rather than name: two criteria may share a name, and the
        calculator resolves the id back to the item a reviewer clicks through to.
        """
        return aggregate(
            [
                Entry(
                    key=str(item.criterion_id),
                    score=self.score_for(item),
                    weight=item.criterion_weight,
                )
                for item in self.items
            ]
        )

    @property
    def communication_aggregate(self) -> Aggregate:
        return aggregate(
            [
                Entry(
                    key=str(item.criterion_id),
                    score=(
                        item.communication_assessment.score
                        if item.communication_assessment is not None
                        else None
                    ),
                    weight=item.criterion_weight,
                )
                for item in self.items
            ]
        )

    @property
    def communication_score(self) -> int | None:
        return self.communication_aggregate.score

    @property
    def overall_score(self) -> int | None:
        """Weighted mean across the criteria that could be scored, or None when none could.

        Weighted by ``ReportItem.criterion_weight``, the share the company assigned each
        criterion when the version was published. That is the whole point of the field: before
        this, ``weight`` was stored, edited in the wizard, and read by nothing.

        This is still explicitly not a hiring score. It says nothing about the criteria the
        interview never reached -- which is why the reviewer UI shows it beside the unscored
        count and the divisor -- and the constitution reserves the decision for a person.
        """
        return self.criterion_aggregate.score

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("report version must be positive")
        if self.kind is not ReportKind.AI_ORIGINAL:
            raise ValueError("only immutable AI original reports are supported")
        if any(item.company_id != self.company_id for item in self.items):
            raise ValueError("ReportItem tenant must match Report")
