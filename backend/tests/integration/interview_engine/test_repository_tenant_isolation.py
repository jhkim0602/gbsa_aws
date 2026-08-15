from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.interview_engine.domain.session import InterviewSession
from interview_evidence.interview_engine.domain.turn import (
    HotViewSyncStatus,
    SessionCheckpoint,
)
from interview_evidence.interview_engine.repositories.postgres import (
    Base,
    SqlAlchemyInterviewRepository,
    TenantScopedInterviewNotFound,
)
from interview_evidence.shared.tenant import ActorType, TenantContext
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_A = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_B = UUID("00000000-0000-7000-8000-000000000002")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000003")


def context(company_id: UUID) -> TenantContext:
    return TenantContext(
        company_id=company_id,
        actor_type=ActorType.SYSTEM,
        actor_id=UUID("00000000-0000-7000-8000-000000000004"),
        request_id=UUID("00000000-0000-7000-8000-000000000005"),
        trace_id=f"trace-{company_id}",
    )


def interview_session() -> InterviewSession:
    return InterviewSession(
        interview_session_id=SESSION_ID,
        company_id=COMPANY_A,
        invitation_id=UUID("00000000-0000-7000-8000-000000000006"),
        applicant_id=UUID("00000000-0000-7000-8000-000000000007"),
        interview_strategy_id=UUID("00000000-0000-7000-8000-000000000008"),
        competency_model_version_id=UUID("00000000-0000-7000-8000-000000000009"),
        created_at=NOW,
    )


def test_sql_repository_requires_company_scope_for_session_and_checkpoint() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as sql_session:
        repository = SqlAlchemyInterviewRepository(sql_session)
        repository.save_session(context(COMPANY_A), interview_session())
        repository.save_checkpoint(
            context(COMPANY_A),
            SessionCheckpoint(
                checkpoint_id=UUID("00000000-0000-7000-8000-000000000010"),
                company_id=COMPANY_A,
                interview_session_id=SESSION_ID,
                session_sequence=0,
                last_final_turn_id=None,
                last_media_chunk_sequence=0,
                pending_turn_id=None,
                hot_view_sync_status=HotViewSyncStatus.PENDING,
                created_at=NOW,
            ),
        )

        assert repository.get_session(context(COMPANY_A), SESSION_ID).company_id == COMPANY_A
        assert repository.latest_checkpoint(context(COMPANY_A), SESSION_ID) is not None

        with pytest.raises(TenantScopedInterviewNotFound):
            repository.get_session(context(COMPANY_B), SESSION_ID)
        with pytest.raises(TenantScopedInterviewNotFound):
            repository.latest_checkpoint(context(COMPANY_B), SESSION_ID)
