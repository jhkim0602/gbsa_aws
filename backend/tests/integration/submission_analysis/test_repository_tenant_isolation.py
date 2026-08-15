from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.domain.submission import (
    SourceType,
    Submission,
)
from interview_evidence.submission_analysis.repositories.postgres import (
    Base,
    SqlAlchemySubmissionRepository,
    TenantScopedSubmissionNotFound,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

COMPANY_A = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_B = UUID("00000000-0000-7000-8000-000000000002")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000003")
SUBMISSION_ID = UUID("00000000-0000-7000-8000-000000000004")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def context(company_id: UUID) -> TenantContext:
    return TenantContext(
        company_id=company_id,
        actor_type=ActorType.SYSTEM,
        actor_id=APPLICANT_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000005"),
        trace_id="lane-b-repository-isolation",
    )


def test_sqlalchemy_repository_scopes_submission_and_protected_git_inputs() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repository = SqlAlchemySubmissionRepository(session)
        repository.save_submission(
            context(COMPANY_A),
            Submission(
                submission_id=SUBMISSION_ID,
                company_id=COMPANY_A,
                invitation_id=UUID("00000000-0000-7000-8000-000000000006"),
                applicant_id=APPLICANT_ID,
                source_type=SourceType.PUBLIC_GIT,
                source_uri="https://github.com/example/candidate-project",
                candidate_identity_inputs={
                    "claimed_names": ("홍길동",),
                    "claimed_emails": ("candidate@example.com",),
                },
                created_at=NOW,
            ),
        )

        restored = repository.get_submission(context(COMPANY_A), SUBMISSION_ID)
        assert restored.candidate_identity_inputs == {
            "claimed_names": ("홍길동",),
            "claimed_emails": ("candidate@example.com",),
        }
        with pytest.raises(TenantScopedSubmissionNotFound):
            repository.get_submission(context(COMPANY_B), SUBMISSION_ID)
