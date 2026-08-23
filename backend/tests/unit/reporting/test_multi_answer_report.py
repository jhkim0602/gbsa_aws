from collections.abc import Sequence
from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import UUID

from interview_evidence.reporting.application.assessment_prompt import AnswerForAssessment
from interview_evidence.reporting.application.assessment_service import CriterionAssessment
from interview_evidence.reporting.domain.report import AssessmentState, AxisAssessment
from interview_evidence.reporting.domain.timeline import TranscriptSegment
from interview_evidence.shared.interview_level import InterviewLevel
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.workers.reporting.report import (
    CriterionAnswerInput,
    CriterionInput,
    ReportGenerator,
)

NOW = datetime(2026, 8, 21, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000003")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000004")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000005")


class CapturingAssessor:
    def __init__(self) -> None:
        self.answers: tuple[AnswerForAssessment, ...] = ()

    def assess(
        self,
        _context: TenantContext,
        *,
        answers: Sequence[AnswerForAssessment],
        **_kwargs: object,
    ) -> CriterionAssessment:
        self.answers = tuple(answers)
        return CriterionAssessment(
            axis_assessments=(
                AxisAssessment(
                    axis="correctness",
                    label="정확성",
                    score=72,
                    rationale="첫 답변의 문제 진단 절차를 근거로 평가함",
                    quoted_evidence_ids=(self.answers[0].evidence_id,),
                ),
                AxisAssessment(
                    axis="ownership",
                    label="본인 기여",
                    score=78,
                    rationale="두 번째 답변의 직접 수행 내용을 근거로 평가함",
                    quoted_evidence_ids=(self.answers[1].evidence_id,),
                ),
            ),
            assessment_state=AssessmentState.CONFIRMED,
            summary="서로 다른 질문의 답변을 종합해 평가함",
            follow_up_question=None,
        )


def test_report_scores_all_unique_answers_for_a_criterion() -> None:
    context = TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=UUID("00000000-0000-7000-8000-000000000006"),
        request_id=UUID("00000000-0000-7000-8000-000000000007"),
        trace_id="trace-multi-answer-report",
    )
    transcripts = (
        _transcript(
            turn_id=UUID("00000000-0000-7000-8000-000000000010"),
            segment_id=UUID("00000000-0000-7000-8000-000000000011"),
            text="로그와 사용자 흐름을 비교해 원인을 좁혔습니다.",
            start_ms=1_000,
            end_ms=3_000,
        ),
        _transcript(
            turn_id=UUID("00000000-0000-7000-8000-000000000012"),
            segment_id=UUID("00000000-0000-7000-8000-000000000013"),
            text="복구 후 오류율을 측정하고 재발 방지 알림을 추가했습니다.",
            start_ms=3_000,
            end_ms=5_000,
        ),
    )
    repository = Mock()
    repository.save_report.side_effect = lambda _context, report: report
    evidence_service = Mock()
    evidence_service.validate.side_effect = lambda _context, *, evidence, **_kwargs: evidence
    assessor = CapturingAssessor()

    report = ReportGenerator(repository, evidence_service, assessor).generate(
        context,
        session_id=SESSION_ID,
        invitation_id=INVITATION_ID,
        competency_model_version_id=VERSION_ID,
        criteria=(
            CriterionInput(
                criterion_id=CRITERION_ID,
                criterion_name="운영 문제 해결",
                criterion_text="서비스 운영 문제를 분석하고 복구하는 역량",
                observation="두 답변을 종합함",
                answers=(
                    CriterionAnswerInput(
                        question="어떻게 원인을 분석했나요?",
                        answer_turn_id=transcripts[0].turn_id,
                        transcript=transcripts[0],
                        video_start_ms=transcripts[0].session_start_ms,
                        video_end_ms=transcripts[0].session_end_ms,
                        interview_stage="technical",
                    ),
                    CriterionAnswerInput(
                        question="복구 후 무엇을 확인했나요?",
                        answer_turn_id=transcripts[1].turn_id,
                        transcript=transcripts[1],
                        video_start_ms=transcripts[1].session_start_ms,
                        video_end_ms=transcripts[1].session_end_ms,
                        interview_stage="project_deep_dive",
                    ),
                ),
            ),
        ),
        recording=Mock(),
        events=(),
        occurred_at=NOW,
        interview_level=InterviewLevel.ENTRY,
    )

    assert len(report.items[0].evidence) == 2
    assert [answer.interview_stage for answer in assessor.answers] == [
        "technical",
        "project_deep_dive",
    ]
    assert report.items[0].axis_assessments[0].quoted_evidence_ids != (
        report.items[0].axis_assessments[1].quoted_evidence_ids
    )


def _transcript(
    *,
    turn_id: UUID,
    segment_id: UUID,
    text: str,
    start_ms: int,
    end_ms: int,
) -> TranscriptSegment:
    return TranscriptSegment(
        transcript_segment_id=segment_id,
        company_id=COMPANY_ID,
        interview_session_id=SESSION_ID,
        turn_id=turn_id,
        speaker="applicant",
        text=text,
        confidence=0.95,
        session_start_ms=start_ms,
        session_end_ms=end_ms,
        source_audio_key=f"recordings/{turn_id}.webm",
        version=1,
        corrected_by=None,
        created_at=NOW,
    )
