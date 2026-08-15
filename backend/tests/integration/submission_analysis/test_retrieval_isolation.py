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

COMPANY_A = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_B = UUID("00000000-0000-7000-8000-000000000002")
APPLICANT_A = UUID("00000000-0000-7000-8000-000000000003")
APPLICANT_B = UUID("00000000-0000-7000-8000-000000000004")


def tenant(company_id: UUID, applicant_id: UUID) -> TenantContext:
    return TenantContext(
        company_id=company_id,
        actor_type=ActorType.APPLICANT,
        actor_id=applicant_id,
        request_id=UUID("00000000-0000-7000-8000-000000000005"),
        trace_id="retrieval-isolation",
    )


def test_search_prefilters_company_and_applicant_before_ranking() -> None:
    index = InMemorySearchIndex()
    for document_id, company_id, applicant_id in (
        ("allowed", COMPANY_A, APPLICANT_A),
        ("other-applicant", COMPANY_A, APPLICANT_B),
        ("other-company", COMPANY_B, APPLICANT_A),
    ):
        index.add(
            SearchDocument(
                document_id=document_id,
                company_id=company_id,
                applicant_id=applicant_id,
                source_id=UUID("00000000-0000-7000-8000-000000000010"),
                text="결제 시스템 장애 복구",
                vector=(1.0, 0.0),
                symbols=(),
                locator={"page": 1},
                ownership_confidence=1,
            )
        )
    retriever = HybridRetriever(index, HybridRetrievalConfig())

    results = retriever.retrieve(
        tenant(COMPANY_A, APPLICANT_A),
        applicant_id=APPLICANT_A,
        query="결제 장애",
        query_vector=(1.0, 0.0),
        limit=10,
    )

    assert [result.document_id for result in results] == ["allowed"]
