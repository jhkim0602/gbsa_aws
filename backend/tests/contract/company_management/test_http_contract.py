from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from interview_evidence.company_management.api import create_lane_a_app
from interview_evidence.company_management.domain.company import Position
from interview_evidence.company_management.domain.criteria import (
    CompetencyModelVersion,
    EvaluationCriterion,
)
from interview_evidence.company_management.repositories.postgres import (
    InMemoryCompanyRepository,
)
from interview_evidence.shared.audit import InMemoryAuditAppender
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.security.principals import (
    CompanyPrincipal,
    FakePrincipalProvider,
)
from interview_evidence.shared.tenant import ActorType, TenantContext

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_USER_ID = UUID("00000000-0000-7000-8000-000000000002")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)

EXPECTED_OPERATIONS = {
    "getCurrentCompanyUser",
    "listPositions",
    "getPosition",
    "createPosition",
    "updatePosition",
    "listInterviewerProfiles",
    "createInterviewerProfile",
    "listCompetencyModelVersions",
    "createCompetencyModelVersion",
    "publishCompetencyModelVersion",
    "listInvitations",
    "createInvitations",
    "exchangeApplicantInvitationToken",
    "revokeApplicantSession",
    "verifyApplicantIdentity",
    "getApplicantConsentPolicy",
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
    assert "listInvitations" in operations
    assert "createInvitations" in operations
    assert "/v1/positions/{position_id}" in app.openapi()["paths"]
    assert "get" in app.openapi()["paths"]["/v1/positions/{position_id}"]
    assert "patch" in app.openapi()["paths"]["/v1/positions/{position_id}"]
    assert "get" in app.openapi()["paths"]["/v1/positions/{position_id}/competency-model-versions"]
    assert "/v1/positions/{position_id}/invitations" in app.openapi()["paths"]
    invitation_schema = app.openapi()["components"]["schemas"]["InvitationView"]
    assert invitation_schema["properties"]["interview_session_id"] == {
        "anyOf": [
            {"type": "string", "format": "uuid"},
            {"type": "null"},
        ],
        "title": "Interview Session Id",
    }


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
        fetched = await client.get(
            f"/v1/positions/{created.json()['position_id']}",
            headers={"Authorization": "Bearer company-token"},
        )
    assert created.status_code == 201
    assert fetched.status_code == 200
    assert fetched.json() == created.json()
    assert set(created.json()) == {
        "position_id",
        "title",
        "description",
        "role_type",
        "headcount",
        "recruitment_start_at",
        "recruitment_end_at",
        "status",
        "row_version",
        "created_at",
    }


@pytest.mark.asyncio
async def test_position_revision_requires_published_criteria_and_rejects_stale_versions() -> None:
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
    auth = {"Authorization": "Bearer company-token"}
    payload = {
        "title": "백엔드 개발자",
        "description": "서비스 개발",
        "role_type": "개발",
        "headcount": 2,
        "recruitment_start_at": "2026-09-01",
        "recruitment_end_at": "2026-09-30",
        "status": "draft",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://testserver",
    ) as client:
        created = await client.post(
            "/v1/positions",
            headers={
                **auth,
                "Idempotency-Key": "position-revision-create",
            },
            json={
                "title": payload["title"],
                "description": payload["description"],
            },
        )
        position_id = created.json()["position_id"]

        activation = await client.patch(
            f"/v1/positions/{position_id}",
            headers={**auth, "If-Match-Version": "1"},
            json={**payload, "status": "active"},
        )
        assert activation.status_code == 422

        updated = await client.patch(
            f"/v1/positions/{position_id}",
            headers={**auth, "If-Match-Version": "1"},
            json={**payload, "title": "시니어 백엔드 개발자"},
        )
        assert updated.status_code == 200
        assert updated.json()["row_version"] == 2

        stale = await client.patch(
            f"/v1/positions/{position_id}",
            headers={**auth, "If-Match-Version": "1"},
            json={**payload, "title": "플랫폼 백엔드 개발자"},
        )
        assert stale.status_code == 409


@pytest.mark.asyncio
async def test_legacy_criterion_versions_without_job_requirements_remain_readable() -> None:
    repository = InMemoryCompanyRepository()
    context = TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.COMPANY_USER,
        actor_id=COMPANY_USER_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000010"),
        trace_id="legacy-criterion-read",
    )
    position_id = UUID("00000000-0000-7000-8000-000000000011")
    repository.save_position(
        context,
        Position(
            position_id=position_id,
            company_id=COMPANY_ID,
            title="레거시 포지션",
            description="이전 면접 기준을 가진 포지션",
            created_by=COMPANY_USER_ID,
            created_at=NOW,
        ),
    )
    version = CompetencyModelVersion.create(
        competency_model_version_id=UUID("00000000-0000-7000-8000-000000000012"),
        company_id=COMPANY_ID,
        position_id=position_id,
        version_number=1,
        criteria=(
            EvaluationCriterion(
                criterion_id=UUID("00000000-0000-7000-8000-000000000013"),
                code="PROBLEM_SOLVING",
                name="문제 해결",
                description="문제를 구조화하는 역량",
                weight=1,
                good_evidence={},
                weak_evidence={},
                abstain_guidance="근거가 없으면 판단을 유보한다.",
                required=True,
            ),
        ),
        prohibited_topics=(),
        interview_duration_minutes=30,
        persona_definition={"name": "system"},
    )
    repository.save_criterion_version(context, version)
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
        repository=repository,
        audit=InMemoryAuditAppender(),
        clock=FrozenClock(NOW),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://testserver",
    ) as client:
        response = await client.get(
            f"/v1/positions/{position_id}/competency-model-versions",
            headers={"Authorization": "Bearer company-token"},
        )

    assert response.status_code == 200
    assert response.json()["items"][0]["job_requirements"] == []
