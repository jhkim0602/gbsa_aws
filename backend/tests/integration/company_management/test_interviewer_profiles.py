from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from interview_evidence.company_management.api import create_lane_a_app
from interview_evidence.company_management.repositories.postgres import InMemoryCompanyRepository
from interview_evidence.shared.audit import InMemoryAuditAppender
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.security.principals import CompanyPrincipal, FakePrincipalProvider

COMPANY_A = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_B = UUID("00000000-0000-7000-8000-000000000002")
USER_A = UUID("00000000-0000-7000-8000-000000000003")
USER_B = UUID("00000000-0000-7000-8000-000000000004")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_interviewer_profiles_are_reusable_and_tenant_scoped() -> None:
    app = create_lane_a_app(
        principal_provider=FakePrincipalProvider(
            company_principals={
                "company-a": CompanyPrincipal(
                    company_id=COMPANY_A,
                    company_user_id=USER_A,
                    identity_subject="oidc|a",
                ),
                "company-b": CompanyPrincipal(
                    company_id=COMPANY_B,
                    company_user_id=USER_B,
                    identity_subject="oidc|b",
                ),
            }
        ),
        repository=InMemoryCompanyRepository(),
        audit=InMemoryAuditAppender(),
        clock=FrozenClock(NOW),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://testserver",
    ) as client:
        created = await client.post(
            "/v1/interviewer-profiles",
            headers={
                "Authorization": "Bearer company-a",
                "Idempotency-Key": "interviewer-profile-create-001",
            },
            json={"name": "하나", "tone": "analytical", "voice_id": "Seoyeon"},
        )
        assert created.status_code == 201
        assert created.json()["name"] == "하나"
        assert "decision" not in created.text

        company_a = await client.get(
            "/v1/interviewer-profiles",
            headers={"Authorization": "Bearer company-a"},
        )
        company_b = await client.get(
            "/v1/interviewer-profiles",
            headers={"Authorization": "Bearer company-b"},
        )

    assert [item["name"] for item in company_a.json()["items"]] == ["하나"]
    assert company_b.json()["items"] == []
