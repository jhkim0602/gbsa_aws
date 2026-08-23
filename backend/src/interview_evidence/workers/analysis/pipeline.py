from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from interview_evidence.shared.aws_clients.ports import AIModel, TextEmbedder
from interview_evidence.shared.ids import Clock, new_uuid7
from interview_evidence.shared.messaging.outbox import Outbox
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.submission_analysis.adapters.search import (
    SearchDocument,
    SearchIndex,
)
from interview_evidence.submission_analysis.application.retrieval import (
    HybridRetrievalConfig,
    HybridRetriever,
)
from interview_evidence.submission_analysis.application.strategy_service import (
    StrategyService,
)
from interview_evidence.submission_analysis.application.verification_map import (
    CriterionVerificationInput,
    RequirementVerificationInput,
    VerificationMapBuilder,
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
from interview_evidence.submission_analysis.domain.strategy import (
    InterviewStrategy,
    StrategyStatus,
)
from interview_evidence.submission_analysis.domain.submission import (
    AnalysisStatus,
    SourceType,
    Submission,
    SubmissionAnalysis,
    SubmissionStatus,
)
from interview_evidence.submission_analysis.repositories.postgres import (
    DuplicateStrategyVersion,
    SubmissionRepository,
)
from interview_evidence.workers.analysis.code_units import (
    ExpandedCodeUnit,
    expand_python_code_units,
)
from interview_evidence.workers.analysis.document_chunker import (
    ChunkingConfig,
    chunk_document,
)
from interview_evidence.workers.analysis.document_extract import (
    DocumentExtractionError,
    DocumentExtractor,
)
from interview_evidence.workers.analysis.git_commits import (
    CommitDiff,
    analyze_candidate_commits,
)
from interview_evidence.workers.analysis.git_fetch import BoundedGitFetcher, GitFetchError
from interview_evidence.workers.analysis.handlers import (
    AnalysisJob,
    AnalysisProcessor,
    AnalysisResult,
    JobStatus,
    NonRetryableAnalysisError,
    RetryableAnalysisError,
)

MAX_EMBEDDING_INPUT_CHARACTERS = 7_000

RETRYABLE_SOURCE_CODES = frozenset(
    {
        "public_git_fetch_failed",
        "public_git_file_fetch_failed",
        "repository_commit_files_unavailable",
        "public_git_parent_unavailable",
        "public_git_author_unavailable",
    }
)
SOURCE_FAILURE_SUMMARY = "제출 자료를 분석할 수 없어 해당 자료는 면접 준비에서 제외됩니다."
SOURCE_CANDIDATE_CLAIM = "source_reference_candidate"


@dataclass(frozen=True, slots=True)
class AnalysisCriterion:
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
class AnalysisRequirement:
    job_requirement_id: UUID
    statement: str
    criterion_code: str
    required: bool
    priority: int


@dataclass(frozen=True, slots=True)
class AnalysisAxis:
    competency_model_version_id: UUID
    criterion_ids: tuple[UUID, ...]
    version_number: int = 1
    criteria: tuple[AnalysisCriterion, ...] = ()
    requirements: tuple[AnalysisRequirement, ...] = ()


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
        extractor: DocumentExtractor,
        search_index: SearchIndex,
        text_embedder: TextEmbedder,
        strategy_model: AIModel,
        axis_provider: AnalysisAxisProvider,
        outbox: Outbox,
        clock: Clock,
        git_fetcher: BoundedGitFetcher | None = None,
    ) -> None:
        self._repository = repository
        self._extractor = extractor
        self._search_index = search_index
        self._text_embedder = text_embedder
        self._strategy_model = strategy_model
        self._axis_provider = axis_provider
        self._outbox = outbox
        self._clock = clock
        self._git_fetcher = git_fetcher

    def embed(self, context: TenantContext, text: str) -> tuple[float, ...]:
        # Titan v2 accepts at most 8,192 tokens. Code and Korean text can approach one
        # token per character, so bound the adapter input below that ceiling. The full
        # source remains persisted and only its semantic representation is shortened.
        bounded_text = text[:MAX_EMBEDDING_INPUT_CHARACTERS]
        return self._text_embedder.embed(context, bounded_text, dimensions=1024)

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
        if submission.source_type is SourceType.PUBLIC_URL:
            raise NonRetryableAnalysisError("public_url_analysis_not_supported")
        try:
            if submission.source_type is SourceType.PUBLIC_GIT:
                if self._git_fetcher is None:
                    return self._record_partial_git(context, submission, job)
                return self._process_git(context, submission, job)
            return self._process_document(context, submission, job)
        except (GitFetchError, DocumentExtractionError) as error:
            code = str(error)
            if code in RETRYABLE_SOURCE_CODES:
                raise RetryableAnalysisError(code) from error
            self._record_failed(context, job.submission_id, code)
            raise NonRetryableAnalysisError(code) from error

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
        pages = self._extractor.extract(context, submission.source_uri)
        drafts = chunk_document(
            pages,
            source_hash=submission.content_hash,
            config=ChunkingConfig(version="document-chunks-v1", max_characters=1200),
        )
        if not drafts:
            raise NonRetryableAnalysisError("document_contains_no_indexable_chunks")
        axis = self._axis_provider.get_axis(
            context,
            invitation_id=submission.invitation_id,
        )
        self._index_criterion_axis(context, axis)
        occurred_at = self._clock.now()
        analysis = SubmissionAnalysis(
            analysis_id=new_uuid7(occurred_at),
            company_id=context.company_id,
            submission_id=submission.submission_id,
            analysis_version=job.analysis_version,
            extractor_version=self._extractor.extractor_version,
            chunk_config_version="document-chunks-v1",
            verification_points=({"type": "answer_verification", "source": "document"},),
            status=AnalysisStatus.READY,
            created_at=occurred_at,
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
                embedding_model=self._text_embedder.model_id,
                embedding_version="titan-v2",
                index_document_id=str(new_uuid7(occurred_at)),
            )
            for draft in drafts
        )
        candidates = tuple(
            SourceReferenceCandidate(
                source_id=chunk.chunk_id,
                source_type="submission_chunk",
                locator=chunk.source_location.model_dump(mode="json", exclude_none=True),
                content_hash=chunk.chunk_hash,
                relevance_score=1.0,
                ownership_confidence=1.0,
            )
            for chunk in chunks
        )
        analysis = self._repository.save_analysis(
            context,
            analysis.model_copy(
                update={
                    "claims": (
                        {"type": "document_extracted", "chunk_count": len(drafts)},
                        *(self._candidate_claim(candidate) for candidate in candidates),
                    )
                }
            ),
        )
        self._repository.save_chunks(context, chunks)
        for draft, chunk in zip(drafts, chunks, strict=True):
            locator = chunk.source_location.model_dump(mode="json", exclude_none=True)
            self._search_index.add(
                SearchDocument(
                    document_id=chunk.index_document_id,
                    company_id=context.company_id,
                    applicant_id=submission.applicant_id,
                    source_id=chunk.chunk_id,
                    text=draft.text,
                    vector=self.embed(context, draft.text),
                    symbols=(),
                    locator=locator,
                    ownership_confidence=1.0,
                    invitation_id=submission.invitation_id,
                    competency_model_version_id=axis.competency_model_version_id,
                    document_type="submission_chunk",
                    source_type="submission_chunk",
                    source_version=str(job.analysis_version),
                    content_hash=chunk.chunk_hash,
                    embedding_model=self._text_embedder.model_id,
                    embedding_version="titan-v2",
                    material_type=submission.material_type.value,
                )
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
        identity = CommitIdentityInput.model_validate(submission.candidate_identity_inputs or {})
        # The identity is resolved before the fetch so the transport can ask GitHub for
        # this candidate's commits instead of whatever landed on the branch last.
        snapshot = self._git_fetcher.fetch(submission.source_uri, identity=identity)
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
                    # What was actually deep-fetched, which is what the evidence rests
                    # on when the listing was larger than the analysis budget.
                    "analyzed_commits": len(snapshot.commits),
                },
                status=GitAnalysisStatus.RUNNING,
            ),
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
        # One path can exist at several contents once more than one commit is analyzed,
        # so a blob is looked up by the commit it was read at. A transport that reports
        # only the head snapshot leaves the commit blank, and those files serve every
        # commit.
        head_files: dict[str, str] = {}
        files_by_commit: dict[str, dict[str, str]] = {}
        for file in snapshot.files:
            source = file.content.decode("utf-8")
            if file.commit_sha:
                files_by_commit.setdefault(file.commit_sha, {})[file.path] = source
            else:
                head_files[file.path] = source
        # Related-test detection asks which *other* file mentions a symbol, so it reads
        # across the whole snapshot rather than one commit. First occurrence wins to keep
        # two runs over the same repository identical.
        related_corpus: dict[str, str] = dict(head_files)
        for commit_files in files_by_commit.values():
            for path, source in commit_files.items():
                related_corpus.setdefault(path, source)
        axis = self._axis_provider.get_axis(
            context,
            invitation_id=submission.invitation_id,
        )
        self._index_criterion_axis(context, axis)
        code_units: list[CandidateCodeUnit] = []
        candidates: list[SourceReferenceCandidate] = []
        commit_by_sha = {
            commit.commit_sha: (commit, analysis)
            for commit, analysis in zip(snapshot.commits, commits, strict=True)
        }
        for commit_sha, (commit, commit_analysis) in commit_by_sha.items():
            commit_files = {**head_files, **files_by_commit.get(commit_sha, {})}
            for path, ranges in commit.changed_line_ranges.items():
                if not path.endswith(".py") or path not in commit_files:
                    continue
                source = commit_files[path]
                related = {
                    candidate_path: related_source
                    for candidate_path, related_source in related_corpus.items()
                    if candidate_path != path
                }
                for expanded in self._python_code_units(
                    path=path,
                    source=source,
                    changed_line_ranges=ranges,
                    related_files=related,
                ):
                    code_unit_id = new_uuid7(occurred_at)
                    document_id = str(code_unit_id)
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
                            text=f"{unit.symbol} {source}",
                            vector=self.embed(context, source),
                            symbols=(unit.symbol,),
                            locator=locator,
                            ownership_confidence=commit_analysis.ownership_confidence,
                            invitation_id=submission.invitation_id,
                            competency_model_version_id=axis.competency_model_version_id,
                            document_type="code_unit",
                            source_type="candidate_code_unit",
                            source_version=commit_sha,
                            content_hash=submission.content_hash or "0" * 64,
                            embedding_model=self._text_embedder.model_id,
                            embedding_version="titan-v2",
                            path=unit.path,
                            symbol=unit.symbol,
                        )
                    )
                    candidates.append(
                        SourceReferenceCandidate(
                            source_id=unit.code_unit_id,
                            source_type="candidate_code_unit",
                            locator=locator,
                            content_hash=hashlib.sha256(source.encode("utf-8")).hexdigest(),
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
                    *(self._candidate_claim(candidate) for candidate in candidates),
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
    def _python_code_units(
        *,
        path: str,
        source: str,
        changed_line_ranges: tuple[tuple[int, int], ...],
        related_files: dict[str, str],
    ) -> tuple[ExpandedCodeUnit, ...]:
        """Expand one changed file, tolerating a file that does not parse.

        Analyzing many commits instead of one makes it likely that a real repository
        contains at least one ``.py`` file the local interpreter cannot parse -- Python 2
        syntax, a template, a deliberately broken fixture. That file yields no evidence,
        but it must not cost the recruiter every other commit in the repository.
        """
        try:
            return expand_python_code_units(
                path=path,
                source=source,
                changed_line_ranges=changed_line_ranges,
                related_files=related_files,
            )
        except SyntaxError:
            return ()

    def _index_criterion_axis(
        self,
        context: TenantContext,
        axis: AnalysisAxis,
    ) -> None:
        for criterion in axis.criteria:
            text = " ".join(
                (
                    criterion.name,
                    criterion.description,
                    *criterion.observable_dimensions,
                    *criterion.follow_up_directions,
                )
            )
            self._search_index.add(
                SearchDocument(
                    document_id=str(
                        uuid5(
                            NAMESPACE_URL,
                            (
                                f"{axis.competency_model_version_id}:"
                                f"criterion:{criterion.criterion_id}"
                            ),
                        )
                    ),
                    company_id=context.company_id,
                    applicant_id=UUID(int=0),
                    source_id=criterion.criterion_id,
                    text=text,
                    vector=self.embed(context, text),
                    symbols=(),
                    locator={"criterion_code": criterion.code},
                    ownership_confidence=1.0,
                    competency_model_version_id=axis.competency_model_version_id,
                    criterion_id=criterion.criterion_id,
                    document_type="criterion_guide",
                    source_type="criterion_guide",
                    source_version=str(axis.version_number),
                    content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    embedding_model=self._text_embedder.model_id,
                    embedding_version="titan-v2",
                )
            )
        for requirement in axis.requirements:
            self._search_index.add(
                SearchDocument(
                    document_id=str(
                        uuid5(
                            NAMESPACE_URL,
                            (
                                f"{axis.competency_model_version_id}:"
                                f"requirement:{requirement.job_requirement_id}"
                            ),
                        )
                    ),
                    company_id=context.company_id,
                    applicant_id=UUID(int=0),
                    source_id=requirement.job_requirement_id,
                    text=requirement.statement,
                    vector=self.embed(context, requirement.statement),
                    symbols=(),
                    locator={"criterion_code": requirement.criterion_code},
                    ownership_confidence=1.0,
                    competency_model_version_id=axis.competency_model_version_id,
                    document_type="job_requirement",
                    source_type="job_requirement",
                    source_version=str(axis.version_number),
                    content_hash=hashlib.sha256(requirement.statement.encode("utf-8")).hexdigest(),
                    embedding_model=self._text_embedder.model_id,
                    embedding_version="titan-v2",
                )
            )

    def finalize_invitation(
        self,
        context: TenantContext,
        *,
        invitation_id: UUID,
        applicant_id: UUID,
        submission_ids: frozenset[UUID],
    ) -> bool:
        analyses = self._repository.list_analyses(context, submission_ids)
        latest_analyses = self._latest_analyses(analyses)
        candidates = self._candidates_from_analyses(latest_analyses)
        if not candidates:
            return False
        axis = self._axis_provider.get_axis(context, invitation_id=invitation_id)
        self._index_criterion_axis(context, axis)
        material_version = self._aggregate_material_version(latest_analyses)
        strategy, created = self._generate_strategy(
            context,
            invitation_id=invitation_id,
            applicant_id=applicant_id,
            axis=axis,
            candidates=candidates,
        )
        if strategy is None:
            return False
        verification_map = self._repository.latest_verification_map(
            context,
            applicant_id=applicant_id,
            invitation_id=invitation_id,
            competency_model_version_id=axis.competency_model_version_id,
        )
        if (
            created
            or verification_map is None
            or verification_map.material_version != material_version
        ):
            self._build_verification_map(
                context,
                applicant_id=applicant_id,
                invitation_id=invitation_id,
                axis=axis,
                material_version=material_version,
            )
        return strategy.status in {StrategyStatus.READY, StrategyStatus.PARTIAL}

    def _generate_strategy(
        self,
        context: TenantContext,
        *,
        invitation_id: UUID,
        applicant_id: UUID,
        axis: AnalysisAxis,
        candidates: list[SourceReferenceCandidate],
    ) -> tuple[InterviewStrategy | None, bool]:
        previous = self._repository.latest_strategy(context, invitation_id)
        candidate_ids = frozenset(candidate.source_id for candidate in candidates)
        if (
            previous is not None
            and previous.competency_model_version_id == axis.competency_model_version_id
            and frozenset(candidate.source_id for candidate in previous.source_reference_candidates)
            == candidate_ids
        ):
            return previous, False
        try:
            strategy = StrategyService(
                self._strategy_model,
                model_config_version="strategy-v1",
                repository=self._repository,
                outbox=self._outbox,
                clock=self._clock,
            ).generate(
                context,
                invitation_id=invitation_id,
                applicant_id=applicant_id,
                competency_model_version_id=axis.competency_model_version_id,
                criterion_ids=axis.criterion_ids,
                source_candidates=tuple(candidates),
                strategy_version=1 if previous is None else previous.strategy_version + 1,
            )
            return strategy, True
        except DuplicateStrategyVersion:
            return self._repository.latest_strategy(context, invitation_id), False

    def _build_verification_map(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        invitation_id: UUID,
        axis: AnalysisAxis,
        material_version: str,
    ) -> None:
        if not axis.criteria:
            return
        VerificationMapBuilder(
            repository=self._repository,
            retriever=HybridRetriever(
                self._search_index,
                HybridRetrievalConfig(),
            ),
            embedder=self._text_embedder,
            clock=self._clock,
        ).build(
            context,
            applicant_id=applicant_id,
            invitation_id=invitation_id,
            competency_model_version_id=axis.competency_model_version_id,
            criterion_version=axis.version_number,
            criteria=tuple(
                CriterionVerificationInput(
                    criterion_id=criterion.criterion_id,
                    code=criterion.code,
                    name=criterion.name,
                    description=criterion.description,
                    required=criterion.required,
                    weight=criterion.weight,
                    observable_dimensions=criterion.observable_dimensions,
                    follow_up_directions=criterion.follow_up_directions,
                    max_follow_ups=criterion.max_follow_ups,
                    time_budget_seconds=criterion.time_budget_seconds,
                )
                for criterion in axis.criteria
            ),
            requirements=tuple(
                RequirementVerificationInput(
                    statement=requirement.statement,
                    criterion_code=requirement.criterion_code,
                    required=requirement.required,
                    priority=requirement.priority,
                )
                for requirement in axis.requirements
            ),
            material_version=material_version,
        )

    @staticmethod
    def _candidate_claim(candidate: SourceReferenceCandidate) -> dict[str, object]:
        return {
            "type": SOURCE_CANDIDATE_CLAIM,
            "candidate": candidate.model_dump(mode="json"),
        }

    @staticmethod
    def _latest_analyses(
        analyses: tuple[SubmissionAnalysis, ...],
    ) -> tuple[SubmissionAnalysis, ...]:
        latest: dict[UUID, SubmissionAnalysis] = {}
        for analysis in analyses:
            current = latest.get(analysis.submission_id)
            if current is None or analysis.analysis_version > current.analysis_version:
                latest[analysis.submission_id] = analysis
        return tuple(latest[key] for key in sorted(latest, key=str))

    @staticmethod
    def _candidates_from_analyses(
        analyses: tuple[SubmissionAnalysis, ...],
    ) -> list[SourceReferenceCandidate]:
        candidates: dict[UUID, SourceReferenceCandidate] = {}
        for analysis in analyses:
            for claim in analysis.claims:
                if claim.get("type") != SOURCE_CANDIDATE_CLAIM:
                    continue
                payload = claim.get("candidate")
                if not isinstance(payload, dict):
                    continue
                candidate = SourceReferenceCandidate.model_validate(payload)
                candidates[candidate.source_id] = candidate
        return [candidates[key] for key in sorted(candidates, key=str)]

    @staticmethod
    def _aggregate_material_version(
        analyses: tuple[SubmissionAnalysis, ...],
    ) -> str:
        identity = "|".join(
            f"{analysis.submission_id}:{analysis.analysis_version}:{analysis.analysis_id}"
            for analysis in analyses
        )
        return f"aggregate-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:32]}"

    def _record_failed(
        self,
        context: TenantContext,
        submission_id: UUID,
        failure_code: str,
    ) -> None:
        """Leave a terminal state so the applicant is not stuck on 분석 중 forever."""
        submission = self._repository.get_submission(context, submission_id)
        if submission.status is not SubmissionStatus.ANALYZING:
            return
        self._repository.save_submission(
            context,
            submission.transition(
                SubmissionStatus.FAILED,
                failure_code=failure_code,
                impact_summary=SOURCE_FAILURE_SUMMARY,
            ),
        )

    @staticmethod
    def _to_analyzing(submission: Submission) -> Submission:
        if submission.status is SubmissionStatus.RECEIVED:
            return submission.transition(SubmissionStatus.VALIDATING).transition(
                SubmissionStatus.ANALYZING
            )
        if submission.status is SubmissionStatus.FAILED:
            return submission.transition(SubmissionStatus.VALIDATING).transition(
                SubmissionStatus.ANALYZING
            )
        if submission.status is SubmissionStatus.PARTIAL:
            return submission.transition(SubmissionStatus.ANALYZING)
        if submission.status is SubmissionStatus.ANALYZING:
            return submission
        raise NonRetryableAnalysisError("submission_state_not_analyzable")
