from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, Protocol
from uuid import UUID, uuid4

from interview_evidence.shared.email_templates import RenderedEmail
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
    receive_count: int = 1


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

    def read_object(self, context: TenantContext, object_key: str) -> bytes: ...


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

    def extend_visibility(self, receipt_handle: str, timeout_seconds: int) -> None: ...

    def healthcheck(self) -> None: ...

    def approximate_depth(self) -> int: ...


class InMemoryObjectStorage:
    def __init__(self) -> None:
        self.intents: list[UploadIntent] = []
        #: Bytes written through `write_object`, keyed the same way S3 keys them. The
        #: recording assembler reads its chunks back out of the bucket, so a store that
        #: only records intents cannot stand in for one in the local runtime.
        self.objects: dict[str, bytes] = {}
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

    def read_object(self, context: TenantContext, object_key: str) -> bytes:
        self._assert_scope(context, object_key)
        return self.objects[object_key]

    def write_object(
        self,
        context: TenantContext,
        *,
        object_key: str,
        body: bytes,
        content_type: str,
    ) -> None:
        self._assert_scope(context, object_key)
        self.objects[object_key] = body

    def create_playback_url(
        self,
        context: TenantContext,
        *,
        object_key: str,
        expires_in_seconds: int,
    ) -> str:
        """No server signs this, so it names the object rather than pretending to be S3.

        The in-memory runtime has no HTTP endpoint that could serve the bytes. A URL for a
        host nobody serves would fail in the reviewer's browser instead of at the boundary,
        so this stays an explicit local scheme that a caller can recognise.
        """
        self._assert_scope(context, object_key)
        if expires_in_seconds < 1:
            raise ValueError("playback URL lifetime must be positive")
        return f"memory://recordings/{object_key}"

    def _assert_scope(self, context: TenantContext, object_key: str) -> None:
        tenant = require_tenant_context(context)
        if not object_key.startswith(f"tenants/{tenant.company_id}/"):
            raise PermissionError("object key is outside the tenant scope")

    def verify_uploaded_object(
        self,
        context: TenantContext,
        *,
        object_key: str,
        expected_byte_size: int,
        expected_sha256: str,
    ) -> bool:
        """Match the S3 adapter: an object is verified when an intent declared it.

        The intent, not the stored bytes, is the record that the upload was authorized with
        this size and digest -- the applicant uploads straight to S3, so an object can exist
        here without this process ever having seen it.
        """
        tenant = require_tenant_context(context)
        if not object_key.startswith(f"tenants/{tenant.company_id}/"):
            raise PermissionError("object key is outside the tenant scope")
        return any(
            intent.object_key == object_key
            and intent.byte_size == expected_byte_size
            and intent.sha256 == expected_sha256
            for intent in self.intents
        )

    def delete_and_verify_object(
        self,
        context: TenantContext,
        object_key: str,
    ) -> bool:
        self._assert_scope(context, object_key)
        self.intents = [intent for intent in self.intents if intent.object_key != object_key]
        self.objects.pop(object_key, None)
        return all(intent.object_key != object_key for intent in self.intents)

    def healthcheck(self) -> None:
        return None


class InMemoryQueue:
    visibility_timeout_seconds = 300

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
            replace(
                delivery,
                receipt_handle=str(uuid4()),
                receive_count=delivery.receive_count + 1,
            )
        )

    def extend_visibility(self, receipt_handle: str, timeout_seconds: int) -> None:
        if receipt_handle not in self._inflight:
            raise LookupError("queue delivery is not in flight")
        if timeout_seconds < 1:
            raise ValueError("visibility timeout must be positive")

    def redeliver_all(self) -> None:
        self._available.extend(
            replace(
                delivery,
                receipt_handle=str(uuid4()),
                receive_count=delivery.receive_count + 1,
            )
            for delivery in tuple(self._available)
        )

    def healthcheck(self) -> None:
        return None

    def approximate_depth(self) -> int:
        return len(self._available) + len(self._inflight)


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
    embedding_version: str

    def embed(
        self,
        context: TenantContext,
        text: str,
        *,
        dimensions: int = 1024,
    ) -> tuple[float, ...]: ...


class EmbeddingProviderError(RuntimeError):
    """A transient managed embedding-provider failure safe to retry."""


class CachingTextEmbedder:
    """Bound repeated embeddings by model, dimensions, and normalized text hash.

    A worker processes several submissions against the same criterion axis and may see
    the same code excerpt more than once across retries. Keeping only vectors (never the
    source text) makes those repeats local cache hits instead of duplicate provider calls.
    """

    def __init__(self, delegate: TextEmbedder, *, max_entries: int = 2_048) -> None:
        if max_entries < 1:
            raise ValueError("embedding cache size must be positive")
        self._delegate = delegate
        self._max_entries = max_entries
        self._vectors: OrderedDict[tuple[str, int, str], tuple[float, ...]] = OrderedDict()
        self.model_id = delegate.model_id
        self.embedding_version = delegate.embedding_version

    def embed(
        self,
        context: TenantContext,
        text: str,
        *,
        dimensions: int = 1024,
    ) -> tuple[float, ...]:
        return self.embed_many(context, (text,), dimensions=dimensions)[0]

    def embed_many(
        self,
        context: TenantContext,
        texts: Sequence[str],
        *,
        dimensions: int = 1024,
    ) -> tuple[tuple[float, ...], ...]:
        require_tenant_context(context)
        normalized_texts = tuple(text.strip() for text in texts)
        if not normalized_texts or any(not text for text in normalized_texts):
            raise ValueError("embedding text must not be blank")
        keys = tuple(
            (
                f"{self.model_id}:{self.embedding_version}",
                dimensions,
                sha256(text.encode("utf-8")).hexdigest(),
            )
            for text in normalized_texts
        )
        missing: OrderedDict[tuple[str, int, str], str] = OrderedDict()
        for key, text in zip(keys, normalized_texts, strict=True):
            if key not in self._vectors:
                missing.setdefault(key, text)
        if missing:
            batch_embed = getattr(self._delegate, "embed_many", None)
            missing_texts = tuple(missing.values())
            generated = (
                tuple(batch_embed(context, missing_texts, dimensions=dimensions))
                if callable(batch_embed)
                else tuple(
                    self._delegate.embed(context, text, dimensions=dimensions)
                    for text in missing_texts
                )
            )
            if len(generated) != len(missing):
                raise EmbeddingProviderError("embedding response count is invalid")
            for key, vector in zip(missing, generated, strict=True):
                self._vectors[key] = vector
                self._vectors.move_to_end(key)
                if len(self._vectors) > self._max_entries:
                    self._vectors.popitem(last=False)
        for key in keys:
            self._vectors.move_to_end(key)
        return tuple(self._vectors[key] for key in keys)


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


class StaticTextEmbedder:
    model_id = "test-static-embedding"
    embedding_version = "test-static-v1"

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
