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
        generation_version: str = "verification-map-rules-v1",
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

        for criterion in criteria:
            linked_requirements = requirements_by_code.get(criterion.code, [])
            query = " ".join(
                (
                    criterion.name,
                    criterion.description,
                    *(item.statement for item in linked_requirements),
                    *criterion.observable_dimensions,
                )
            )
            results = self._retriever.retrieve(
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
            linked_priority = min(
                (item.priority for item in linked_requirements),
                default=5,
            )
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
                    priority=(linked_priority if criterion.required else linked_priority + 10),
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
