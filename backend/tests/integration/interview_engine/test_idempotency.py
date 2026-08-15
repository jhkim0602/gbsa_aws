from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.interview_engine.application.idempotency import (
    IdempotencyConflict,
    InMemoryIdempotencyStore,
    JsonMappingIdempotencyStore,
)
from interview_evidence.interview_engine.repositories.postgres import Base
from interview_evidence.shared.tenant import ActorType, TenantContext
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.APPLICANT,
        actor_id=UUID("00000000-0000-7000-8000-000000000003"),
        request_id=UUID("00000000-0000-7000-8000-000000000004"),
        trace_id="trace-lane-c-idempotency",
    )


def test_duplicate_answer_upload_and_job_return_original_result() -> None:
    store = InMemoryIdempotencyStore()

    for operation, key in (
        ("answer.complete", "answer-complete-0001"),
        ("recording.upload", "recording-upload-0001"),
        ("question.generate", "question-job-0001"),
    ):
        calls = 0

        def execute(operation_name: str = operation) -> dict[str, str]:
            nonlocal calls
            calls += 1
            return {"operation": operation_name, "result": "accepted"}

        first = store.execute(
            context(),
            session_id=SESSION_ID,
            operation=operation,
            idempotency_key=key,
            request_payload={"sequence": 3},
            execute=execute,
            occurred_at=NOW,
        )
        duplicate = store.execute(
            context(),
            session_id=SESSION_ID,
            operation=operation,
            idempotency_key=key,
            request_payload={"sequence": 3},
            execute=execute,
            occurred_at=NOW,
        )

        assert duplicate == first
        assert calls == 1


def test_reusing_key_with_different_payload_is_rejected() -> None:
    store = InMemoryIdempotencyStore()
    store.execute(
        context(),
        session_id=SESSION_ID,
        operation="answer.complete",
        idempotency_key="answer-complete-conflict",
        request_payload={"sequence": 3},
        execute=lambda: {"turn_id": "turn-1"},
        occurred_at=NOW,
    )

    with pytest.raises(IdempotencyConflict):
        store.execute(
            context(),
            session_id=SESSION_ID,
            operation="answer.complete",
            idempotency_key="answer-complete-conflict",
            request_payload={"sequence": 4},
            execute=lambda: {"turn_id": "turn-2"},
            occurred_at=NOW,
        )


def test_sql_idempotency_result_survives_store_recreation() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    calls = 0

    with Session(engine) as sql_session:
        first_store = JsonMappingIdempotencyStore(sql_session)

        def execute() -> dict[str, str]:
            nonlocal calls
            calls += 1
            return {"status": "accepted"}

        first = first_store.execute(
            context(),
            session_id=SESSION_ID,
            operation="answer.complete",
            idempotency_key="durable-answer-0001",
            request_payload={"sequence": 3},
            execute=execute,
            occurred_at=NOW,
        )
        sql_session.commit()

    with Session(engine) as sql_session:
        recreated_store = JsonMappingIdempotencyStore(sql_session)
        duplicate = recreated_store.execute(
            context(),
            session_id=SESSION_ID,
            operation="answer.complete",
            idempotency_key="durable-answer-0001",
            request_payload={"sequence": 3},
            execute=execute,
            occurred_at=NOW,
        )

    assert duplicate == first
    assert calls == 1
