from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


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
    follow_up_question: str | None = None

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

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("report version must be positive")
        if self.kind is not ReportKind.AI_ORIGINAL:
            raise ValueError("only immutable AI original reports are supported")
        if any(item.company_id != self.company_id for item in self.items):
            raise ValueError("ReportItem tenant must match Report")
