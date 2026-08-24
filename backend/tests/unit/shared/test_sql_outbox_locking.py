from typing import Any, cast

from interview_evidence.shared.persistence import SQLOutbox
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session


def test_sql_outbox_locks_pending_rows_without_waiting() -> None:
    session = RecordingSession()

    assert SQLOutbox(cast(Session, session)).pending() == ()

    statement = session.statement
    assert statement is not None
    compiled = str(statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE SKIP LOCKED" in compiled


def test_sql_outbox_narrows_to_the_requested_types_before_the_page_limit() -> None:
    """Filter and limit have to be in that order, or a backlog hides what is behind it.

    `interview.checkpoint_changed` is written to the outbox but routed nowhere, so it stays
    pending for good. Limiting first meant a page of those was the whole result, and the
    `interview.completed` queued behind them never reached the reporting queue.
    """
    session = RecordingSession()

    SQLOutbox(cast(Session, session)).pending(
        event_types=("interview.completed", "report.generation_requested"),
    )

    statement = session.statement
    assert statement is not None
    compiled = str(statement.compile(dialect=postgresql.dialect()))
    assert "event_type IN" in compiled
    assert compiled.index("event_type IN") < compiled.index("LIMIT")


class RecordingSession:
    def __init__(self) -> None:
        self.statement: Any | None = None

    def scalars(self, statement: Any) -> tuple[object, ...]:
        self.statement = statement
        return ()
