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
                "job_requirements": [
                    {
                        "requirement_type": "preferred",
                        "statement": "ECS 운영 장애 대응 경험",
                        "priority": 2,
                        "criterion_code": "PROBLEM_SOLVING",
                    }
                ],
                "criteria": [
                    {
                        "code": "PROBLEM_SOLVING",
                        "name": "문제 해결",
                        "description": "대안을 비교하고 근거를 설명한다.",
                        "weight": 100,
                        "verification_guide": {
                            "observable_dimensions": [
                                "실제 상황",
                                "본인 행동",
                                "결과",
                            ],
                            "strong_answer_signals": ["판단 근거가 구체적임"],
                            "weak_answer_signals": ["팀 결과만 언급함"],
                            "follow_up_directions": ["본인이 직접 수행한 행동"],
                            "max_follow_ups": 2,
                            "time_budget_seconds": 300,
                        },
                        "abstain_guidance": "근거가 없으면 판단을 보류한다.",
                        "common_questions": ["어떤 대안을 검토했나요?"],
                        "required": True,
                    }
                ],
                "prohibited_topics": ["가족관계"],
                "interview_duration_minutes": 30,
            },
        )
        assert criteria.status_code == 201
        assert criteria.json()["job_requirements"][0]["statement"] == ("ECS 운영 장애 대응 경험")
        assert criteria.json()["persona_definition"]["mode"] == "system_managed"
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

        versions = await client.get(
            f"/v1/positions/{position_id}/competency-model-versions",
            headers=company_headers,
        )
        assert versions.status_code == 200
        assert versions.json()["items"][0]["status"] == "published"

        activated = await client.patch(
            f"/v1/positions/{position_id}",
            headers={
                **company_headers,
                "If-Match-Version": "1",
            },
            json={
                "title": "백엔드 플랫폼 개발자",
                "description": "Python과 AWS 기반 서비스를 개발하고 운영합니다.",
                "role_type": "개발",
                "headcount": 2,
                "recruitment_start_at": "2026-09-01",
                "recruitment_end_at": "2026-10-15",
                "status": "active",
            },
        )
        assert activated.status_code == 200
        assert activated.json()["title"] == "백엔드 플랫폼 개발자"
        assert activated.json()["status"] == "active"
        assert activated.json()["row_version"] == 2

        invitation = await client.post(
            f"/v1/positions/{position_id}/invitations",
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
        invitation_view = invitation.json()["invitations"][0]
        invitation_id = invitation_view["invitation_id"]
        assert invitation_view["applicant_display_name"] == "홍길동"
        assert "invitation_token" not in invitation.text

        invitation_page = await client.get(
            f"/v1/positions/{position_id}/invitations",
            headers=company_headers,
        )
        assert invitation_page.status_code == 200
        assert invitation_page.json()["items"][0]["applicant_display_name"] == "홍길동"

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
