from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from interview_evidence.recruiting_assistant.application import (
    AssistantAnswerService,
    AssistantSearchQuery,
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
from interview_evidence.shared.tenant import ActorType, TenantContext
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
OTHER_COMPANY_ID = UUID("00000000-0000-7000-8000-000000000002")
USER_ID = UUID("00000000-0000-7000-8000-000000000003")
POSITION_ID = UUID("00000000-0000-7000-8000-000000000004")
OTHER_POSITION_ID = UUID("00000000-0000-7000-8000-000000000005")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000006")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000007")
REPORT_ID = UUID("00000000-0000-7000-8000-000000000008")
REPORT_ITEM_ID = UUID("00000000-0000-7000-8000-000000000009")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000010")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000011")
NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


class AnswerModel:
    def __init__(self) -> None:
        self.source_id: UUID | None = None
        self.calls: list[dict[str, Any]] = []

    def generate(
        self,
        context: TenantContext,
        model_input: Mapping[str, Any],
    ) -> dict[str, Any]:
        context.assert_company(COMPANY_ID)
        self.calls.append(dict(model_input))
        return {
            "answer": "지원자는 ECS 장애 원인을 분석하고 배포 절차를 개선한 경험이 있습니다.",
            "source_ids": [str(self.source_id)] if self.source_id is not None else [],
        }


def _context(company_id: UUID = COMPANY_ID) -> TenantContext:
    return TenantContext(
        company_id=company_id,
        actor_type=ActorType.COMPANY_USER,
        actor_id=USER_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000012"),
        trace_id="assistant-search",
    )


def _vector(first: float = 1.0) -> tuple[float, ...]:
    return (first, *(0.0 for _ in range(1023)))


def _report(
    *,
    company_id: UUID = COMPANY_ID,
    report_id: UUID = REPORT_ID,
    invitation_id: UUID = INVITATION_ID,
    observation: str = "ECS 장애 원인을 분석하고 배포 절차를 개선했습니다.",
) -> Report:
    item = ReportItem(
        report_item_id=REPORT_ITEM_ID,
        company_id=company_id,
        report_id=report_id,
        criterion_id=CRITERION_ID,
        criterion_name="문제 해결",
        competency_model_version_id=VERSION_ID,
        assessment_state=AssessmentState.INSUFFICIENT_EVIDENCE,
        observation=observation,
        rationale="실제 최종 답변만 평가 근거로 사용",
        sufficiency="insufficient",
        uncertainty="추가 확인 필요",
        evidence=(),
    )
    return Report(
        report_id=report_id,
        company_id=company_id,
        interview_session_id=UUID("00000000-0000-7000-8000-000000000013"),
        invitation_id=invitation_id,
        version=1,
        kind=ReportKind.AI_ORIGINAL,
        model_version="test-model",
        prompt_version="test-prompt",
        config_version="test-config",
        status=ReportStatus.PARTIAL,
        summary="최종 답변 근거를 검토한 리포트",
        created_at=NOW,
        items=(item,),
    )


def test_report_projection_is_idempotent_and_searchable_by_position() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    embedder = StaticTextEmbedder(_vector())

    with Session(engine) as session:
        repository = SQLAlchemyAssistantDocumentRepository(session)
        projector = ReportSearchProjector(repository, embedder)
        service = AssistantSearchService(repository, embedder)

        first = projector.project(
            _context(),
            position_id=POSITION_ID,
            position_title="백엔드 엔지니어",
            applicant_id=APPLICANT_ID,
            applicant_display_name="김민준",
            report=_report(),
        )
        second = projector.project(
            _context(),
            position_id=POSITION_ID,
            position_title="백엔드 엔지니어",
            applicant_id=APPLICANT_ID,
            applicant_display_name="김민준",
            report=_report(),
        )
        results = service.search(
            _context(),
            AssistantSearchQuery(
                query="ECS 장애 해결 경험",
                position_id=POSITION_ID,
                limit=8,
            ),
        )

    assert len(first) == 2
    assert tuple(item.assistant_document_id for item in first) == tuple(
        item.assistant_document_id for item in second
    )
    assert {item.embedding_version for item in first} == {embedder.embedding_version}
    assert {result.document_type for result in results} == {
        "report_summary",
        "report_criterion",
    }
    criterion = next(result for result in results if result.document_type == "report_criterion")
    assert criterion.position_id == POSITION_ID
    assert criterion.applicant_id == APPLICANT_ID
    assert criterion.metadata["criterion_name"] == "문제 해결"
    assert criterion.metadata["applicant_display_name"] == "김민준"


def test_search_never_crosses_company_or_position_scope() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    embedder = StaticTextEmbedder(_vector())

    with Session(engine) as session:
        repository = SQLAlchemyAssistantDocumentRepository(session)
        projector = ReportSearchProjector(repository, embedder)
        service = AssistantSearchService(repository, embedder)
        projector.project(
            _context(),
            position_id=POSITION_ID,
            position_title="백엔드 엔지니어",
            applicant_id=APPLICANT_ID,
            applicant_display_name="김민준",
            report=_report(),
        )
        projector.project(
            _context(OTHER_COMPANY_ID),
            position_id=OTHER_POSITION_ID,
            position_title="데이터 엔지니어",
            applicant_id=APPLICANT_ID,
            applicant_display_name="이서연",
            report=_report(
                company_id=OTHER_COMPANY_ID,
                report_id=UUID("00000000-0000-7000-8000-000000000020"),
                invitation_id=UUID("00000000-0000-7000-8000-000000000021"),
            ),
        )

        wrong_position = service.search(
            _context(),
            AssistantSearchQuery(
                query="ECS",
                position_id=OTHER_POSITION_ID,
            ),
        )
        company_results = service.search(
            _context(),
            AssistantSearchQuery(query="ECS", position_id=None),
        )

    assert wrong_position == ()
    assert company_results
    assert all(result.position_id == POSITION_ID for result in company_results)


def test_search_excludes_documents_from_a_different_embedding_space() -> None:
    class OtherEmbedding(StaticTextEmbedder):
        model_id = "other-embedding"
        embedding_version = "other-v1"

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    indexed_embedder = StaticTextEmbedder(_vector())
    query_embedder = OtherEmbedding(_vector())

    with Session(engine) as session:
        repository = SQLAlchemyAssistantDocumentRepository(session)
        ReportSearchProjector(repository, indexed_embedder).project(
            _context(),
            position_id=POSITION_ID,
            position_title="백엔드 엔지니어",
            applicant_id=APPLICANT_ID,
            applicant_display_name="김민준",
            report=_report(),
        )
        results = AssistantSearchService(repository, query_embedder).search(
            _context(),
            AssistantSearchQuery(query="ECS 장애", position_id=POSITION_ID),
        )

    assert results == ()


def test_search_can_filter_candidates_below_a_configured_relevance_score() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    indexed_embedder = StaticTextEmbedder(_vector())
    unrelated_embedder = StaticTextEmbedder((0.0, 1.0, *(0.0 for _ in range(1022))))

    with Session(engine) as session:
        repository = SQLAlchemyAssistantDocumentRepository(session)
        ReportSearchProjector(repository, indexed_embedder).project(
            _context(),
            position_id=POSITION_ID,
            position_title="백엔드 엔지니어",
            applicant_id=APPLICANT_ID,
            applicant_display_name="김민준",
            report=_report(),
        )
        results = AssistantSearchService(
            repository,
            unrelated_embedder,
            minimum_score=0.1,
        ).search(
            _context(),
            AssistantSearchQuery(query="완전히 무관한 질문", position_id=POSITION_ID),
        )

    assert results == ()


def test_assistant_documents_are_deleted_and_verified_by_invitation() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    embedder = StaticTextEmbedder(_vector())

    with Session(engine) as session:
        repository = SQLAlchemyAssistantDocumentRepository(session)
        documents = ReportSearchProjector(repository, embedder).project(
            _context(),
            position_id=POSITION_ID,
            position_title="백엔드 엔지니어",
            applicant_id=APPLICANT_ID,
            applicant_display_name="김민준",
            report=_report(),
        )
        ids = repository.list_document_ids_for_invitation(_context(), INVITATION_ID)
        verified = [repository.delete_and_verify(_context(), document_id) for document_id in ids]

    assert set(ids) == {document.assistant_document_id for document in documents}
    assert verified == [True, True]


def test_rag_answer_only_returns_source_ids_that_were_actually_retrieved() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    embedder = StaticTextEmbedder(_vector())
    model = AnswerModel()

    with Session(engine) as session:
        repository = SQLAlchemyAssistantDocumentRepository(session)
        search = AssistantSearchService(repository, embedder)
        ReportSearchProjector(repository, embedder).project(
            _context(),
            position_id=POSITION_ID,
            position_title="백엔드 엔지니어",
            applicant_id=APPLICANT_ID,
            applicant_display_name="김민준",
            report=_report(),
        )
        retrieved = search.search(
            _context(),
            AssistantSearchQuery(query="ECS 장애", position_id=POSITION_ID),
        )
        model.source_id = retrieved[0].assistant_document_id
        answer = AssistantAnswerService(search, model).answer(
            _context(),
            scope="position",
            query=AssistantSearchQuery(query="ECS 장애", position_id=POSITION_ID),
        )

    assert "ECS 장애 원인" in answer.answer
    assert tuple(source.assistant_document_id for source in answer.sources) == (model.source_id,)
    assert answer.degraded_mode is None
    assert model.calls[0]["temperature"] == 0.1


def test_rag_answer_does_not_call_model_without_grounding_sources() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    embedder = StaticTextEmbedder(_vector())
    model = AnswerModel()

    with Session(engine) as session:
        search = AssistantSearchService(
            SQLAlchemyAssistantDocumentRepository(session),
            embedder,
        )
        answer = AssistantAnswerService(search, model).answer(
            _context(),
            scope="position",
            query=AssistantSearchQuery(query="없는 근거", position_id=POSITION_ID),
        )

    assert answer.degraded_mode == "no_sources"
    assert answer.sources == ()
    assert model.calls == []


def test_rag_answer_rejects_model_output_without_a_retrieved_citation() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    embedder = StaticTextEmbedder(_vector())
    model = AnswerModel()
    model.source_id = UUID("00000000-0000-7000-8000-000000000999")

    with Session(engine) as session:
        repository = SQLAlchemyAssistantDocumentRepository(session)
        ReportSearchProjector(repository, embedder).project(
            _context(),
            position_id=POSITION_ID,
            position_title="백엔드 엔지니어",
            applicant_id=APPLICANT_ID,
            applicant_display_name="김민준",
            report=_report(),
        )
        answer = AssistantAnswerService(
            AssistantSearchService(repository, embedder),
            model,
        ).answer(
            _context(),
            scope="position",
            query=AssistantSearchQuery(query="ECS 장애", position_id=POSITION_ID),
        )

    assert answer.degraded_mode == "citation_validation_failed"
    assert answer.sources == ()
