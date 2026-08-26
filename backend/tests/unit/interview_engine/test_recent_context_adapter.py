from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

from interview_evidence.interview_engine.adapters.recent_context import (
    InMemoryRecentContext,
    PostgresRecentContext,
    RecentContextSnapshot,
)
from interview_evidence.interview_engine.repositories.postgres import InterviewRepository
from interview_evidence.shared.tenant import ActorType, TenantContext

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
CHECKPOINT_ID = UUID("00000000-0000-7000-8000-000000000005")
LAST_TURN_ID = UUID("00000000-0000-7000-8000-000000000006")
CREATED_AT = datetime(2026, 8, 22, 9, 0, tzinfo=UTC)


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=UUID("00000000-0000-7000-8000-000000000003"),
        request_id=UUID("00000000-0000-7000-8000-000000000004"),
        trace_id="trace-postgres-recent-context",
    )


class FakeInterviewRepository:
    def get_session(self, context: TenantContext, session_id: UUID) -> object:
        context.assert_company(COMPANY_ID)
        assert session_id == SESSION_ID
        return SimpleNamespace(company_id=COMPANY_ID)

    def latest_checkpoint(self, context: TenantContext, session_id: UUID) -> object:
        context.assert_company(COMPANY_ID)
        assert session_id == SESSION_ID
        return SimpleNamespace(
            checkpoint_id=CHECKPOINT_ID,
            session_sequence=4,
            last_final_turn_id=LAST_TURN_ID,
            pending_turn_id=None,
            last_media_chunk_sequence=2,
            created_at=CREATED_AT,
        )


def test_postgres_adapter_reads_the_durable_checkpoint() -> None:
    adapter = PostgresRecentContext(cast(InterviewRepository, FakeInterviewRepository()))

    restored = adapter.get(context(), SESSION_ID)

    assert restored is not None
    assert restored.company_id == COMPANY_ID
    assert restored.interview_session_id == SESSION_ID
    assert restored.session_sequence == 4
    assert restored.checkpoint_id == CHECKPOINT_ID
    assert restored.last_final_turn_id == LAST_TURN_ID
    assert restored.last_media_chunk_sequence == 2
    assert restored.expires_at == datetime(2026, 8, 29, 9, 0, tzinfo=UTC)
    assert adapter.put(context(), restored) == restored


def test_in_memory_adapter_round_trips_tenant_scoped_snapshot() -> None:
    adapter = InMemoryRecentContext()
    snapshot = RecentContextSnapshot(
        company_id=COMPANY_ID,
        interview_session_id=SESSION_ID,
        session_sequence=4,
        checkpoint_id=CHECKPOINT_ID,
        last_final_turn_id=LAST_TURN_ID,
        pending_turn_id=None,
        last_media_chunk_sequence=2,
        last_reconciled_event_id=UUID("00000000-0000-7000-8000-000000000007"),
        expires_at=datetime(2026, 8, 22, 9, 0, tzinfo=UTC),
    )

    adapter.put(context(), snapshot)
    assert adapter.get(context(), SESSION_ID) == snapshot

    adapter.delete(context(), SESSION_ID)
    assert adapter.get(context(), SESSION_ID) is None
