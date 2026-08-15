from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from typing import Protocol
from uuid import UUID

from interview_evidence.shared.aws_clients.ports import ConsumableQueue, EventQueue
from interview_evidence.shared.ids import Clock
from interview_evidence.shared.messaging.outbox import (
    Outbox,
    OutboxEvent,
    ProcessedMessage,
)
from interview_evidence.shared.tenant import ActorType, TenantContext

EventHandler = Callable[[TenantContext, OutboxEvent], object]


class ProcessedMessageStore(Protocol):
    def contains(
        self,
        *,
        consumer_name: str,
        event_id: UUID,
        event_version: int,
    ) -> bool: ...

    def get(
        self,
        *,
        consumer_name: str,
        event_id: UUID,
        event_version: int,
    ) -> ProcessedMessage: ...

    def record(self, message: ProcessedMessage) -> None: ...


class InMemoryProcessedMessageStore:
    def __init__(self) -> None:
        self._messages: dict[tuple[str, UUID, int], ProcessedMessage] = {}

    def contains(
        self,
        *,
        consumer_name: str,
        event_id: UUID,
        event_version: int,
    ) -> bool:
        return (consumer_name, event_id, event_version) in self._messages

    def get(
        self,
        *,
        consumer_name: str,
        event_id: UUID,
        event_version: int,
    ) -> ProcessedMessage:
        return self._messages[(consumer_name, event_id, event_version)]

    def record(self, message: ProcessedMessage) -> None:
        self._messages.setdefault(
            (message.consumer_name, message.event_id, message.event_version),
            message,
        )


class OutboxDispatcher:
    def __init__(
        self,
        *,
        outbox: Outbox,
        queues: Mapping[str, EventQueue],
        routing: Mapping[str, str],
    ) -> None:
        self.outbox = outbox
        self._queues = dict(queues)
        self._routing = dict(routing)

    def dispatch_once(self) -> int:
        published = 0
        for event in self.outbox.pending():
            queue_name = self._routing.get(event.event_type)
            if queue_name is None:
                continue
            queue = self._queues[queue_name]
            queue.publish(
                TenantContext(
                    company_id=event.company_id,
                    actor_type=ActorType.SYSTEM,
                    actor_id=event.outbox_event_id,
                    request_id=event.outbox_event_id,
                    trace_id=event.trace_id,
                ),
                event.event_type,
                {
                    "event_id": str(event.outbox_event_id),
                    "event_version": event.event_version,
                    "idempotency_key": event.idempotency_key,
                    "occurred_at": event.occurred_at.isoformat(),
                    "aggregate_type": event.aggregate_type,
                    "aggregate_id": str(event.aggregate_id),
                    "aggregate_version": event.aggregate_version,
                    "payload": event.payload,
                },
            )
            self.outbox.mark_published(event.outbox_event_id)
            published += 1
        return published


class MessageConsumer:
    def __init__(
        self,
        *,
        consumer_name: str,
        queue: ConsumableQueue,
        processed: ProcessedMessageStore,
        handlers: Mapping[str, EventHandler],
        clock: Clock,
    ) -> None:
        self._consumer_name = consumer_name
        self._queue = queue
        self._processed = processed
        self._handlers = dict(handlers)
        self._clock = clock

    def consume_once(self, *, max_messages: int) -> int:
        completed = 0
        for delivery in self._queue.receive(max_messages=max_messages):
            if self._processed.contains(
                consumer_name=self._consumer_name,
                event_id=delivery.event_id,
                event_version=delivery.event_version,
            ):
                self._queue.acknowledge(delivery.receipt_handle)
                completed += 1
                continue
            handler = self._handlers.get(delivery.event_type)
            if handler is None:
                self._queue.acknowledge(delivery.receipt_handle)
                completed += 1
                continue
            event = OutboxEvent(
                outbox_event_id=delivery.event_id,
                company_id=delivery.company_id,
                aggregate_type=delivery.aggregate_type,
                aggregate_id=delivery.aggregate_id,
                aggregate_version=delivery.aggregate_version,
                event_type=delivery.event_type,
                event_version=delivery.event_version,
                payload=dict(delivery.payload),
                idempotency_key=delivery.idempotency_key,
                trace_id=delivery.trace_id,
                occurred_at=delivery.occurred_at,
            )
            context = TenantContext(
                company_id=delivery.company_id,
                actor_type=ActorType.SYSTEM,
                actor_id=delivery.event_id,
                request_id=delivery.event_id,
                trace_id=delivery.trace_id,
            )
            try:
                outcome = handler(context, event)
            except (TimeoutError, ConnectionError):
                self._queue.retry(delivery.receipt_handle)
                continue
            digest = hashlib.sha256(repr(outcome).encode("utf-8")).hexdigest()
            self._processed.record(
                ProcessedMessage(
                    consumer_name=self._consumer_name,
                    event_id=delivery.event_id,
                    event_version=delivery.event_version,
                    idempotency_key=delivery.idempotency_key,
                    first_processed_at=self._clock.now(),
                    outcome_digest=digest,
                )
            )
            self._queue.acknowledge(delivery.receipt_handle)
            completed += 1
        return completed
