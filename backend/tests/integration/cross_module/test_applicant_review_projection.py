from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.interview_engine.application.deletion_targets import (
    InMemoryInterviewTargetDeleter,
    InterviewDeletionTargets,
)
from interview_evidence.interview_engine.application.public import InterviewEnginePublic
from interview_evidence.interview_engine.domain.session import (
    InterviewSession,
    InterviewSessionState,
)
from interview_evidence.interview_engine.repositories.postgres import (
    InMemoryInterviewRepository,
)
from interview_evidence.shared.tenant import ActorType, TenantContext

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
OTHER_COMPANY_ID = UUID("00000000-0000-7000-8000-000000000099")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000010")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000011")
NOW = datetime(2026, 8, 16, 9, 0, tzinfo=UTC)


def _context(company_id: UUID) -> TenantContext:
    return TenantContext(
        company_id=company_id,
        actor_type=ActorType.COMPANY_USER,
        actor_id=UUID("00000000-0000-7000-8000-000000000002"),
        request_id=UUID("00000000-0000-7000-8000-000000000003"),
        trace_id="applicant-review-projection",
    )


def test_public_boundary_resolves_a_session_by_invitation_without_cross_tenant_leakage() -> None:
    repository = InMemoryInterviewRepository()
    context = _context(COMPANY_ID)
    repository.save_session(
        context,
        InterviewSession(
            interview_session_id=SESSION_ID,
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=UUID("00000000-0000-7000-8000-000000000012"),
            interview_strategy_id=UUID("00000000-0000-7000-8000-000000000013"),
            competency_model_version_id=UUID("00000000-0000-7000-8000-000000000014"),
            state=InterviewSessionState.REVIEWABLE,
            created_at=NOW,
            started_at=NOW,
            completed_at=NOW,
        ),
    )
    public = InterviewEnginePublic(
        repository=repository,
        deletion_targets=InterviewDeletionTargets(repository),
        target_deleter=InMemoryInterviewTargetDeleter(repository=repository),
    )

    snapshot = public.find_session_for_invitation(
        context,
        invitation_id=INVITATION_ID,
    )

    assert snapshot is not None
    assert snapshot.interview_session_id == SESSION_ID
    assert (
        public.find_session_for_invitation(
            _context(OTHER_COMPANY_ID),
            invitation_id=INVITATION_ID,
        )
        is None
    )
