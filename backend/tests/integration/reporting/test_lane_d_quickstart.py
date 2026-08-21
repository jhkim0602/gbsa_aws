from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.reporting.application.deletion_service import DeletionService
from interview_evidence.reporting.application.evidence_service import EvidenceService
from interview_evidence.reporting.application.review_service import ReviewService
from interview_evidence.reporting.application.transcript_service import TranscriptService
from interview_evidence.reporting.domain.deletion import DeletionTarget
from interview_evidence.reporting.domain.report import AssessmentState
from interview_evidence.reporting.domain.review import Decision
from interview_evidence.reporting.repositories.postgres import (
    InMemoryReportingRepository,
)
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.workers.reporting.media import MediaPostProcessor
from interview_evidence.workers.reporting.report import (
    CriterionAnswerInput,
    CriterionInput,
    ReportGenerator,
)

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000003")
TURN_ID = UUID("00000000-0000-7000-8000-000000000004")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000005")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000006")


@dataclass(frozen=True)
class FinalTurn:
    turn_id: UUID = TURN_ID
    company_id: UUID = COMPANY_ID
    interview_session_id: UUID = SESSION_ID
    speaker: str = "applicant"
    status: str = "final"
    text: str = "장애 상황에서 캐시와 큐를 비교하고 큐를 선택했습니다."


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.COMPANY_USER,
        actor_id=UUID("00000000-0000-7000-8000-000000000007"),
        request_id=UUID("00000000-0000-7000-8000-000000000008"),
        trace_id="trace-lane-d-quickstart",
    )


def test_completed_session_to_human_decision_and_verified_deletion() -> None:
    repository = InMemoryReportingRepository()
    transcript = TranscriptService(repository).ingest_final_turn(
        context(),
        turn=FinalTurn(),
        session_start_ms=1000,
        session_end_ms=5000,
        source_audio_key="opaque/audio/1",
        confidence=0.95,
        occurred_at=NOW,
    )
    recording = MediaPostProcessor(repository).build_manifest(
        context(),
        session_id=SESSION_ID,
        chunks=((0, 3000, "a" * 64), (3500, 8000, "b" * 64)),
        output_object_key="opaque/video/final-1",
        occurred_at=NOW,
    )
    assert recording.status.value == "partial"
    assert recording.missing_ranges == ((3000, 3500),)

    generated = ReportGenerator(repository, EvidenceService(repository)).generate(
        context(),
        session_id=SESSION_ID,
        invitation_id=INVITATION_ID,
        competency_model_version_id=VERSION_ID,
        criteria=(
            CriterionInput(
                criterion_id=CRITERION_ID,
                observation="대안 비교",
                answers=(
                    CriterionAnswerInput(
                        question="대안을 어떻게 비교했나요?",
                        answer_turn_id=TURN_ID,
                        transcript=transcript,
                        video_start_ms=1000,
                        video_end_ms=2800,
                        interview_stage="technical",
                    ),
                ),
            ),
        ),
        recording=recording,
        events=(),
        occurred_at=NOW,
    )
    assert generated.items[0].assessment_state is AssessmentState.CONFIRMED
    assert generated.items[0].evidence

    review = ReviewService(repository)
    override = review.override_assessment(
        context(),
        report_id=generated.report_id,
        report_item_id=generated.items[0].report_item_id,
        assessment_state="needs_follow_up",
        reason="운영 규모에 대한 추가 확인이 필요하다.",
        occurred_at=NOW,
    )
    decision = review.record_final_decision(
        context(),
        report_id=generated.report_id,
        invitation_id=INVITATION_ID,
        decision=Decision.HOLD,
        reason="사람 면접에서 추가 확인한다.",
        occurred_at=NOW,
    )
    assert override.created_at == decision.created_at
    assert generated.summary == "최종 답변 Evidence에 기반한 AI 원본 리포트"

    target = DeletionTarget.pending(
        target_id=UUID("00000000-0000-7000-8000-000000000009"),
        owner_lane="D",
        store="aurora",
        target_type="report",
        resource_id=str(generated.report_id),
    )
    deletion = DeletionService(
        repository,
        enumerators=(lambda _context, _scope, _id: (target,),),
        executors={"D": lambda _context, _target: True},
    )
    request, _ = deletion.request(
        context(),
        scope_type="invitation",
        scope_id=INVITATION_ID,
        reason="지원자 삭제 요청",
        policy_snapshot={"retention_days": 180},
        occurred_at=NOW,
    )
    completed = deletion.execute(
        context(),
        request_id=request.deletion_request_id,
        occurred_at=NOW,
    )
    assert completed.status.value == "completed"
