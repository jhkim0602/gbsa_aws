from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from interview_evidence.interview_engine.application.idempotency import InMemoryIdempotencyStore
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
        object_id: UUID,
        expected_byte_size: int,
        expected_sha256: str,
    ) -> bool: ...


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


class RecordingService:
    def __init__(
        self,
        storage: ObjectStorage,
        *,
        repository: InterviewRepository | None = None,
        idempotency: InMemoryIdempotencyStore | None = None,
        verifier: RecordingObjectVerifier | None = None,
    ) -> None:
        self._storage = storage
        self._repository = repository
        self._idempotency = idempotency
        self._verifier = verifier

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
            object_id=intent.object_id,
            expected_byte_size=intent.byte_size,
            expected_sha256=intent.content_hash,
        ):
            raise RecordingIntegrityError("recording object metadata did not match intent")
        for existing in self._repository.list_recording_chunks(context, intent.session_id):
            overlaps = (
                intent.session_start_ms < existing.session_end_ms
                and intent.session_end_ms > existing.session_start_ms
            )
            if overlaps and existing.sequence != intent.sequence:
                raise RecordingIntegrityError("recording chunk time range overlaps")
        chunk = RecordingChunk(
            recording_chunk_id=intent.object_id,
            company_id=context.company_id,
            interview_session_id=intent.session_id,
            sequence=intent.sequence,
            object_key=(
                f"companies/{context.company_id}/sessions/{intent.session_id}/"
                f"recording/chunks/{intent.sequence:06d}"
            ),
            content_hash=intent.content_hash,
            byte_size=intent.byte_size,
            session_start_ms=intent.session_start_ms,
            session_end_ms=intent.session_end_ms,
            upload_status=RecordingUploadStatus.VERIFIED,
            idempotency_key=intent.idempotency_key,
            created_at=intent.occurred_at,
        )
        return self._repository.save_recording_chunk(context, chunk)
