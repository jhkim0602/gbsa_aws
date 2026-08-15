from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.interview_engine.adapters.recent_context import (
    InMemoryRecentContext,
)
from interview_evidence.interview_engine.application.checkpoints import CheckpointService
from interview_evidence.interview_engine.application.context_reconciliation import (
    ContextReconciler,
)
from interview_evidence.interview_engine.domain.session import InterviewSession
from interview_evidence.interview_engine.domain.turn import (
    HotViewSyncStatus,
    InterviewTurn,
    TurnSpeaker,
    TurnStatus,
)
from interview_evidence.interview_engine.repositories.postgres import (
    InMemoryInterviewRepository,
)
from interview_evidence.shared.messaging.outbox import OutboxEvent
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.APPLICANT,
        actor_id=UUID("00000000-0000-7000-8000-000000000003"),
        request_id=UUID("00000000-0000-7000-8000-000000000004"),
        trace_id="trace-lane-c-reconciliation",
    )


def session() -> InterviewSession:
    return InterviewSession(
        interview_session_id=SESSION_ID,
        company_id=COMPANY_ID,
        invitation_id=UUID("00000000-0000-7000-8000-000000000005"),
        applicant_id=context().actor_id,
        interview_strategy_id=UUID("00000000-0000-7000-8000-000000000006"),
        competency_model_version_id=UUID("00000000-0000-7000-8000-000000000007"),
        session_sequence=4,
        created_at=NOW,
    )


def final_turn() -> InterviewTurn:
    return InterviewTurn(
        turn_id=UUID("00000000-0000-7000-8000-000000000008"),
        company_id=COMPANY_ID,
        interview_session_id=SESSION_ID,
        sequence=2,
        speaker=TurnSpeaker.APPLICANT,
        status=TurnStatus.FINAL,
        text="보호된 최종 답변",
        idempotency_key="answer-complete-0002",
        finalized_at=NOW,
    )


def test_missing_or_stale_hot_view_is_rebuilt_from_durable_checkpoint() -> None:
    repository = InMemoryInterviewRepository()
    repository.save_session(context(), session())
    repository.save_turn(context(), final_turn())
    checkpoint = CheckpointService(repository).create(
        context(),
        session_id=SESSION_ID,
        last_final_turn_id=final_turn().turn_id,
        last_media_chunk_sequence=5,
        pending_turn_id=None,
        hot_view_sync_status=HotViewSyncStatus.PENDING,
        occurred_at=NOW,
    )
    hot_view = InMemoryRecentContext()
    reconciler = ContextReconciler(repository, hot_view)

    first = reconciler.get_or_rebuild(
        context(),
        session_id=SESSION_ID,
        last_reconciled_event_id=UUID("00000000-0000-7000-8000-000000000009"),
    )
    assert first.checkpoint_id == checkpoint.checkpoint_id
    assert first.last_final_turn_id == final_turn().turn_id
    assert first.last_media_chunk_sequence == 5
    assert first.source == "aurora_rebuild"

    hot_view.force_sequence(context(), SESSION_ID, session_sequence=1)
    rebuilt = reconciler.get_or_rebuild(
        context(),
        session_id=SESSION_ID,
        last_reconciled_event_id=UUID("00000000-0000-7000-8000-000000000010"),
    )
    assert rebuilt.session_sequence == 4
    assert rebuilt.source == "aurora_rebuild"


def test_hot_view_write_failure_returns_durable_fallback() -> None:
    repository = InMemoryInterviewRepository()
    repository.save_session(context(), session())
    CheckpointService(repository).create(
        context(),
        session_id=SESSION_ID,
        last_final_turn_id=None,
        last_media_chunk_sequence=0,
        pending_turn_id=None,
        hot_view_sync_status=HotViewSyncStatus.PENDING,
        occurred_at=NOW,
    )
    hot_view = InMemoryRecentContext(fail_writes=True)

    result = ContextReconciler(repository, hot_view).get_or_rebuild(
        context(),
        session_id=SESSION_ID,
        last_reconciled_event_id=None,
    )

    assert result.source == "aurora_fallback"
    assert "context_hot_view" in result.degraded_modes


def test_checkpoint_outbox_event_rebuilds_hot_view_without_protected_text() -> None:
    repository = InMemoryInterviewRepository()
    repository.save_session(context(), session())
    checkpoint = CheckpointService(repository).create(
        context(),
        session_id=SESSION_ID,
        last_final_turn_id=None,
        last_media_chunk_sequence=3,
        pending_turn_id=None,
        hot_view_sync_status=HotViewSyncStatus.PENDING,
        occurred_at=NOW,
    )
    hot_view = InMemoryRecentContext()
    event = OutboxEvent(
        outbox_event_id=UUID("00000000-0000-7000-8000-000000000011"),
        company_id=COMPANY_ID,
        aggregate_type="interview_session",
        aggregate_id=SESSION_ID,
        aggregate_version=4,
        event_type="interview.checkpoint_changed",
        event_version=1,
        payload={
            "session_id": str(SESSION_ID),
            "checkpoint_id": str(checkpoint.checkpoint_id),
        },
        idempotency_key="checkpoint-reconcile-0001",
        trace_id=context().trace_id,
        occurred_at=NOW,
    )

    result = ContextReconciler(repository, hot_view).reconcile_event(context(), event)

    assert result.checkpoint_id == checkpoint.checkpoint_id
    assert result.last_media_chunk_sequence == 3
    assert hot_view.get(context(), SESSION_ID) is not None
