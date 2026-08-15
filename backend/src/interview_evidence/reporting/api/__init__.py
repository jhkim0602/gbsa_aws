from sqlalchemy.orm import Session

from interview_evidence.reporting.api.company_routes import (
    LaneDRuntime,
    create_lane_d_app,
    create_lane_d_runtime,
)
from interview_evidence.reporting.repositories.postgres import (
    ReportingRepository,
    SQLAlchemyReportingRepository,
)


def create_sql_repository(session: Session) -> ReportingRepository:
    return SQLAlchemyReportingRepository(session)


__all__ = [
    "LaneDRuntime",
    "create_lane_d_app",
    "create_lane_d_runtime",
    "create_sql_repository",
]
