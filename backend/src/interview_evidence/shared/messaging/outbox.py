from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from interview_evidence.shared.observability import is_prohibited_field


class ProhibitedPayloadError(TypeError):
    """Raised when protected text or secrets are placed on an event."""


def _assert_safe_payload(value: Any, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if is_prohibited_field(key_text):
                raise ProhibitedPayloadError(f"{path}.{key_text} is prohibited")
            _assert_safe_payload(item, f"{path}.{key_text}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _assert_safe_payload(item, f"{path}[{index}]")


class PublishStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"


class OutboxEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outbox_event_id: UUID
    company_id: UUID
    aggregate_type: str = Field(min_length=1, max_length=100)
    aggregate_id: UUID
    aggregate_version: int = Field(ge=0)
    event_type: str = Field(min_length=1, max_length=200)
    event_version: int = Field(ge=1)
    payload: dict[str, Any]
    idempotency_key: str = Field(min_length=8, max_length=200)
    trace_id: str = Field(min_length=1, max_length=200)
    occurred_at: datetime
    publish_status: PublishStatus = PublishStatus.PENDING
    publish_attempts: int = Field(default=0, ge=0)
    delivery_attempt: int = Field(default=1, ge=1, exclude=True)

    @field_validator("payload")
    @classmethod
    def payload_contains_identifiers_only(cls, value: dict[str, Any]) -> dict[str, Any]:
        _assert_safe_payload(value)
        return value


class ProcessedMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    consumer_name: str = Field(min_length=1, max_length=200)
    event_id: UUID
    event_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=200)
    first_processed_at: datetime
    outcome_digest: str = Field(min_length=1, max_length=128)


class Outbox(Protocol):
    def append(self, event: OutboxEvent) -> OutboxEvent: ...

    def pending(self) -> tuple[OutboxEvent, ...]: ...

    def mark_published(self, event_id: UUID) -> None: ...


class InMemoryOutbox:
    def __init__(self) -> None:
        self._events: dict[UUID, OutboxEvent] = {}
        self._idempotency_index: dict[str, UUID] = {}

    def append(self, event: OutboxEvent) -> OutboxEvent:
        existing_id = self._idempotency_index.get(event.idempotency_key)
        if existing_id is not None:
            return self._events[existing_id]
        existing = self._events.get(event.outbox_event_id)
        if existing is not None:
            return existing
        self._events[event.outbox_event_id] = event
        self._idempotency_index[event.idempotency_key] = event.outbox_event_id
        return event

    def pending(self) -> tuple[OutboxEvent, ...]:
        return tuple(
            event
            for event in self._events.values()
            if event.publish_status is PublishStatus.PENDING
        )

    def mark_published(self, event_id: UUID) -> None:
        event = self._events[event_id]
        self._events[event_id] = event.model_copy(
            update={
                "publish_status": PublishStatus.PUBLISHED,
                "publish_attempts": event.publish_attempts + 1,
            }
        )
