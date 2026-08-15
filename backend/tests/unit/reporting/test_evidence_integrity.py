from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.reporting.domain.report import (
    AssessmentState,
    Evidence,
    EvidenceRangeError,
    ReportItem,
    Sufficiency,
)

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
REPORT_ITEM_ID = UUID("00000000-0000-7000-8000-000000000002")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000003")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000004")
ANSWER_TURN_ID = UUID("00000000-0000-7000-8000-000000000005")
SEGMENT_ID = UUID("00000000-0000-7000-8000-000000000006")


def evidence(*, start_ms: int = 1000, end_ms: int = 3000) -> Evidence:
    return Evidence(
        evidence_id=UUID("00000000-0000-7000-8000-000000000007"),
        company_id=COMPANY_ID,
        report_item_id=REPORT_ITEM_ID,
        criterion_id=CRITERION_ID,
        competency_model_version_id=VERSION_ID,
        answer_turn_id=ANSWER_TURN_ID,
        transcript_segment_id=SEGMENT_ID,
        video_start_ms=start_ms,
        video_end_ms=end_ms,
        observation="지원자가 장애 원인과 대안을 비교했다.",
        rationale="최종 답변에 구체적인 트레이드오프가 있다.",
        sufficiency=Sufficiency.DIRECT,
        generation_version="report-v1",
        created_at=NOW,
    )


def test_confirmed_and_partial_items_require_valid_final_answer_evidence() -> None:
    with pytest.raises(ValueError, match="valid Evidence"):
        ReportItem(
            report_item_id=REPORT_ITEM_ID,
            company_id=COMPANY_ID,
            report_id=UUID("00000000-0000-7000-8000-000000000008"),
            criterion_id=CRITERION_ID,
            competency_model_version_id=VERSION_ID,
            assessment_state=AssessmentState.CONFIRMED,
            observation="관찰",
            rationale="판단",
            sufficiency="enough",
            uncertainty="낮음",
            evidence=(),
        )

    item = ReportItem(
        report_item_id=REPORT_ITEM_ID,
        company_id=COMPANY_ID,
        report_id=UUID("00000000-0000-7000-8000-000000000008"),
        criterion_id=CRITERION_ID,
        competency_model_version_id=VERSION_ID,
        assessment_state=AssessmentState.PARTIALLY_CONFIRMED,
        observation="관찰",
        rationale="판단",
        sufficiency="partial",
        uncertainty="중간",
        evidence=(evidence(),),
    )
    assert item.evidence[0].answer_turn_id == ANSWER_TURN_ID


def test_evidence_rejects_missing_or_technical_failure_ranges() -> None:
    candidate = evidence(start_ms=2000, end_ms=5000)
    with pytest.raises(EvidenceRangeError, match="missing recording range"):
        candidate.validate_timeline(
            answer_turn_id=ANSWER_TURN_ID,
            transcript_start_ms=1500,
            transcript_end_ms=5200,
            missing_ranges=((4000, 6000),),
            technical_failure_ranges=(),
        )
    with pytest.raises(EvidenceRangeError, match="technical failure"):
        candidate.validate_timeline(
            answer_turn_id=ANSWER_TURN_ID,
            transcript_start_ms=1500,
            transcript_end_ms=5200,
            missing_ranges=(),
            technical_failure_ranges=((0, 2500),),
        )
