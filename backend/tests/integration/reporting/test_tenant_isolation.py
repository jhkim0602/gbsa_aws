from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.reporting.domain.report import Report, ReportKind, ReportStatus
from interview_evidence.reporting.repositories.postgres import (
    Base,
    SQLAlchemyReportingRepository,
    TenantScopedReportingNotFound,
)
from interview_evidence.shared.tenant import ActorType, TenantContext
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_A = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_B = UUID("00000000-0000-7000-8000-000000000002")
REPORT_ID = UUID("00000000-0000-7000-8000-000000000003")


def context(company_id: UUID) -> TenantContext:
    return TenantContext(
        company_id=company_id,
        actor_type=ActorType.COMPANY_USER,
        actor_id=UUID("00000000-0000-7000-8000-000000000004"),
        request_id=UUID("00000000-0000-7000-8000-000000000005"),
        trace_id="trace-reporting-tenant",
    )


def test_sql_repository_hides_report_from_another_tenant() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repository = SQLAlchemyReportingRepository(session)
        report = Report(
            report_id=REPORT_ID,
            company_id=COMPANY_A,
            interview_session_id=UUID("00000000-0000-7000-8000-000000000006"),
            invitation_id=UUID("00000000-0000-7000-8000-000000000007"),
            version=1,
            kind=ReportKind.AI_ORIGINAL,
            model_version="model-v1",
            prompt_version="prompt-v1",
            config_version="config-v1",
            status=ReportStatus.READY,
            summary="AI 원본",
            created_at=NOW,
        )
        repository.save_report(context(COMPANY_A), report)

        assert repository.get_report(context(COMPANY_A), REPORT_ID) == report
        with pytest.raises(TenantScopedReportingNotFound):
            repository.get_report(context(COMPANY_B), REPORT_ID)
        assert (
            repository.get_report_for_session(context(COMPANY_B), report.interview_session_id)
            is None
        )
