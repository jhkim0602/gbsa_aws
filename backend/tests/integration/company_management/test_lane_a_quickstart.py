from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from interview_evidence.company_management.api import create_lane_a_runtime
from interview_evidence.company_management.repositories.postgres import (
    InMemoryCompanyRepository,
)
from interview_evidence.shared.audit import InMemoryAuditAppender
from interview_evidence.shared.aws_clients.ports import InMemoryEmailSender
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.security.principals import (
    CompanyPrincipal,
    FakePrincipalProvider,
)

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_USER_ID = UUID("00000000-0000-7000-8000-000000000002")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_lane_a_company_to_consented_applicant_journey() -> None:
    email_sender = InMemoryEmailSender()
    repository = InMemoryCompanyRepository()
    runtime = create_lane_a_runtime(
        principal_provider=FakePrincipalProvider(
            company_principals={
                "company-token": CompanyPrincipal(
                    company_id=COMPANY_ID,
                    company_user_id=COMPANY_USER_ID,
                    identity_subject="oidc|company-user",
                )
            }
        ),
        repository=repository,
        audit=InMemoryAuditAppender(),
        clock=FrozenClock(NOW),
        email_sender=email_sender,
        applicant_access_base_url="https://applicant.example/access",
    )
    company_headers = {"Authorization": "Bearer company-token"}

    async with AsyncClient(
        transport=ASGITransport(app=runtime.app),
        base_url="https://testserver",
    ) as client:
        position = await client.post(
            "/v1/positions",
            headers={
                **company_headers,
                "Idempotency-Key": "quickstart-position",
            },
            json={
                "title": "백엔드 개발자",
                "description": "Python과 AWS 기반 서비스를 개발합니다.",
            },
        )
        assert position.status_code == 201
        position_id = position.json()["position_id"]

        criteria = await client.post(
            f"/v1/positions/{position_id}/competency-model-versions",
            headers={
                **company_headers,
                "Idempotency-Key": "quickstart-criteria",
            },
            json={
                "criteria": [
                    {
                        "code": "PROBLEM_SOLVING",
                        "name": "문제 해결",
                        "description": "대안을 비교하고 근거를 설명한다.",
                        "weight": 1,
                        "good_evidence": {"signal": "tradeoff"},
                        "weak_evidence": {"signal": "unsupported"},
                        "abstain_guidance": "근거가 없으면 판단을 보류한다.",
                        "common_questions": ["어떤 대안을 검토했나요?"],
                        "required": True,
                    }
                ],
                "prohibited_topics": ["가족관계"],
                "interview_duration_minutes": 30,
                "persona_definition": {
                    "name": "GBSA 면접관",
                    "tone": "차분함",
                },
            },
        )
        assert criteria.status_code == 201
        version_id = criteria.json()["competency_model_version_id"]

        published_criteria = await client.post(
            f"/v1/competency-model-versions/{version_id}/publish",
            headers={
                **company_headers,
                "Idempotency-Key": "quickstart-publish-criteria",
                "If-Match-Version": "1",
            },
        )
        assert published_criteria.status_code == 200
        assert published_criteria.json()["status"] == "published"

        campaign = await client.post(
            "/v1/campaigns",
            headers={
                **company_headers,
                "Idempotency-Key": "quickstart-campaign",
            },
            json={
                "position_id": position_id,
                "competency_model_version_id": version_id,
                "name": "2026 백엔드 채용",
                "candidate_instructions": "조용한 환경에서 진행해 주세요.",
            },
        )
        assert campaign.status_code == 201
        campaign_id = campaign.json()["campaign_id"]

        published_campaign = await client.post(
            f"/v1/campaigns/{campaign_id}/publish",
            headers={
                **company_headers,
                "Idempotency-Key": "quickstart-publish-campaign",
                "If-Match-Version": "1",
            },
        )
        assert published_campaign.status_code == 200

        invitation = await client.post(
            f"/v1/campaigns/{campaign_id}/invitations",
            headers={
                **company_headers,
                "Idempotency-Key": "quickstart-invitation",
            },
            json={
                "applicants": [
                    {
                        "email": "applicant@example.com",
                        "display_name": "홍길동",
                    }
                ],
                "expires_at": (NOW + timedelta(days=7)).isoformat(),
            },
        )
        assert invitation.status_code == 202
        invitation_id = invitation.json()["invitations"][0]["invitation_id"]
        assert "invitation_token" not in invitation.text

        invitation_url = str(email_sender.messages[0].template_data["invitation_url"])
        raw_token = parse_qs(urlparse(invitation_url).query)["token"][0]
        exchange = await client.post(
            "/v1/applicant/access/exchange",
            headers={"Idempotency-Key": "quickstart-token-exchange"},
            json={"invitation_token": raw_token},
        )
        assert exchange.status_code == 204
        assert "HttpOnly" in exchange.headers["set-cookie"]
        assert "Secure" in exchange.headers["set-cookie"]

        verified = await client.post(
            "/v1/applicant/identity-verifications",
            headers={"Idempotency-Key": "quickstart-identity"},
            json={"display_name": "홍길동", "verification_value": "1234"},
        )
        assert verified.status_code == 200
        assert verified.json()["state"] == "identity_verified"

        policy = await client.get("/v1/applicant/consents")
        assert policy.status_code == 200
        assert "최종 채용 결정은 기업의 사람이 수행" in policy.json()["ai_role"]
        assert policy.json()["retention_days"] == 180

        consent = await client.post(
            "/v1/applicant/consents",
            headers={"Idempotency-Key": "quickstart-consent"},
            json={
                "policy_version": policy.json()["policy_version"],
                "accepted_purposes": [
                    "document_analysis",
                    "recording",
                    "ai_assessment",
                ],
                "consent_content_digest": policy.json()["content_digest"],
            },
        )
    assert consent.status_code == 201
    assert consent.json()["retention_days"] == 180
    assert repository.invitations[UUID(invitation_id)].status == "consented"
    assert runtime.outbox.pending()[0].event_type == "invitation.consent_completed"
