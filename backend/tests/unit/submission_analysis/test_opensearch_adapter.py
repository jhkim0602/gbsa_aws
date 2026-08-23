from __future__ import annotations

import json
from uuid import UUID

from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.adapters.opensearch import (
    AwsOpenSearchIndex,
    HttpResponse,
)
from interview_evidence.submission_analysis.adapters.search import SearchDocument

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000002")
SOURCE_ID = UUID("00000000-0000-7000-8000-000000000003")


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.APPLICANT,
        actor_id=APPLICANT_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000004"),
        trace_id="opensearch-test",
    )


def test_opensearch_adapter_always_filters_company_and_applicant() -> None:
    requests: list[tuple[str, str, bytes | None]] = []

    def transport(
        method: str,
        url: str,
        body: bytes | None,
        _headers: dict[str, str],
    ) -> HttpResponse:
        requests.append((method, url, body))
        if method == "POST":
            return HttpResponse(
                status=200,
                body=json.dumps(
                    {
                        "hits": {
                            "hits": [
                                {
                                    "_id": "doc-1",
                                    "_score": 0.9,
                                    "_source": {
                                        "company_id": str(COMPANY_ID),
                                        "applicant_id": str(APPLICANT_ID),
                                        "source_id": str(SOURCE_ID),
                                        "text": "PaymentService retry policy",
                                        "vector": [1.0, 0.0],
                                        "symbols": ["PaymentService"],
                                        "locator": {"path": "payment.py"},
                                        "ownership_confidence": 0.7,
                                    },
                                }
                            ]
                        }
                    }
                ).encode(),
            )
        return HttpResponse(status=200, body=b"{}")

    index = AwsOpenSearchIndex(
        endpoint="https://collection.example.aoss.amazonaws.com",
        index_name="candidate-source-v1",
        region="ap-northeast-2",
        transport=transport,
        signer=lambda _method, _url, _body: {},
    )
    document = SearchDocument(
        document_id="doc-1",
        company_id=COMPANY_ID,
        applicant_id=APPLICANT_ID,
        source_id=SOURCE_ID,
        text="PaymentService retry policy",
        vector=(1.0, 0.0),
        symbols=("PaymentService",),
        locator={"path": "payment.py"},
        ownership_confidence=0.7,
    )
    index.add(document)
    candidates = index.candidates(
        _context(),
        applicant_id=APPLICANT_ID,
        query="retry",
        query_vector=(1.0, 0.0),
        exact_symbol="PaymentService",
        embedding_model="gemini-embedding-001",
        embedding_version="vertex-gemini-v1",
    )
    assert candidates[0].document.source_id == SOURCE_ID
    search_body = json.loads(requests[1][2] or b"{}")
    filters = search_body["query"]["bool"]["filter"]
    assert {"term": {"company_id": str(COMPANY_ID)}} in filters
    assert {"term": {"applicant_id": str(APPLICANT_ID)}} in filters
    assert {"term": {"embedding_model.keyword": "gemini-embedding-001"}} in filters
    assert {"term": {"embedding_version.keyword": "vertex-gemini-v1"}} in filters


def test_opensearch_deletion_requeries_the_same_tenant_before_verifying() -> None:
    requests: list[dict[str, object]] = []

    def transport(
        _method: str,
        _url: str,
        body: bytes | None,
        _headers: dict[str, str],
    ) -> HttpResponse:
        payload = json.loads(body or b"{}")
        requests.append(payload)
        if len(requests) == 1:
            return HttpResponse(status=200, body=b'{"deleted":1}')
        return HttpResponse(status=200, body=b'{"count":0}')

    index = AwsOpenSearchIndex(
        endpoint="https://collection.example.aoss.amazonaws.com",
        index_name="candidate-source-v1",
        region="ap-northeast-2",
        transport=transport,
        signer=lambda _method, _url, _body: {},
    )

    assert index.delete_and_verify(_context(), "doc-1") is True
    assert requests[0]["query"]["bool"]["filter"] == [
        {"term": {"company_id": str(COMPANY_ID)}},
        {"ids": {"values": ["doc-1"]}},
    ]
    assert requests[1]["query"]["bool"]["filter"] == [
        {"term": {"company_id": str(COMPANY_ID)}},
        {"ids": {"values": ["doc-1"]}},
    ]


def test_opensearch_deletion_waits_until_the_document_is_absent() -> None:
    requests: list[dict[str, object]] = []

    def transport(
        _method: str,
        _url: str,
        body: bytes | None,
        _headers: dict[str, str],
    ) -> HttpResponse:
        requests.append(json.loads(body or b"{}"))
        if len(requests) == 1:
            return HttpResponse(status=200, body=b'{"deleted":1}')
        if len(requests) == 2:
            return HttpResponse(status=200, body=b'{"count":1}')
        return HttpResponse(status=200, body=b'{"count":0}')

    index = AwsOpenSearchIndex(
        endpoint="https://collection.example.aoss.amazonaws.com",
        index_name="candidate-source-v1",
        region="ap-northeast-2",
        transport=transport,
        signer=lambda _method, _url, _body: {},
        verification_attempts=2,
        verification_delay_seconds=0,
    )

    assert index.delete_and_verify(_context(), "doc-1") is True
    assert len(requests) == 3
