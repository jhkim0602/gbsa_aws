import json
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


@pytest.mark.asyncio
async def test_protected_request_content_is_not_projected_into_audit_events() -> None:
    audit = InMemoryAuditAppender()
    app = create_lane_a_app(
        principal_provider=FakePrincipalProvider(
            company_principals={
                "secret-bearer-value": CompanyPrincipal(
                    company_id=COMPANY_ID,
                    company_user_id=COMPANY_USER_ID,
                    identity_subject="oidc|company-user",
                )
            }
        ),
        repository=InMemoryCompanyRepository(),
        audit=audit,
        clock=FrozenClock(NOW),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://testserver",
    ) as client:
        response = await client.post(
            "/v1/positions",
            headers={
                "Authorization": "Bearer secret-bearer-value",
                "Idempotency-Key": "position-create-0001",
            },
            json={
                "title": "민감한 내부 포지션명",
                "description": "지원자에게만 공개되는 긴 설명",
            },
        )

    assert response.status_code == 201
    serialized = json.dumps(
        [event.model_dump(mode="json") for event in audit.events],
        ensure_ascii=False,
    )
    assert "secret-bearer-value" not in serialized
    assert "민감한 내부 포지션명" not in serialized
    assert "지원자에게만 공개되는 긴 설명" not in serialized
    assert audit.events[0].metadata == {"row_version": 1}
