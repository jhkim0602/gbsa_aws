from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from interview_evidence.shared.tenant import TenantContext


class RetrievalRecord(Protocol):
    source_id: UUID
    score: float
    locator: dict[str, object]
    ownership_confidence: float


class SubmissionRetrieval(Protocol):
    def retrieve_context(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        query: str,
        query_vector: tuple[float, ...],
        criterion_id: UUID,
        config_version: str,
        limit: int,
        exact_symbol: str | None = None,
    ) -> tuple[RetrievalRecord, ...]: ...


@dataclass(frozen=True, slots=True)
class RetrievedContext:
    source_id: UUID
    score: float
    locator: dict[str, object]
    ownership_confidence: float


@dataclass(frozen=True, slots=True)
class RetrievalOutcome:
    hits: tuple[RetrievedContext, ...]
    degraded_mode: str | None = None
    user_message: str | None = None


class RetrievalClient:
    def __init__(self, provider: SubmissionRetrieval, *, limit: int = 5) -> None:
        self._provider = provider
        self._limit = limit

    def retrieve(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        session_id: UUID,
        query: str,
        query_vector: tuple[float, ...],
        criterion_id: UUID,
        config_version: str,
        exact_symbol: str | None = None,
    ) -> RetrievalOutcome:
        del session_id
        try:
            results = self._provider.retrieve_context(
                context,
                applicant_id=applicant_id,
                query=query,
                query_vector=query_vector,
                criterion_id=criterion_id,
                config_version=config_version,
                limit=self._limit,
                exact_symbol=exact_symbol,
            )
        except Exception:
            return RetrievalOutcome(
                hits=(),
                degraded_mode="search_fallback",
                user_message="관련 자료를 불러오지 못해 공통 평가 질문으로 진행합니다.",
            )
        if not results:
            return RetrievalOutcome(hits=(), degraded_mode="search_no_result")
        return RetrievalOutcome(
            hits=tuple(
                RetrievedContext(
                    source_id=result.source_id,
                    score=result.score,
                    locator=dict(result.locator),
                    ownership_confidence=result.ownership_confidence,
                )
                for result in results
            )
        )
