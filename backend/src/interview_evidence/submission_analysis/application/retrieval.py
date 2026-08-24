from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from interview_evidence.shared.tenant import TenantContext
from interview_evidence.submission_analysis.adapters.search import SearchIndex


@dataclass(frozen=True, slots=True)
class HybridRetrievalConfig:
    vector_weight: float = 0.55
    lexical_weight: float = 0.3
    exact_symbol_boost: float = 0.8
    ownership_weight: float = 0.15


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    document_id: str
    source_id: UUID
    score: float
    locator: dict[str, object]
    excerpt: str
    source_type: str
    material_type: str | None
    ownership_confidence: float
    score_components: dict[str, float]


class HybridRetriever:
    def __init__(
        self,
        index: SearchIndex,
        config: HybridRetrievalConfig,
    ) -> None:
        self._index = index
        self._config = config

    def retrieve(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        query: str,
        query_vector: tuple[float, ...],
        limit: int,
        exact_symbol: str | None = None,
        invitation_id: UUID | None = None,
        competency_model_version_id: UUID | None = None,
        criterion_id: UUID | None = None,
        embedding_model: str | None = None,
        embedding_version: str | None = None,
        source_types: frozenset[str] | None = None,
    ) -> tuple[RetrievalResult, ...]:
        candidates = self._index.candidates(
            context,
            applicant_id=applicant_id,
            query=query,
            query_vector=query_vector,
            exact_symbol=exact_symbol,
            invitation_id=invitation_id,
            competency_model_version_id=competency_model_version_id,
            criterion_id=criterion_id,
            embedding_model=embedding_model,
            embedding_version=embedding_version,
            source_types=source_types,
        )
        results = [
            RetrievalResult(
                document_id=candidate.document.document_id,
                source_id=candidate.document.source_id,
                score=(
                    candidate.vector_score * self._config.vector_weight
                    + candidate.lexical_score * self._config.lexical_weight
                    + candidate.exact_symbol_score * self._config.exact_symbol_boost
                    + candidate.document.ownership_confidence * self._config.ownership_weight
                ),
                locator=candidate.document.locator,
                excerpt=candidate.document.text[:2000],
                source_type=candidate.document.source_type,
                material_type=candidate.document.material_type,
                ownership_confidence=candidate.document.ownership_confidence,
                score_components={
                    "vector": candidate.vector_score,
                    "lexical": candidate.lexical_score,
                    "exact_symbol": candidate.exact_symbol_score,
                    "ownership": candidate.document.ownership_confidence,
                },
            )
            for candidate in candidates
        ]
        return tuple(sorted(results, key=lambda result: result.score, reverse=True)[:limit])
