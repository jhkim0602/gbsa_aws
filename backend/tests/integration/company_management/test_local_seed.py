from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.company_management.api import (
    ensure_company_principal,
    ensure_local_demo_recruiting,
)
from interview_evidence.company_management.repositories.postgres import (
    Base,
    CompanyRow,
    CompanyUserRow,
    CompetencyModelVersionRow,
    InvitationRow,
    PositionRow,
)
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_USER_ID = UUID("00000000-0000-7000-8000-000000000002")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def test_local_company_principal_seed_is_idempotent() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        for _ in range(2):
            ensure_company_principal(
                session,
                company_id=COMPANY_ID,
                company_user_id=COMPANY_USER_ID,
                company_name="Local Interview Evidence Company",
                identity_subject="local-production-company-user",
                email_normalized="local-company@example.test",
                now=NOW,
            )
        session.commit()

        assert session.scalar(select(func.count()).select_from(CompanyRow)) == 1
        assert session.scalar(select(func.count()).select_from(CompanyUserRow)) == 1
        company_user = session.get(CompanyUserRow, COMPANY_USER_ID)
        assert company_user is not None
        assert company_user.company_id == COMPANY_ID


def test_local_recruiting_demo_seed_is_idempotent_and_status_diverse() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        ensure_company_principal(
            session,
            company_id=COMPANY_ID,
            company_user_id=COMPANY_USER_ID,
            company_name="Local Interview Evidence Company",
            identity_subject="local-production-company-user",
            email_normalized="local-company@example.test",
            now=NOW,
        )
        for _ in range(2):
            demo_position_id = ensure_local_demo_recruiting(
                session,
                company_id=COMPANY_ID,
                company_user_id=COMPANY_USER_ID,
                now=NOW,
            )
        session.commit()

        assert session.scalar(select(func.count()).select_from(PositionRow)) == 1
        assert session.scalar(select(func.count()).select_from(CompetencyModelVersionRow)) == 1
        invitations = session.scalars(
            select(InvitationRow).where(InvitationRow.position_id == demo_position_id)
        ).all()
        assert len(invitations) == 5
        assert {invitation.status for invitation in invitations} >= {
            "invited",
            "analyzing",
            "ready",
            "completed",
            "reviewed",
        }
