from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from interview_evidence.company_management.api import create_lane_a_app
from interview_evidence.company_management.repositories.postgres import (
    InMemoryCompanyRepository,
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

EXPECTED_OPERATIONS = {
    "getCurrentCompanyUser",
    "listPositions",
    "createPosition",
    "createCompetencyModelVersion",
    "publishCompetencyModelVersion",
    "createCampaign",
    "publishCampaign",
    "listInvitations",
    "createInvitations",
    "exchangeApplicantInvitationToken",
    "verifyApplicantIdentity",
    "recordApplicantConsent",
}


def test_lane_a_exposes_the_frozen_http_operations() -> None:
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
        repository=InMemoryCompanyRepository(),
        audit=InMemoryAuditAppender(),
        clock=FrozenClock(NOW),
    )

    operations = {
        operation["operationId"]
        for path in app.openapi()["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    }
    assert operations >= EXPECTED_OPERATIONS


@pytest.mark.asyncio
async def test_position_contract_rejects_unknown_fields_and_returns_contract_shape() -> None:
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
        repository=InMemoryCompanyRepository(),
        audit=InMemoryAuditAppender(),
        clock=FrozenClock(NOW),
    )
    headers = {
        "Authorization": "Bearer company-token",
        "Idempotency-Key": "position-create-0001",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://testserver",
    ) as client:
        invalid = await client.post(
            "/v1/positions",
            headers=headers,
            json={
                "title": "백엔드 개발자",
                "description": "서비스 개발",
                "company_id": str(COMPANY_ID),
            },
        )
        assert invalid.status_code == 422

        created = await client.post(
            "/v1/positions",
            headers=headers,
            json={"title": "백엔드 개발자", "description": "서비스 개발"},
        )
    assert created.status_code == 201
    assert set(created.json()) == {
        "position_id",
        "title",
        "description",
        "status",
        "row_version",
        "created_at",
    }
