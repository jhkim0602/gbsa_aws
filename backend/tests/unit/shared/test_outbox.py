from collections.abc import Iterable
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from interview_evidence.shared.aws_clients.ports import InMemoryQueue
from interview_evidence.shared.messaging.outbox import (
    InMemoryOutbox,
    OutboxEvent,
    ProhibitedPayloadError,
)
from interview_evidence.shared.messaging.worker import OutboxDispatcher


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


def test_dispatch_asks_only_for_the_types_it_can_route() -> None:
    """A routable event queued behind unroutable ones still has to reach its queue.

    `interview.checkpoint_changed` is written to the outbox but appears in no routing table, so
    it is skipped on every pass and stays pending for good -- tens accumulate per interview.
    `pending` returns one bounded page of the oldest rows, so once there are a page of them the
    dispatcher sees nothing else, and `interview.completed` stops being published: the reporting
    worker is never asked for a report and the console waits forever.
    """
    outbox = InMemoryOutbox()
    queue = InMemoryQueue()
    for index in range(120):
        outbox.append(
            make_event({"submission_id": "00000000-0000-7000-8000-000000000003"}).model_copy(
                update={
                    "outbox_event_id": UUID(f"00000000-0000-7000-8000-000000900{index:03d}"),
                    "event_type": "interview.checkpoint_changed",
                    "idempotency_key": f"checkpoint-{index:04d}",
                }
            )
        )
    routable = make_event({"submission_id": "00000000-0000-7000-8000-000000000003"})
    outbox.append(routable)

    asked: list[tuple[str, ...]] = []
    unfiltered = outbox.pending

    def recording_pending(**kwargs: object) -> tuple[OutboxEvent, ...]:
        event_types = kwargs.get("event_types")
        asked.append(tuple(sorted(cast(Iterable[str], event_types))) if event_types else ())
        return unfiltered(**kwargs)  # type: ignore[arg-type]

    outbox.pending = recording_pending  # type: ignore[method-assign]
    published = OutboxDispatcher(
        outbox=outbox,
        queues={"analysis": queue},
        routing={"submission.analysis_requested": "analysis"},
    ).dispatch_once()

    assert asked == [("submission.analysis_requested",)]
    assert published == 1
    assert queue.receive(max_messages=1)[0].event_id == routable.outbox_event_id


def test_an_unfiltered_request_still_returns_everything_pending() -> None:
    """Callers that legitimately want the whole backlog -- tests, operational scripts -- keep
    working; the filter is an argument the dispatcher passes, not a change to the default."""
    outbox = InMemoryOutbox()
    outbox.append(make_event({"submission_id": "00000000-0000-7000-8000-000000000003"}))

    assert len(outbox.pending()) == 1
    assert outbox.pending(event_types=("nothing.matches",)) == ()
