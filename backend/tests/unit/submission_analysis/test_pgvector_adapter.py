from uuid import UUID

from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.adapters.postgres_hybrid import (
    PostgresHybridSearchIndex,
)
from interview_evidence.submission_analysis.adapters.search import SearchDocument
from interview_evidence.submission_analysis.repositories.postgres import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
OTHER_COMPANY_ID = UUID("00000000-0000-7000-8000-000000000002")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000003")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000004")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000005")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000006")


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.APPLICANT,
        actor_id=APPLICANT_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000007"),
        trace_id="pgvector-adapter",
    )


def _vector(first: float, second: float) -> tuple[float, ...]:
    return (first, second, *(0.0 for _ in range(1022)))


def test_postgres_hybrid_adapter_filters_scope_and_returns_source_excerpt() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        index = PostgresHybridSearchIndex(session)
        for company_id, source_id, text in (
            (
                COMPANY_ID,
                UUID("00000000-0000-7000-8000-000000000010"),
                "ECS 배포 자동화 경험",
            ),
            (
                OTHER_COMPANY_ID,
                UUID("00000000-0000-7000-8000-000000000011"),
                "ECS 운영 장애 복구 경험",
            ),
        ):
            index.add(
                SearchDocument(
                    document_id=str(source_id),
                    company_id=company_id,
                    applicant_id=APPLICANT_ID,
                    source_id=source_id,
                    text=text,
                    vector=_vector(1.0, 0.0),
                    symbols=("ECS",),
                    locator={"page": 1},
                    ownership_confidence=1.0,
                    invitation_id=INVITATION_ID,
                    competency_model_version_id=VERSION_ID,
                    criterion_id=CRITERION_ID,
                    material_type="resume",
                    embedding_model="amazon.titan-embed-text-v2:0",
                    embedding_version="titan-v2",
                )
            )

        candidates = index.candidates(
            _context(),
            applicant_id=APPLICANT_ID,
            invitation_id=INVITATION_ID,
            competency_model_version_id=VERSION_ID,
            criterion_id=CRITERION_ID,
            query="ECS 배포",
            query_vector=_vector(1.0, 0.0),
            exact_symbol="ECS",
        )

    assert len(candidates) == 1
    assert candidates[0].document.company_id == COMPANY_ID
    assert candidates[0].document.text == "ECS 배포 자동화 경험"
    assert candidates[0].document.material_type == "resume"
    assert candidates[0].exact_symbol_score == 1.0


def test_criterion_filter_keeps_criterion_agnostic_submission_chunks() -> None:
    """Applicant chunks carry no criterion, so a criterion query must still reach them."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    chunk_id = UUID("00000000-0000-7000-8000-000000000020")
    with Session(engine) as session:
        index = PostgresHybridSearchIndex(session)
        index.add(
            SearchDocument(
                document_id=str(chunk_id),
                company_id=COMPANY_ID,
                applicant_id=APPLICANT_ID,
                source_id=chunk_id,
                text="장애 원인을 규명하고 재발을 방지한 경험",
                vector=_vector(1.0, 0.0),
                symbols=(),
                locator={"page_number": 1},
                ownership_confidence=1.0,
                invitation_id=INVITATION_ID,
                competency_model_version_id=VERSION_ID,
                criterion_id=None,
                document_type="submission_chunk",
                source_type="submission_chunk",
                embedding_model="amazon.titan-embed-text-v2:0",
                embedding_version="titan-v2",
            )
        )

        candidates = index.candidates(
            _context(),
            applicant_id=APPLICANT_ID,
            invitation_id=INVITATION_ID,
            competency_model_version_id=VERSION_ID,
            criterion_id=CRITERION_ID,
            query="장애 원인 규명",
            query_vector=_vector(1.0, 0.0),
            exact_symbol=None,
        )

    assert tuple(candidate.document.source_id for candidate in candidates) == (chunk_id,)


def test_embedding_filter_excludes_vectors_from_another_provider() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    gcp_id = UUID("00000000-0000-7000-8000-000000000021")
    aws_id = UUID("00000000-0000-7000-8000-000000000022")
    with Session(engine) as session:
        index = PostgresHybridSearchIndex(session)
        for source_id, model, version in (
            (gcp_id, "gemini-embedding-001", "vertex-gemini-v1"),
            (aws_id, "amazon.titan-embed-text-v2:0", "titan-v2"),
        ):
            index.add(
                SearchDocument(
                    document_id=str(source_id),
                    company_id=COMPANY_ID,
                    applicant_id=APPLICANT_ID,
                    source_id=source_id,
                    text="동일한 프로젝트 설명",
                    vector=_vector(1.0, 0.0),
                    symbols=(),
                    locator={"page_number": 1},
                    ownership_confidence=1.0,
                    invitation_id=INVITATION_ID,
                    competency_model_version_id=VERSION_ID,
                    embedding_model=model,
                    embedding_version=version,
                )
            )

        candidates = index.candidates(
            _context(),
            applicant_id=APPLICANT_ID,
            query="프로젝트",
            query_vector=_vector(1.0, 0.0),
            exact_symbol=None,
            embedding_model="gemini-embedding-001",
            embedding_version="vertex-gemini-v1",
        )

    assert tuple(candidate.document.source_id for candidate in candidates) == (gcp_id,)


def test_source_type_filter_returns_only_github_code() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    document_id = UUID("00000000-0000-7000-8000-000000000025")
    code_id = UUID("00000000-0000-7000-8000-000000000026")
    with Session(engine) as session:
        index = PostgresHybridSearchIndex(session)
        for source_id, source_type, locator in (
            (document_id, "submission_chunk", {"page_number": 1}),
            (code_id, "candidate_code_unit", {"path": "src/service.py"}),
        ):
            index.add(
                SearchDocument(
                    document_id=str(source_id),
                    company_id=COMPANY_ID,
                    applicant_id=APPLICANT_ID,
                    source_id=source_id,
                    text="프로젝트 서비스 구현",
                    vector=_vector(1.0, 0.0),
                    symbols=(),
                    locator=locator,
                    ownership_confidence=1.0,
                    invitation_id=INVITATION_ID,
                    competency_model_version_id=VERSION_ID,
                    source_type=source_type,
                )
            )

        candidates = index.candidates(
            _context(),
            applicant_id=APPLICANT_ID,
            query="프로젝트",
            query_vector=_vector(1.0, 0.0),
            exact_symbol=None,
            source_types=frozenset({"candidate_code_unit"}),
        )

    assert tuple(candidate.document.source_id for candidate in candidates) == (code_id,)


def test_debug_documents_return_extracted_text_for_the_current_invitation() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    chunk_id = UUID("00000000-0000-7000-8000-000000000030")
    code_id = UUID("00000000-0000-7000-8000-000000000031")
    with Session(engine) as session:
        index = PostgresHybridSearchIndex(session)
        index.add(
            SearchDocument(
                document_id=str(chunk_id),
                company_id=COMPANY_ID,
                applicant_id=APPLICANT_ID,
                source_id=chunk_id,
                text="지원자가 제출한 이력서에서 추출된 문단",
                vector=_vector(1.0, 0.0),
                symbols=(),
                locator={"page_number": 2, "section": "경력"},
                ownership_confidence=1.0,
                invitation_id=INVITATION_ID,
                competency_model_version_id=VERSION_ID,
                document_type="submission_chunk",
                source_type="submission_chunk",
                embedding_model="amazon.titan-embed-text-v2:0",
                embedding_version="titan-v2",
                material_type="resume",
            )
        )
        index.add(
            SearchDocument(
                document_id=str(code_id),
                company_id=COMPANY_ID,
                applicant_id=APPLICANT_ID,
                source_id=code_id,
                text=(
                    "process_order\n커밋: 주문 처리 개선\n파일: src/order.py\n"
                    "def process_order():\n    return True"
                ),
                vector=_vector(1.0, 0.0),
                symbols=("process_order",),
                locator={
                    "path": "src/order.py",
                    "symbol": "process_order",
                    "start_line": 10,
                    "end_line": 12,
                    "commit_sha": "abcdef1234567890",
                    "commit_message": "주문 처리 개선",
                },
                ownership_confidence=1.0,
                invitation_id=INVITATION_ID,
                competency_model_version_id=VERSION_ID,
                document_type="code_unit",
                source_type="candidate_code_unit",
                embedding_model="gemini-embedding-001",
                embedding_version="gemini-v1",
                path="src/order.py",
                symbol="process_order",
            )
        )

        documents = index.list_debug_documents(
            _context(),
            applicant_id=APPLICANT_ID,
            invitation_id=INVITATION_ID,
        )

    assert len(documents) == 2
    assert documents[0].text == "지원자가 제출한 이력서에서 추출된 문단"
    assert documents[0].material_type == "resume"
    assert documents[0].locator == {"page_number": 2, "section": "경력"}
    assert documents[1].source_type == "candidate_code_unit"
    assert documents[1].text.endswith("def process_order():\n    return True")
    assert documents[1].locator["path"] == "src/order.py"
