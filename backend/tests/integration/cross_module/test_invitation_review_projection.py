"""The invitation projection must carry Lane D's report status, not just declare the field.

``InvitationView.report_status`` existed for a while with nothing populating it, so the
console's 분석 리포트 열기 button could never light up. Asserted over HTTP rather than on the
boundary alone (``test_d_to_a`` already covers that) because the defect was in the wiring:
the boundary was built and registered, just never handed to the router.
"""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from interview_evidence.company_management.api import create_lane_a_app
from interview_evidence.company_management.domain.company import Position, PositionStatus
from interview_evidence.company_management.domain.criteria import (
    CompetencyModelVersion,
    EvaluationCriterion,
)
from interview_evidence.company_management.domain.hiring import Invitation, InvitationStatus
from interview_evidence.company_management.repositories.postgres import (
    InMemoryCompanyRepository,
)
from interview_evidence.integration.reporting_company import ReportingCompanyBoundary
from interview_evidence.reporting.application.deletion_service import DeletionService
from interview_evidence.reporting.application.public import ReportingPublic
from interview_evidence.reporting.domain.report import Report, ReportKind, ReportStatus
from interview_evidence.reporting.repositories.postgres import InMemoryReportingRepository
from interview_evidence.shared.audit import InMemoryAuditAppender
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.security.principals import (
    CompanyPrincipal,
    FakePrincipalProvider,
)
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 16, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_USER_ID = UUID("00000000-0000-7000-8000-000000000002")
POSITION_ID = UUID("00000000-0000-7000-8000-000000000003")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000004")
REVIEWED_INVITATION_ID = UUID("00000000-0000-7000-8000-000000000005")
PENDING_INVITATION_ID = UUID("00000000-0000-7000-8000-000000000006")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000007")
REPORT_ID = UUID("00000000-0000-7000-8000-000000000008")


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.COMPANY_USER,
        actor_id=COMPANY_USER_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000009"),
        trace_id="invitation-review-projection",
    )


def _invitation(invitation_id: UUID, email: str, status: InvitationStatus) -> Invitation:
    return Invitation(
        invitation_id=invitation_id,
        company_id=COMPANY_ID,
        position_id=POSITION_ID,
        competency_model_version_id=VERSION_ID,
        applicant_id=UUID(int=invitation_id.int + 1),
        applicant_email_normalized=email,
        applicant_display_name=email.split("@")[0],
        token_hash=sha256(f"projection:{invitation_id}".encode()).hexdigest(),
        expires_at=NOW + timedelta(days=7),
        status=status,
        identity_verified_at=NOW,
        last_state_actor_type="system",
    )


@pytest.mark.asyncio
async def test_listed_invitations_carry_the_report_status_of_their_own_report() -> None:
    company_repository = InMemoryCompanyRepository()
    context = _context()
    company_repository.save_position(
        context,
        Position(
            position_id=POSITION_ID,
            company_id=COMPANY_ID,
            title="백엔드 개발자",
            description="리포트 상태 투영을 확인하는 포지션입니다.",
            created_by=COMPANY_USER_ID,
            status=PositionStatus.ACTIVE,
            created_at=NOW,
        ),
    )
    company_repository.save_criterion_version(
        context,
        CompetencyModelVersion.create(
            competency_model_version_id=VERSION_ID,
            company_id=COMPANY_ID,
            position_id=POSITION_ID,
            version_number=1,
            criteria=(
                EvaluationCriterion(
                    criterion_id=UUID("00000000-0000-7000-8000-00000000000a"),
                    code="PROBLEM_SOLVING",
                    name="문제 해결",
                    description="문제를 구조화하는 역량",
                    weight=1,
                    abstain_guidance="근거가 없으면 판단을 유보한다.",
                    required=True,
                ),
            ),
            prohibited_topics=(),
            interview_duration_minutes=30,
            persona_definition={"name": "system"},
        ),
    )
    company_repository.save_invitation(
        context,
        _invitation(REVIEWED_INVITATION_ID, "reviewed@example.test", InvitationStatus.REVIEWED),
    )
    company_repository.save_invitation(
        context,
        _invitation(PENDING_INVITATION_ID, "pending@example.test", InvitationStatus.INVITED),
    )

    reporting_repository = InMemoryReportingRepository()
    reporting_repository.save_report(
        context,
        Report(
            report_id=REPORT_ID,
            company_id=COMPANY_ID,
            interview_session_id=SESSION_ID,
            invitation_id=REVIEWED_INVITATION_ID,
            version=1,
            kind=ReportKind.AI_ORIGINAL,
            model_version="model-v1",
            prompt_version="prompt-v1",
            config_version="report-config-v1",
            status=ReportStatus.READY,
            summary="실제 답변 Evidence에 기반한 원본 리포트",
            created_at=NOW,
        ),
    )
    app = create_lane_a_app(
        principal_provider=FakePrincipalProvider(
            company_principals={
                "company-token": CompanyPrincipal(
                    company_id=COMPANY_ID,
                    company_user_id=COMPANY_USER_ID,
                    identity_subject="oidc|company-user",
                )
            }
        ),
        repository=company_repository,
        audit=InMemoryAuditAppender(),
        clock=FrozenClock(NOW),
        invitation_reviews=ReportingCompanyBoundary(
            ReportingPublic(
                repository=reporting_repository,
                deletion_service=DeletionService(
                    reporting_repository,
                    enumerators=(),
                    executors={},
                ),
            )
        ),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://testserver",
    ) as client:
        response = await client.get(
            f"/v1/positions/{POSITION_ID}/invitations",
            headers={"Authorization": "Bearer company-token"},
        )

    assert response.status_code == 200
    statuses = {item["invitation_id"]: item["report_status"] for item in response.json()["items"]}
    assert statuses[str(REVIEWED_INVITATION_ID)] == "ready"
    # Absent, not "pending": the console distinguishes "no report yet" from a failed one.
    assert statuses[str(PENDING_INVITATION_ID)] is None
