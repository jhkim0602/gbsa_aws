from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from interview_evidence.reporting.application.assessment_prompt import AnswerForAssessment
from interview_evidence.reporting.application.assessment_service import (
    CriterionAssessment,
    CriterionAssessor,
)
from interview_evidence.reporting.application.evidence_service import EvidenceService
from interview_evidence.reporting.domain.report import (
    AssessmentState,
    Evidence,
    EvidenceRangeError,
    Report,
    ReportItem,
    ReportKind,
    ReportStatus,
    Sufficiency,
)
from interview_evidence.reporting.domain.timeline import (
    RecordingAsset,
    SessionEvent,
    TranscriptSegment,
)
from interview_evidence.reporting.repositories.postgres import ReportingRepository
from interview_evidence.shared.ids import new_uuid7
from interview_evidence.shared.interview_level import (
    DEFAULT_INTERVIEW_LEVEL,
    InterviewLevel,
)
from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class CriterionInput:
    criterion_id: UUID
    observation: str
    answer_turn_id: UUID
    transcript: TranscriptSegment
    video_start_ms: int
    video_end_ms: int
    criterion_name: str = ""
    #: What the criterion asks for, so the scorer judges the answer against the company's
    #: own wording rather than against a generic idea of a good answer.
    criterion_text: str = ""
    #: The question the applicant was actually answering. Without it a terse answer reads
    #: as evasive when it may have been exactly what was asked for.
    question: str = ""


class ReportGenerator:
    def __init__(
        self,
        repository: ReportingRepository,
        evidence_service: EvidenceService,
        assessor: CriterionAssessor | None = None,
    ) -> None:
        self._repository = repository
        self._evidence_service = evidence_service
        # Left unset the report still generates, just without axis scores. Reports made
        # before scoring existed look the same way, and the console reads both as
        # "no scores on this report".
        self._assessor = assessor

    def generate(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        invitation_id: UUID,
        competency_model_version_id: UUID,
        criteria: tuple[CriterionInput, ...],
        recording: RecordingAsset,
        events: tuple[SessionEvent, ...],
        occurred_at: datetime,
        interview_level: InterviewLevel = DEFAULT_INTERVIEW_LEVEL,
        model_config_version: str = "report-config-v1",
    ) -> Report:
        report_id = new_uuid7(occurred_at)
        items: list[ReportItem] = []
        for criterion in criteria:
            report_item_id = new_uuid7(occurred_at)
            candidate = Evidence(
                evidence_id=new_uuid7(occurred_at),
                company_id=context.company_id,
                report_item_id=report_item_id,
                criterion_id=criterion.criterion_id,
                competency_model_version_id=competency_model_version_id,
                answer_turn_id=criterion.answer_turn_id,
                transcript_segment_id=criterion.transcript.transcript_segment_id,
                video_start_ms=criterion.video_start_ms,
                video_end_ms=criterion.video_end_ms,
                observation=criterion.observation,
                rationale="최종 답변의 자막과 유효 영상 구간에 직접 연결됨",
                sufficiency=Sufficiency.DIRECT,
                generation_version="report-v1",
                created_at=occurred_at,
            )
            try:
                valid = self._evidence_service.validate(
                    context,
                    evidence=candidate,
                    final_answer_turn_id=criterion.answer_turn_id,
                    transcript=criterion.transcript,
                    recording=recording,
                    events=events,
                )
            except (EvidenceRangeError, ValueError):
                state = AssessmentState.INSUFFICIENT_EVIDENCE
                evidence: tuple[Evidence, ...] = ()
                uncertainty = "유효한 영상·자막 Evidence가 부족함"
            else:
                state = AssessmentState.CONFIRMED
                evidence = (valid,)
                uncertainty = "AI 원본이며 사람 검토 필요"
            assessment = self._assess(
                context,
                criterion=criterion,
                evidence=evidence,
                interview_level=interview_level,
                model_config_version=model_config_version,
            )
            if assessment is not None:
                # The model read the answer; its state supersedes the recording check that
                # produced ``state`` above. Confirmed is only allowed to survive while
                # Evidence exists, which ReportItem enforces anyway.
                state = (
                    assessment.assessment_state
                    if evidence
                    else AssessmentState.INSUFFICIENT_EVIDENCE
                )
            items.append(
                ReportItem(
                    report_item_id=report_item_id,
                    company_id=context.company_id,
                    report_id=report_id,
                    criterion_id=criterion.criterion_id,
                    criterion_name=criterion.criterion_name,
                    competency_model_version_id=competency_model_version_id,
                    assessment_state=state,
                    observation=(
                        assessment.summary if assessment is not None else criterion.observation
                    ),
                    rationale="실제 최종 답변만 평가 근거로 사용",
                    sufficiency="direct" if evidence else "insufficient",
                    uncertainty=uncertainty,
                    evidence=evidence,
                    follow_up_question=_follow_up_for(assessment, evidence=evidence),
                    axis_assessments=(
                        assessment.axis_assessments if assessment is not None else ()
                    ),
                )
            )
        report = Report(
            report_id=report_id,
            company_id=context.company_id,
            interview_session_id=session_id,
            invitation_id=invitation_id,
            version=1,
            kind=ReportKind.AI_ORIGINAL,
            model_version="bedrock-model-v1",
            prompt_version="report-prompt-v1",
            config_version="report-config-v1",
            status=(
                ReportStatus.READY if all(item.evidence for item in items) else ReportStatus.PARTIAL
            ),
            summary="최종 답변 Evidence에 기반한 AI 원본 리포트",
            created_at=occurred_at,
            items=tuple(items),
        )
        return self._repository.save_report(context, report)

    def _assess(
        self,
        context: TenantContext,
        *,
        criterion: CriterionInput,
        evidence: tuple[Evidence, ...],
        interview_level: InterviewLevel,
        model_config_version: str,
    ) -> CriterionAssessment | None:
        """Score the criterion against the Evidence that survived validation.

        Only validated Evidence is offered to the scorer. An answer whose video range was
        missing or overlapped a technical failure cannot be played back, so a score citing
        it would be one the reviewer has no way to check.
        """
        if self._assessor is None or not evidence:
            return None
        return self._assessor.assess(
            context,
            criterion_id=criterion.criterion_id,
            criterion_name=criterion.criterion_name or "평가 기준",
            criterion_text=criterion.criterion_text or criterion.observation,
            answers=tuple(
                AnswerForAssessment(
                    evidence_id=item.evidence_id,
                    question=criterion.question,
                    answer_text=criterion.transcript.text,
                    video_start_ms=item.video_start_ms,
                    video_end_ms=item.video_end_ms,
                )
                for item in evidence
            ),
            model_config_version=model_config_version,
            interview_level=interview_level,
        )


def _follow_up_for(
    assessment: CriterionAssessment | None,
    *,
    evidence: tuple[Evidence, ...],
) -> str | None:
    if not evidence:
        return "사람 면접에서 구체적인 사례를 추가로 확인해 주세요."
    return assessment.follow_up_question if assessment is not None else None
