from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from interview_evidence.shared.tenant import TenantContext


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
    invitation_id: UUID | None = None
    competency_model_version_id: UUID | None = None
    criterion_id: UUID | None = None
    document_type: str = "submission_chunk"
    source_type: str = "submission_chunk"
    source_version: str = "1"
    content_hash: str = ""
    embedding_model: str = "unknown"
    embedding_version: str = "unknown"
    path: str | None = None
    symbol: str | None = None


@dataclass(frozen=True, slots=True)
class SearchCandidate:
    document: SearchDocument
    vector_score: float
    lexical_score: float
    exact_symbol_score: float


class SearchIndex(Protocol):
    def add(self, document: SearchDocument) -> None: ...

    def delete(self, context: TenantContext, document_id: str) -> bool: ...

    def candidates(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        query: str,
        query_vector: tuple[float, ...],
        exact_symbol: str | None,
        invitation_id: UUID | None = None,
        competency_model_version_id: UUID | None = None,
        criterion_id: UUID | None = None,
    ) -> tuple[SearchCandidate, ...]: ...


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right) or not left:
        return 0
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(
        sum(value * value for value in right)
    )
    if denominator == 0:
        return 0
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator
