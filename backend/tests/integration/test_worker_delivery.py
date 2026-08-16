from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.runtime.worker import (
    EVENT_QUEUE_ROUTING,
    InterviewCompletedEventHandler,
    ParityProbeEventHandler,
    create_environment_worker_runtime,
)
from interview_evidence.shared.aws_clients.ports import InMemoryQueue
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.messaging.outbox import (
    InMemoryOutbox,
    OutboxEvent,
    ProcessedMessage,
)
from interview_evidence.shared.messaging.worker import (
    InMemoryProcessedMessageStore,
    MessageConsumer,
    OutboxDispatcher,
)
from interview_evidence.shared.operations import InMemoryMetricRecorder
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000101")
ACTOR_ID = UUID("00000000-0000-7000-8000-000000000102")
EVENT_ID = UUID("00000000-0000-7000-8000-000000000103")
AGGREGATE_ID = UUID("00000000-0000-7000-8000-000000000104")


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=ACTOR_ID,
        request_id=EVENT_ID,
        trace_id="worker-trace",
    )


def _event() -> OutboxEvent:
    return OutboxEvent(
        outbox_event_id=EVENT_ID,
        company_id=COMPANY_ID,
        aggregate_type="submission",
        aggregate_id=AGGREGATE_ID,
        aggregate_version=1,
        event_type="submission.analysis_requested",
        event_version=1,
        payload={
            "submission_id": str(AGGREGATE_ID),
            "analysis_version": 1,
            "source_type": "pdf",
            "source_object_id": str(AGGREGATE_ID),
        },
        idempotency_key="analysis-request-0001",
        trace_id="worker-trace",
        occurred_at=NOW,
    )


def test_outbox_dispatch_marks_published_only_after_queue_accepts() -> None:
    outbox = InMemoryOutbox()
    queue = InMemoryQueue()
    outbox.append(_event())

    dispatched = OutboxDispatcher(
        outbox=outbox,
        queues={"analysis": queue},
        routing={"submission.analysis_requested": "analysis"},
    ).dispatch_once()

    assert dispatched == 1
    assert outbox.pending() == ()
    delivery = queue.receive(max_messages=1)[0]
    assert delivery.event_id == EVENT_ID
    assert delivery.company_id == COMPANY_ID
    assert delivery.payload["submission_id"] == str(AGGREGATE_ID)


def test_consumer_records_success_and_suppresses_duplicate_delivery() -> None:
    queue = InMemoryQueue()
    processed = InMemoryProcessedMessageStore()
    calls: list[UUID] = []

    def handle(context: TenantContext, event: OutboxEvent) -> str:
        context.assert_company(event.company_id)
        calls.append(event.outbox_event_id)
        return "ready"

    dispatcher = OutboxDispatcher(
        outbox=InMemoryOutbox(),
        queues={"analysis": queue},
        routing={"submission.analysis_requested": "analysis"},
    )
    dispatcher.outbox.append(_event())
    dispatcher.dispatch_once()
    queue.redeliver_all()

    consumer = MessageConsumer(
        consumer_name="analysis-worker",
        queue=queue,
        processed=processed,
        handlers={"submission.analysis_requested": handle},
        clock=FrozenClock(NOW),
    )

    assert consumer.consume_once(max_messages=10) == 2
    assert calls == [EVENT_ID]
    assert queue.receive(max_messages=10) == ()
    assert processed.contains(
        consumer_name="analysis-worker",
        event_id=EVENT_ID,
        event_version=1,
    )


def test_consumer_requeues_retryable_failure_without_recording_success() -> None:
    queue = InMemoryQueue()
    processed = InMemoryProcessedMessageStore()
    attempts = 0

    def handle(_context: TenantContext, _event: OutboxEvent) -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("dependency timeout")
        return "ready"

    dispatcher = OutboxDispatcher(
        outbox=InMemoryOutbox(),
        queues={"analysis": queue},
        routing={"submission.analysis_requested": "analysis"},
    )
    dispatcher.outbox.append(_event())
    dispatcher.dispatch_once()
    consumer = MessageConsumer(
        consumer_name="analysis-worker",
        queue=queue,
        processed=processed,
        handlers={"submission.analysis_requested": handle},
        clock=FrozenClock(NOW),
    )

    assert consumer.consume_once(max_messages=1) == 0
    assert not processed.contains(
        consumer_name="analysis-worker",
        event_id=EVENT_ID,
        event_version=1,
    )
    assert consumer.consume_once(max_messages=1) == 1
    assert attempts == 2
    assert processed.get(
        consumer_name="analysis-worker",
        event_id=EVENT_ID,
        event_version=1,
    ) == ProcessedMessage(
        consumer_name="analysis-worker",
        event_id=EVENT_ID,
        event_version=1,
        idempotency_key="analysis-request-0001",
        first_processed_at=NOW,
        outcome_digest=processed.get(
            consumer_name="analysis-worker",
            event_id=EVENT_ID,
            event_version=1,
        ).outcome_digest,
    )


def test_local_worker_runtime_executes_a_cycle_without_cloud_dependencies() -> None:
    runtime = create_environment_worker_runtime({"APP_ENVIRONMENT": "local"})

    assert runtime.run_once() == 0


def test_worker_records_queue_depth_handler_latency_and_retry_outcome() -> None:
    queue = InMemoryQueue()
    metrics = InMemoryMetricRecorder()
    dispatcher = OutboxDispatcher(
        outbox=InMemoryOutbox(),
        queues={"analysis": queue},
        routing={"submission.analysis_requested": "analysis"},
        metrics=metrics,
    )
    dispatcher.outbox.append(_event())
    dispatcher.dispatch_once()

    def fail_once(_context: TenantContext, _event: OutboxEvent) -> str:
        raise TimeoutError("temporary dependency failure")

    consumer = MessageConsumer(
        consumer_name="analysis-worker",
        queue_name="analysis",
        queue=queue,
        processed=InMemoryProcessedMessageStore(),
        handlers={"submission.analysis_requested": fail_once},
        clock=FrozenClock(NOW),
        metrics=metrics,
    )
    assert consumer.consume_once(max_messages=1) == 0

    names = [record.name for record in metrics.records]
    assert "queue_depth" in names
    assert "pipeline_stage_latency_ms" in names
    assert any(
        record.name == "worker_delivery" and record.dimensions["outcome"] == "retrying"
        for record in metrics.records
    )


def test_parity_probe_uses_real_worker_delivery_contract() -> None:
    probe_event = _event().model_copy(
        update={
            "aggregate_type": "system_parity",
            "event_type": "system.parity_probe",
            "payload": {"probe_id": str(AGGREGATE_ID)},
            "idempotency_key": "system-parity-probe-0001",
        }
    )
    outbox = InMemoryOutbox()
    queue = InMemoryQueue()
    processed = InMemoryProcessedMessageStore()
    outbox.append(probe_event)

    dispatcher = OutboxDispatcher(
        outbox=outbox,
        queues={"analysis": queue},
        routing=EVENT_QUEUE_ROUTING,
    )
    consumer = MessageConsumer(
        consumer_name="analysis-worker",
        queue_name="analysis",
        queue=queue,
        processed=processed,
        handlers={"system.parity_probe": ParityProbeEventHandler()},
        clock=FrozenClock(NOW),
    )

    assert dispatcher.dispatch_once() == 1
    assert consumer.consume_once(max_messages=1) == 1
    assert processed.contains(
        consumer_name="analysis-worker",
        event_id=EVENT_ID,
        event_version=1,
    )
    assert EVENT_QUEUE_ROUTING["system.parity_probe"] == "analysis"


def test_interview_completion_requests_media_postprocessing() -> None:
    outbox = InMemoryOutbox()
    completed = _event().model_copy(
        update={
            "aggregate_type": "interview_session",
            "event_type": "interview.completed",
            "payload": {
                "interview_session_id": str(AGGREGATE_ID),
                "invitation_id": str(UUID("00000000-0000-7000-8000-000000000105")),
                "last_turn_id": str(UUID("00000000-0000-7000-8000-000000000106")),
                "completed_at": NOW.isoformat(),
                "media_status": "pending",
            },
        }
    )

    requested = InterviewCompletedEventHandler(
        outbox,
        FrozenClock(NOW),
    )(_context(), completed)

    assert requested.event_type == "media.postprocess_requested"
    assert requested.payload["interview_session_id"] == str(AGGREGATE_ID)
    assert outbox.pending() == (requested,)
