from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations
from uuid import UUID

from interview_evidence.shared.aws_clients.ports import TextEmbedder
from interview_evidence.shared.ids import Clock, new_uuid7
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.submission_analysis.application.retrieval import (
    HybridRetriever,
    RetrievalResult,
)
from interview_evidence.submission_analysis.domain.retrieval import (
    CandidateClaim,
    CandidateVerificationMap,
    ClaimConflict,
    VerificationTarget,
    VerificationTargetType,
)
from interview_evidence.submission_analysis.repositories.postgres import (
    SubmissionRepository,
)


@dataclass(frozen=True, slots=True)
class CriterionVerificationInput:
    criterion_id: UUID
    code: str
    name: str
    description: str
    required: bool
    weight: float
    observable_dimensions: tuple[str, ...]
    follow_up_directions: tuple[str, ...]
    max_follow_ups: int
    time_budget_seconds: int


@dataclass(frozen=True, slots=True)
class RequirementVerificationInput:
    statement: str
    criterion_code: str
    required: bool
    priority: int


class VerificationMapBuilder:
    def __init__(
        self,
        *,
        repository: SubmissionRepository,
        retriever: HybridRetriever,
        embedder: TextEmbedder,
        clock: Clock,
        retrieval_version: str = "aurora-hybrid-v1",
        generation_version: str = "verification-map-rules-v2-requirement-evidence-boost",
    ) -> None:
        self._repository = repository
        self._retriever = retriever
        self._embedder = embedder
        self._clock = clock
        self._retrieval_version = retrieval_version
        self._generation_version = generation_version

    def build(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        invitation_id: UUID,
        competency_model_version_id: UUID,
        criterion_version: int,
        criteria: tuple[CriterionVerificationInput, ...],
        requirements: tuple[RequirementVerificationInput, ...],
        material_version: str,
    ) -> CandidateVerificationMap:
        occurred_at = self._clock.now()
        targets: list[VerificationTarget] = []
        requirements_by_code: dict[str, list[RequirementVerificationInput]] = {}
        for requirement in requirements:
            requirements_by_code.setdefault(requirement.criterion_code, []).append(requirement)

        for criterion_index, criterion in enumerate(criteria):
            linked_requirements = requirements_by_code.get(criterion.code, [])
            query = " ".join(
                (
                    criterion.name,
                    criterion.description,
                    *criterion.observable_dimensions,
                )
            )
            base_results = self._retriever.retrieve(
                context,
                applicant_id=applicant_id,
                invitation_id=invitation_id,
                competency_model_version_id=competency_model_version_id,
                query=query,
                query_vector=self._embedder.embed(
                    context,
                    query,
                    dimensions=1024,
                ),
                criterion_id=criterion.criterion_id,
                embedding_model=self._embedder.model_id,
                embedding_version=self._embedder.embedding_version,
                limit=5,
            )
            considered_requirements = _bounded_requirements(linked_requirements)
            requirement_results: tuple[RetrievalResult, ...] = ()
            matched_requirements: tuple[RequirementVerificationInput, ...] = ()
            if considered_requirements:
                requirement_query = " ".join(
                    requirement.statement for requirement in considered_requirements
                )
                requirement_results = self._retriever.retrieve(
                    context,
                    applicant_id=applicant_id,
                    invitation_id=invitation_id,
                    competency_model_version_id=competency_model_version_id,
                    query=requirement_query,
                    query_vector=self._embedder.embed(
                        context,
                        requirement_query,
                        dimensions=1024,
                    ),
                    criterion_id=criterion.criterion_id,
                    embedding_model=self._embedder.model_id,
                    embedding_version=self._embedder.embedding_version,
                    limit=3,
                )
                matched_requirements = _matched_requirements(
                    considered_requirements,
                    requirement_results,
                )
            results = _merge_results(base_results, requirement_results, limit=5)
            claims = tuple(
                CandidateClaim(
                    candidate_claim_id=new_uuid7(occurred_at),
                    company_id=context.company_id,
                    applicant_id=applicant_id,
                    invitation_id=invitation_id,
                    competency_model_version_id=competency_model_version_id,
                    criterion_id=criterion.criterion_id,
                    claim_type="material_mention",
                    neutral_text=(f"자료에 {criterion.name} 관련 경험이 언급되어 있습니다."),
                    source_id=result.source_id,
                    locator=result.locator,
                    content_hash=sha256(result.excerpt.encode("utf-8")).hexdigest(),
                    extraction_version=self._generation_version,
                    confidence=max(0.0, min(1.0, result.score)),
                )
                for result in results
            )
            self._repository.save_candidate_claims(context, claims)
            conflicts = tuple(
                ClaimConflict(
                    claim_conflict_id=new_uuid7(occurred_at),
                    company_id=context.company_id,
                    applicant_id=applicant_id,
                    invitation_id=invitation_id,
                    criterion_id=criterion.criterion_id,
                    left_claim_id=left_claim.candidate_claim_id,
                    right_claim_id=right_claim.candidate_claim_id,
                    conflict_type="material_difference",
                    verification_objective=(
                        f"{criterion.name} 관련 자료 사이의 차이를 실제 답변으로 확인합니다."
                    ),
                )
                for (left_claim, left_result), (right_claim, right_result) in combinations(
                    zip(claims, results, strict=True),
                    2,
                )
                if _has_material_difference(left_result.excerpt, right_result.excerpt)
            )
            self._repository.save_claim_conflicts(context, conflicts)
            corpus = " ".join(result.excerpt.casefold() for result in results)
            missing = tuple(
                dimension
                for dimension in criterion.observable_dimensions
                if not _dimension_is_mentioned(dimension, corpus)
            )
            uncertain_ownership = any(result.ownership_confidence < 0.5 for result in results)
            if conflicts:
                target_type = VerificationTargetType.SOURCE_CONFLICT
                objective = conflicts[0].verification_objective
            elif not results:
                target_type = VerificationTargetType.NOT_MENTIONED
                objective = f"자료에 언급되지 않은 {criterion.name} 경험을 중립적으로 확인합니다."
            elif uncertain_ownership:
                target_type = VerificationTargetType.OWNERSHIP_UNCERTAIN
                objective = (
                    f"{criterion.name} 관련 작업에서 지원자가 직접 수행한 범위를 확인합니다."
                )
            elif missing:
                target_type = VerificationTargetType.DETAIL_MISSING
                objective = (
                    f"{criterion.name} 관련 자료에서 확인되지 않은 "
                    f"{', '.join(missing)} 내용을 실제 답변으로 확인합니다."
                )
            else:
                target_type = VerificationTargetType.CLAIM_FOUND
                objective = f"자료에 언급된 {criterion.name} 경험의 상황과 본인 행동을 확인합니다."
            matched_priority = _matched_requirement_priority(matched_requirements)
            targets.append(
                VerificationTarget(
                    verification_target_id=new_uuid7(occurred_at),
                    company_id=context.company_id,
                    applicant_id=applicant_id,
                    invitation_id=invitation_id,
                    competency_model_version_id=competency_model_version_id,
                    criterion_id=criterion.criterion_id,
                    target_type=target_type,
                    objective=objective,
                    missing_dimensions=missing,
                    priority=(
                        matched_priority if matched_priority is not None else 20 + criterion_index
                    ),
                    max_follow_ups=criterion.max_follow_ups,
                    source_reference_candidates=tuple(result.source_id for result in results),
                )
            )

        ordered = tuple(
            sorted(
                targets,
                key=lambda target: (target.priority, str(target.criterion_id)),
            )
        )
        self._repository.save_verification_targets(context, ordered)
        verification_map = CandidateVerificationMap(
            candidate_verification_map_id=new_uuid7(occurred_at),
            company_id=context.company_id,
            applicant_id=applicant_id,
            invitation_id=invitation_id,
            competency_model_version_id=competency_model_version_id,
            criterion_version=criterion_version,
            material_version=material_version,
            retrieval_version=self._retrieval_version,
            embedding_model=self._embedder.model_id,
            embedding_version=self._embedder.embedding_version,
            generation_version=self._generation_version,
            ordered_target_ids=tuple(target.verification_target_id for target in ordered),
            time_budget_seconds=sum(criterion.time_budget_seconds for criterion in criteria),
            readiness_state="ready" if ordered else "degraded",
            created_at=occurred_at,
        )
        return self._repository.save_verification_map(context, verification_map)


def _dimension_is_mentioned(dimension: str, corpus: str) -> bool:
    normalized = dimension.casefold().strip()
    if normalized and normalized in corpus:
        return True
    tokens = {
        token for token in normalized.replace("·", " ").replace("/", " ").split() if len(token) >= 2
    }
    return bool(tokens) and any(token in corpus for token in tokens)


def _has_material_difference(left: str, right: str) -> bool:
    negation_markers = ("않", "없", "미사용", "not ", "never ")
    left_normalized = left.casefold()
    right_normalized = right.casefold()
    left_negated = any(marker in left_normalized for marker in negation_markers)
    right_negated = any(marker in right_normalized for marker in negation_markers)
    return left_negated != right_negated


def _bounded_requirements(
    requirements: list[RequirementVerificationInput],
    *,
    max_query_characters: int = 3000,
) -> tuple[RequirementVerificationInput, ...]:
    selected: list[RequirementVerificationInput] = []
    used = 0
    for requirement in sorted(
        requirements,
        key=lambda item: (not item.required, item.priority, item.statement),
    ):
        statement = " ".join(requirement.statement.split())
        if not statement:
            continue
        remaining = max_query_characters - used
        if remaining <= 0:
            break
        if len(statement) > remaining and selected:
            break
        selected.append(requirement)
        used += min(len(statement), remaining) + 1
    return tuple(selected)


def _matched_requirements(
    requirements: tuple[RequirementVerificationInput, ...],
    results: tuple[RetrievalResult, ...],
) -> tuple[RequirementVerificationInput, ...]:
    related_results = tuple(result for result in results if _result_is_related(result))
    if not related_results:
        return ()
    lexical_matches = tuple(
        requirement
        for requirement in requirements
        if any(
            _statement_matches_excerpt(requirement.statement, result.excerpt)
            for result in related_results
        )
    )
    if lexical_matches:
        return lexical_matches
    return requirements[:1]


def _result_is_related(result: RetrievalResult) -> bool:
    semantic = result.score_components.get("vector", 0.0)
    lexical = result.score_components.get("lexical", 0.0)
    return result.score >= 0.35 and (semantic >= 0.35 or lexical > 0)


def _statement_matches_excerpt(statement: str, excerpt: str) -> bool:
    normalized_excerpt = excerpt.casefold()
    tokens = {
        token.strip(".,()[]{}:;·/\\")
        for token in statement.casefold().split()
        if len(token.strip(".,()[]{}:;·/\\")) >= 2
    }
    return bool(tokens) and any(token in normalized_excerpt for token in tokens)


def _matched_requirement_priority(
    requirements: tuple[RequirementVerificationInput, ...],
) -> int | None:
    if not requirements:
        return None
    required_priorities = [item.priority for item in requirements if item.required]
    if required_priorities:
        return min(required_priorities)
    return 5 + min(item.priority for item in requirements)


def _merge_results(
    *groups: tuple[RetrievalResult, ...],
    limit: int,
) -> tuple[RetrievalResult, ...]:
    by_document: dict[str, RetrievalResult] = {}
    for result in (result for group in groups for result in group):
        document_id = result.document_id
        current = by_document.get(document_id)
        if current is None or result.score > current.score:
            by_document[document_id] = result
    return tuple(
        sorted(
            by_document.values(),
            key=lambda result: result.score,
            reverse=True,
        )[:limit]
    )
