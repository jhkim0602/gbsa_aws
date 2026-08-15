from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, Protocol
from uuid import UUID, uuid4

from interview_evidence.shared.ids import new_uuid7
from interview_evidence.shared.tenant import TenantContext, require_tenant_context


@dataclass(frozen=True, slots=True)
class UploadIntent:
    object_id: UUID
    company_id: UUID
    namespace: str
    byte_size: int
    sha256: str
    object_key: str
    url: str
    required_headers: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class QueueMessage:
    company_id: UUID
    event_type: str
    payload: Mapping[str, Any]
    trace_id: str


@dataclass(frozen=True, slots=True)
class QueueDelivery:
    receipt_handle: str
    event_id: UUID
    event_version: int
    idempotency_key: str
    company_id: UUID
    aggregate_type: str
    aggregate_id: UUID
    aggregate_version: int
    event_type: str
    payload: Mapping[str, Any]
    trace_id: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class SearchHit:
    company_id: UUID
    source_id: UUID
    score: float
    locator: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class SpeechToTextCall:
    company_id: UUID
    byte_length: int
    sample_rate_hz: int


@dataclass(frozen=True, slots=True)
class TextToSpeechCall:
    company_id: UUID
    text_sha256: str
    voice_id: str


@dataclass(frozen=True, slots=True)
class EmailMessage:
    message_id: UUID
    company_id: UUID
    template_id: str
    recipient_ref: UUID
    recipient_address_sha256: str
    template_data: Mapping[str, Any]


class _DeterministicIds:
    def __init__(self) -> None:
        self._counter = 0
        self._epoch = datetime(2026, 8, 15, tzinfo=UTC)

    def next(self) -> UUID:
        self._counter += 1
        return new_uuid7(
            self._epoch + timedelta(milliseconds=self._counter),
            random_bits=self._counter,
        )


class ObjectStorage(Protocol):
    def create_upload_intent(
        self,
        context: TenantContext,
        namespace: str,
        byte_size: int,
        sha256: str,
    ) -> UploadIntent: ...


class EventQueue(Protocol):
    def publish(
        self,
        context: TenantContext,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> None: ...


class ConsumableQueue(EventQueue, Protocol):
    def receive(self, *, max_messages: int) -> tuple[QueueDelivery, ...]: ...

    def acknowledge(self, receipt_handle: str) -> None: ...

    def retry(self, receipt_handle: str) -> None: ...

    def healthcheck(self) -> None: ...

    def approximate_depth(self) -> int: ...


class SearchPort(Protocol):
    def search(
        self,
        context: TenantContext,
        query: str,
        *,
        limit: int,
    ) -> Sequence[SearchHit]: ...


class AIModel(Protocol):
    def generate(
        self,
        context: TenantContext,
        model_input: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


class SpeechToText(Protocol):
    def transcribe(
        self,
        context: TenantContext,
        audio: bytes,
        *,
        sample_rate_hz: int,
    ) -> Mapping[str, Any]: ...


class TextToSpeech(Protocol):
    def synthesize(
        self,
        context: TenantContext,
        text: str,
        *,
        voice_id: str,
    ) -> Mapping[str, Any]: ...


class EmailSender(Protocol):
    def send_template(
        self,
        context: TenantContext,
        template_id: str,
        recipient_ref: UUID,
        recipient_address: str,
        template_data: Mapping[str, Any],
    ) -> UUID: ...


class InMemoryObjectStorage:
    def __init__(self) -> None:
        self.intents: list[UploadIntent] = []
        self._ids = _DeterministicIds()

    def create_upload_intent(
        self,
        context: TenantContext,
        namespace: str,
        byte_size: int,
        sha256: str,
    ) -> UploadIntent:
        tenant = require_tenant_context(context)
        if byte_size < 0:
            raise ValueError("byte_size must be non-negative")
        if len(sha256) != 64:
            raise ValueError("sha256 must contain 64 hexadecimal characters")
        intent = UploadIntent(
            object_id=self._ids.next(),
            company_id=tenant.company_id,
            namespace=namespace,
            byte_size=byte_size,
            sha256=sha256,
            object_key=(f"tenants/{tenant.company_id}/{namespace}/{self._ids.next()}"),
            url="https://uploads.local/presigned",
            required_headers={"x-amz-checksum-sha256": sha256},
        )
        self.intents.append(intent)
        return intent

    def delete_and_verify_object(
        self,
        context: TenantContext,
        object_key: str,
    ) -> bool:
        tenant = require_tenant_context(context)
        if not object_key.startswith(f"tenants/{tenant.company_id}/"):
            raise PermissionError("object key is outside the tenant scope")
        self.intents = [intent for intent in self.intents if intent.object_key != object_key]
        return all(intent.object_key != object_key for intent in self.intents)

    def healthcheck(self) -> None:
        return None


class InMemoryQueue:
    def __init__(self) -> None:
        self.messages: list[QueueMessage] = []
        self._available: list[QueueDelivery] = []
        self._inflight: dict[str, QueueDelivery] = {}

    def publish(
        self,
        context: TenantContext,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> None:
        tenant = require_tenant_context(context)
        self.messages.append(
            QueueMessage(
                company_id=tenant.company_id,
                event_type=event_type,
                payload=deepcopy(dict(payload)),
                trace_id=tenant.trace_id,
            )
        )
        event_id = UUID(str(payload.get("event_id", uuid4())))
        occurred_at_raw = payload.get("occurred_at")
        occurred_at = (
            datetime.fromisoformat(str(occurred_at_raw))
            if occurred_at_raw is not None
            else datetime.now(UTC)
        )
        event_payload = payload.get("payload", payload)
        if not isinstance(event_payload, Mapping):
            raise TypeError("queue event payload must be an object")
        self._available.append(
            QueueDelivery(
                receipt_handle=str(uuid4()),
                event_id=event_id,
                event_version=int(payload.get("event_version", 1)),
                idempotency_key=str(payload.get("idempotency_key", event_id)),
                company_id=tenant.company_id,
                aggregate_type=str(payload.get("aggregate_type", "event")),
                aggregate_id=UUID(str(payload.get("aggregate_id", event_id))),
                aggregate_version=int(payload.get("aggregate_version", 1)),
                event_type=event_type,
                payload=deepcopy(dict(event_payload)),
                trace_id=tenant.trace_id,
                occurred_at=occurred_at,
            )
        )

    def receive(self, *, max_messages: int) -> tuple[QueueDelivery, ...]:
        deliveries = tuple(self._available[:max_messages])
        del self._available[:max_messages]
        for delivery in deliveries:
            self._inflight[delivery.receipt_handle] = delivery
        return deliveries

    def acknowledge(self, receipt_handle: str) -> None:
        self._inflight.pop(receipt_handle, None)

    def retry(self, receipt_handle: str) -> None:
        delivery = self._inflight.pop(receipt_handle)
        self._available.append(
            QueueDelivery(
                receipt_handle=str(uuid4()),
                event_id=delivery.event_id,
                event_version=delivery.event_version,
                idempotency_key=delivery.idempotency_key,
                company_id=delivery.company_id,
                aggregate_type=delivery.aggregate_type,
                aggregate_id=delivery.aggregate_id,
                aggregate_version=delivery.aggregate_version,
                event_type=delivery.event_type,
                payload=delivery.payload,
                trace_id=delivery.trace_id,
                occurred_at=delivery.occurred_at,
            )
        )

    def redeliver_all(self) -> None:
        self._available.extend(
            QueueDelivery(
                receipt_handle=str(uuid4()),
                event_id=delivery.event_id,
                event_version=delivery.event_version,
                idempotency_key=delivery.idempotency_key,
                company_id=delivery.company_id,
                aggregate_type=delivery.aggregate_type,
                aggregate_id=delivery.aggregate_id,
                aggregate_version=delivery.aggregate_version,
                event_type=delivery.event_type,
                payload=delivery.payload,
                trace_id=delivery.trace_id,
                occurred_at=delivery.occurred_at,
            )
            for delivery in tuple(self._available)
        )

    def healthcheck(self) -> None:
        return None

    def approximate_depth(self) -> int:
        return len(self._available) + len(self._inflight)


class StaticSearch:
    def __init__(self, hits: Sequence[SearchHit]) -> None:
        self._hits = tuple(hits)
        self.calls: list[tuple[UUID, str, int]] = []

    def search(
        self,
        context: TenantContext,
        query: str,
        *,
        limit: int,
    ) -> tuple[SearchHit, ...]:
        tenant = require_tenant_context(context)
        self.calls.append((tenant.company_id, query, limit))
        scoped = (hit for hit in self._hits if hit.company_id == tenant.company_id)
        return tuple(sorted(scoped, key=lambda hit: hit.score, reverse=True))[:limit]


class DeterministicAIModel:
    def __init__(self, response: Mapping[str, Any]) -> None:
        self._response = dict(response)
        self.calls: list[tuple[UUID, Mapping[str, Any]]] = []

    def generate(
        self,
        context: TenantContext,
        model_input: Mapping[str, Any],
    ) -> dict[str, Any]:
        tenant = require_tenant_context(context)
        self.calls.append((tenant.company_id, deepcopy(dict(model_input))))
        return deepcopy(self._response)


class DeterministicSpeechToText:
    def __init__(self, response: Mapping[str, Any]) -> None:
        self._response = dict(response)
        self.calls: list[SpeechToTextCall] = []

    def transcribe(
        self,
        context: TenantContext,
        audio: bytes,
        *,
        sample_rate_hz: int,
    ) -> dict[str, Any]:
        tenant = require_tenant_context(context)
        self.calls.append(
            SpeechToTextCall(
                company_id=tenant.company_id,
                byte_length=len(audio),
                sample_rate_hz=sample_rate_hz,
            )
        )
        return deepcopy(self._response)


class DeterministicTextToSpeech:
    def __init__(self, response: Mapping[str, Any]) -> None:
        self._response = dict(response)
        self.calls: list[TextToSpeechCall] = []

    def synthesize(
        self,
        context: TenantContext,
        text: str,
        *,
        voice_id: str,
    ) -> dict[str, Any]:
        tenant = require_tenant_context(context)
        self.calls.append(
            TextToSpeechCall(
                company_id=tenant.company_id,
                text_sha256=sha256(text.encode("utf-8")).hexdigest(),
                voice_id=voice_id,
            )
        )
        return deepcopy(self._response)


class InMemoryEmailSender:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []
        self._ids = _DeterministicIds()

    def send_template(
        self,
        context: TenantContext,
        template_id: str,
        recipient_ref: UUID,
        recipient_address: str,
        template_data: Mapping[str, Any],
    ) -> UUID:
        tenant = require_tenant_context(context)
        message = EmailMessage(
            message_id=self._ids.next(),
            company_id=tenant.company_id,
            template_id=template_id,
            recipient_ref=recipient_ref,
            recipient_address_sha256=sha256(
                recipient_address.strip().casefold().encode("utf-8")
            ).hexdigest(),
            template_data=deepcopy(dict(template_data)),
        )
        self.messages.append(message)
        return message.message_id
