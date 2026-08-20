from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from interview_evidence.interview_engine.application.idempotency import IdempotencyStore
from interview_evidence.interview_engine.domain.turn import (
    RecordingChunk,
    RecordingUploadStatus,
)
from interview_evidence.interview_engine.repositories.postgres import InterviewRepository
from interview_evidence.shared.aws_clients.ports import ObjectStorage
from interview_evidence.shared.tenant import TenantContext


class RecordingUploadUnavailable(RuntimeError):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class RecordingIntegrityError(ValueError):
    pass


class RecordingObjectVerifier(Protocol):
    def verify(
        self,
        context: TenantContext,
        *,
        object_key: str,
        expected_byte_size: int,
        expected_sha256: str,
    ) -> bool: ...


class VerifiableObjectStorage(Protocol):
    def verify_uploaded_object(
        self,
        context: TenantContext,
        *,
        object_key: str,
        expected_byte_size: int,
        expected_sha256: str,
    ) -> bool: ...


class StorageRecordingVerifier:
    """Confirm a recording chunk against the bucket it was uploaded to."""

    def __init__(self, storage: VerifiableObjectStorage) -> None:
        self._storage = storage

    def verify(
        self,
        context: TenantContext,
        *,
        object_key: str,
        expected_byte_size: int,
        expected_sha256: str,
    ) -> bool:
        return self._storage.verify_uploaded_object(
            context,
            object_key=object_key,
            expected_byte_size=expected_byte_size,
            expected_sha256=expected_sha256,
        )


@dataclass(frozen=True, slots=True)
class RecordingUploadIntent:
    object_id: UUID
    session_id: UUID
    sequence: int
    byte_size: int
    content_hash: str
    session_start_ms: int
    session_end_ms: int
    idempotency_key: str
    occurred_at: datetime
    #: Where the browser actually PUTs the chunk. Carried from the storage adapter rather
    #: than rebuilt by the route, which is how recordings previously went to a host that
    #: does not exist. The object key is kept so verification can find what was uploaded.
    object_key: str = ""
    method: str = "PUT"
    url: str = ""
    required_headers: dict[str, str] = field(default_factory=dict)
    expires_at: datetime | None = None


class RecordingService:
    def __init__(
        self,
        storage: ObjectStorage,
        *,
        repository: InterviewRepository | None = None,
        idempotency: IdempotencyStore | None = None,
        verifier: RecordingObjectVerifier | None = None,
        upload_ttl: timedelta = timedelta(minutes=15),
    ) -> None:
        self._storage = storage
        self._repository = repository
        self._idempotency = idempotency
        self._verifier = verifier
        self._upload_ttl = upload_ttl

    def issue_upload_intent(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        sequence: int,
        byte_size: int,
        content_hash: str,
        session_start_ms: int,
        session_end_ms: int,
        idempotency_key: str,
        occurred_at: datetime,
    ) -> RecordingUploadIntent:
        if session_end_ms <= session_start_ms:
            raise ValueError("recording range must be increasing")
        namespace = f"sessions/{session_id}/recording/chunks/{sequence:06d}"
        try:
            intent = self._storage.create_upload_intent(
                context,
                namespace,
                byte_size,
                content_hash,
            )
        except Exception as error:
            raise RecordingUploadUnavailable(
                "recording upload is temporarily unavailable",
                retryable=True,
            ) from error
        return RecordingUploadIntent(
            object_id=intent.object_id,
            session_id=session_id,
            sequence=sequence,
            byte_size=byte_size,
            content_hash=content_hash,
            session_start_ms=session_start_ms,
            session_end_ms=session_end_ms,
            idempotency_key=idempotency_key,
            occurred_at=occurred_at,
            object_key=intent.object_key,
            url=intent.url,
            required_headers=dict(intent.required_headers),
            expires_at=occurred_at + self._upload_ttl,
        )

    def verify_uploaded_chunk(
        self,
        context: TenantContext,
        *,
        intent: RecordingUploadIntent,
    ) -> RecordingChunk:
        if self._repository is None or self._idempotency is None or self._verifier is None:
            raise RuntimeError("recording verification dependencies are not configured")
        return self._idempotency.execute(
            context,
            session_id=intent.session_id,
            operation="recording.verify",
            idempotency_key=intent.idempotency_key,
            request_payload={
                "object_id": str(intent.object_id),
                "sequence": intent.sequence,
                "byte_size": intent.byte_size,
                "content_hash": intent.content_hash,
                "session_start_ms": intent.session_start_ms,
                "session_end_ms": intent.session_end_ms,
            },
            execute=lambda: self._verify_once(context, intent),
            occurred_at=intent.occurred_at,
        )

    def _verify_once(
        self,
        context: TenantContext,
        intent: RecordingUploadIntent,
    ) -> RecordingChunk:
        assert self._repository is not None
        assert self._verifier is not None
        if not self._verifier.verify(
            context,
            object_key=intent.object_key,
            expected_byte_size=intent.byte_size,
            expected_sha256=intent.content_hash,
        ):
            raise RecordingIntegrityError("recording object metadata did not match intent")
        existing_chunks = self._repository.list_recording_chunks(context, intent.session_id)
        session_start_ms = intent.session_start_ms
        previous = max(
            (chunk for chunk in existing_chunks if chunk.sequence < intent.sequence),
            key=lambda chunk: chunk.sequence,
            default=None,
        )
        if previous is not None and session_start_ms < previous.session_end_ms:
            if (
                previous.sequence != intent.sequence - 1
                or intent.session_end_ms <= previous.session_end_ms
            ):
                raise RecordingIntegrityError("recording chunk time range overlaps")
            session_start_ms = previous.session_end_ms
        for existing in existing_chunks:
            overlaps = (
                session_start_ms < existing.session_end_ms
                and intent.session_end_ms > existing.session_start_ms
            )
            if overlaps and existing.sequence != intent.sequence:
                raise RecordingIntegrityError("recording chunk time range overlaps")
        chunk = RecordingChunk(
            recording_chunk_id=intent.object_id,
            company_id=context.company_id,
            interview_session_id=intent.session_id,
            sequence=intent.sequence,
            # The key the object was actually uploaded to. A key composed here instead
            # pointed the manifest and the review player at something that was never
            # written.
            object_key=intent.object_key,
            content_hash=intent.content_hash,
            byte_size=intent.byte_size,
            session_start_ms=session_start_ms,
            session_end_ms=intent.session_end_ms,
            upload_status=RecordingUploadStatus.VERIFIED,
            idempotency_key=intent.idempotency_key,
            created_at=intent.occurred_at,
        )
        return self._repository.save_recording_chunk(context, chunk)
