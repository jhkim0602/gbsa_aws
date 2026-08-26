from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from interview_evidence.company_management.adapters.applicant_session import (
    IssuedInvitationToken,
)
from interview_evidence.company_management.adapters.company_auth import CompanyAuthAdapter
from interview_evidence.company_management.api.company_routes import create_company_router
from interview_evidence.company_management.application.hiring_service import InvitationIssuance
from interview_evidence.company_management.domain.hiring import Invitation
from interview_evidence.shared.audit import InMemoryAuditAppender
from interview_evidence.shared.security.principals import (
    CompanyPrincipal,
    FakePrincipalProvider,
)
from interview_evidence.shared.submission_materials import DEFAULT_SUBMISSION_REQUIREMENTS

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_USER_ID = UUID("00000000-0000-7000-8000-000000000002")
POSITION_ID = UUID("00000000-0000-7000-8000-000000000003")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000004")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000005")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000006")
NOW = datetime(2026, 8, 26, 9, 0, tzinfo=UTC)


class CompanyServiceStub:
    def get_current_user(self, context: object, principal: object) -> object:
        del context, principal
        return SimpleNamespace()


class HiringServiceStub:
    def issue_invitations(
        self,
        context: object,
        **kwargs: object,
    ) -> tuple[InvitationIssuance, ...]:
        del context
        expires_at = kwargs["expires_at"]
        assert isinstance(expires_at, datetime)
        invitation = Invitation.create(
            invitation_id=INVITATION_ID,
            company_id=COMPANY_ID,
            position_id=POSITION_ID,
            competency_model_version_id=VERSION_ID,
            applicant_id=APPLICANT_ID,
            applicant_email="unverified@example.com",
            applicant_display_name="수동 초대",
            submission_requirements=DEFAULT_SUBMISSION_REQUIREMENTS,
            token_hash="a" * 64,
            expires_at=expires_at,
        )
        token = IssuedInvitationToken(
            invitation_id=INVITATION_ID,
            token_hash="a" * 64,
            expires_at=expires_at,
            raw_token="manual-secret-token",
        )
        return (InvitationIssuance(invitation=invitation, token=token),)


class EmailHandlerStub:
    def handle(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("manual links must not send email")


@pytest.mark.asyncio
async def test_manual_delivery_returns_a_single_use_access_link_without_email() -> None:
    audit = InMemoryAuditAppender()
    router = create_company_router(
        auth=CompanyAuthAdapter(
            FakePrincipalProvider(
                company_principals={
                    "company-token": CompanyPrincipal(
                        company_id=COMPANY_ID,
                        company_user_id=COMPANY_USER_ID,
                        identity_subject="oidc|company-user",
                    )
                }
            )
        ),
        company_service=cast(Any, CompanyServiceStub()),
        criteria_service=cast(Any, SimpleNamespace()),
        interviewer_service=cast(Any, SimpleNamespace()),
        hiring_service=cast(Any, HiringServiceStub()),
        template_service=cast(Any, SimpleNamespace()),
        audit=audit,
        invitation_email=cast(Any, EmailHandlerStub()),
        applicant_access_base_url="https://applicant.example/access",
    )
    app = FastAPI()
    app.include_router(router)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://testserver",
    ) as client:
        response = await client.post(
            f"/v1/positions/{POSITION_ID}/invitations",
            headers={
                "Authorization": "Bearer company-token",
                "Idempotency-Key": "manual-invitation-link",
            },
            json={
                "applicants": [
                    {
                        "email": "unverified@example.com",
                        "display_name": "수동 초대",
                    }
                ],
                "expires_at": (NOW + timedelta(days=7)).isoformat(),
                "delivery_method": "manual_link",
            },
        )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["accepted_count"] == 1
    assert body["rejected_count"] == 0
    assert body["access_links"] == [
        {
            "invitation_id": str(INVITATION_ID),
            "applicant_email": "unverified@example.com",
            "applicant_display_name": "수동 초대",
            "access_url": "https://applicant.example/access/manual-secret-token",
            "expires_at": (NOW + timedelta(days=7)).isoformat().replace("+00:00", "Z"),
        }
    ]
    assert any(event.action == "invitation.manual_links_created" for event in audit.events)
