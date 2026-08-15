from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.interview_engine.domain.turn import (
    RecordingChunk,
    RecordingUploadStatus,
)
from pydantic import ValidationError


def test_recording_chunk_requires_digest_and_ordered_session_range() -> None:
    chunk = RecordingChunk(
        recording_chunk_id=UUID("00000000-0000-7000-8000-000000000001"),
        company_id=UUID("00000000-0000-7000-8000-000000000002"),
        interview_session_id=UUID("00000000-0000-7000-8000-000000000003"),
        sequence=2,
        object_key="companies/c/sessions/s/recording/chunks/000002",
        content_hash="a" * 64,
        byte_size=1024,
        session_start_ms=2000,
        session_end_ms=4000,
        upload_status=RecordingUploadStatus.VERIFIED,
        idempotency_key="recording-chunk-0002",
        created_at=datetime(2026, 8, 15, 9, 0, tzinfo=UTC),
    )
    assert chunk.sequence == 2

    with pytest.raises(ValidationError):
        chunk.model_copy(update={"session_end_ms": 1000}, deep=True).model_validate(
            chunk.model_copy(update={"session_end_ms": 1000}).model_dump()
        )
