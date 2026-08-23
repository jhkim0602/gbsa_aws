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


class RecordingSession:
    def __init__(self) -> None:
        self.statement: Any | None = None

    def scalars(self, statement: Any) -> tuple[object, ...]:
        self.statement = statement
        return ()
