from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.interview_engine.application.idempotency import InMemoryIdempotencyStore
from interview_evidence.interview_engine.application.recording_service import (
    RecordingIntegrityError,
    RecordingService,
)
from interview_evidence.interview_engine.domain.session import InterviewSession
from interview_evidence.interview_engine.domain.turn import RecordingUploadStatus
from interview_evidence.interview_engine.repositories.postgres import (
    InMemoryInterviewRepository,
)
from interview_evidence.shared.aws_clients.ports import InMemoryObjectStorage
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=UUID("00000000-0000-7000-8000-000000000003"),
        request_id=UUID("00000000-0000-7000-8000-000000000004"),
        trace_id="trace-recording-verification",
    )


def session() -> InterviewSession:
    return InterviewSession(
        interview_session_id=SESSION_ID,
        company_id=COMPANY_ID,
        invitation_id=UUID("00000000-0000-7000-8000-000000000005"),
        applicant_id=UUID("00000000-0000-7000-8000-000000000006"),
        interview_strategy_id=UUID("00000000-0000-7000-8000-000000000007"),
        competency_model_version_id=UUID("00000000-0000-7000-8000-000000000008"),
        created_at=NOW,
    )


class StaticVerifier:
    def __init__(self, verified: bool) -> None:
        self.verified = verified

    def verify(
        self,
        _context: TenantContext,
        *,
        object_key: str,
        expected_byte_size: int,
        expected_sha256: str,
    ) -> bool:
        del object_key, expected_byte_size, expected_sha256
        return self.verified


def test_verified_upload_creates_one_chunk_for_duplicate_confirmation() -> None:
    repository = InMemoryInterviewRepository()
    repository.save_session(context(), session())
    service = RecordingService(
        InMemoryObjectStorage(),
        repository=repository,
        idempotency=InMemoryIdempotencyStore(),
        verifier=StaticVerifier(True),
    )
    intent = service.issue_upload_intent(
        context(),
        session_id=SESSION_ID,
        sequence=1,
        byte_size=1024,
        content_hash="a" * 64,
        session_start_ms=0,
        session_end_ms=2000,
        idempotency_key="recording-upload-0001",
        occurred_at=NOW,
    )

    first = service.verify_uploaded_chunk(context(), intent=intent)
    duplicate = service.verify_uploaded_chunk(context(), intent=intent)

    assert duplicate == first
    assert first.upload_status is RecordingUploadStatus.VERIFIED
    assert len(repository.list_recording_chunks(context(), SESSION_ID)) == 1


def test_digest_or_size_verification_failure_does_not_create_chunk() -> None:
    repository = InMemoryInterviewRepository()
    repository.save_session(context(), session())
    service = RecordingService(
        InMemoryObjectStorage(),
        repository=repository,
        idempotency=InMemoryIdempotencyStore(),
        verifier=StaticVerifier(False),
    )
    intent = service.issue_upload_intent(
        context(),
        session_id=SESSION_ID,
        sequence=1,
        byte_size=1024,
        content_hash="a" * 64,
        session_start_ms=0,
        session_end_ms=2000,
        idempotency_key="recording-upload-0001",
        occurred_at=NOW,
    )

    with pytest.raises(RecordingIntegrityError):
        service.verify_uploaded_chunk(context(), intent=intent)

    assert repository.list_recording_chunks(context(), SESSION_ID) == ()
