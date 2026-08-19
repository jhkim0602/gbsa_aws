from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any, Protocol
from uuid import UUID

from interview_evidence.shared.email_templates import RenderedEmail
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
class TextEmbeddingCall:
    company_id: UUID
    text_sha256: str
    dimensions: int


@dataclass(frozen=True, slots=True)
class EmailMessage:
    message_id: UUID
    company_id: UUID
    template_id: str
    recipient_ref: UUID
    recipient_address_sha256: str
    template_data: Mapping[str, Any]
    rendered: RenderedEmail


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


class TextEmbedder(Protocol):
    model_id: str

    def embed(
        self,
        context: TenantContext,
        text: str,
        *,
        dimensions: int = 1024,
    ) -> tuple[float, ...]: ...


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
        rendered: RenderedEmail,
    ) -> UUID: ...


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


class StaticTextEmbedder:
    model_id = "test-static-embedding"

    def __init__(self, vector: Sequence[float]) -> None:
        self._vector = tuple(float(value) for value in vector)
        self.calls: list[TextEmbeddingCall] = []

    def embed(
        self,
        context: TenantContext,
        text: str,
        *,
        dimensions: int = 1024,
    ) -> tuple[float, ...]:
        tenant = require_tenant_context(context)
        if not text.strip():
            raise ValueError("embedding text must not be blank")
        if dimensions != len(self._vector):
            raise ValueError("configured embedding dimensions do not match requested dimensions")
        self.calls.append(
            TextEmbeddingCall(
                company_id=tenant.company_id,
                text_sha256=sha256(text.encode("utf-8")).hexdigest(),
                dimensions=dimensions,
            )
        )
        return self._vector
