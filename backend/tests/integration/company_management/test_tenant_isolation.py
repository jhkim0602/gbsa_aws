from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from interview_evidence.company_management.api import create_lane_a_app
from interview_evidence.company_management.domain.company import Company, Position
from interview_evidence.company_management.domain.criteria import (
    CompetencyModelStatus,
    CompetencyModelVersion,
    EvaluationCriterion,
    JobRequirement,
    RequirementType,
)
from interview_evidence.company_management.repositories.postgres import (
    Base,
    InMemoryCompanyRepository,
    SqlAlchemyCompanyRepository,
    TenantScopedResourceNotFound,
)
from interview_evidence.shared.audit import InMemoryAuditAppender
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.security.principals import (
    CompanyPrincipal,
    FakePrincipalProvider,
)
from interview_evidence.shared.tenant import ActorType, TenantContext
from sqlalchemy import create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import Session

COMPANY_A = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_B = UUID("00000000-0000-7000-8000-000000000002")
USER_A = UUID("00000000-0000-7000-8000-000000000003")
USER_B = UUID("00000000-0000-7000-8000-000000000004")
POSITION_ID = UUID("00000000-0000-7000-8000-000000000005")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def context(company_id: UUID, actor_id: UUID) -> TenantContext:
    return TenantContext(
        company_id=company_id,
        actor_type=ActorType.COMPANY_USER,
        actor_id=actor_id,
        request_id=UUID("00000000-0000-7000-8000-000000000006"),
        trace_id="tenant-isolation",
    )


def test_repository_never_returns_another_company_resource() -> None:
    repository = InMemoryCompanyRepository()
    tenant_a = context(COMPANY_A, USER_A)
    tenant_b = context(COMPANY_B, USER_B)
    position = Position(
        position_id=POSITION_ID,
        company_id=COMPANY_A,
        title="백엔드 개발자",
        description="서비스 개발",
        created_by=USER_A,
        created_at=NOW,
    )
    repository.save_position(tenant_a, position)

    assert repository.get_position(tenant_a, POSITION_ID) == position
    assert repository.list_positions(tenant_b) == ()
    with pytest.raises(TenantScopedResourceNotFound):
        repository.get_position(tenant_b, POSITION_ID)


def test_repository_rejects_writing_a_resource_with_a_mismatched_company() -> None:
    repository = InMemoryCompanyRepository()
    tenant_b = context(COMPANY_B, USER_B)
    position = Position(
        position_id=POSITION_ID,
        company_id=COMPANY_A,
        title="백엔드 개발자",
        description="서비스 개발",
        created_by=USER_A,
        created_at=NOW,
    )

    with pytest.raises(PermissionError):
        repository.save_position(tenant_b, position)


def test_sqlalchemy_repository_applies_the_tenant_predicate() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    tenant_a = context(COMPANY_A, USER_A)
    tenant_b = context(COMPANY_B, USER_B)
    with Session(engine) as session:
        repository = SqlAlchemyCompanyRepository(session)
        repository.save_company(
            tenant_a,
            Company(
                company_id=COMPANY_A,
                name="회사 A",
                created_at=NOW,
                updated_at=NOW,
            ),
        )
        repository.save_position(
            tenant_a,
            Position(
                position_id=POSITION_ID,
                company_id=COMPANY_A,
                title="백엔드 개발자",
                description="서비스 개발",
                created_by=USER_A,
                created_at=NOW,
            ),
        )
        version = CompetencyModelVersion.create(
            competency_model_version_id=UUID("00000000-0000-7000-8000-000000000007"),
            company_id=COMPANY_A,
            position_id=POSITION_ID,
            version_number=1,
            criteria=(
                EvaluationCriterion(
                    criterion_id=UUID("00000000-0000-7000-8000-000000000008"),
                    code="PROBLEM_SOLVING",
                    name="문제 해결",
                    description="대안을 비교한다.",
                    weight=1,
                    abstain_guidance="근거가 없으면 보류한다.",
                    required=True,
                ),
            ),
            prohibited_topics=(),
            interview_duration_minutes=30,
            persona_definition={"name": "면접관"},
        )
        repository.save_criterion_version(tenant_a, version)

        assert repository.get_position(tenant_a, POSITION_ID).company_id == COMPANY_A
        assert (
            repository.get_criterion_version(
                tenant_a,
                version.competency_model_version_id,
            )
            .criteria[0]
            .code
            == "PROBLEM_SOLVING"
        )
        with pytest.raises(TenantScopedResourceNotFound):
            repository.get_position(tenant_b, POSITION_ID)


def test_resaving_a_version_keeps_requirements_within_their_criterion_foreign_key() -> None:
    # Publishing re-saves an existing version, which replaces its criteria and
    # requirements. fk_job_requirements_criterion means the requirement rows have to be
    # deleted before the criteria they reference, so this exercises that ordering
    # against a database that actually enforces the constraint.
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(connection: DBAPIConnection, _record: object) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    tenant_a = context(COMPANY_A, USER_A)
    with Session(engine) as session:
        repository = SqlAlchemyCompanyRepository(session)
        repository.save_company(
            tenant_a,
            Company(company_id=COMPANY_A, name="회사 A", created_at=NOW, updated_at=NOW),
        )
        repository.save_position(
            tenant_a,
            Position(
                position_id=POSITION_ID,
                company_id=COMPANY_A,
                title="백엔드 개발자",
                description="서비스 개발",
                created_by=USER_A,
                created_at=NOW,
            ),
        )
        version = CompetencyModelVersion.create(
            competency_model_version_id=UUID("00000000-0000-7000-8000-000000000009"),
            company_id=COMPANY_A,
            position_id=POSITION_ID,
            version_number=1,
            job_requirements=(
                JobRequirement(
                    job_requirement_id=UUID("00000000-0000-7000-8000-00000000000a"),
                    requirement_type=RequirementType.REQUIRED,
                    statement="장애 대응 경험",
                    priority=1,
                    criterion_code="PROBLEM_SOLVING",
                ),
            ),
            criteria=(
                EvaluationCriterion(
                    criterion_id=UUID("00000000-0000-7000-8000-00000000000b"),
                    code="PROBLEM_SOLVING",
                    name="문제 해결",
                    description="대안을 비교한다.",
                    weight=1,
                    abstain_guidance="근거가 없으면 보류한다.",
                    required=True,
                ),
            ),
            prohibited_topics=(),
            interview_duration_minutes=30,
        )
        repository.save_criterion_version(tenant_a, version)

        published = version.publish(expected_version=version.row_version, published_at=NOW)
        repository.save_criterion_version(tenant_a, published)

        stored = repository.get_criterion_version(
            tenant_a,
            version.competency_model_version_id,
        )
        assert stored.status is CompetencyModelStatus.PUBLISHED
        assert stored.job_requirements[0].criterion_code == "PROBLEM_SOLVING"
        assert stored.criteria[0].code == "PROBLEM_SOLVING"


@pytest.mark.asyncio
async def test_company_routes_do_not_reveal_another_tenants_position() -> None:
    repository = InMemoryCompanyRepository()
    tenant_a = context(COMPANY_A, USER_A)
    repository.save_position(
        tenant_a,
        Position(
            position_id=POSITION_ID,
            company_id=COMPANY_A,
            title="백엔드 개발자",
            description="서비스 개발",
            created_by=USER_A,
            created_at=NOW,
        ),
    )
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
        repository=repository,
        audit=InMemoryAuditAppender(),
        clock=FrozenClock(NOW),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://testserver",
    ) as client:
        listed = await client.get(
            "/v1/positions",
            headers={"Authorization": "Bearer company-b"},
        )
        assert listed.status_code == 200
        assert listed.json()["items"] == []

        mutated = await client.post(
            f"/v1/positions/{POSITION_ID}/competency-model-versions",
            headers={
                "Authorization": "Bearer company-b",
                "Idempotency-Key": "cross-tenant-denial",
            },
            json={
                "job_requirements": [
                    {
                        "requirement_type": "required",
                        "statement": "문제 해결 경험",
                        "priority": 1,
                        "criterion_code": "PROBLEM_SOLVING",
                    }
                ],
                "criteria": [
                    {
                        "code": "PROBLEM_SOLVING",
                        "name": "문제 해결",
                        "description": "대안을 비교한다.",
                        "weight": 100,
                        "verification_guide": {
                            "observable_dimensions": ["상황", "행동", "결과"],
                            "strong_answer_signals": ["판단 근거가 구체적임"],
                            "weak_answer_signals": ["결과만 언급함"],
                            "follow_up_directions": ["본인이 수행한 행동"],
                            "max_follow_ups": 1,
                            "time_budget_seconds": 300,
                        },
                        "abstain_guidance": "근거가 없으면 보류한다.",
                        "common_questions": [],
                        "required": True,
                    }
                ],
                "prohibited_topics": [],
                "interview_duration_minutes": 30,
            },
        )
        assert mutated.status_code == 404
