from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.interview_engine.application.checkpoints import CheckpointService
from interview_evidence.interview_engine.application.deletion_targets import (
    InMemoryInterviewTargetDeleter,
    InterviewDeletionTargets,
)
from interview_evidence.interview_engine.application.public import InterviewEnginePublic
from interview_evidence.interview_engine.domain.session import InterviewSession
from interview_evidence.interview_engine.domain.turn import (
    HotViewSyncStatus,
    InterviewTurn,
    RecordingChunk,
    RecordingUploadStatus,
    TurnSpeaker,
    TurnStatus,
)
from interview_evidence.interview_engine.repositories.postgres import (
    InMemoryInterviewRepository,
)
from interview_evidence.shared.ids import CommandMeta
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
TURN_ID = UUID("00000000-0000-7000-8000-000000000003")


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=UUID("00000000-0000-7000-8000-000000000004"),
        request_id=UUID("00000000-0000-7000-8000-000000000005"),
        trace_id="trace-lane-c-public",
    )


def test_public_facade_exposes_only_frozen_session_turn_media_and_deletion_contracts() -> None:
    repository = InMemoryInterviewRepository()
    session = repository.save_session(
        context(),
        InterviewSession(
            interview_session_id=SESSION_ID,
            company_id=COMPANY_ID,
            invitation_id=UUID("00000000-0000-7000-8000-000000000006"),
            applicant_id=UUID("00000000-0000-7000-8000-000000000007"),
            interview_strategy_id=UUID("00000000-0000-7000-8000-000000000008"),
            competency_model_version_id=UUID("00000000-0000-7000-8000-000000000009"),
            created_at=NOW,
        ),
    )
    turn = repository.save_turn(
        context(),
        InterviewTurn(
            turn_id=TURN_ID,
            company_id=COMPANY_ID,
            interview_session_id=SESSION_ID,
            sequence=1,
            speaker=TurnSpeaker.APPLICANT,
            status=TurnStatus.FINAL,
            text="보호된 최종 답변",
            idempotency_key="answer-complete-0001",
            finalized_at=NOW,
        ),
    )
    CheckpointService(repository).create(
        context(),
        session_id=SESSION_ID,
        last_final_turn_id=TURN_ID,
        last_media_chunk_sequence=1,
        pending_turn_id=None,
        hot_view_sync_status=HotViewSyncStatus.PENDING,
        occurred_at=NOW,
    )
    chunk = repository.save_recording_chunk(
        context(),
        RecordingChunk(
            recording_chunk_id=UUID("00000000-0000-7000-8000-000000000010"),
            company_id=COMPANY_ID,
            interview_session_id=SESSION_ID,
            sequence=1,
            object_key=f"companies/{COMPANY_ID}/sessions/{SESSION_ID}/chunks/000001",
            content_hash="a" * 64,
            byte_size=1024,
            session_start_ms=0,
            session_end_ms=2000,
            upload_status=RecordingUploadStatus.VERIFIED,
            idempotency_key="recording-upload-0001",
            created_at=NOW,
        ),
    )
    deleter = InMemoryInterviewTargetDeleter()
    public = InterviewEnginePublic(
        repository=repository,
        deletion_targets=InterviewDeletionTargets(repository),
        target_deleter=deleter,
    )

    snapshot = public.get_session_snapshot(context(), session_id=SESSION_ID)
    assert snapshot.state == session.state.value
    assert snapshot.last_final_turn_id == TURN_ID
    assert public.get_final_turn(context(), session_id=SESSION_ID, turn_id=TURN_ID) == turn
    assert public.list_final_turns(context(), session_id=SESSION_ID) == (turn,)
    assert public.resolve_recording_chunks(context(), session_id=SESSION_ID)[0].object_key == (
        chunk.object_key
    )

    targets = public.enumerate_interview_deletion_targets(context(), session_id=SESSION_ID)
    receipt = public.delete_interview_target(
        context(),
        target=targets[0],
        meta=CommandMeta(
            idempotency_key="delete-lane-c-target-0001",
            occurred_at=NOW,
        ),
    )
    assert receipt.verified_absent is True
