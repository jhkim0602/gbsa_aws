from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.integration.interview_reporting import (
    FinalTurnRange,
    InterviewReportingBoundary,
)
from interview_evidence.interview_engine.application.deletion_targets import (
    InMemoryInterviewTargetDeleter,
    InterviewDeletionTargets,
)
from interview_evidence.interview_engine.application.public import InterviewEnginePublic
from interview_evidence.interview_engine.domain.session import (
    InterviewSession,
    InterviewSessionState,
)
from interview_evidence.interview_engine.domain.turn import (
    InterviewTurn,
    RecordingChunk,
    RecordingUploadStatus,
    TurnSpeaker,
    TurnStatus,
)
from interview_evidence.interview_engine.repositories.postgres import (
    InMemoryInterviewRepository,
)
from interview_evidence.reporting.application.transcript_service import TranscriptService
from interview_evidence.reporting.repositories.postgres import InMemoryReportingRepository
from interview_evidence.shared.tenant import ActorType, TenantContext, TenantScopeError
from interview_evidence.workers.reporting.media import MediaPostProcessor

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
OTHER_COMPANY_ID = UUID("00000000-0000-7000-8000-000000000002")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000003")
QUESTION_TURN_ID = UUID("00000000-0000-7000-8000-000000000004")
ANSWER_TURN_ID = UUID("00000000-0000-7000-8000-000000000005")


def context(company_id: UUID = COMPANY_ID) -> TenantContext:
    return TenantContext(
        company_id=company_id,
        actor_type=ActorType.SYSTEM,
        actor_id=UUID("00000000-0000-7000-8000-000000000006"),
        request_id=UUID("00000000-0000-7000-8000-000000000007"),
        trace_id="cross-c-to-d",
    )


def build_boundary(
    *,
    state: InterviewSessionState = InterviewSessionState.COMPLETED,
) -> tuple[InterviewReportingBoundary, InMemoryReportingRepository]:
    interview_repository = InMemoryInterviewRepository()
    interview_repository.save_session(
        context(),
        InterviewSession(
            interview_session_id=SESSION_ID,
            company_id=COMPANY_ID,
            invitation_id=UUID("00000000-0000-7000-8000-000000000008"),
            applicant_id=UUID("00000000-0000-7000-8000-000000000009"),
            interview_strategy_id=UUID("00000000-0000-7000-8000-000000000010"),
            competency_model_version_id=UUID("00000000-0000-7000-8000-000000000011"),
            state=state,
            session_sequence=8,
            row_version=9,
            created_at=NOW,
            started_at=NOW,
            completed_at=NOW if state is InterviewSessionState.COMPLETED else None,
        ),
    )
    for turn in (
        InterviewTurn(
            turn_id=QUESTION_TURN_ID,
            company_id=COMPANY_ID,
            interview_session_id=SESSION_ID,
            sequence=1,
            speaker=TurnSpeaker.INTERVIEWER,
            status=TurnStatus.FINAL,
            text="장애 상황에서 어떤 대안을 비교했습니까?",
            target_criterion_id=UUID("00000000-0000-7000-8000-000000000012"),
            idempotency_key="cross-question-final",
            model_config_version="question-v1",
            finalized_at=NOW,
        ),
        InterviewTurn(
            turn_id=ANSWER_TURN_ID,
            company_id=COMPANY_ID,
            interview_session_id=SESSION_ID,
            sequence=2,
            speaker=TurnSpeaker.APPLICANT,
            status=TurnStatus.FINAL,
            text="캐시와 큐를 비교하고 복구 가능성 때문에 큐를 선택했습니다.",
            idempotency_key="cross-answer-final",
            finalized_at=NOW,
        ),
        InterviewTurn(
            turn_id=UUID("00000000-0000-7000-8000-000000000013"),
            company_id=COMPANY_ID,
            interview_session_id=SESSION_ID,
            sequence=3,
            speaker=TurnSpeaker.APPLICANT,
            status=TurnStatus.RECORDING,
            idempotency_key="cross-answer-partial",
        ),
    ):
        interview_repository.save_turn(context(), turn)

    for sequence, status, start_ms, end_ms, digest in (
        (1, RecordingUploadStatus.VERIFIED, 0, 2000, "a" * 64),
        (2, RecordingUploadStatus.FAILED, 2000, 2500, "b" * 64),
        (3, RecordingUploadStatus.VERIFIED, 2500, 5000, "c" * 64),
    ):
        interview_repository.save_recording_chunk(
            context(),
            RecordingChunk(
                recording_chunk_id=UUID(f"00000000-0000-7000-8000-{sequence:012d}"),
                company_id=COMPANY_ID,
                interview_session_id=SESSION_ID,
                sequence=sequence,
                object_key=(
                    f"companies/{COMPANY_ID}/sessions/{SESSION_ID}/recording/chunks/{sequence:06d}"
                ),
                content_hash=digest,
                byte_size=1024,
                session_start_ms=start_ms,
                session_end_ms=end_ms,
                upload_status=status,
                idempotency_key=f"cross-recording-{sequence:04d}",
                created_at=NOW,
            ),
        )

    interview_public = InterviewEnginePublic(
        repository=interview_repository,
        deletion_targets=InterviewDeletionTargets(interview_repository),
        target_deleter=InMemoryInterviewTargetDeleter(),
    )
    reporting_repository = InMemoryReportingRepository()
    return (
        InterviewReportingBoundary(
            interview=interview_public,
            transcript_service=TranscriptService(reporting_repository),
            media_processor=MediaPostProcessor(reporting_repository),
        ),
        reporting_repository,
    )


def test_lane_d_uses_real_final_turns_and_verified_media_boundary() -> None:
    boundary, reporting_repository = build_boundary()

    projected = boundary.project_completed_session(
        context(),
        session_id=SESSION_ID,
        turn_ranges=(
            FinalTurnRange(
                turn_id=QUESTION_TURN_ID,
                session_start_ms=0,
                session_end_ms=1000,
                confidence=1.0,
            ),
            FinalTurnRange(
                turn_id=ANSWER_TURN_ID,
                session_start_ms=2500,
                session_end_ms=4500,
                confidence=0.94,
            ),
        ),
        output_object_key=f"companies/{COMPANY_ID}/sessions/{SESSION_ID}/recording/final/v1",
        occurred_at=NOW,
    )

    transcripts = reporting_repository.list_transcripts(context(), SESSION_ID)
    assert tuple(segment.turn_id for segment in transcripts) == (
        QUESTION_TURN_ID,
        ANSWER_TURN_ID,
    )
    assert projected.recording.status == "partial"
    assert projected.recording.missing_ranges == ((2000, 2500),)
    assert all("000002" not in segment.source_audio_key for segment in transcripts)
    assert projected.competency_model_version_id == UUID("00000000-0000-7000-8000-000000000011")


def test_lane_d_boundary_rejects_unfinished_or_cross_tenant_session() -> None:
    unfinished, _ = build_boundary(state=InterviewSessionState.IN_PROGRESS)
    with pytest.raises(ValueError, match="completed"):
        unfinished.project_completed_session(
            context(),
            session_id=SESSION_ID,
            turn_ranges=(),
            output_object_key="opaque/final",
            occurred_at=NOW,
        )

    completed, _ = build_boundary()
    with pytest.raises((LookupError, TenantScopeError)):
        completed.project_completed_session(
            context(OTHER_COMPANY_ID),
            session_id=SESSION_ID,
            turn_ranges=(),
            output_object_key="opaque/final",
            occurred_at=NOW,
        )
