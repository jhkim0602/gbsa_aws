from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Protocol, TypeVar
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, Uuid, delete, select
from sqlalchemy.orm import (
    DeclarativeBase,
    InstrumentedAttribute,
    Mapped,
    Session,
    mapped_column,
)

from interview_evidence.shared.tenant import TenantContext, require_tenant_context
from interview_evidence.submission_analysis.domain.git_analysis import (
    CandidateCodeUnit,
    GitAnalysisStatus,
    GitCommitAnalysis,
    GitRepositoryAnalysis,
    OwnershipClass,
)
from interview_evidence.submission_analysis.domain.retrieval import (
    CandidateClaim,
    CandidateVerificationMap,
    ClaimConflict,
    VerificationTarget,
    VerificationTargetType,
)
from interview_evidence.submission_analysis.domain.source import (
    SourceLocation,
    SourceReferenceCandidate,
    SubmissionChunk,
)
from interview_evidence.submission_analysis.domain.strategy import (
    InterviewStrategy,
    StrategyStatus,
    VerificationPoint,
)
from interview_evidence.submission_analysis.domain.submission import (
    AnalysisStatus,
    SourceType,
    Submission,
    SubmissionAnalysis,
    SubmissionStatus,
)


class TenantScopedSubmissionNotFound(LookupError):
    """Raised without revealing another tenant or applicant's resources."""


class TenantOwned(Protocol):
    @property
    def company_id(self) -> UUID: ...


TenantOwnedT = TypeVar("TenantOwnedT", bound=TenantOwned)


class Base(DeclarativeBase):
    pass


class SubmissionRow(Base):
    __tablename__ = "submissions"

    submission_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    invitation_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    applicant_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    source_type: Mapped[str] = mapped_column(String(30))
    source_uri: Mapped[str] = mapped_column(String(4096))
    original_filename: Mapped[str | None] = mapped_column(String(255))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    byte_size: Mapped[int | None] = mapped_column(Integer)
    media_type: Mapped[str | None] = mapped_column(String(200))
    candidate_identity_inputs: Mapped[dict[str, list[str]] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    impact_summary: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    row_version: Mapped[int] = mapped_column(Integer)


class SubmissionAnalysisRow(Base):
    __tablename__ = "submission_analyses"

    analysis_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    submission_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    analysis_version: Mapped[int] = mapped_column(Integer)
    extractor_version: Mapped[str] = mapped_column(String(100))
    chunk_config_version: Mapped[str] = mapped_column(String(100))
    claims: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    conflicts: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    verification_points: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    impact_summary: Mapped[str | None] = mapped_column(String(2000))


class SubmissionChunkRow(Base):
    __tablename__ = "submission_chunks"

    chunk_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    applicant_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    submission_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    analysis_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    source_location: Mapped[dict[str, object]] = mapped_column(JSON)
    text_object_key: Mapped[str] = mapped_column(String(2048))
    source_hash: Mapped[str] = mapped_column(String(64))
    chunk_hash: Mapped[str] = mapped_column(String(64))
    embedding_model: Mapped[str] = mapped_column(String(200))
    embedding_version: Mapped[str] = mapped_column(String(100))
    index_document_id: Mapped[str] = mapped_column(String(512))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GitRepositoryAnalysisRow(Base):
    __tablename__ = "git_repository_analyses"

    repository_analysis_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    submission_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    repository_url: Mapped[str] = mapped_column(String(4096))
    default_branch: Mapped[str] = mapped_column(String(500))
    pinned_head_sha: Mapped[str] = mapped_column(String(40))
    candidate_identity_inputs: Mapped[dict[str, object]] = mapped_column(JSON)
    limits_applied: Mapped[dict[str, int]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30))


class GitCommitAnalysisRow(Base):
    __tablename__ = "git_commit_analyses"

    git_commit_analysis_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    repository_analysis_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    parent_sha: Mapped[str] = mapped_column(String(40))
    commit_sha: Mapped[str] = mapped_column(String(40))
    author_match_inputs: Mapped[dict[str, object]] = mapped_column(JSON)
    change_summary_object_key: Mapped[str] = mapped_column(String(2048))
    ownership_confidence: Mapped[float] = mapped_column(Float)
    ownership_class: Mapped[str] = mapped_column(String(30))
    ownership_explanation: Mapped[list[str]] = mapped_column(JSON)


class CandidateCodeUnitRow(Base):
    __tablename__ = "candidate_code_units"

    code_unit_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    git_commit_analysis_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    path: Mapped[str] = mapped_column(String(1000))
    language: Mapped[str] = mapped_column(String(100))
    symbol: Mapped[str] = mapped_column(String(500))
    original_line_range: Mapped[list[int]] = mapped_column(JSON)
    current_line_range: Mapped[list[int]] = mapped_column(JSON)
    authored_snapshot_key: Mapped[str] = mapped_column(String(2048))
    current_snapshot_key: Mapped[str] = mapped_column(String(2048))
    candidate_owned_regions: Mapped[list[list[int]]] = mapped_column(JSON)
    related_test_ids: Mapped[list[str]] = mapped_column(JSON)
    dependency_ids: Mapped[list[str]] = mapped_column(JSON)
    index_document_ids: Mapped[list[str]] = mapped_column(JSON)


class InterviewStrategyRow(Base):
    __tablename__ = "interview_strategies"

    interview_strategy_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    invitation_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    applicant_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    competency_model_version_id: Mapped[UUID] = mapped_column(Uuid)
    strategy_version: Mapped[int] = mapped_column(Integer)
    common_topics: Mapped[list[str]] = mapped_column(JSON)
    verification_points: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    follow_up_directions: Mapped[dict[str, list[str]]] = mapped_column(JSON)
    time_budget: Mapped[dict[str, int]] = mapped_column(JSON)
    required_evidence_plan: Mapped[dict[str, int]] = mapped_column(JSON)
    source_reference_candidates: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    model_config_version: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30))


class RetrievalDocumentRow(Base):
    __tablename__ = "retrieval_documents"

    retrieval_document_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    applicant_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    invitation_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    competency_model_version_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    criterion_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    document_type: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    source_version: Mapped[str] = mapped_column(String(100))
    content_hash: Mapped[str] = mapped_column(String(64))
    locator: Mapped[dict[str, object]] = mapped_column(JSON)
    protected_text: Mapped[str] = mapped_column(Text)
    search_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024))
    embedding_model: Mapped[str] = mapped_column(String(200))
    embedding_version: Mapped[str] = mapped_column(String(100))
    source_type: Mapped[str] = mapped_column(String(40))
    path: Mapped[str | None] = mapped_column(String(1000))
    symbol: Mapped[str | None] = mapped_column(String(500))
    ownership_confidence: Mapped[float | None] = mapped_column(Float)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CandidateClaimRow(Base):
    __tablename__ = "candidate_claims"

    candidate_claim_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    applicant_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    invitation_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    competency_model_version_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    criterion_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    claim_type: Mapped[str] = mapped_column(String(40))
    neutral_text: Mapped[str] = mapped_column(String(4000))
    source_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    locator: Mapped[dict[str, object]] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    extraction_version: Mapped[str] = mapped_column(String(100))
    confidence: Mapped[float] = mapped_column(Float)


class ClaimConflictRow(Base):
    __tablename__ = "claim_conflicts"

    claim_conflict_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    applicant_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    invitation_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    criterion_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    left_claim_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    right_claim_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    conflict_type: Mapped[str] = mapped_column(String(50))
    verification_objective: Mapped[str] = mapped_column(String(4000))


class VerificationTargetRow(Base):
    __tablename__ = "verification_targets"

    verification_target_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    applicant_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    invitation_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    competency_model_version_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    criterion_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    target_type: Mapped[str] = mapped_column(String(40))
    objective: Mapped[str] = mapped_column(String(4000))
    missing_dimensions: Mapped[list[str]] = mapped_column(JSON)
    priority: Mapped[int] = mapped_column(Integer)
    max_follow_ups: Mapped[int] = mapped_column(Integer)
    source_reference_candidates: Mapped[list[str]] = mapped_column(JSON)


class CandidateVerificationMapRow(Base):
    __tablename__ = "candidate_verification_maps"

    candidate_verification_map_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    applicant_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    invitation_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    competency_model_version_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    criterion_version: Mapped[int] = mapped_column(Integer)
    material_version: Mapped[str] = mapped_column(String(100))
    retrieval_version: Mapped[str] = mapped_column(String(100))
    embedding_model: Mapped[str] = mapped_column(String(200))
    embedding_version: Mapped[str] = mapped_column(String(100))
    generation_version: Mapped[str] = mapped_column(String(100))
    ordered_target_ids: Mapped[list[str]] = mapped_column(JSON)
    time_budget_seconds: Mapped[int] = mapped_column(Integer)
    readiness_state: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SubmissionRepository(Protocol):
    def save_submission(self, context: TenantContext, submission: Submission) -> Submission: ...
    def get_submission(self, context: TenantContext, submission_id: UUID) -> Submission: ...
    def list_submissions(
        self, context: TenantContext, applicant_id: UUID
    ) -> tuple[Submission, ...]: ...
    def list_submissions_for_invitation(
        self, context: TenantContext, invitation_id: UUID
    ) -> tuple[Submission, ...]: ...
    def save_analysis(
        self, context: TenantContext, analysis: SubmissionAnalysis
    ) -> SubmissionAnalysis: ...
    def list_analyses(
        self, context: TenantContext, submission_ids: frozenset[UUID]
    ) -> tuple[SubmissionAnalysis, ...]: ...
    def save_chunks(
        self, context: TenantContext, chunks: tuple[SubmissionChunk, ...]
    ) -> tuple[SubmissionChunk, ...]: ...
    def list_chunks(
        self, context: TenantContext, applicant_id: UUID
    ) -> tuple[SubmissionChunk, ...]: ...
    def get_chunk(self, context: TenantContext, chunk_id: UUID) -> SubmissionChunk: ...
    def save_git_repository_analysis(
        self, context: TenantContext, analysis: GitRepositoryAnalysis
    ) -> GitRepositoryAnalysis: ...
    def list_git_repository_analyses(
        self, context: TenantContext, submission_ids: frozenset[UUID]
    ) -> tuple[GitRepositoryAnalysis, ...]: ...
    def save_git_commit_analyses(
        self, context: TenantContext, analyses: tuple[GitCommitAnalysis, ...]
    ) -> tuple[GitCommitAnalysis, ...]: ...
    def list_git_commit_analyses(
        self, context: TenantContext, repository_analysis_ids: frozenset[UUID]
    ) -> tuple[GitCommitAnalysis, ...]: ...
    def save_code_units(
        self, context: TenantContext, units: tuple[CandidateCodeUnit, ...]
    ) -> tuple[CandidateCodeUnit, ...]: ...
    def list_code_units(
        self, context: TenantContext, commit_analysis_ids: frozenset[UUID]
    ) -> tuple[CandidateCodeUnit, ...]: ...
    def get_code_unit(self, context: TenantContext, code_unit_id: UUID) -> CandidateCodeUnit: ...
    def get_git_commit_analysis(
        self, context: TenantContext, commit_analysis_id: UUID
    ) -> GitCommitAnalysis: ...
    def save_strategy(
        self, context: TenantContext, strategy: InterviewStrategy
    ) -> InterviewStrategy: ...
    def latest_strategy(
        self, context: TenantContext, invitation_id: UUID
    ) -> InterviewStrategy | None: ...
    def get_strategy(self, context: TenantContext, strategy_id: UUID) -> InterviewStrategy: ...
    def save_candidate_claims(
        self,
        context: TenantContext,
        claims: tuple[CandidateClaim, ...],
    ) -> tuple[CandidateClaim, ...]: ...
    def list_candidate_claims(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        invitation_id: UUID,
    ) -> tuple[CandidateClaim, ...]: ...
    def save_claim_conflicts(
        self,
        context: TenantContext,
        conflicts: tuple[ClaimConflict, ...],
    ) -> tuple[ClaimConflict, ...]: ...
    def list_claim_conflicts(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        invitation_id: UUID,
    ) -> tuple[ClaimConflict, ...]: ...
    def save_verification_targets(
        self,
        context: TenantContext,
        targets: tuple[VerificationTarget, ...],
    ) -> tuple[VerificationTarget, ...]: ...
    def save_verification_map(
        self,
        context: TenantContext,
        verification_map: CandidateVerificationMap,
    ) -> CandidateVerificationMap: ...
    def get_verification_map(
        self,
        context: TenantContext,
        verification_map_id: UUID,
    ) -> CandidateVerificationMap: ...
    def latest_verification_map(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        invitation_id: UUID,
        competency_model_version_id: UUID,
    ) -> CandidateVerificationMap | None: ...
    def list_verification_maps(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        invitation_id: UUID,
    ) -> tuple[CandidateVerificationMap, ...]: ...
    def list_verification_targets(
        self,
        context: TenantContext,
        verification_map: CandidateVerificationMap,
    ) -> tuple[VerificationTarget, ...]: ...
    def list_retrieval_document_ids(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        invitation_id: UUID,
    ) -> tuple[UUID, ...]: ...
    def delete_and_verify_target(
        self,
        context: TenantContext,
        *,
        resource_type: str,
        resource_id: UUID,
    ) -> bool: ...


class InMemorySubmissionRepository:
    def __init__(self) -> None:
        self.submissions: dict[UUID, Submission] = {}
        self.analyses: dict[UUID, SubmissionAnalysis] = {}
        self.chunks: dict[UUID, SubmissionChunk] = {}
        self.git_repositories: dict[UUID, GitRepositoryAnalysis] = {}
        self.git_commits: dict[UUID, GitCommitAnalysis] = {}
        self.code_units: dict[UUID, CandidateCodeUnit] = {}
        self.strategies: dict[UUID, InterviewStrategy] = {}
        self.candidate_claims: dict[UUID, CandidateClaim] = {}
        self.claim_conflicts: dict[UUID, ClaimConflict] = {}
        self.verification_targets: dict[UUID, VerificationTarget] = {}
        self.verification_maps: dict[UUID, CandidateVerificationMap] = {}

    @staticmethod
    def _scoped(
        context: TenantContext,
        values: Mapping[UUID, TenantOwnedT],
        resource_id: UUID,
    ) -> TenantOwnedT:
        tenant = require_tenant_context(context)
        value = values.get(resource_id)
        if value is None or value.company_id != tenant.company_id:
            raise TenantScopedSubmissionNotFound("submission resource not found")
        return value

    def save_submission(self, context: TenantContext, submission: Submission) -> Submission:
        require_tenant_context(context).assert_company(submission.company_id)
        self.submissions[submission.submission_id] = submission
        return submission

    def get_submission(self, context: TenantContext, submission_id: UUID) -> Submission:
        return self._scoped(context, self.submissions, submission_id)

    def list_submissions(
        self, context: TenantContext, applicant_id: UUID
    ) -> tuple[Submission, ...]:
        tenant = require_tenant_context(context)
        if tenant.actor_type.value == "applicant" and tenant.actor_id != applicant_id:
            raise PermissionError("applicant scope mismatch")
        return tuple(
            value
            for value in self.submissions.values()
            if value.company_id == tenant.company_id and value.applicant_id == applicant_id
        )

    def list_submissions_for_invitation(
        self, context: TenantContext, invitation_id: UUID
    ) -> tuple[Submission, ...]:
        tenant = require_tenant_context(context)
        return tuple(
            value
            for value in self.submissions.values()
            if value.company_id == tenant.company_id and value.invitation_id == invitation_id
        )

    def save_analysis(
        self, context: TenantContext, analysis: SubmissionAnalysis
    ) -> SubmissionAnalysis:
        require_tenant_context(context).assert_company(analysis.company_id)
        self.get_submission(context, analysis.submission_id)
        self.analyses[analysis.analysis_id] = analysis
        return analysis

    def list_analyses(
        self, context: TenantContext, submission_ids: frozenset[UUID]
    ) -> tuple[SubmissionAnalysis, ...]:
        tenant = require_tenant_context(context)
        return tuple(
            analysis
            for analysis in self.analyses.values()
            if analysis.company_id == tenant.company_id and analysis.submission_id in submission_ids
        )

    def save_chunks(
        self, context: TenantContext, chunks: tuple[SubmissionChunk, ...]
    ) -> tuple[SubmissionChunk, ...]:
        for chunk in chunks:
            require_tenant_context(context).assert_company(chunk.company_id)
            self.get_submission(context, chunk.submission_id)
            self.chunks[chunk.chunk_id] = chunk
        return chunks

    def list_chunks(
        self, context: TenantContext, applicant_id: UUID
    ) -> tuple[SubmissionChunk, ...]:
        tenant = require_tenant_context(context)
        return tuple(
            chunk
            for chunk in self.chunks.values()
            if chunk.company_id == tenant.company_id and chunk.applicant_id == applicant_id
        )

    def get_chunk(self, context: TenantContext, chunk_id: UUID) -> SubmissionChunk:
        return self._scoped(context, self.chunks, chunk_id)

    def save_git_repository_analysis(
        self,
        context: TenantContext,
        analysis: GitRepositoryAnalysis,
    ) -> GitRepositoryAnalysis:
        require_tenant_context(context).assert_company(analysis.company_id)
        self.get_submission(context, analysis.submission_id)
        self.git_repositories[analysis.repository_analysis_id] = analysis
        return analysis

    def list_git_repository_analyses(
        self, context: TenantContext, submission_ids: frozenset[UUID]
    ) -> tuple[GitRepositoryAnalysis, ...]:
        tenant = require_tenant_context(context)
        return tuple(
            analysis
            for analysis in self.git_repositories.values()
            if analysis.company_id == tenant.company_id and analysis.submission_id in submission_ids
        )

    def save_git_commit_analyses(
        self,
        context: TenantContext,
        analyses: tuple[GitCommitAnalysis, ...],
    ) -> tuple[GitCommitAnalysis, ...]:
        for analysis in analyses:
            require_tenant_context(context).assert_company(analysis.company_id)
            self.git_commits[analysis.git_commit_analysis_id] = analysis
        return analyses

    def list_git_commit_analyses(
        self, context: TenantContext, repository_analysis_ids: frozenset[UUID]
    ) -> tuple[GitCommitAnalysis, ...]:
        tenant = require_tenant_context(context)
        return tuple(
            analysis
            for analysis in self.git_commits.values()
            if analysis.company_id == tenant.company_id
            and analysis.repository_analysis_id in repository_analysis_ids
        )

    def save_code_units(
        self,
        context: TenantContext,
        units: tuple[CandidateCodeUnit, ...],
    ) -> tuple[CandidateCodeUnit, ...]:
        for unit in units:
            require_tenant_context(context).assert_company(unit.company_id)
            self.code_units[unit.code_unit_id] = unit
        return units

    def list_code_units(
        self, context: TenantContext, commit_analysis_ids: frozenset[UUID]
    ) -> tuple[CandidateCodeUnit, ...]:
        tenant = require_tenant_context(context)
        return tuple(
            unit
            for unit in self.code_units.values()
            if unit.company_id == tenant.company_id
            and unit.git_commit_analysis_id in commit_analysis_ids
        )

    def get_code_unit(self, context: TenantContext, code_unit_id: UUID) -> CandidateCodeUnit:
        return self._scoped(context, self.code_units, code_unit_id)

    def get_git_commit_analysis(
        self, context: TenantContext, commit_analysis_id: UUID
    ) -> GitCommitAnalysis:
        return self._scoped(context, self.git_commits, commit_analysis_id)

    def save_strategy(
        self, context: TenantContext, strategy: InterviewStrategy
    ) -> InterviewStrategy:
        require_tenant_context(context).assert_company(strategy.company_id)
        self.strategies[strategy.interview_strategy_id] = strategy
        return strategy

    def latest_strategy(
        self, context: TenantContext, invitation_id: UUID
    ) -> InterviewStrategy | None:
        tenant = require_tenant_context(context)
        matches = [
            strategy
            for strategy in self.strategies.values()
            if strategy.company_id == tenant.company_id and strategy.invitation_id == invitation_id
        ]
        return max(matches, key=lambda value: value.strategy_version, default=None)

    def get_strategy(self, context: TenantContext, strategy_id: UUID) -> InterviewStrategy:
        return self._scoped(context, self.strategies, strategy_id)

    def save_candidate_claims(
        self,
        context: TenantContext,
        claims: tuple[CandidateClaim, ...],
    ) -> tuple[CandidateClaim, ...]:
        tenant = require_tenant_context(context)
        for claim in claims:
            tenant.assert_company(claim.company_id)
            self.candidate_claims[claim.candidate_claim_id] = claim
        return claims

    def list_candidate_claims(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        invitation_id: UUID,
    ) -> tuple[CandidateClaim, ...]:
        tenant = require_tenant_context(context)
        return tuple(
            claim
            for claim in self.candidate_claims.values()
            if claim.company_id == tenant.company_id
            and claim.applicant_id == applicant_id
            and claim.invitation_id == invitation_id
        )

    def save_claim_conflicts(
        self,
        context: TenantContext,
        conflicts: tuple[ClaimConflict, ...],
    ) -> tuple[ClaimConflict, ...]:
        tenant = require_tenant_context(context)
        for conflict in conflicts:
            tenant.assert_company(conflict.company_id)
            self.claim_conflicts[conflict.claim_conflict_id] = conflict
        return conflicts

    def list_claim_conflicts(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        invitation_id: UUID,
    ) -> tuple[ClaimConflict, ...]:
        tenant = require_tenant_context(context)
        return tuple(
            conflict
            for conflict in self.claim_conflicts.values()
            if conflict.company_id == tenant.company_id
            and conflict.applicant_id == applicant_id
            and conflict.invitation_id == invitation_id
        )

    def save_verification_targets(
        self,
        context: TenantContext,
        targets: tuple[VerificationTarget, ...],
    ) -> tuple[VerificationTarget, ...]:
        tenant = require_tenant_context(context)
        for target in targets:
            tenant.assert_company(target.company_id)
            self.verification_targets[target.verification_target_id] = target
        return targets

    def save_verification_map(
        self,
        context: TenantContext,
        verification_map: CandidateVerificationMap,
    ) -> CandidateVerificationMap:
        require_tenant_context(context).assert_company(verification_map.company_id)
        self.verification_maps[verification_map.candidate_verification_map_id] = verification_map
        return verification_map

    def get_verification_map(
        self,
        context: TenantContext,
        verification_map_id: UUID,
    ) -> CandidateVerificationMap:
        return self._scoped(context, self.verification_maps, verification_map_id)

    def latest_verification_map(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        invitation_id: UUID,
        competency_model_version_id: UUID,
    ) -> CandidateVerificationMap | None:
        tenant = require_tenant_context(context)
        matches = (
            verification_map
            for verification_map in self.verification_maps.values()
            if verification_map.company_id == tenant.company_id
            and verification_map.applicant_id == applicant_id
            and verification_map.invitation_id == invitation_id
            and verification_map.competency_model_version_id == competency_model_version_id
        )
        return max(matches, key=lambda item: item.created_at, default=None)

    def list_verification_maps(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        invitation_id: UUID,
    ) -> tuple[CandidateVerificationMap, ...]:
        tenant = require_tenant_context(context)
        return tuple(
            verification_map
            for verification_map in self.verification_maps.values()
            if verification_map.company_id == tenant.company_id
            and verification_map.applicant_id == applicant_id
            and verification_map.invitation_id == invitation_id
        )

    def list_verification_targets(
        self,
        context: TenantContext,
        verification_map: CandidateVerificationMap,
    ) -> tuple[VerificationTarget, ...]:
        require_tenant_context(context).assert_company(verification_map.company_id)
        return tuple(
            self._scoped(context, self.verification_targets, target_id)
            for target_id in verification_map.ordered_target_ids
        )

    def list_retrieval_document_ids(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        invitation_id: UUID,
    ) -> tuple[UUID, ...]:
        require_tenant_context(context)
        return ()

    def delete_and_verify_target(
        self,
        context: TenantContext,
        *,
        resource_type: str,
        resource_id: UUID,
    ) -> bool:
        tenant = require_tenant_context(context)
        if resource_type == "submission":
            submission = self.submissions.get(resource_id)
            if submission is not None:
                tenant.assert_company(submission.company_id)
                self.submissions.pop(resource_id, None)
            return resource_id not in self.submissions
        if resource_type == "submission_analysis":
            analysis = self.analyses.get(resource_id)
            if analysis is not None:
                tenant.assert_company(analysis.company_id)
                self.analyses.pop(resource_id, None)
            return resource_id not in self.analyses
        if resource_type == "submission_chunk":
            chunk = self.chunks.get(resource_id)
            if chunk is not None:
                tenant.assert_company(chunk.company_id)
                self.chunks.pop(resource_id, None)
            return resource_id not in self.chunks
        if resource_type == "git_repository_analysis":
            repository_analysis = self.git_repositories.get(resource_id)
            if repository_analysis is not None:
                tenant.assert_company(repository_analysis.company_id)
                self.git_repositories.pop(resource_id, None)
            return resource_id not in self.git_repositories
        if resource_type == "git_commit_analysis":
            commit_analysis = self.git_commits.get(resource_id)
            if commit_analysis is not None:
                tenant.assert_company(commit_analysis.company_id)
                self.git_commits.pop(resource_id, None)
            return resource_id not in self.git_commits
        if resource_type == "candidate_code_unit":
            code_unit = self.code_units.get(resource_id)
            if code_unit is not None:
                tenant.assert_company(code_unit.company_id)
                self.code_units.pop(resource_id, None)
            return resource_id not in self.code_units
        if resource_type == "interview_strategy":
            strategy = self.strategies.get(resource_id)
            if strategy is not None:
                tenant.assert_company(strategy.company_id)
                self.strategies.pop(resource_id, None)
            return resource_id not in self.strategies
        if resource_type == "candidate_claim":
            claim = self.candidate_claims.get(resource_id)
            if claim is not None:
                tenant.assert_company(claim.company_id)
                self.candidate_claims.pop(resource_id, None)
            return resource_id not in self.candidate_claims
        if resource_type == "claim_conflict":
            conflict = self.claim_conflicts.get(resource_id)
            if conflict is not None:
                tenant.assert_company(conflict.company_id)
                self.claim_conflicts.pop(resource_id, None)
            return resource_id not in self.claim_conflicts
        if resource_type == "verification_target":
            target = self.verification_targets.get(resource_id)
            if target is not None:
                tenant.assert_company(target.company_id)
                self.verification_targets.pop(resource_id, None)
            return resource_id not in self.verification_targets
        if resource_type == "candidate_verification_map":
            verification_map = self.verification_maps.get(resource_id)
            if verification_map is not None:
                tenant.assert_company(verification_map.company_id)
                self.verification_maps.pop(resource_id, None)
            return resource_id not in self.verification_maps
        raise ValueError("unsupported submission deletion target")


class SqlAlchemySubmissionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _delete_row(
        self,
        context: TenantContext,
        *,
        row_type: type[Base],
        company_column: InstrumentedAttribute[UUID],
        id_column: InstrumentedAttribute[UUID],
        resource_id: UUID,
    ) -> bool:
        tenant = require_tenant_context(context)
        predicate = (
            company_column == tenant.company_id,
            id_column == resource_id,
        )
        self._session.execute(delete(row_type).where(*predicate))
        self._session.flush()
        return self._session.scalar(select(row_type).where(*predicate)) is None

    def save_submission(self, context: TenantContext, submission: Submission) -> Submission:
        require_tenant_context(context).assert_company(submission.company_id)
        self._session.merge(
            SubmissionRow(
                submission_id=submission.submission_id,
                company_id=submission.company_id,
                invitation_id=submission.invitation_id,
                applicant_id=submission.applicant_id,
                source_type=submission.source_type.value,
                source_uri=submission.source_uri,
                original_filename=submission.original_filename,
                content_hash=submission.content_hash,
                byte_size=submission.byte_size,
                media_type=submission.media_type,
                candidate_identity_inputs=(
                    {
                        key: list(values)
                        for key, values in submission.candidate_identity_inputs.items()
                    }
                    if submission.candidate_identity_inputs is not None
                    else None
                ),
                status=submission.status.value,
                failure_code=submission.failure_code,
                impact_summary=submission.impact_summary,
                created_at=submission.created_at,
                row_version=submission.row_version,
            )
        )
        self._session.flush()
        return submission

    def get_submission(self, context: TenantContext, submission_id: UUID) -> Submission:
        tenant = require_tenant_context(context)
        row = self._session.scalar(
            select(SubmissionRow).where(
                SubmissionRow.company_id == tenant.company_id,
                SubmissionRow.submission_id == submission_id,
            )
        )
        if row is None:
            raise TenantScopedSubmissionNotFound("submission resource not found")
        return Submission(
            submission_id=row.submission_id,
            company_id=row.company_id,
            invitation_id=row.invitation_id,
            applicant_id=row.applicant_id,
            source_type=SourceType(row.source_type),
            source_uri=row.source_uri,
            original_filename=row.original_filename,
            content_hash=row.content_hash,
            byte_size=row.byte_size,
            media_type=row.media_type,
            candidate_identity_inputs=(
                {
                    key: tuple(str(item) for item in values)
                    for key, values in row.candidate_identity_inputs.items()
                }
                if row.candidate_identity_inputs is not None
                else None
            ),
            status=SubmissionStatus(row.status),
            failure_code=row.failure_code,
            impact_summary=row.impact_summary,
            created_at=row.created_at,
            row_version=row.row_version,
        )

    def list_submissions(
        self, context: TenantContext, applicant_id: UUID
    ) -> tuple[Submission, ...]:
        tenant = require_tenant_context(context)
        rows = self._session.scalars(
            select(SubmissionRow).where(
                SubmissionRow.company_id == tenant.company_id,
                SubmissionRow.applicant_id == applicant_id,
            )
        ).all()
        return tuple(self.get_submission(context, row.submission_id) for row in rows)

    def list_submissions_for_invitation(
        self, context: TenantContext, invitation_id: UUID
    ) -> tuple[Submission, ...]:
        tenant = require_tenant_context(context)
        rows = self._session.scalars(
            select(SubmissionRow).where(
                SubmissionRow.company_id == tenant.company_id,
                SubmissionRow.invitation_id == invitation_id,
            )
        ).all()
        return tuple(self.get_submission(context, row.submission_id) for row in rows)

    def save_analysis(
        self, context: TenantContext, analysis: SubmissionAnalysis
    ) -> SubmissionAnalysis:
        require_tenant_context(context).assert_company(analysis.company_id)
        self._session.merge(
            SubmissionAnalysisRow(
                analysis_id=analysis.analysis_id,
                company_id=analysis.company_id,
                submission_id=analysis.submission_id,
                analysis_version=analysis.analysis_version,
                extractor_version=analysis.extractor_version,
                chunk_config_version=analysis.chunk_config_version,
                claims=list(analysis.claims),
                conflicts=list(analysis.conflicts),
                verification_points=list(analysis.verification_points),
                status=analysis.status.value,
                created_at=analysis.created_at,
                failure_code=analysis.failure_code,
                impact_summary=analysis.impact_summary,
            )
        )
        self._session.flush()
        return analysis

    def list_analyses(
        self, context: TenantContext, submission_ids: frozenset[UUID]
    ) -> tuple[SubmissionAnalysis, ...]:
        if not submission_ids:
            return ()
        tenant = require_tenant_context(context)
        rows = self._session.scalars(
            select(SubmissionAnalysisRow).where(
                SubmissionAnalysisRow.company_id == tenant.company_id,
                SubmissionAnalysisRow.submission_id.in_(submission_ids),
            )
        ).all()
        return tuple(self._analysis_from_row(row) for row in rows)

    def save_chunks(
        self, context: TenantContext, chunks: tuple[SubmissionChunk, ...]
    ) -> tuple[SubmissionChunk, ...]:
        for chunk in chunks:
            require_tenant_context(context).assert_company(chunk.company_id)
            self._session.merge(
                SubmissionChunkRow(
                    chunk_id=chunk.chunk_id,
                    company_id=chunk.company_id,
                    applicant_id=chunk.applicant_id,
                    submission_id=chunk.submission_id,
                    analysis_id=chunk.analysis_id,
                    source_location=chunk.source_location.model_dump(
                        mode="json", exclude_none=True
                    ),
                    text_object_key=chunk.text_object_key,
                    source_hash=chunk.source_hash,
                    chunk_hash=chunk.chunk_hash,
                    embedding_model=chunk.embedding_model,
                    embedding_version=chunk.embedding_version,
                    index_document_id=chunk.index_document_id,
                    deleted_at=chunk.deleted_at,
                )
            )
        self._session.flush()
        return chunks

    def list_chunks(
        self, context: TenantContext, applicant_id: UUID
    ) -> tuple[SubmissionChunk, ...]:
        tenant = require_tenant_context(context)
        rows = self._session.scalars(
            select(SubmissionChunkRow).where(
                SubmissionChunkRow.company_id == tenant.company_id,
                SubmissionChunkRow.applicant_id == applicant_id,
            )
        ).all()
        return tuple(
            SubmissionChunk(
                chunk_id=row.chunk_id,
                company_id=row.company_id,
                applicant_id=row.applicant_id,
                submission_id=row.submission_id,
                analysis_id=row.analysis_id,
                source_location=SourceLocation.model_validate(row.source_location),
                text_object_key=row.text_object_key,
                source_hash=row.source_hash,
                chunk_hash=row.chunk_hash,
                embedding_model=row.embedding_model,
                embedding_version=row.embedding_version,
                index_document_id=row.index_document_id,
                deleted_at=row.deleted_at,
            )
            for row in rows
        )

    def get_chunk(self, context: TenantContext, chunk_id: UUID) -> SubmissionChunk:
        tenant = require_tenant_context(context)
        row = self._session.scalar(
            select(SubmissionChunkRow).where(
                SubmissionChunkRow.company_id == tenant.company_id,
                SubmissionChunkRow.chunk_id == chunk_id,
            )
        )
        if row is None:
            raise TenantScopedSubmissionNotFound("submission resource not found")
        return SubmissionChunk(
            chunk_id=row.chunk_id,
            company_id=row.company_id,
            applicant_id=row.applicant_id,
            submission_id=row.submission_id,
            analysis_id=row.analysis_id,
            source_location=SourceLocation.model_validate(row.source_location),
            text_object_key=row.text_object_key,
            source_hash=row.source_hash,
            chunk_hash=row.chunk_hash,
            embedding_model=row.embedding_model,
            embedding_version=row.embedding_version,
            index_document_id=row.index_document_id,
            deleted_at=row.deleted_at,
        )

    def save_git_repository_analysis(
        self,
        context: TenantContext,
        analysis: GitRepositoryAnalysis,
    ) -> GitRepositoryAnalysis:
        require_tenant_context(context).assert_company(analysis.company_id)
        self._session.merge(
            GitRepositoryAnalysisRow(
                repository_analysis_id=analysis.repository_analysis_id,
                company_id=analysis.company_id,
                submission_id=analysis.submission_id,
                repository_url=analysis.repository_url,
                default_branch=analysis.default_branch,
                pinned_head_sha=analysis.pinned_head_sha,
                candidate_identity_inputs=analysis.candidate_identity_inputs,
                limits_applied=analysis.limits_applied,
                status=analysis.status.value,
            )
        )
        self._session.flush()
        return analysis

    def list_git_repository_analyses(
        self, context: TenantContext, submission_ids: frozenset[UUID]
    ) -> tuple[GitRepositoryAnalysis, ...]:
        if not submission_ids:
            return ()
        tenant = require_tenant_context(context)
        rows = self._session.scalars(
            select(GitRepositoryAnalysisRow).where(
                GitRepositoryAnalysisRow.company_id == tenant.company_id,
                GitRepositoryAnalysisRow.submission_id.in_(submission_ids),
            )
        ).all()
        return tuple(self._git_repository_from_row(row) for row in rows)

    def save_git_commit_analyses(
        self,
        context: TenantContext,
        analyses: tuple[GitCommitAnalysis, ...],
    ) -> tuple[GitCommitAnalysis, ...]:
        for analysis in analyses:
            require_tenant_context(context).assert_company(analysis.company_id)
            self._session.merge(
                GitCommitAnalysisRow(
                    git_commit_analysis_id=analysis.git_commit_analysis_id,
                    company_id=analysis.company_id,
                    repository_analysis_id=analysis.repository_analysis_id,
                    parent_sha=analysis.parent_sha,
                    commit_sha=analysis.commit_sha,
                    author_match_inputs=analysis.author_match_inputs,
                    change_summary_object_key=analysis.change_summary_object_key,
                    ownership_confidence=analysis.ownership_confidence,
                    ownership_class=analysis.ownership_class.value,
                    ownership_explanation=list(analysis.ownership_explanation),
                )
            )
        self._session.flush()
        return analyses

    def list_git_commit_analyses(
        self, context: TenantContext, repository_analysis_ids: frozenset[UUID]
    ) -> tuple[GitCommitAnalysis, ...]:
        if not repository_analysis_ids:
            return ()
        tenant = require_tenant_context(context)
        rows = self._session.scalars(
            select(GitCommitAnalysisRow).where(
                GitCommitAnalysisRow.company_id == tenant.company_id,
                GitCommitAnalysisRow.repository_analysis_id.in_(repository_analysis_ids),
            )
        ).all()
        return tuple(self._git_commit_from_row(row) for row in rows)

    def save_code_units(
        self,
        context: TenantContext,
        units: tuple[CandidateCodeUnit, ...],
    ) -> tuple[CandidateCodeUnit, ...]:
        for unit in units:
            require_tenant_context(context).assert_company(unit.company_id)
            self._session.merge(
                CandidateCodeUnitRow(
                    code_unit_id=unit.code_unit_id,
                    company_id=unit.company_id,
                    git_commit_analysis_id=unit.git_commit_analysis_id,
                    path=unit.path,
                    language=unit.language,
                    symbol=unit.symbol,
                    original_line_range=list(unit.original_line_range),
                    current_line_range=list(unit.current_line_range),
                    authored_snapshot_key=unit.authored_snapshot_key,
                    current_snapshot_key=unit.current_snapshot_key,
                    candidate_owned_regions=[
                        list(region) for region in unit.candidate_owned_regions
                    ],
                    related_test_ids=list(unit.related_test_ids),
                    dependency_ids=list(unit.dependency_ids),
                    index_document_ids=list(unit.index_document_ids),
                )
            )
        self._session.flush()
        return units

    def list_code_units(
        self, context: TenantContext, commit_analysis_ids: frozenset[UUID]
    ) -> tuple[CandidateCodeUnit, ...]:
        if not commit_analysis_ids:
            return ()
        tenant = require_tenant_context(context)
        rows = self._session.scalars(
            select(CandidateCodeUnitRow).where(
                CandidateCodeUnitRow.company_id == tenant.company_id,
                CandidateCodeUnitRow.git_commit_analysis_id.in_(commit_analysis_ids),
            )
        ).all()
        return tuple(self._code_unit_from_row(row) for row in rows)

    def get_code_unit(self, context: TenantContext, code_unit_id: UUID) -> CandidateCodeUnit:
        tenant = require_tenant_context(context)
        row = self._session.scalar(
            select(CandidateCodeUnitRow).where(
                CandidateCodeUnitRow.company_id == tenant.company_id,
                CandidateCodeUnitRow.code_unit_id == code_unit_id,
            )
        )
        if row is None:
            raise TenantScopedSubmissionNotFound("submission resource not found")
        return self._code_unit_from_row(row)

    def get_git_commit_analysis(
        self, context: TenantContext, commit_analysis_id: UUID
    ) -> GitCommitAnalysis:
        tenant = require_tenant_context(context)
        row = self._session.scalar(
            select(GitCommitAnalysisRow).where(
                GitCommitAnalysisRow.company_id == tenant.company_id,
                GitCommitAnalysisRow.git_commit_analysis_id == commit_analysis_id,
            )
        )
        if row is None:
            raise TenantScopedSubmissionNotFound("submission resource not found")
        return self._git_commit_from_row(row)

    def save_strategy(
        self, context: TenantContext, strategy: InterviewStrategy
    ) -> InterviewStrategy:
        require_tenant_context(context).assert_company(strategy.company_id)
        self._session.merge(
            InterviewStrategyRow(
                interview_strategy_id=strategy.interview_strategy_id,
                company_id=strategy.company_id,
                invitation_id=strategy.invitation_id,
                applicant_id=strategy.applicant_id,
                competency_model_version_id=strategy.competency_model_version_id,
                strategy_version=strategy.strategy_version,
                common_topics=list(strategy.common_topics),
                verification_points=[
                    value.model_dump(mode="json") for value in strategy.verification_points
                ],
                follow_up_directions=strategy.follow_up_directions,
                time_budget=strategy.time_budget,
                required_evidence_plan=strategy.required_evidence_plan,
                source_reference_candidates=[
                    value.model_dump(mode="json") for value in strategy.source_reference_candidates
                ],
                model_config_version=strategy.model_config_version,
                status=strategy.status.value,
            )
        )
        self._session.flush()
        return strategy

    def latest_strategy(
        self, context: TenantContext, invitation_id: UUID
    ) -> InterviewStrategy | None:
        tenant = require_tenant_context(context)
        row = self._session.scalar(
            select(InterviewStrategyRow)
            .where(
                InterviewStrategyRow.company_id == tenant.company_id,
                InterviewStrategyRow.invitation_id == invitation_id,
            )
            .order_by(InterviewStrategyRow.strategy_version.desc())
            .limit(1)
        )
        if row is None:
            return None
        return self._strategy_from_row(row)

    def get_strategy(self, context: TenantContext, strategy_id: UUID) -> InterviewStrategy:
        tenant = require_tenant_context(context)
        row = self._session.scalar(
            select(InterviewStrategyRow).where(
                InterviewStrategyRow.company_id == tenant.company_id,
                InterviewStrategyRow.interview_strategy_id == strategy_id,
            )
        )
        if row is None:
            raise TenantScopedSubmissionNotFound("submission resource not found")
        return self._strategy_from_row(row)

    def save_candidate_claims(
        self,
        context: TenantContext,
        claims: tuple[CandidateClaim, ...],
    ) -> tuple[CandidateClaim, ...]:
        tenant = require_tenant_context(context)
        for claim in claims:
            tenant.assert_company(claim.company_id)
            self._session.merge(
                CandidateClaimRow(
                    candidate_claim_id=claim.candidate_claim_id,
                    company_id=claim.company_id,
                    applicant_id=claim.applicant_id,
                    invitation_id=claim.invitation_id,
                    competency_model_version_id=claim.competency_model_version_id,
                    criterion_id=claim.criterion_id,
                    claim_type=claim.claim_type,
                    neutral_text=claim.neutral_text,
                    source_id=claim.source_id,
                    locator=claim.locator,
                    content_hash=claim.content_hash,
                    extraction_version=claim.extraction_version,
                    confidence=claim.confidence,
                )
            )
        self._session.flush()
        return claims

    def list_candidate_claims(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        invitation_id: UUID,
    ) -> tuple[CandidateClaim, ...]:
        tenant = require_tenant_context(context)
        rows = self._session.scalars(
            select(CandidateClaimRow).where(
                CandidateClaimRow.company_id == tenant.company_id,
                CandidateClaimRow.applicant_id == applicant_id,
                CandidateClaimRow.invitation_id == invitation_id,
            )
        ).all()
        return tuple(
            CandidateClaim(
                candidate_claim_id=row.candidate_claim_id,
                company_id=row.company_id,
                applicant_id=row.applicant_id,
                invitation_id=row.invitation_id,
                competency_model_version_id=row.competency_model_version_id,
                criterion_id=row.criterion_id,
                claim_type=row.claim_type,
                neutral_text=row.neutral_text,
                source_id=row.source_id,
                locator=row.locator,
                content_hash=row.content_hash,
                extraction_version=row.extraction_version,
                confidence=row.confidence,
            )
            for row in rows
        )

    def save_claim_conflicts(
        self,
        context: TenantContext,
        conflicts: tuple[ClaimConflict, ...],
    ) -> tuple[ClaimConflict, ...]:
        tenant = require_tenant_context(context)
        for conflict in conflicts:
            tenant.assert_company(conflict.company_id)
            self._session.merge(
                ClaimConflictRow(
                    claim_conflict_id=conflict.claim_conflict_id,
                    company_id=conflict.company_id,
                    applicant_id=conflict.applicant_id,
                    invitation_id=conflict.invitation_id,
                    criterion_id=conflict.criterion_id,
                    left_claim_id=conflict.left_claim_id,
                    right_claim_id=conflict.right_claim_id,
                    conflict_type=conflict.conflict_type,
                    verification_objective=conflict.verification_objective,
                )
            )
        self._session.flush()
        return conflicts

    def list_claim_conflicts(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        invitation_id: UUID,
    ) -> tuple[ClaimConflict, ...]:
        tenant = require_tenant_context(context)
        rows = self._session.scalars(
            select(ClaimConflictRow).where(
                ClaimConflictRow.company_id == tenant.company_id,
                ClaimConflictRow.applicant_id == applicant_id,
                ClaimConflictRow.invitation_id == invitation_id,
            )
        ).all()
        return tuple(
            ClaimConflict(
                claim_conflict_id=row.claim_conflict_id,
                company_id=row.company_id,
                applicant_id=row.applicant_id,
                invitation_id=row.invitation_id,
                criterion_id=row.criterion_id,
                left_claim_id=row.left_claim_id,
                right_claim_id=row.right_claim_id,
                conflict_type=row.conflict_type,
                verification_objective=row.verification_objective,
            )
            for row in rows
        )

    def save_verification_targets(
        self,
        context: TenantContext,
        targets: tuple[VerificationTarget, ...],
    ) -> tuple[VerificationTarget, ...]:
        tenant = require_tenant_context(context)
        for target in targets:
            tenant.assert_company(target.company_id)
            self._session.merge(
                VerificationTargetRow(
                    verification_target_id=target.verification_target_id,
                    company_id=target.company_id,
                    applicant_id=target.applicant_id,
                    invitation_id=target.invitation_id,
                    competency_model_version_id=target.competency_model_version_id,
                    criterion_id=target.criterion_id,
                    target_type=target.target_type.value,
                    objective=target.objective,
                    missing_dimensions=list(target.missing_dimensions),
                    priority=target.priority,
                    max_follow_ups=target.max_follow_ups,
                    source_reference_candidates=[
                        str(value) for value in target.source_reference_candidates
                    ],
                )
            )
        self._session.flush()
        return targets

    def save_verification_map(
        self,
        context: TenantContext,
        verification_map: CandidateVerificationMap,
    ) -> CandidateVerificationMap:
        require_tenant_context(context).assert_company(verification_map.company_id)
        self._session.merge(
            CandidateVerificationMapRow(
                candidate_verification_map_id=(verification_map.candidate_verification_map_id),
                company_id=verification_map.company_id,
                applicant_id=verification_map.applicant_id,
                invitation_id=verification_map.invitation_id,
                competency_model_version_id=(verification_map.competency_model_version_id),
                criterion_version=verification_map.criterion_version,
                material_version=verification_map.material_version,
                retrieval_version=verification_map.retrieval_version,
                embedding_model=verification_map.embedding_model,
                embedding_version=verification_map.embedding_version,
                generation_version=verification_map.generation_version,
                ordered_target_ids=[str(value) for value in verification_map.ordered_target_ids],
                time_budget_seconds=verification_map.time_budget_seconds,
                readiness_state=verification_map.readiness_state,
                created_at=verification_map.created_at,
            )
        )
        self._session.flush()
        return verification_map

    def get_verification_map(
        self,
        context: TenantContext,
        verification_map_id: UUID,
    ) -> CandidateVerificationMap:
        tenant = require_tenant_context(context)
        row = self._session.scalar(
            select(CandidateVerificationMapRow).where(
                CandidateVerificationMapRow.company_id == tenant.company_id,
                CandidateVerificationMapRow.candidate_verification_map_id == verification_map_id,
            )
        )
        if row is None:
            raise TenantScopedSubmissionNotFound("submission resource not found")
        return CandidateVerificationMap(
            candidate_verification_map_id=row.candidate_verification_map_id,
            company_id=row.company_id,
            applicant_id=row.applicant_id,
            invitation_id=row.invitation_id,
            competency_model_version_id=row.competency_model_version_id,
            criterion_version=row.criterion_version,
            material_version=row.material_version,
            retrieval_version=row.retrieval_version,
            embedding_model=row.embedding_model,
            embedding_version=row.embedding_version,
            generation_version=row.generation_version,
            ordered_target_ids=tuple(UUID(value) for value in row.ordered_target_ids),
            time_budget_seconds=row.time_budget_seconds,
            readiness_state=row.readiness_state,
            created_at=row.created_at,
        )

    def latest_verification_map(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        invitation_id: UUID,
        competency_model_version_id: UUID,
    ) -> CandidateVerificationMap | None:
        tenant = require_tenant_context(context)
        row = self._session.scalar(
            select(CandidateVerificationMapRow)
            .where(
                CandidateVerificationMapRow.company_id == tenant.company_id,
                CandidateVerificationMapRow.applicant_id == applicant_id,
                CandidateVerificationMapRow.invitation_id == invitation_id,
                CandidateVerificationMapRow.competency_model_version_id
                == competency_model_version_id,
            )
            .order_by(CandidateVerificationMapRow.created_at.desc())
            .limit(1)
        )
        if row is None:
            return None
        return CandidateVerificationMap(
            candidate_verification_map_id=row.candidate_verification_map_id,
            company_id=row.company_id,
            applicant_id=row.applicant_id,
            invitation_id=row.invitation_id,
            competency_model_version_id=row.competency_model_version_id,
            criterion_version=row.criterion_version,
            material_version=row.material_version,
            retrieval_version=row.retrieval_version,
            embedding_model=row.embedding_model,
            embedding_version=row.embedding_version,
            generation_version=row.generation_version,
            ordered_target_ids=tuple(UUID(value) for value in row.ordered_target_ids),
            time_budget_seconds=row.time_budget_seconds,
            readiness_state=row.readiness_state,
            created_at=row.created_at,
        )

    def list_verification_maps(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        invitation_id: UUID,
    ) -> tuple[CandidateVerificationMap, ...]:
        tenant = require_tenant_context(context)
        rows = self._session.scalars(
            select(CandidateVerificationMapRow).where(
                CandidateVerificationMapRow.company_id == tenant.company_id,
                CandidateVerificationMapRow.applicant_id == applicant_id,
                CandidateVerificationMapRow.invitation_id == invitation_id,
            )
        ).all()
        return tuple(
            CandidateVerificationMap(
                candidate_verification_map_id=row.candidate_verification_map_id,
                company_id=row.company_id,
                applicant_id=row.applicant_id,
                invitation_id=row.invitation_id,
                competency_model_version_id=row.competency_model_version_id,
                criterion_version=row.criterion_version,
                material_version=row.material_version,
                retrieval_version=row.retrieval_version,
                embedding_model=row.embedding_model,
                embedding_version=row.embedding_version,
                generation_version=row.generation_version,
                ordered_target_ids=tuple(UUID(value) for value in row.ordered_target_ids),
                time_budget_seconds=row.time_budget_seconds,
                readiness_state=row.readiness_state,
                created_at=row.created_at,
            )
            for row in rows
        )

    def list_verification_targets(
        self,
        context: TenantContext,
        verification_map: CandidateVerificationMap,
    ) -> tuple[VerificationTarget, ...]:
        tenant = require_tenant_context(context)
        rows = self._session.scalars(
            select(VerificationTargetRow).where(
                VerificationTargetRow.company_id == tenant.company_id,
                VerificationTargetRow.verification_target_id.in_(
                    verification_map.ordered_target_ids
                ),
            )
        ).all()
        by_id = {row.verification_target_id: row for row in rows}
        return tuple(
            VerificationTarget(
                verification_target_id=by_id[target_id].verification_target_id,
                company_id=by_id[target_id].company_id,
                applicant_id=by_id[target_id].applicant_id,
                invitation_id=by_id[target_id].invitation_id,
                competency_model_version_id=(by_id[target_id].competency_model_version_id),
                criterion_id=by_id[target_id].criterion_id,
                target_type=VerificationTargetType(by_id[target_id].target_type),
                objective=by_id[target_id].objective,
                missing_dimensions=tuple(by_id[target_id].missing_dimensions),
                priority=by_id[target_id].priority,
                max_follow_ups=by_id[target_id].max_follow_ups,
                source_reference_candidates=tuple(
                    UUID(value) for value in by_id[target_id].source_reference_candidates
                ),
            )
            for target_id in verification_map.ordered_target_ids
            if target_id in by_id
        )

    def list_retrieval_document_ids(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        invitation_id: UUID,
    ) -> tuple[UUID, ...]:
        tenant = require_tenant_context(context)
        return tuple(
            self._session.scalars(
                select(RetrievalDocumentRow.retrieval_document_id).where(
                    RetrievalDocumentRow.company_id == tenant.company_id,
                    RetrievalDocumentRow.applicant_id == applicant_id,
                    RetrievalDocumentRow.invitation_id == invitation_id,
                )
            ).all()
        )

    def delete_and_verify_target(
        self,
        context: TenantContext,
        *,
        resource_type: str,
        resource_id: UUID,
    ) -> bool:
        row: tuple[
            type[Base],
            InstrumentedAttribute[UUID],
            InstrumentedAttribute[UUID],
        ]
        if resource_type == "submission":
            row = (SubmissionRow, SubmissionRow.company_id, SubmissionRow.submission_id)
        elif resource_type == "submission_analysis":
            row = (
                SubmissionAnalysisRow,
                SubmissionAnalysisRow.company_id,
                SubmissionAnalysisRow.analysis_id,
            )
        elif resource_type == "submission_chunk":
            row = (
                SubmissionChunkRow,
                SubmissionChunkRow.company_id,
                SubmissionChunkRow.chunk_id,
            )
        elif resource_type == "git_repository_analysis":
            row = (
                GitRepositoryAnalysisRow,
                GitRepositoryAnalysisRow.company_id,
                GitRepositoryAnalysisRow.repository_analysis_id,
            )
        elif resource_type == "git_commit_analysis":
            row = (
                GitCommitAnalysisRow,
                GitCommitAnalysisRow.company_id,
                GitCommitAnalysisRow.git_commit_analysis_id,
            )
        elif resource_type == "candidate_code_unit":
            row = (
                CandidateCodeUnitRow,
                CandidateCodeUnitRow.company_id,
                CandidateCodeUnitRow.code_unit_id,
            )
        elif resource_type == "interview_strategy":
            row = (
                InterviewStrategyRow,
                InterviewStrategyRow.company_id,
                InterviewStrategyRow.interview_strategy_id,
            )
        elif resource_type == "candidate_claim":
            row = (
                CandidateClaimRow,
                CandidateClaimRow.company_id,
                CandidateClaimRow.candidate_claim_id,
            )
        elif resource_type == "claim_conflict":
            row = (
                ClaimConflictRow,
                ClaimConflictRow.company_id,
                ClaimConflictRow.claim_conflict_id,
            )
        elif resource_type == "verification_target":
            row = (
                VerificationTargetRow,
                VerificationTargetRow.company_id,
                VerificationTargetRow.verification_target_id,
            )
        elif resource_type == "candidate_verification_map":
            row = (
                CandidateVerificationMapRow,
                CandidateVerificationMapRow.company_id,
                CandidateVerificationMapRow.candidate_verification_map_id,
            )
        else:
            raise ValueError("unsupported submission deletion target")
        return self._delete_row(
            context,
            row_type=row[0],
            company_column=row[1],
            id_column=row[2],
            resource_id=resource_id,
        )

    @staticmethod
    def _strategy_from_row(row: InterviewStrategyRow) -> InterviewStrategy:
        return InterviewStrategy(
            interview_strategy_id=row.interview_strategy_id,
            company_id=row.company_id,
            invitation_id=row.invitation_id,
            applicant_id=row.applicant_id,
            competency_model_version_id=row.competency_model_version_id,
            strategy_version=row.strategy_version,
            common_topics=tuple(row.common_topics),
            verification_points=tuple(
                VerificationPoint.model_validate(value) for value in row.verification_points
            ),
            follow_up_directions=row.follow_up_directions,
            time_budget=row.time_budget,
            required_evidence_plan=row.required_evidence_plan,
            source_reference_candidates=tuple(
                SourceReferenceCandidate.model_validate(value)
                for value in row.source_reference_candidates
            ),
            model_config_version=row.model_config_version,
            status=StrategyStatus(row.status),
        )

    @staticmethod
    def _analysis_from_row(row: SubmissionAnalysisRow) -> SubmissionAnalysis:
        return SubmissionAnalysis(
            analysis_id=row.analysis_id,
            company_id=row.company_id,
            submission_id=row.submission_id,
            analysis_version=row.analysis_version,
            extractor_version=row.extractor_version,
            chunk_config_version=row.chunk_config_version,
            claims=tuple(row.claims),
            conflicts=tuple(row.conflicts),
            verification_points=tuple(row.verification_points),
            status=AnalysisStatus(row.status),
            created_at=row.created_at,
            failure_code=row.failure_code,
            impact_summary=row.impact_summary,
        )

    @staticmethod
    def _git_repository_from_row(
        row: GitRepositoryAnalysisRow,
    ) -> GitRepositoryAnalysis:
        return GitRepositoryAnalysis(
            repository_analysis_id=row.repository_analysis_id,
            company_id=row.company_id,
            submission_id=row.submission_id,
            repository_url=row.repository_url,
            default_branch=row.default_branch,
            pinned_head_sha=row.pinned_head_sha,
            candidate_identity_inputs=row.candidate_identity_inputs,
            limits_applied=row.limits_applied,
            status=GitAnalysisStatus(row.status),
        )

    @staticmethod
    def _git_commit_from_row(row: GitCommitAnalysisRow) -> GitCommitAnalysis:
        return GitCommitAnalysis(
            git_commit_analysis_id=row.git_commit_analysis_id,
            company_id=row.company_id,
            repository_analysis_id=row.repository_analysis_id,
            parent_sha=row.parent_sha,
            commit_sha=row.commit_sha,
            author_match_inputs=row.author_match_inputs,
            change_summary_object_key=row.change_summary_object_key,
            ownership_confidence=row.ownership_confidence,
            ownership_class=OwnershipClass(row.ownership_class),
            ownership_explanation=tuple(row.ownership_explanation),
        )

    @staticmethod
    def _code_unit_from_row(row: CandidateCodeUnitRow) -> CandidateCodeUnit:
        return CandidateCodeUnit(
            code_unit_id=row.code_unit_id,
            company_id=row.company_id,
            git_commit_analysis_id=row.git_commit_analysis_id,
            path=row.path,
            language=row.language,
            symbol=row.symbol,
            original_line_range=tuple(row.original_line_range),
            current_line_range=tuple(row.current_line_range),
            authored_snapshot_key=row.authored_snapshot_key,
            current_snapshot_key=row.current_snapshot_key,
            candidate_owned_regions=tuple(tuple(region) for region in row.candidate_owned_regions),
            related_test_ids=tuple(row.related_test_ids),
            dependency_ids=tuple(row.dependency_ids),
            index_document_ids=tuple(row.index_document_ids),
        )
