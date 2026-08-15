from uuid import UUID

from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.adapters.search import (
    InMemorySearchIndex,
    SearchDocument,
)
from interview_evidence.submission_analysis.application.retrieval import (
    HybridRetrievalConfig,
    HybridRetriever,
)

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000002")


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.APPLICANT,
        actor_id=APPLICANT_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000003"),
        trace_id="hybrid-retrieval",
    )


def test_exact_symbol_and_lexical_match_can_outrank_vector_similarity() -> None:
    index = InMemorySearchIndex()
    index.add(
        SearchDocument(
            document_id="semantic",
            company_id=COMPANY_ID,
            applicant_id=APPLICANT_ID,
            source_id=UUID("00000000-0000-7000-8000-000000000010"),
            text="결제 장애를 줄인 경험",
            vector=(1.0, 0.0),
            symbols=(),
            locator={"page": 1},
            ownership_confidence=1,
        )
    )
    index.add(
        SearchDocument(
            document_id="symbol",
            company_id=COMPANY_ID,
            applicant_id=APPLICANT_ID,
            source_id=UUID("00000000-0000-7000-8000-000000000011"),
            text="calculate_total 결제 합계 계산",
            vector=(0.4, 0.6),
            symbols=("calculate_total",),
            locator={"path": "src/payment.py", "symbol": "calculate_total"},
            ownership_confidence=0.8,
        )
    )
    retriever = HybridRetriever(
        index,
        HybridRetrievalConfig(
            vector_weight=0.3,
            lexical_weight=0.3,
            exact_symbol_boost=1.0,
            ownership_weight=0.1,
        ),
    )

    results = retriever.retrieve(
        context(),
        applicant_id=APPLICANT_ID,
        query="calculate_total 결제",
        query_vector=(1.0, 0.0),
        exact_symbol="calculate_total",
        limit=2,
    )

    assert [result.document_id for result in results] == ["symbol", "semantic"]
    assert results[0].score_components["exact_symbol"] == 1.0
