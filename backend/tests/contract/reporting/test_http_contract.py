from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.reporting.api import create_lane_d_app
from interview_evidence.reporting.repositories.postgres import (
    InMemoryReportingRepository,
)
from interview_evidence.shared.audit import InMemoryAuditAppender
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.security.principals import (
    CompanyPrincipal,
    FakePrincipalProvider,
)

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_USER_ID = UUID("00000000-0000-7000-8000-000000000002")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def test_lane_d_exposes_frozen_reporting_and_privacy_operations() -> None:
    app = create_lane_d_app(
        principal_provider=FakePrincipalProvider(
            company_principals={
                "company-token": CompanyPrincipal(
                    company_id=COMPANY_ID,
                    company_user_id=COMPANY_USER_ID,
                    identity_subject="oidc|reviewer",
                )
            }
        ),
        repository=InMemoryReportingRepository(),
        audit=InMemoryAuditAppender(),
        clock=FrozenClock(NOW),
    )
    operations = {
        operation["operationId"]
        for path in app.openapi()["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    }
    assert operations >= {
        "getInterviewReport",
        "getInterviewTimeline",
        "createHumanAssessmentReview",
        "createReviewArtifact",
        "recordHumanFinalDecision",
        "createDeletionRequest",
        "getDeletionRequest",
    }
