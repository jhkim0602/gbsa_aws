from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.interview_engine.adapters.recent_context import InMemoryRecentContext
from interview_evidence.interview_engine.application.checkpoints import CheckpointService
from interview_evidence.interview_engine.application.context_reconciliation import (
    ContextReconciler,
)
from interview_evidence.interview_engine.application.idempotency import InMemoryIdempotencyStore
from interview_evidence.interview_engine.application.recovery_service import RecoveryService
from interview_evidence.interview_engine.domain.session import (
    InterviewSession,
    InterviewSessionState,
)
from interview_evidence.interview_engine.domain.turn import (
    HotViewSyncStatus,
    InterviewTurn,
    TurnSpeaker,
    TurnStatus,
)
from interview_evidence.interview_engine.repositories.postgres import (
    InMemoryInterviewRepository,
)
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
ANSWER_TURN_ID = UUID("00000000-0000-7000-8000-000000000008")


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.APPLICANT,
        actor_id=UUID("00000000-0000-7000-8000-000000000003"),
        request_id=UUID("00000000-0000-7000-8000-000000000004"),
        trace_id="trace-lane-c-recovery",
    )


def session() -> InterviewSession:
    return InterviewSession(
        interview_session_id=SESSION_ID,
        company_id=COMPANY_ID,
        invitation_id=UUID("00000000-0000-7000-8000-000000000005"),
        applicant_id=context().actor_id,
        interview_strategy_id=UUID("00000000-0000-7000-8000-000000000006"),
        competency_model_version_id=UUID("00000000-0000-7000-8000-000000000007"),
        state=InterviewSessionState.AWAITING_ANSWER,
        session_sequence=3,
        created_at=NOW,
        started_at=NOW,
    )


def test_duplicate_answer_creates_one_turn_and_stale_sequence_gets_snapshot() -> None:
    repository = InMemoryInterviewRepository()
    repository.save_session(context(), session())
    checkpoint_service = CheckpointService(repository)
    recovery = RecoveryService(
        repository=repository,
        idempotency=InMemoryIdempotencyStore(),
        checkpoints=checkpoint_service,
        reconciler=ContextReconciler(repository, InMemoryRecentContext()),
    )

    first = recovery.finalize_answer(
        context(),
        session_id=SESSION_ID,
        expected_sequence=3,
        answer_turn_id=ANSWER_TURN_ID,
        text="보호된 최종 답변",
        last_recording_chunk_sequence=5,
        idempotency_key="answer-complete-0003",
        occurred_at=NOW,
    )
    duplicate = recovery.finalize_answer(
        context(),
        session_id=SESSION_ID,
        expected_sequence=3,
        answer_turn_id=ANSWER_TURN_ID,
        text="보호된 최종 답변",
        last_recording_chunk_sequence=5,
        idempotency_key="answer-complete-0003",
        occurred_at=NOW,
    )

    assert duplicate == first
    assert len(repository.list_final_turns(context(), SESSION_ID)) == 1

    stale = recovery.finalize_answer(
        context(),
        session_id=SESSION_ID,
        expected_sequence=1,
        answer_turn_id=UUID("00000000-0000-7000-8000-000000000009"),
        text="오래된 클라이언트 답변",
        last_recording_chunk_sequence=4,
        idempotency_key="answer-complete-stale",
        occurred_at=NOW,
    )
    assert stale.message_type == "resume.snapshot"
    assert stale.server_sequence == first.server_sequence
    assert len(repository.list_final_turns(context(), SESSION_ID)) == 1


def test_reconnect_returns_last_durable_turn_and_media_sequence() -> None:
    repository = InMemoryInterviewRepository()
    repository.save_session(context(), session())
    repository.save_turn(
        context(),
        InterviewTurn(
            turn_id=ANSWER_TURN_ID,
            company_id=COMPANY_ID,
            interview_session_id=SESSION_ID,
            sequence=2,
            speaker=TurnSpeaker.APPLICANT,
            status=TurnStatus.FINAL,
            text="보호된 최종 답변",
            idempotency_key="answer-complete-0002",
            finalized_at=NOW,
        ),
    )
    checkpoint = CheckpointService(repository).create(
        context(),
        session_id=SESSION_ID,
        last_final_turn_id=ANSWER_TURN_ID,
        last_media_chunk_sequence=7,
        pending_turn_id=None,
        hot_view_sync_status=HotViewSyncStatus.PENDING,
        occurred_at=NOW,
    )
    recovery = RecoveryService(
        repository=repository,
        idempotency=InMemoryIdempotencyStore(),
        checkpoints=CheckpointService(repository),
        reconciler=ContextReconciler(repository, InMemoryRecentContext()),
    )

    snapshot = recovery.resume(
        context(),
        session_id=SESSION_ID,
        client_sequence=1,
    )

    assert snapshot.message_type == "resume.snapshot"
    assert snapshot.checkpoint_id == checkpoint.checkpoint_id
    assert snapshot.last_final_turn_id == ANSWER_TURN_ID
    assert snapshot.last_verified_recording_chunk_sequence == 7
