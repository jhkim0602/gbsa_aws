from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from interview_evidence.shared.aws_clients.ports import AIModel
from interview_evidence.shared.ids import Clock, new_uuid7
from interview_evidence.shared.messaging.outbox import Outbox
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.submission_analysis.adapters.search import (
    SearchDocument,
    SearchIndex,
)
from interview_evidence.submission_analysis.application.strategy_service import (
    StrategyService,
)
from interview_evidence.submission_analysis.domain.git_analysis import (
    CandidateCodeUnit,
    CommitIdentityInput,
    GitAnalysisStatus,
    GitCommitCandidate,
    GitRepositoryAnalysis,
)
from interview_evidence.submission_analysis.domain.source import (
    SourceReferenceCandidate,
    SubmissionChunk,
)
from interview_evidence.submission_analysis.domain.submission import (
    AnalysisStatus,
    SourceType,
    Submission,
    SubmissionAnalysis,
    SubmissionStatus,
)
from interview_evidence.submission_analysis.repositories.postgres import (
    SubmissionRepository,
)
from interview_evidence.workers.analysis.code_units import expand_python_code_units
from interview_evidence.workers.analysis.document_chunker import (
    ChunkingConfig,
    chunk_document,
)
from interview_evidence.workers.analysis.document_extract import (
    DocumentExtractionAdapter,
)
from interview_evidence.workers.analysis.git_commits import (
    CommitDiff,
    analyze_candidate_commits,
)
from interview_evidence.workers.analysis.git_fetch import BoundedGitFetcher
from interview_evidence.workers.analysis.handlers import (
    AnalysisJob,
    AnalysisProcessor,
    AnalysisResult,
    JobStatus,
    NonRetryableAnalysisError,
)


@dataclass(frozen=True, slots=True)
class AnalysisAxis:
    competency_model_version_id: UUID
    criterion_ids: tuple[UUID, ...]


class AnalysisAxisProvider(Protocol):
    def get_axis(
        self,
        context: TenantContext,
        *,
        invitation_id: UUID,
    ) -> AnalysisAxis: ...


class SubmissionAnalysisPipeline(AnalysisProcessor):
    def __init__(
        self,
        *,
        repository: SubmissionRepository,
        extractor: DocumentExtractionAdapter,
        search_index: SearchIndex,
        strategy_model: AIModel,
        axis_provider: AnalysisAxisProvider,
        outbox: Outbox,
        clock: Clock,
        git_fetcher: BoundedGitFetcher | None = None,
    ) -> None:
        self._repository = repository
        self._extractor = extractor
        self._search_index = search_index
        self._strategy_model = strategy_model
        self._axis_provider = axis_provider
        self._outbox = outbox
        self._clock = clock
        self._git_fetcher = git_fetcher

    @staticmethod
    def embed(text: str) -> tuple[float, ...]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return tuple((digest[index % len(digest)] - 127.5) / 127.5 for index in range(1024))

    def process(self, context: TenantContext, job: AnalysisJob) -> AnalysisResult:
        existing = next(
            (
                analysis
                for analysis in self._repository.list_analyses(
                    context,
                    frozenset({job.submission_id}),
                )
                if analysis.analysis_version == job.analysis_version
            ),
            None,
        )
        if existing is not None:
            return AnalysisResult(
                status=JobStatus(existing.status.value),
                analysis_id=existing.analysis_id,
                impact_code=existing.failure_code,
            )

        submission = self._repository.get_submission(context, job.submission_id)
        if (
            submission.invitation_id != job.invitation_id
            or submission.applicant_id != job.applicant_id
            or submission.source_type is not job.source_type
        ):
            raise NonRetryableAnalysisError("analysis_job_scope_mismatch")
        if submission.source_type is SourceType.PUBLIC_GIT:
            if self._git_fetcher is None:
                return self._record_partial_git(context, submission, job)
            return self._process_git(context, submission, job)
        if submission.source_type is SourceType.PUBLIC_URL:
            raise NonRetryableAnalysisError("public_url_analysis_not_supported")
        return self._process_document(context, submission, job)

    def _process_document(
        self,
        context: TenantContext,
        submission: Submission,
        job: AnalysisJob,
    ) -> AnalysisResult:
        if submission.content_hash is None:
            raise NonRetryableAnalysisError("document_integrity_metadata_missing")
        analyzing = self._to_analyzing(submission)
        self._repository.save_submission(context, analyzing)
        pages = self._extractor.extract(context, job.source_object_id)
        drafts = chunk_document(
            pages,
            source_hash=submission.content_hash,
            config=ChunkingConfig(version="document-chunks-v1", max_characters=1200),
        )
        if not drafts:
            raise NonRetryableAnalysisError("document_contains_no_indexable_chunks")
        occurred_at = self._clock.now()
        analysis = self._repository.save_analysis(
            context,
            SubmissionAnalysis(
                analysis_id=new_uuid7(occurred_at),
                company_id=context.company_id,
                submission_id=submission.submission_id,
                analysis_version=job.analysis_version,
                extractor_version=self._extractor.extractor_version,
                chunk_config_version="document-chunks-v1",
                claims=({"type": "document_extracted", "chunk_count": len(drafts)},),
                verification_points=({"type": "answer_verification", "source": "document"},),
                status=AnalysisStatus.READY,
                created_at=occurred_at,
            ),
        )
        chunks = tuple(
            SubmissionChunk(
                chunk_id=new_uuid7(occurred_at),
                company_id=context.company_id,
                applicant_id=submission.applicant_id,
                submission_id=submission.submission_id,
                analysis_id=analysis.analysis_id,
                source_location=draft.source_location,
                text_object_key=(
                    f"companies/{context.company_id}/invitations/"
                    f"{submission.invitation_id}/submissions/{submission.submission_id}/"
                    f"derived/{job.analysis_version}/{draft.chunk_hash}"
                ),
                source_hash=draft.source_hash,
                chunk_hash=draft.chunk_hash,
                embedding_model="deterministic-sha256-1024",
                embedding_version="v1",
                index_document_id=f"submission-chunk-{new_uuid7(occurred_at)}",
            )
            for draft in drafts
        )
        self._repository.save_chunks(context, chunks)
        candidates: list[SourceReferenceCandidate] = []
        for draft, chunk in zip(drafts, chunks, strict=True):
            locator = chunk.source_location.model_dump(mode="json", exclude_none=True)
            self._search_index.add(
                SearchDocument(
                    document_id=chunk.index_document_id,
                    company_id=context.company_id,
                    applicant_id=submission.applicant_id,
                    source_id=chunk.chunk_id,
                    text=draft.text,
                    vector=self.embed(draft.text),
                    symbols=(),
                    locator=locator,
                    ownership_confidence=1.0,
                )
            )
            candidates.append(
                SourceReferenceCandidate(
                    source_id=chunk.chunk_id,
                    source_type="submission_chunk",
                    locator=locator,
                    content_hash=chunk.chunk_hash,
                    relevance_score=1.0,
                    ownership_confidence=1.0,
                )
            )
        axis = self._axis_provider.get_axis(
            context,
            invitation_id=submission.invitation_id,
        )
        StrategyService(
            self._strategy_model,
            model_config_version="strategy-v1",
            repository=self._repository,
            outbox=self._outbox,
            clock=self._clock,
        ).generate(
            context,
            invitation_id=submission.invitation_id,
            applicant_id=submission.applicant_id,
            competency_model_version_id=axis.competency_model_version_id,
            criterion_ids=axis.criterion_ids,
            source_candidates=tuple(candidates),
            strategy_version=1,
        )
        self._repository.save_submission(
            context,
            analyzing.transition(SubmissionStatus.READY),
        )
        return AnalysisResult(
            status=JobStatus.READY,
            analysis_id=analysis.analysis_id,
        )

    def _record_partial_git(
        self,
        context: TenantContext,
        submission: Submission,
        job: AnalysisJob,
    ) -> AnalysisResult:
        analyzing = self._to_analyzing(submission)
        self._repository.save_submission(context, analyzing)
        occurred_at = self._clock.now()
        analysis = self._repository.save_analysis(
            context,
            SubmissionAnalysis(
                analysis_id=new_uuid7(occurred_at),
                company_id=context.company_id,
                submission_id=submission.submission_id,
                analysis_version=job.analysis_version,
                extractor_version="public-git-metadata-v1",
                chunk_config_version="code-units-v1",
                verification_points=(
                    {
                        "type": "git_ownership_follow_up",
                        "repository_url_present": True,
                    },
                ),
                status=AnalysisStatus.PARTIAL,
                created_at=occurred_at,
                failure_code="git_commit_evidence_pending",
                impact_summary="공개 저장소의 기여 범위는 면접에서 추가 확인합니다.",
            ),
        )
        self._repository.save_submission(
            context,
            analyzing.transition(
                SubmissionStatus.PARTIAL,
                failure_code="git_commit_evidence_pending",
                impact_summary="공개 저장소의 기여 범위는 면접에서 추가 확인합니다.",
            ),
        )
        return AnalysisResult(
            status=JobStatus.PARTIAL,
            analysis_id=analysis.analysis_id,
            impact_code="git_commit_evidence_pending",
        )

    def _process_git(
        self,
        context: TenantContext,
        submission: Submission,
        job: AnalysisJob,
    ) -> AnalysisResult:
        assert self._git_fetcher is not None
        analyzing = self._to_analyzing(submission)
        self._repository.save_submission(context, analyzing)
        snapshot = self._git_fetcher.fetch(submission.source_uri)
        if not snapshot.commits:
            return self._record_partial_git(context, analyzing, job)
        occurred_at = self._clock.now()
        repository_analysis = self._repository.save_git_repository_analysis(
            context,
            GitRepositoryAnalysis(
                repository_analysis_id=new_uuid7(occurred_at),
                company_id=context.company_id,
                submission_id=submission.submission_id,
                repository_url=snapshot.repository_url,
                default_branch=snapshot.default_branch,
                pinned_head_sha=snapshot.pinned_head_sha,
                candidate_identity_inputs={
                    key: list(values)
                    for key, values in (submission.candidate_identity_inputs or {}).items()
                },
                limits_applied={
                    "max_files": len(snapshot.files),
                    "max_commits": snapshot.commit_count,
                },
                status=GitAnalysisStatus.RUNNING,
            ),
        )
        identity = CommitIdentityInput.model_validate(
            submission.candidate_identity_inputs or {}
        )
        commits = analyze_candidate_commits(
            company_id=context.company_id,
            repository_analysis_id=repository_analysis.repository_analysis_id,
            commits=tuple(
                CommitDiff(
                    candidate=GitCommitCandidate(
                        parent_sha=commit.parent_sha,
                        commit_sha=commit.commit_sha,
                        author_name=commit.author_name,
                        author_email=commit.author_email,
                        changed_paths=commit.changed_paths,
                    ),
                    changed_line_count=sum(
                        end - start + 1
                        for ranges in commit.changed_line_ranges.values()
                        for start, end in ranges
                    ),
                    summary_object_key=(
                        f"companies/{context.company_id}/invitations/"
                        f"{submission.invitation_id}/submissions/{submission.submission_id}/"
                        f"github/{repository_analysis.repository_analysis_id}/commits/"
                        f"{commit.commit_sha}/summary.json"
                    ),
                )
                for commit in snapshot.commits
            ),
            identity=identity,
        )
        self._repository.save_git_commit_analyses(context, commits)
        files = {file.path: file.content.decode("utf-8") for file in snapshot.files}
        code_units: list[CandidateCodeUnit] = []
        candidates: list[SourceReferenceCandidate] = []
        commit_by_sha = {
            commit.commit_sha: (commit, analysis)
            for commit, analysis in zip(snapshot.commits, commits, strict=True)
        }
        for commit_sha, (commit, commit_analysis) in commit_by_sha.items():
            for path, ranges in commit.changed_line_ranges.items():
                if not path.endswith(".py") or path not in files:
                    continue
                related = {
                    candidate_path: source
                    for candidate_path, source in files.items()
                    if candidate_path != path
                }
                for expanded in expand_python_code_units(
                    path=path,
                    source=files[path],
                    changed_line_ranges=ranges,
                    related_files=related,
                ):
                    code_unit_id = new_uuid7(occurred_at)
                    document_id = f"code-unit-{code_unit_id}"
                    unit = CandidateCodeUnit(
                        code_unit_id=code_unit_id,
                        company_id=context.company_id,
                        git_commit_analysis_id=commit_analysis.git_commit_analysis_id,
                        path=expanded.path,
                        language=expanded.language,
                        symbol=expanded.symbol,
                        original_line_range=expanded.line_range,
                        current_line_range=expanded.line_range,
                        authored_snapshot_key=(
                            f"companies/{context.company_id}/invitations/"
                            f"{submission.invitation_id}/submissions/{submission.submission_id}/"
                            f"github/{repository_analysis.repository_analysis_id}/snapshot/"
                            f"{commit_sha}/authored/{code_unit_id}"
                        ),
                        current_snapshot_key=(
                            f"companies/{context.company_id}/invitations/"
                            f"{submission.invitation_id}/submissions/{submission.submission_id}/"
                            f"github/{repository_analysis.repository_analysis_id}/snapshot/"
                            f"{snapshot.pinned_head_sha}/current/{code_unit_id}"
                        ),
                        candidate_owned_regions=expanded.candidate_owned_regions,
                        related_test_ids=expanded.related_test_paths,
                        index_document_ids=(document_id,),
                    )
                    code_units.append(unit)
                    locator = {
                        "path": unit.path,
                        "symbol": unit.symbol,
                        "start_line": unit.current_line_range[0],
                        "end_line": unit.current_line_range[1],
                        "commit_sha": commit_sha,
                    }
                    self._search_index.add(
                        SearchDocument(
                            document_id=document_id,
                            company_id=context.company_id,
                            applicant_id=submission.applicant_id,
                            source_id=unit.code_unit_id,
                            text=f"{unit.symbol} {files[path]}",
                            vector=self.embed(files[path]),
                            symbols=(unit.symbol,),
                            locator=locator,
                            ownership_confidence=commit_analysis.ownership_confidence,
                        )
                    )
                    candidates.append(
                        SourceReferenceCandidate(
                            source_id=unit.code_unit_id,
                            source_type="candidate_code_unit",
                            locator=locator,
                            content_hash=hashlib.sha256(
                                files[path].encode("utf-8")
                            ).hexdigest(),
                            relevance_score=1.0,
                            ownership_confidence=commit_analysis.ownership_confidence,
                        )
                    )
        if not code_units:
            return self._record_partial_git(context, analyzing, job)
        self._repository.save_code_units(context, tuple(code_units))
        analysis = self._repository.save_analysis(
            context,
            SubmissionAnalysis(
                analysis_id=new_uuid7(occurred_at),
                company_id=context.company_id,
                submission_id=submission.submission_id,
                analysis_version=job.analysis_version,
                extractor_version="bounded-public-git-v1",
                chunk_config_version="code-units-v1",
                claims=(
                    {
                        "type": "public_git_snapshot",
                        "commit_count": len(commits),
                        "code_unit_count": len(code_units),
                    },
                ),
                verification_points=tuple(
                    {
                        "type": "git_ownership_follow_up",
                        "source_id": str(candidate.source_id),
                        "ownership_confidence": candidate.ownership_confidence,
                    }
                    for candidate in candidates
                ),
                status=AnalysisStatus.READY,
                created_at=occurred_at,
            ),
        )
        axis = self._axis_provider.get_axis(context, invitation_id=submission.invitation_id)
        StrategyService(
            self._strategy_model,
            model_config_version="strategy-v1",
            repository=self._repository,
            outbox=self._outbox,
            clock=self._clock,
        ).generate(
            context,
            invitation_id=submission.invitation_id,
            applicant_id=submission.applicant_id,
            competency_model_version_id=axis.competency_model_version_id,
            criterion_ids=axis.criterion_ids,
            source_candidates=tuple(candidates),
            strategy_version=1,
        )
        self._repository.save_git_repository_analysis(
            context,
            repository_analysis.model_copy(update={"status": GitAnalysisStatus.READY}),
        )
        self._repository.save_submission(
            context,
            analyzing.transition(SubmissionStatus.READY),
        )
        return AnalysisResult(status=JobStatus.READY, analysis_id=analysis.analysis_id)

    @staticmethod
    def _to_analyzing(submission: Submission) -> Submission:
        if submission.status is SubmissionStatus.RECEIVED:
            return submission.transition(SubmissionStatus.VALIDATING).transition(
                SubmissionStatus.ANALYZING
            )
        if submission.status in {SubmissionStatus.PARTIAL, SubmissionStatus.FAILED}:
            return submission.transition(SubmissionStatus.ANALYZING)
        if submission.status is SubmissionStatus.ANALYZING:
            return submission
        raise NonRetryableAnalysisError("submission_state_not_analyzable")
