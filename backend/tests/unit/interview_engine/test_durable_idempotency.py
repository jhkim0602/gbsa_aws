from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.interview_engine.application.idempotency import (
    IdempotencyConflict,
    SqlAlchemyIdempotencyStore,
)
from interview_evidence.interview_engine.domain.session import (
    InterviewSession,
    InterviewSessionState,
)
from interview_evidence.interview_engine.repositories.postgres import Base
from interview_evidence.shared.tenant import ActorType, TenantContext
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

NOW = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.APPLICANT,
        actor_id=UUID("00000000-0000-7000-8000-000000000003"),
        request_id=UUID("00000000-0000-7000-8000-000000000004"),
        trace_id="trace-durable-interview-command",
    )


def result() -> InterviewSession:
    return InterviewSession(
        interview_session_id=SESSION_ID,
        company_id=COMPANY_ID,
        invitation_id=UUID("00000000-0000-7000-8000-000000000005"),
        applicant_id=context().actor_id,
        interview_strategy_id=UUID("00000000-0000-7000-8000-000000000006"),
        competency_model_version_id=UUID("00000000-0000-7000-8000-000000000007"),
        state=InterviewSessionState.IN_PROGRESS,
        session_sequence=1,
        row_version=2,
        created_at=NOW,
        started_at=NOW,
    )


def test_sql_idempotency_restores_typed_result_after_store_recreation() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    callback_count = 0

    with Session(engine) as session:
        store = SqlAlchemyIdempotencyStore(session)

        def execute() -> InterviewSession:
            nonlocal callback_count
            callback_count += 1
            return result()

        first = store.execute(
            context(),
            session_id=SESSION_ID,
            operation="session.start",
            idempotency_key="session-start-0001",
            request_payload={"expected_sequence": 0},
            execute=execute,
            occurred_at=NOW,
        )
        session.commit()

    with Session(engine) as session:
        duplicate = SqlAlchemyIdempotencyStore(session).execute(
            context(),
            session_id=SESSION_ID,
            operation="session.start",
            idempotency_key="session-start-0001",
            request_payload={"expected_sequence": 0},
            execute=lambda: pytest.fail("duplicate callback must not run"),
            occurred_at=NOW,
        )

    assert callback_count == 1
    assert duplicate == first
    assert isinstance(duplicate, InterviewSession)


def test_sql_idempotency_rejects_reused_key_with_different_request() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        store = SqlAlchemyIdempotencyStore(session)
        store.execute(
            context(),
            session_id=SESSION_ID,
            operation="session.start",
            idempotency_key="session-start-0002",
            request_payload={"expected_sequence": 0},
            execute=result,
            occurred_at=NOW,
        )
        session.commit()

    with Session(engine) as session, pytest.raises(IdempotencyConflict):
        SqlAlchemyIdempotencyStore(session).execute(
            context(),
            session_id=SESSION_ID,
            operation="session.start",
            idempotency_key="session-start-0002",
            request_payload={"expected_sequence": 1},
            execute=result,
            occurred_at=NOW,
        )
