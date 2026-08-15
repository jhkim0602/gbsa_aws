from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.shared.messaging.outbox import (
    InMemoryOutbox,
    OutboxEvent,
    ProhibitedPayloadError,
)


def make_event(payload: dict[str, object]) -> OutboxEvent:
    return OutboxEvent(
        outbox_event_id=UUID("00000000-0000-7000-8000-000000000001"),
        company_id=UUID("00000000-0000-7000-8000-000000000002"),
        aggregate_type="submission",
        aggregate_id=UUID("00000000-0000-7000-8000-000000000003"),
        aggregate_version=1,
        event_type="submission.analysis_requested",
        event_version=1,
        payload=payload,
        idempotency_key="analysis-submission-1",
        trace_id="trace-outbox",
        occurred_at=datetime(2026, 8, 15, tzinfo=UTC),
    )


def test_duplicate_outbox_event_returns_original_record() -> None:
    outbox = InMemoryOutbox()
    event = make_event({"submission_id": "00000000-0000-7000-8000-000000000003"})

    assert outbox.append(event) == event
    assert outbox.append(event) == event
    assert len(outbox.pending()) == 1


def test_outbox_rejects_protected_text_and_secrets() -> None:
    with pytest.raises(ProhibitedPayloadError):
        make_event({"answer_text": "protected applicant answer"})
