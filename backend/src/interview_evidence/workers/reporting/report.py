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
from interview_evidence.reporting.application.requirement_assessment import (
    RequirementAssessor,
    RequirementDefinition,
    RequirementEvidenceCandidate,
)
from interview_evidence.reporting.domain.report import (
    COMMUNICATION_SEPARATED_CONFIG_VERSION,
    AssessmentState,
    Evidence,
    EvidenceRangeError,
    Report,
    ReportItem,
    ReportKind,
    ReportStatus,
    RequirementAssessment,
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
class CriterionAnswerInput:
    """One scored applicant answer and the question it followed."""

    question: str
    answer_turn_id: UUID
    transcript: TranscriptSegment
    video_start_ms: int
    video_end_ms: int
    interview_stage: str


@dataclass(frozen=True, slots=True)
class CriterionInput:
    """One criterion and every non-duplicate answer that addressed it."""

    criterion_id: UUID
    observation: str
    answers: tuple[CriterionAnswerInput, ...] = ()
    criterion_name: str = ""
    #: What the criterion asks for, so the scorer judges the answer against the company's
    #: own wording rather than against a generic idea of a good answer.
    criterion_text: str = ""
    #: What this criterion counts for in the report score, from the published version. Defaults
    #: to 1.0 so a caller that does not pass weights produces the plain mean this used to be.
    weight: float = 1.0


@dataclass(frozen=True, slots=True)
class RequirementInput:
    job_requirement_id: UUID
    requirement_type: str
    statement: str
    material_evidence: tuple[RequirementEvidenceCandidate, ...] = ()


class ReportGenerator:
    def __init__(
        self,
        repository: ReportingRepository,
        evidence_service: EvidenceService,
        assessor: CriterionAssessor | None = None,
        requirement_assessor: RequirementAssessor | None = None,
    ) -> None:
        self._repository = repository
        self._evidence_service = evidence_service
        # Left unset the report still generates, just without axis scores. Reports made
        # before scoring existed look the same way, and the console reads both as
        # "no scores on this report".
        self._assessor = assessor
        self._requirement_assessor = requirement_assessor

    def generate(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        invitation_id: UUID,
        competency_model_version_id: UUID,
        criteria: tuple[CriterionInput, ...],
        requirements: tuple[RequirementInput, ...] = (),
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
            if not criterion.answers:
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
            validated: list[Evidence] = []
            for answer in criterion.answers:
                try:
                    candidate = Evidence(
                        evidence_id=new_uuid7(occurred_at),
                        company_id=context.company_id,
                        report_item_id=report_item_id,
                        criterion_id=criterion.criterion_id,
                        competency_model_version_id=competency_model_version_id,
                        answer_turn_id=answer.answer_turn_id,
                        transcript_segment_id=answer.transcript.transcript_segment_id,
                        video_start_ms=answer.video_start_ms,
                        video_end_ms=answer.video_end_ms,
                        observation=f"{_stage_label(answer.interview_stage)}에서 확인한 답변",
                        rationale="질문에 이어진 최종 답변의 자막과 영상 구간에 직접 연결됨",
                        sufficiency=Sufficiency.DIRECT,
                        generation_version="report-v1",
                        created_at=occurred_at,
                    )
                    valid = self._evidence_service.validate(
                        context,
                        evidence=candidate,
                        final_answer_turn_id=answer.answer_turn_id,
                        transcript=answer.transcript,
                        recording=recording,
                        events=events,
                    )
                except (EvidenceRangeError, ValueError):
                    continue
                validated.append(valid)
            evidence = tuple(validated)
            if evidence:
                state = AssessmentState.CONFIRMED
                uncertainty = (
                    f"답변 {len(criterion.answers)}개 중 검증 가능한 Evidence "
                    f"{len(evidence)}개를 평가함"
                )
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
        requirement_assessments = self._assess_requirements(
            context,
            requirements=requirements,
            criteria=criteria,
            report_items=tuple(items),
            model_config_version=model_config_version,
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
            summary="평가 질문별 최종 답변 Evidence에 기반한 AI 원본 리포트",
            created_at=occurred_at,
            items=tuple(items),
            requirement_assessments=requirement_assessments,
        )
        return self._repository.save_report(context, report)

    def _assess_requirements(
        self,
        context: TenantContext,
        *,
        requirements: tuple[RequirementInput, ...],
        criteria: tuple[CriterionInput, ...],
        report_items: tuple[ReportItem, ...],
        model_config_version: str,
    ) -> tuple[RequirementAssessment, ...]:
        if self._requirement_assessor is None or not requirements:
            return ()
        answers_by_turn = {
            answer.answer_turn_id: answer for criterion in criteria for answer in criterion.answers
        }
        interview_evidence = tuple(
            RequirementEvidenceCandidate(
                evidence_id=evidence.evidence_id,
                source_kind="interview",
                source_type="interview_answer",
                excerpt=answers_by_turn[evidence.answer_turn_id].transcript.text,
                locator={
                    "answer_turn_id": str(evidence.answer_turn_id),
                    "transcript_segment_id": str(evidence.transcript_segment_id),
                    "video_start_ms": evidence.video_start_ms,
                    "video_end_ms": evidence.video_end_ms,
                },
            )
            for item in report_items
            for evidence in item.evidence
            if evidence.answer_turn_id in answers_by_turn
        )
        return tuple(
            self._requirement_assessor.assess(
                context,
                requirement=RequirementDefinition(
                    job_requirement_id=requirement.job_requirement_id,
                    requirement_type=requirement.requirement_type,
                    statement=requirement.statement,
                ),
                candidates=(*requirement.material_evidence, *interview_evidence),
                model_config_version=model_config_version,
            )
            for requirement in requirements
        )

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
        if self._assessor is None or not evidence:
            return None
        answers_by_turn = {answer.answer_turn_id: answer for answer in criterion.answers}
        return self._assessor.assess(
            context,
            criterion_id=criterion.criterion_id,
            criterion_name=criterion.criterion_name or "평가 기준",
            criterion_text=criterion.criterion_text or criterion.observation,
            answers=tuple(
                AnswerForAssessment(
                    evidence_id=item.evidence_id,
                    question=answers_by_turn[item.answer_turn_id].question,
                    answer_text=answers_by_turn[item.answer_turn_id].transcript.text,
                    video_start_ms=item.video_start_ms,
                    video_end_ms=item.video_end_ms,
                    interview_stage=answers_by_turn[item.answer_turn_id].interview_stage,
                )
                for item in evidence
                if item.answer_turn_id in answers_by_turn
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


def _stage_label(stage: str) -> str:
    return {
        "technical": "기술 면접",
        "project_deep_dive": "프로젝트 심층",
        "behavioral": "협업·인성 면접",
    }.get(stage, "면접")
