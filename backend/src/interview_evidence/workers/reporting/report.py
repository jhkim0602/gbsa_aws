from __future__ import annotations

from collections.abc import Mapping
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
    COMMUNICATION_SEPARATED_CONFIG_VERSION,
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
    """One criterion to report on, with the answer that addressed it -- if there was one.

    ``answer_turn_id`` and ``transcript`` are ``None`` when the interview never produced an
    answer for this criterion. That is not an error and must not be dropped: the criterion still
    carries ``weight``, so leaving it out of the report would shrink the divisor the score is
    read against without saying so. It becomes an ``insufficient_evidence`` item instead, which
    the report aggregate excludes with its weight visible.
    """

    criterion_id: UUID
    observation: str
    answer_turn_id: UUID | None
    transcript: TranscriptSegment | None
    video_start_ms: int = 0
    video_end_ms: int = 0
    criterion_name: str = ""
    #: What the criterion asks for, so the scorer judges the answer against the company's
    #: own wording rather than against a generic idea of a good answer.
    criterion_text: str = ""
    #: The question the applicant was actually answering. Without it a terse answer reads
    #: as evasive when it may have been exactly what was asked for.
    question: str = ""
    #: What this criterion counts for in the report score, from the published version. Defaults
    #: to 1.0 so a caller that does not pass weights produces the plain mean this used to be.
    weight: float = 1.0


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
        axis_weights: Mapping[str, float] | None = None,
    ) -> Report:
        report_id = new_uuid7(occurred_at)
        items: list[ReportItem] = []
        for criterion in criteria:
            report_item_id = new_uuid7(occurred_at)
            state = AssessmentState.INSUFFICIENT_EVIDENCE
            evidence: tuple[Evidence, ...] = ()
            uncertainty = "유효한 영상·자막 Evidence가 부족함"
            if criterion.answer_turn_id is None or criterion.transcript is None:
                # The interview never reached this criterion. Reported rather than omitted:
                # it carries weight, and a criterion missing from the report would shrink the
                # divisor without appearing anywhere a reviewer could see it.
                uncertainty = "이 기준을 확인할 답변이 면접에서 나오지 않았음"
                items.append(
                    self._unscored_item(
                        criterion,
                        report_id=report_id,
                        report_item_id=report_item_id,
                        company_id=context.company_id,
                        competency_model_version_id=competency_model_version_id,
                        uncertainty=uncertainty,
                        axis_weights=axis_weights,
                    )
                )
                continue
            try:
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
                valid = self._evidence_service.validate(
                    context,
                    evidence=candidate,
                    final_answer_turn_id=criterion.answer_turn_id,
                    transcript=criterion.transcript,
                    recording=recording,
                    events=events,
                )
            except (EvidenceRangeError, ValueError):
                pass
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
                    # Snapshotted onto the item, not looked up when the score is read. The
                    # version these came from can be superseded or deleted, and a reviewer must
                    # still be able to see why the number is what it is.
                    criterion_weight=criterion.weight,
                    axis_weights=dict(axis_weights or {}),
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
            prompt_version="assessment-prompt-v2",
            config_version=COMMUNICATION_SEPARATED_CONFIG_VERSION,
            status=(
                ReportStatus.READY if all(item.evidence for item in items) else ReportStatus.PARTIAL
            ),
            summary="최종 답변 Evidence에 기반한 AI 원본 리포트",
            created_at=occurred_at,
            items=tuple(items),
        )
        return self._repository.save_report(context, report)

    @staticmethod
    def _unscored_item(
        criterion: CriterionInput,
        *,
        report_id: UUID,
        report_item_id: UUID,
        company_id: UUID,
        competency_model_version_id: UUID,
        uncertainty: str,
        axis_weights: Mapping[str, float] | None,
    ) -> ReportItem:
        """A criterion the interview never reached, reported with its weight intact.

        No Evidence, so no axis scores and nothing for the model to read -- offering it an empty
        payload would invite it to invent a judgement. What matters is that the item exists:
        ``Report.criterion_aggregate`` then excludes it *and reports its weight*, so the divisor
        the reviewer sees accounts for the part of the interview that did not happen.
        """
        return ReportItem(
            report_item_id=report_item_id,
            company_id=company_id,
            report_id=report_id,
            criterion_id=criterion.criterion_id,
            criterion_name=criterion.criterion_name,
            competency_model_version_id=competency_model_version_id,
            assessment_state=AssessmentState.INSUFFICIENT_EVIDENCE,
            observation=criterion.observation,
            rationale="면접에서 이 기준을 확인할 답변이 나오지 않아 채점하지 않음",
            sufficiency="insufficient",
            uncertainty=uncertainty,
            evidence=(),
            follow_up_question=None,
            axis_assessments=(),
            criterion_weight=criterion.weight,
            axis_weights=dict(axis_weights or {}),
        )

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
        # No transcript means no answer, and Evidence cannot exist without one -- but the type
        # allows the combination, so it is refused here rather than dereferenced. A scorer given
        # an empty answer would be invited to invent a judgement.
        if self._assessor is None or not evidence or criterion.transcript is None:
            return None
        transcript = criterion.transcript
        return self._assessor.assess(
            context,
            criterion_id=criterion.criterion_id,
            criterion_name=criterion.criterion_name or "평가 기준",
            criterion_text=criterion.criterion_text or criterion.observation,
            answers=tuple(
                AnswerForAssessment(
                    evidence_id=item.evidence_id,
                    question=criterion.question,
                    answer_text=transcript.text,
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
