from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, TypeVar, cast
from uuid import UUID

from interview_evidence.interview_engine.application.recording_service import RecordingService
from interview_evidence.interview_engine.domain.turn import RecordingChunk
from interview_evidence.shared.aws_clients.ports import UploadIntent
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 20, 8, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
ResultT = TypeVar("ResultT")


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._results: dict[tuple[UUID, str, str], object] = {}

    def execute(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        operation: str,
        idempotency_key: str,
        request_payload: Mapping[str, Any],
        execute: Callable[[], ResultT],
        occurred_at: datetime,
    ) -> ResultT:
        del context, request_payload, occurred_at
        key = (session_id, operation, idempotency_key)
        if key not in self._results:
            self._results[key] = execute()
        return cast(ResultT, self._results[key])


class StaticVerifier:
    def verify(
        self,
        _context: TenantContext,
        *,
        object_key: str,
        expected_byte_size: int,
        expected_sha256: str,
    ) -> bool:
        del object_key, expected_byte_size, expected_sha256
        return True


class RecordingRepository:
    def __init__(self) -> None:
        self._chunks: list[RecordingChunk] = []

    def list_recording_chunks(
        self, _context: TenantContext, session_id: UUID
    ) -> tuple[RecordingChunk, ...]:
        return tuple(chunk for chunk in self._chunks if chunk.interview_session_id == session_id)

    def save_recording_chunk(
        self, _context: TenantContext, chunk: RecordingChunk
    ) -> RecordingChunk:
        self._chunks.append(chunk)
        return chunk


class StaticObjectStorage:
    def __init__(self) -> None:
        self._sequence = 0

    def create_upload_intent(
        self,
        context: TenantContext,
        namespace: str,
        byte_size: int,
        sha256: str,
    ) -> UploadIntent:
        self._sequence += 1
        return UploadIntent(
            object_id=UUID(f"00000000-0000-7000-8000-{self._sequence:012d}"),
            company_id=context.company_id,
            namespace=namespace,
            byte_size=byte_size,
            sha256=sha256,
            object_key=f"test/{namespace}",
            url=f"http://storage.test/{namespace}",
            required_headers={},
        )


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=UUID("00000000-0000-7000-8000-000000000003"),
        request_id=UUID("00000000-0000-7000-8000-000000000004"),
        trace_id="trace-recording-service",
    )


def test_adjacent_chunk_overlap_is_trimmed_to_the_previous_chunk_end() -> None:
    repository = RecordingRepository()
    service = RecordingService(
        cast(Any, StaticObjectStorage()),
        repository=cast(Any, repository),
        idempotency=InMemoryIdempotencyStore(),
        verifier=StaticVerifier(),
    )
    first_intent = service.issue_upload_intent(
        context(),
        session_id=SESSION_ID,
        sequence=1,
        byte_size=1024,
        content_hash="a" * 64,
        session_start_ms=12,
        session_end_ms=2012,
        idempotency_key="recording-upload-0001",
        occurred_at=NOW,
    )
    overlapping_final_intent = service.issue_upload_intent(
        context(),
        session_id=SESSION_ID,
        sequence=2,
        byte_size=512,
        content_hash="b" * 64,
        session_start_ms=203,
        session_end_ms=2203,
        idempotency_key="recording-upload-0002",
        occurred_at=NOW,
    )

    service.verify_uploaded_chunk(context(), intent=first_intent)
    final_chunk = service.verify_uploaded_chunk(context(), intent=overlapping_final_intent)

    assert final_chunk.session_start_ms == 2012
    assert final_chunk.session_end_ms == 2203
