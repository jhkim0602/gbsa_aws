from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

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
from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class CriterionInput:
    criterion_id: UUID
    observation: str
    answer_turn_id: UUID
    transcript: TranscriptSegment
    video_start_ms: int
    video_end_ms: int


class ReportGenerator:
    def __init__(
        self,
        repository: ReportingRepository,
        evidence_service: EvidenceService,
    ) -> None:
        self._repository = repository
        self._evidence_service = evidence_service

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
            items.append(
                ReportItem(
                    report_item_id=report_item_id,
                    company_id=context.company_id,
                    report_id=report_id,
                    criterion_id=criterion.criterion_id,
                    competency_model_version_id=competency_model_version_id,
                    assessment_state=state,
                    observation=criterion.observation,
                    rationale="실제 최종 답변만 평가 근거로 사용",
                    sufficiency="direct" if evidence else "insufficient",
                    uncertainty=uncertainty,
                    evidence=evidence,
                    follow_up_question=(
                        None if evidence else "사람 면접에서 구체적인 사례를 추가로 확인해 주세요."
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
