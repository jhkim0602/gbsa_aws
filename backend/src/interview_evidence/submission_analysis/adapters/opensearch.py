from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

import botocore.session  # type: ignore[import-untyped]
from botocore.auth import SigV4Auth  # type: ignore[import-untyped]
from botocore.awsrequest import AWSRequest  # type: ignore[import-untyped]

from interview_evidence.shared.tenant import TenantContext, require_tenant_context
from interview_evidence.submission_analysis.adapters.search import (
    SearchCandidate,
    SearchDocument,
)


class OpenSearchUnavailable(RuntimeError):
    """Sanitized OpenSearch Serverless failure."""


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    body: bytes


Transport = Callable[[str, str, bytes | None, dict[str, str]], HttpResponse]
Signer = Callable[[str, str, bytes | None], Mapping[str, str]]


class AwsOpenSearchIndex:
    def __init__(
        self,
        *,
        endpoint: str,
        index_name: str,
        region: str,
        transport: Transport | None = None,
        signer: Signer | None = None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._index_name = index_name
        self._region = region
        self._transport = transport or _http_transport
        self._signer = signer or self._sigv4_headers

    def add(self, document: SearchDocument) -> None:
        self._request(
            "PUT",
            f"/{self._index_name}/_doc/{document.document_id}",
            {
                "company_id": str(document.company_id),
                "applicant_id": str(document.applicant_id),
                "source_id": str(document.source_id),
                "text": document.text,
                "vector": list(document.vector),
                "symbols": list(document.symbols),
                "locator": document.locator,
                "ownership_confidence": document.ownership_confidence,
            },
        )

    def delete(self, context: TenantContext, document_id: str) -> bool:
        tenant = require_tenant_context(context)
        response = self._request(
            "POST",
            f"/{self._index_name}/_delete_by_query",
            {
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"company_id": str(tenant.company_id)}},
                            {"ids": {"values": [document_id]}},
                        ]
                    }
                }
            },
        )
        deleted = response.get("deleted", 0)
        return isinstance(deleted, int) and deleted >= 0

    def candidates(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        query: str,
        query_vector: tuple[float, ...],
        exact_symbol: str | None,
    ) -> tuple[SearchCandidate, ...]:
        tenant = require_tenant_context(context)
        if tenant.actor_type.value == "applicant" and tenant.actor_id != applicant_id:
            raise PermissionError("applicant scope mismatch")
        should: list[dict[str, object]] = [
            {"match": {"text": {"query": query}}},
            {
                "knn": {
                    "vector": {
                        "vector": list(query_vector),
                        "k": 50,
                    }
                }
            },
        ]
        if exact_symbol is not None:
            should.append({"term": {"symbols.keyword": exact_symbol}})
        response = self._request(
            "POST",
            f"/{self._index_name}/_search",
            {
                "size": 50,
                "_source": [
                    "company_id",
                    "applicant_id",
                    "source_id",
                    "text",
                    "vector",
                    "symbols",
                    "locator",
                    "ownership_confidence",
                ],
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"company_id": str(tenant.company_id)}},
                            {"term": {"applicant_id": str(applicant_id)}},
                        ],
                        "should": should,
                        "minimum_should_match": 1,
                    }
                },
            },
        )
        raw_hits = response.get("hits")
        if not isinstance(raw_hits, dict):
            return ()
        entries = raw_hits.get("hits")
        if not isinstance(entries, list):
            return ()
        return tuple(
            candidate
            for entry in entries
            if (candidate := _candidate(entry, query, query_vector, exact_symbol)) is not None
        )

    def _request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, object],
    ) -> dict[str, Any]:
        body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        url = f"{self._endpoint}{path}"
        headers = {
            "content-type": "application/json",
            **dict(self._signer(method, url, body)),
        }
        try:
            response = self._transport(method, url, body, headers)
        except Exception as error:
            raise OpenSearchUnavailable("search service unavailable") from error
        if response.status < 200 or response.status >= 300:
            raise OpenSearchUnavailable("search service request failed")
        if not response.body:
            return {}
        try:
            decoded = json.loads(response.body)
        except json.JSONDecodeError as error:
            raise OpenSearchUnavailable("search service response is invalid") from error
        if not isinstance(decoded, dict):
            raise OpenSearchUnavailable("search service response is invalid")
        return cast(dict[str, Any], decoded)

    def _sigv4_headers(
        self,
        method: str,
        url: str,
        body: bytes | None,
    ) -> Mapping[str, str]:
        credentials = botocore.session.get_session().get_credentials()
        if credentials is None:
            raise OpenSearchUnavailable("AWS credentials are unavailable")
        request = AWSRequest(
            method=method,
            url=url,
            data=body,
            headers={"content-type": "application/json"},
        )
        SigV4Auth(
            credentials.get_frozen_credentials(),
            "aoss",
            self._region,
        ).add_auth(request)
        return {str(key): str(value) for key, value in request.headers.items()}


def _candidate(
    raw: object,
    query: str,
    query_vector: tuple[float, ...],
    exact_symbol: str | None,
) -> SearchCandidate | None:
    if not isinstance(raw, dict):
        return None
    source = raw.get("_source")
    if not isinstance(source, dict):
        return None
    try:
        document = SearchDocument(
            document_id=str(raw["_id"]),
            company_id=UUID(str(source["company_id"])),
            applicant_id=UUID(str(source["applicant_id"])),
            source_id=UUID(str(source["source_id"])),
            text=str(source["text"]),
            vector=tuple(_as_float(value) for value in cast(list[object], source["vector"])),
            symbols=tuple(str(value) for value in cast(list[object], source["symbols"])),
            locator=cast(dict[str, object], source["locator"]),
            ownership_confidence=_as_float(source["ownership_confidence"]),
        )
    except (KeyError, TypeError, ValueError):
        return None
    terms = {term.casefold() for term in query.split() if term}
    document_terms = {term.casefold() for term in document.text.replace("_", " ").split() if term}
    lexical = len(terms & document_terms) / len(terms) if terms else 0.0
    exact = (
        1.0
        if exact_symbol is not None
        and exact_symbol.casefold() in {symbol.casefold() for symbol in document.symbols}
        else 0.0
    )
    return SearchCandidate(
        document=document,
        vector_score=_cosine(query_vector, document.vector),
        lexical_score=lexical,
        exact_symbol_score=exact,
    )


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(
        sum(value * value for value in right)
    )
    if denominator == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator


def _as_float(value: object) -> float:
    if isinstance(value, int | float | str):
        return float(value)
    raise TypeError("numeric search field is invalid")


def _http_transport(
    method: str,
    url: str,
    body: bytes | None,
    headers: dict[str, str],
) -> HttpResponse:
    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            return HttpResponse(status=response.status, body=response.read())
    except urllib.error.HTTPError as error:
        return HttpResponse(status=error.code, body=error.read())
