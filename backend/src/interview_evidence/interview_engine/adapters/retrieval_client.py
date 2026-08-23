from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Protocol
from uuid import UUID

from interview_evidence.interview_engine.application.interview_plan import (
    InterviewStage,
)
from interview_evidence.shared.aws_clients.ports import TextEmbedder
from interview_evidence.shared.tenant import TenantContext

_STAGE_SOURCE_BOOSTS: Final = {
    InterviewStage.TECHNICAL: {"candidate_code_unit": 0.15},
    InterviewStage.PROJECT_DEEP_DIVE: {"candidate_code_unit": 0.4},
    InterviewStage.BEHAVIORAL: {"candidate_code_unit": -0.25},
}
_STAGE_MATERIAL_BOOSTS: Final = {
    InterviewStage.TECHNICAL: {
        "resume": 0.24,
        "career_description": 0.18,
        "portfolio": 0.12,
        "cover_letter": 0.06,
    },
    InterviewStage.PROJECT_DEEP_DIVE: {
        "projects": 0.35,
        "portfolio": 0.3,
        "career_description": 0.2,
        "resume": 0.1,
    },
    InterviewStage.BEHAVIORAL: {
        "cover_letter": 0.3,
        "career_description": 0.25,
        "resume": 0.18,
        "portfolio": 0.08,
    },
}
_COLLABORATION_TERMS: Final = (
    "협업",
    "코드 리뷰",
    "피드백",
    "갈등",
    "의사소통",
    "팀",
)


class RetrievalRecord(Protocol):
    source_id: UUID
    score: float
    locator: dict[str, object]
    ownership_confidence: float
    excerpt: str
    source_type: str
    material_type: str | None


class SubmissionRetrieval(Protocol):
    def retrieve_context(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        invitation_id: UUID,
        competency_model_version_id: UUID,
        query: str,
        query_vector: tuple[float, ...],
        criterion_id: UUID,
        config_version: str,
        limit: int,
        exact_symbol: str | None = None,
        embedding_model: str | None = None,
        embedding_version: str | None = None,
    ) -> tuple[RetrievalRecord, ...]: ...


@dataclass(frozen=True, slots=True)
class RetrievedContext:
    source_id: UUID
    score: float
    locator: dict[str, object]
    ownership_confidence: float
    excerpt: str
    source_type: str
    material_type: str | None = None


@dataclass(frozen=True, slots=True)
class RetrievalOutcome:
    hits: tuple[RetrievedContext, ...]
    degraded_mode: str | None = None
    user_message: str | None = None


class RetrievalClient:
    def __init__(
        self,
        provider: SubmissionRetrieval,
        *,
        embedder: TextEmbedder | None = None,
        limit: int = 5,
    ) -> None:
        self._provider = provider
        self._embedder = embedder
        self._limit = limit

    def retrieve(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        invitation_id: UUID,
        competency_model_version_id: UUID,
        session_id: UUID,
        query: str,
        query_vector: tuple[float, ...] | None,
        criterion_id: UUID,
        config_version: str,
        exact_symbol: str | None = None,
        interview_stage: InterviewStage = InterviewStage.TECHNICAL,
    ) -> RetrievalOutcome:
        del session_id
        try:
            active_query_vector = query_vector
            if active_query_vector is None:
                if self._embedder is None:
                    raise RuntimeError("semantic query embedder is unavailable")
                active_query_vector = self._embedder.embed(
                    context,
                    query,
                    dimensions=1024,
                )
            embedding_scope = (
                {
                    "embedding_model": self._embedder.model_id,
                    "embedding_version": self._embedder.embedding_version,
                }
                if self._embedder is not None
                else {}
            )
            results = self._provider.retrieve_context(
                context,
                applicant_id=applicant_id,
                invitation_id=invitation_id,
                competency_model_version_id=competency_model_version_id,
                query=query,
                query_vector=active_query_vector,
                criterion_id=criterion_id,
                config_version=config_version,
                limit=self._limit * 3,
                exact_symbol=exact_symbol,
                **embedding_scope,
            )
        except Exception:
            return RetrievalOutcome(
                hits=(),
                degraded_mode="search_fallback",
                user_message="관련 자료를 불러오지 못해 공통 평가 질문으로 진행합니다.",
            )
        if not results:
            return RetrievalOutcome(hits=(), degraded_mode="search_no_result")
        ranked = sorted(
            results,
            key=lambda result: (
                _stage_adjusted_score(result, interview_stage),
                result.score,
            ),
            reverse=True,
        )[: self._limit]
        return RetrievalOutcome(
            hits=tuple(
                RetrievedContext(
                    source_id=result.source_id,
                    score=_stage_adjusted_score(result, interview_stage),
                    locator=dict(result.locator),
                    ownership_confidence=result.ownership_confidence,
                    excerpt=str(getattr(result, "excerpt", "")),
                    source_type=str(
                        getattr(
                            result,
                            "source_type",
                            (
                                "candidate_code_unit"
                                if "path" in result.locator
                                else "submission_chunk"
                            ),
                        )
                    ),
                    material_type=_optional_string(getattr(result, "material_type", None)),
                )
                for result in ranked
            )
        )


def _stage_adjusted_score(record: RetrievalRecord, stage: InterviewStage) -> float:
    source_type = str(getattr(record, "source_type", "submission_chunk"))
    material_type = _optional_string(getattr(record, "material_type", None))
    source_boost = _STAGE_SOURCE_BOOSTS[stage].get(source_type, 0.0)
    if stage is InterviewStage.BEHAVIORAL and source_type == "candidate_code_unit":
        excerpt = str(getattr(record, "excerpt", "")).casefold()
        if any(term.casefold() in excerpt for term in _COLLABORATION_TERMS):
            source_boost = 0.05
    return (
        record.score
        + source_boost
        + _STAGE_MATERIAL_BOOSTS[stage].get(
            material_type or "",
            0.0,
        )
    )


def _optional_string(value: object) -> str | None:
    return str(value) if value is not None else None
