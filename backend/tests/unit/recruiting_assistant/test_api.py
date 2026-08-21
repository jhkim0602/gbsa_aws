import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from interview_evidence.company_management.domain.company import Position, PositionStatus
from interview_evidence.main import create_app
from interview_evidence.recruiting_assistant.api import create_assistant_router
from interview_evidence.recruiting_assistant.application import (
    AssistantAnswerService,
    AssistantSearchService,
    ReportSearchProjector,
)
from interview_evidence.recruiting_assistant.repository import (
    Base,
    SQLAlchemyAssistantDocumentRepository,
)
from interview_evidence.reporting.domain.report import (
    AssessmentState,
    Report,
    ReportItem,
    ReportKind,
    ReportStatus,
)
from interview_evidence.shared.aws_clients.ports import StaticTextEmbedder
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.security.principals import (
    ApplicantPrincipal,
    CompanyPrincipal,
    PrincipalNotFoundError,
)
from interview_evidence.shared.tenant import TenantContext
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000101")
USER_ID = UUID("00000000-0000-7000-8000-000000000102")
POSITION_ID = UUID("00000000-0000-7000-8000-000000000103")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000104")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000105")
REPORT_ID = UUID("00000000-0000-7000-8000-000000000106")
ITEM_ID = UUID("00000000-0000-7000-8000-000000000107")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000108")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000109")
NOW = datetime(2026, 8, 21, 13, 0, tzinfo=UTC)


class Principals:
    def get_company_principal(self, credential: str) -> CompanyPrincipal:
        if credential != "company-token":
            raise PrincipalNotFoundError
        return CompanyPrincipal(
            company_id=COMPANY_ID,
            company_user_id=USER_ID,
            identity_subject="test-company-user",
        )

    def get_applicant_principal(self, credential: str) -> ApplicantPrincipal:
        raise PrincipalNotFoundError


class Positions:
    def __init__(self, *, archived: bool = False) -> None:
        self._archived = archived

    def get_position(self, context: TenantContext, position_id: UUID) -> Position:
        context.assert_company(COMPANY_ID)
        if position_id != POSITION_ID:
            raise LookupError("position not found")
        return Position(
            position_id=POSITION_ID,
            company_id=COMPANY_ID,
            title="백엔드 개발자",
            description="서비스 개발",
            created_by=USER_ID,
            status=PositionStatus.ACTIVE,
            recruitment_end_at=(
                date(2026, 8, 20) if self._archived else None
            ),
            created_at=NOW,
        )

    def list_positions(self, context: TenantContext) -> tuple[Position, ...]:
        return (self.get_position(context, POSITION_ID),)


class Audit:
    def __init__(self) -> None:
        self.actions: list[str] = []

    def append(
        self,
        context: TenantContext,
        *,
        action: str,
        resource_type: str,
        resource_id: UUID,
        result: str,
        metadata: dict[str, Any],
    ) -> UUID:
        context.assert_company(COMPANY_ID)
        del resource_type, resource_id, result, metadata
        self.actions.append(action)
        return UUID("00000000-0000-7000-8000-000000000110")

    def delete_for_resource(
        self,
        context: TenantContext,
        resource_id: UUID,
    ) -> bool:
        del context, resource_id
        return True


class GroundedModel:
    def generate(
        self,
        context: TenantContext,
        model_input: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        context.assert_company(COMPANY_ID)
        system = model_input["system"]
        assert isinstance(system, str)
        assert "관련되거나 비슷한 사례" in system
        assert "실제로 답변에 활용한 source_id" in system
        assert "채용 여부를 최종 결정" not in system
        assert "서로 다른 포지션의 점수" not in system
        messages = model_input["messages"]
        assert isinstance(messages, list)
        content = messages[0]["content"][0]["text"]
        payload = json.loads(content)
        assert "relevance_score" in payload["provided_sources"][0]
        assert "score_components" in payload["provided_sources"][0]
        source_id = payload["provided_sources"][0]["source_id"]
        return {
            "answer": "지원자는 장애 원인을 분석하고 배포 절차를 개선한 경험이 있습니다.",
            "source_ids": [source_id],
        }


def _report() -> Report:
    return Report(
        report_id=REPORT_ID,
        company_id=COMPANY_ID,
        interview_session_id=UUID("00000000-0000-7000-8000-000000000111"),
        invitation_id=INVITATION_ID,
        version=1,
        kind=ReportKind.AI_ORIGINAL,
        model_version="test-model",
        prompt_version="test-prompt",
        config_version="test-config",
        status=ReportStatus.PARTIAL,
        summary="최종 답변 기반 리포트",
        created_at=NOW,
        items=(
            ReportItem(
                report_item_id=ITEM_ID,
                company_id=COMPANY_ID,
                report_id=REPORT_ID,
                criterion_id=CRITERION_ID,
                criterion_name="문제 해결",
                competency_model_version_id=VERSION_ID,
                assessment_state=AssessmentState.INSUFFICIENT_EVIDENCE,
                observation="장애 원인을 분석하고 배포 절차를 개선했습니다.",
                rationale="최종 답변 기반",
                sufficiency="insufficient",
                uncertainty="추가 검토 필요",
                evidence=(),
            ),
        ),
    )


def test_assistant_http_search_and_grounded_answer() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    repository = SQLAlchemyAssistantDocumentRepository(session)
    embedder = StaticTextEmbedder((1.0, *(0.0 for _ in range(1023))))
    context = TenantContext(
        company_id=COMPANY_ID,
        actor_type="company_user",
        actor_id=USER_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000112"),
        trace_id="assistant-api-seed",
    )
    ReportSearchProjector(repository, embedder).project(
        context,
        position_id=POSITION_ID,
        position_title="백엔드 엔지니어",
        applicant_id=APPLICANT_ID,
        applicant_display_name="김민준",
        report=_report(),
    )
    session.commit()
    search = AssistantSearchService(repository, embedder)
    audit = Audit()
    app = create_app(
        [
            create_assistant_router(
                principal_provider=Principals(),
                company_service=Positions(),
                search_service=search,
                answer_service=AssistantAnswerService(search, GroundedModel()),
                audit=audit,
                clock=FrozenClock(NOW),
            )
        ]
    )

    with TestClient(app) as client:
        searched = client.post(
            "/v1/assistant/search",
            headers={"Authorization": "Bearer company-token"},
            json={
                "scope": "position",
                "position_id": str(POSITION_ID),
                "query": "장애 대응 경험",
            },
        )
        answered = client.post(
            "/v1/assistant/answers",
            headers={"Authorization": "Bearer company-token"},
            json={
                "scope": "position",
                "position_id": str(POSITION_ID),
                "query": "장애 대응 경험을 알려줘",
            },
        )
        invalid_scope = client.post(
            "/v1/assistant/answers",
            headers={"Authorization": "Bearer company-token"},
            json={
                "scope": "company",
                "position_id": str(POSITION_ID),
                "query": "장애 대응 경험",
            },
        )
        streamed = client.post(
            "/v1/assistant/answers/stream",
            headers={"Authorization": "Bearer company-token"},
            json={
                "scope": "position",
                "position_id": str(POSITION_ID),
                "query": "장애 대응 경험을 알려줘",
            },
        )

    session.close()
    assert searched.status_code == 200, searched.text
    assert searched.json()["sources"]
    assert answered.status_code == 200
    assert answered.json()["sources"]
    assert "배포 절차" in answered.json()["answer"]
    assert streamed.status_code == 200
    assert "event: delta" in streamed.text
    assert "event: sources" in streamed.text
    assert "event: done" in streamed.text
    assert invalid_scope.status_code == 422
    assert audit.actions == [
        "assistant.search",
        "assistant.answer",
        "assistant.answer_stream",
    ]


def test_company_scope_excludes_archived_positions_but_explicit_scope_can_search() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    repository = SQLAlchemyAssistantDocumentRepository(session)
    embedder = StaticTextEmbedder((1.0, *(0.0 for _ in range(1023))))
    context = TenantContext(
        company_id=COMPANY_ID,
        actor_type="company_user",
        actor_id=USER_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000113"),
        trace_id="assistant-archive-seed",
    )
    ReportSearchProjector(repository, embedder).project(
        context,
        position_id=POSITION_ID,
        position_title="백엔드 엔지니어",
        applicant_id=APPLICANT_ID,
        applicant_display_name="김민준",
        report=_report(),
    )
    session.commit()
    search = AssistantSearchService(repository, embedder)
    app = create_app(
        [
            create_assistant_router(
                principal_provider=Principals(),
                company_service=Positions(archived=True),
                search_service=search,
                answer_service=AssistantAnswerService(search, GroundedModel()),
                audit=Audit(),
                clock=FrozenClock(NOW),
            )
        ]
    )

    with TestClient(app) as client:
        company_scope = client.post(
            "/v1/assistant/search",
            headers={"Authorization": "Bearer company-token"},
            json={"scope": "company", "query": "장애 대응 경험"},
        )
        archived_scope = client.post(
            "/v1/assistant/search",
            headers={"Authorization": "Bearer company-token"},
            json={
                "scope": "position",
                "position_id": str(POSITION_ID),
                "query": "장애 대응 경험",
            },
        )

    session.close()
    assert company_scope.status_code == 200
    assert company_scope.json()["sources"] == []
    assert archived_scope.status_code == 200
    assert archived_scope.json()["sources"]
