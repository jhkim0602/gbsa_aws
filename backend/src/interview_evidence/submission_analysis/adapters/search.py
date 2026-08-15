from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import UUID

from interview_evidence.shared.tenant import TenantContext, require_tenant_context


@dataclass(frozen=True, slots=True)
class SearchDocument:
    document_id: str
    company_id: UUID
    applicant_id: UUID
    source_id: UUID
    text: str
    vector: tuple[float, ...]
    symbols: tuple[str, ...]
    locator: dict[str, object]
    ownership_confidence: float


@dataclass(frozen=True, slots=True)
class SearchCandidate:
    document: SearchDocument
    vector_score: float
    lexical_score: float
    exact_symbol_score: float


class InMemorySearchIndex:
    def __init__(self) -> None:
        self._documents: dict[str, SearchDocument] = {}

    def add(self, document: SearchDocument) -> None:
        self._documents[document.document_id] = document

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
        if applicant_id != tenant.actor_id and tenant.actor_type.value == "applicant":
            raise PermissionError("applicant scope mismatch")
        query_terms = {term.casefold() for term in query.split() if term}
        matches: list[SearchCandidate] = []
        for document in self._documents.values():
            if document.company_id != tenant.company_id or document.applicant_id != applicant_id:
                continue
            document_terms = {
                term.casefold() for term in document.text.replace("_", " ").split() if term
            }
            lexical = len(query_terms & document_terms) / len(query_terms) if query_terms else 0
            exact = (
                1.0
                if exact_symbol is not None
                and exact_symbol.casefold() in {symbol.casefold() for symbol in document.symbols}
                else 0.0
            )
            matches.append(
                SearchCandidate(
                    document=document,
                    vector_score=_cosine(query_vector, document.vector),
                    lexical_score=lexical,
                    exact_symbol_score=exact,
                )
            )
        return tuple(matches)


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right) or not left:
        return 0
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(
        sum(value * value for value in right)
    )
    if denominator == 0:
        return 0
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator
