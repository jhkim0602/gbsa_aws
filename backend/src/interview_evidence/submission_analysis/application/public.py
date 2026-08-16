from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from interview_evidence.shared.ids import CommandMeta
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.submission_analysis.application.deletion_targets import (
    SubmissionDeletionReceipt,
    SubmissionDeletionTarget,
    SubmissionDeletionTargets,
    SubmissionTargetDeleter,
)
from interview_evidence.submission_analysis.application.retrieval import (
    HybridRetriever,
    RetrievalResult,
)
from interview_evidence.submission_analysis.domain.strategy import InterviewStrategy
from interview_evidence.submission_analysis.repositories.postgres import (
    SubmissionRepository,
    TenantScopedSubmissionNotFound,
)


@dataclass(frozen=True, slots=True)
class SubmissionStatusSnapshot:
    submission_id: UUID
    source_type: str
    status: str
    failure_code: str | None
    impact_summary: str | None


@dataclass(frozen=True, slots=True)
class AnalysisStatusSnapshot:
    company_id: UUID
    invitation_id: UUID
    submissions: tuple[SubmissionStatusSnapshot, ...]
    strategy_ready: bool
    strategy_id: UUID | None
    strategy_version: int | None


@dataclass(frozen=True, slots=True)
class ResolvedSourceReference:
    source_id: UUID
    source_type: str
    locator: dict[str, object]
    content_hash: str | None
    ownership_confidence: float


@dataclass(frozen=True, slots=True)
class VerificationTargetSnapshot:
    verification_target_id: UUID
    criterion_id: UUID
    target_type: str
    objective: str
    missing_dimensions: tuple[str, ...]
    priority: int
    max_follow_ups: int
    source_reference_candidates: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class CandidateVerificationMapSnapshot:
    candidate_verification_map_id: UUID
    company_id: UUID
    applicant_id: UUID
    invitation_id: UUID
    competency_model_version_id: UUID
    criterion_version: int
    retrieval_version: str
    generation_version: str
    time_budget_seconds: int
    readiness_state: str
    targets: tuple[VerificationTargetSnapshot, ...]


class SubmissionAnalysisPublic:
    """Frozen Lane B boundary. No raw applicant source text crosses this facade."""

    def __init__(
        self,
        *,
        repository: SubmissionRepository,
        retriever: HybridRetriever,
        deletion_targets: SubmissionDeletionTargets,
        target_deleter: SubmissionTargetDeleter,
    ) -> None:
        self._repository = repository
        self._retriever = retriever
        self._deletion_targets = deletion_targets
        self._target_deleter = target_deleter

    def get_analysis_status(
        self,
        context: TenantContext,
        *,
        invitation_id: UUID,
    ) -> AnalysisStatusSnapshot:
        submissions = self._repository.list_submissions_for_invitation(context, invitation_id)
        strategy = self._repository.latest_strategy(context, invitation_id)
        return AnalysisStatusSnapshot(
            company_id=context.company_id,
            invitation_id=invitation_id,
            submissions=tuple(
                SubmissionStatusSnapshot(
                    submission_id=submission.submission_id,
                    source_type=submission.source_type.value,
                    status=submission.status.value,
                    failure_code=submission.failure_code,
                    impact_summary=submission.impact_summary,
                )
                for submission in submissions
            ),
            strategy_ready=(strategy is not None and strategy.status.value in {"ready", "partial"}),
            strategy_id=(strategy.interview_strategy_id if strategy is not None else None),
            strategy_version=(strategy.strategy_version if strategy is not None else None),
        )

    def get_strategy_snapshot(
        self,
        context: TenantContext,
        *,
        strategy_id: UUID,
    ) -> InterviewStrategy:
        return self._repository.get_strategy(context, strategy_id)

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
    ) -> tuple[RetrievalResult, ...]:
        if not config_version:
            raise ValueError("retrieval config version is required")
        return self._retriever.retrieve(
            context,
            applicant_id=applicant_id,
            invitation_id=invitation_id,
            competency_model_version_id=competency_model_version_id,
            criterion_id=criterion_id,
            query=query,
            query_vector=query_vector,
            exact_symbol=exact_symbol,
            limit=limit,
        )

    def get_verification_map(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        invitation_id: UUID,
        competency_model_version_id: UUID,
    ) -> CandidateVerificationMapSnapshot | None:
        verification_map = self._repository.latest_verification_map(
            context,
            applicant_id=applicant_id,
            invitation_id=invitation_id,
            competency_model_version_id=competency_model_version_id,
        )
        if verification_map is None:
            return None
        targets = self._repository.list_verification_targets(
            context,
            verification_map,
        )
        return CandidateVerificationMapSnapshot(
            candidate_verification_map_id=(verification_map.candidate_verification_map_id),
            company_id=verification_map.company_id,
            applicant_id=verification_map.applicant_id,
            invitation_id=verification_map.invitation_id,
            competency_model_version_id=(verification_map.competency_model_version_id),
            criterion_version=verification_map.criterion_version,
            retrieval_version=verification_map.retrieval_version,
            generation_version=verification_map.generation_version,
            time_budget_seconds=verification_map.time_budget_seconds,
            readiness_state=verification_map.readiness_state,
            targets=tuple(
                VerificationTargetSnapshot(
                    verification_target_id=target.verification_target_id,
                    criterion_id=target.criterion_id,
                    target_type=target.target_type.value,
                    objective=target.objective,
                    missing_dimensions=target.missing_dimensions,
                    priority=target.priority,
                    max_follow_ups=target.max_follow_ups,
                    source_reference_candidates=(target.source_reference_candidates),
                )
                for target in targets
            ),
        )

    def resolve_source_reference(
        self,
        context: TenantContext,
        *,
        source_id: UUID,
    ) -> ResolvedSourceReference:
        try:
            chunk = self._repository.get_chunk(context, source_id)
        except TenantScopedSubmissionNotFound:
            code_unit = self._repository.get_code_unit(context, source_id)
            commit = self._repository.get_git_commit_analysis(
                context, code_unit.git_commit_analysis_id
            )
            return ResolvedSourceReference(
                source_id=code_unit.code_unit_id,
                source_type="candidate_code_unit",
                locator={
                    "path": code_unit.path,
                    "symbol": code_unit.symbol,
                    "start_line": code_unit.current_line_range[0],
                    "end_line": code_unit.current_line_range[1],
                    "commit_sha": commit.commit_sha,
                },
                content_hash=None,
                ownership_confidence=commit.ownership_confidence,
            )
        else:
            return ResolvedSourceReference(
                source_id=chunk.chunk_id,
                source_type="submission_chunk",
                locator=chunk.source_location.model_dump(mode="json", exclude_none=True),
                content_hash=chunk.chunk_hash,
                ownership_confidence=1,
            )

    def enumerate_submission_deletion_targets(
        self,
        context: TenantContext,
        *,
        invitation_id: UUID,
        applicant_id: UUID,
    ) -> tuple[SubmissionDeletionTarget, ...]:
        return self._deletion_targets.enumerate_owned_targets(
            context,
            invitation_id=invitation_id,
            applicant_id=applicant_id,
        )

    def delete_submission_target(
        self,
        context: TenantContext,
        *,
        target: SubmissionDeletionTarget,
        meta: CommandMeta,
    ) -> SubmissionDeletionReceipt:
        return self._target_deleter.delete_and_verify(context, target, meta)
