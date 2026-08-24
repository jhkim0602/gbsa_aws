from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.shared.aws_clients.ports import InMemoryObjectStorage
from interview_evidence.shared.idempotency import InMemoryResourceIdempotencyStore
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.messaging.outbox import InMemoryOutbox
from interview_evidence.shared.security.principals import ApplicantPrincipal
from interview_evidence.shared.submission_materials import SubmissionMaterialType
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.shared.uploads import InMemoryUploadIntentStore
from interview_evidence.submission_analysis.adapters.object_storage import (
    ScopedSubmissionStorage,
)
from interview_evidence.submission_analysis.application.submission_service import (
    SubmissionService,
)
from interview_evidence.submission_analysis.application.submission_validator import (
    SubmissionValidator,
)
from interview_evidence.submission_analysis.domain.submission import SourceType
from interview_evidence.submission_analysis.repositories.postgres import (
    InMemorySubmissionRepository,
)

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
FIRST_INVITATION_ID = UUID("00000000-0000-7000-8000-000000000101")
SECOND_INVITATION_ID = UUID("00000000-0000-7000-8000-000000000102")
FIRST_APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000201")
SECOND_APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000202")
NOW = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)


def _principal(invitation_id: UUID, applicant_id: UUID) -> ApplicantPrincipal:
    return ApplicantPrincipal(
        company_id=COMPANY_ID,
        invitation_id=invitation_id,
        applicant_id=applicant_id,
        session_id=UUID(int=applicant_id.int + 100),
    )


def _context(applicant_id: UUID) -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.APPLICANT,
        actor_id=applicant_id,
        request_id=UUID(int=applicant_id.int + 200),
        trace_id=f"submission-{applicant_id}",
    )


def test_identical_file_key_is_scoped_to_each_invitation() -> None:
    clock = FrozenClock(NOW)
    repository = InMemorySubmissionRepository()
    service = SubmissionService(
        repository,
        ScopedSubmissionStorage(
            InMemoryObjectStorage(),
            clock=clock,
            intent_store=InMemoryUploadIntentStore(),
        ),
        SubmissionValidator(),
        InMemoryOutbox(),
        clock,
        InMemoryResourceIdempotencyStore(),
    )
    first_principal = _principal(FIRST_INVITATION_ID, FIRST_APPLICANT_ID)
    second_principal = _principal(SECOND_INVITATION_ID, SECOND_APPLICANT_ID)
    first_context = _context(FIRST_APPLICANT_ID)
    second_context = _context(SECOND_APPLICANT_ID)

    first_intent = service.create_upload_intent(
        first_context,
        first_principal,
        source_type=SourceType.RESUME,
        filename="resume.pdf",
        media_type="application/pdf",
        byte_size=2048,
        sha256="a" * 64,
    )
    second_intent = service.create_upload_intent(
        second_context,
        second_principal,
        source_type=SourceType.RESUME,
        filename="resume.pdf",
        media_type="application/pdf",
        byte_size=2048,
        sha256="a" * 64,
    )
    shared_key = "submission-resume-identical-document"

    first = service.register_file_submission(
        first_context,
        first_principal,
        material_type=SubmissionMaterialType.RESUME,
        source_type=SourceType.RESUME,
        upload_id=first_intent.upload_id,
        idempotency_key=shared_key,
    )
    second = service.register_file_submission(
        second_context,
        second_principal,
        material_type=SubmissionMaterialType.RESUME,
        source_type=SourceType.RESUME,
        upload_id=second_intent.upload_id,
        idempotency_key=shared_key,
    )
    repeated = service.register_file_submission(
        second_context,
        second_principal,
        material_type=SubmissionMaterialType.RESUME,
        source_type=SourceType.RESUME,
        upload_id=second_intent.upload_id,
        idempotency_key=shared_key,
    )

    assert first.submission_id != second.submission_id
    assert first.invitation_id == FIRST_INVITATION_ID
    assert second.invitation_id == SECOND_INVITATION_ID
    assert repeated.submission_id == second.submission_id
