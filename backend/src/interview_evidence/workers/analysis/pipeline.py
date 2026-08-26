from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from interview_evidence.shared.aws_clients.ports import (
    AIModel,
    EmbeddingProviderError,
    TextEmbedder,
)
from interview_evidence.shared.ids import Clock, new_uuid7
from interview_evidence.shared.messaging.outbox import Outbox
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.submission_analysis.adapters.search import (
    CurrentDocumentLookup,
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
    expand_commit_code_units,
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
from interview_evidence.workers.analysis.git_evidence_selector import (
    GitEvidenceCandidate,
    select_git_evidence,
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
MAX_GIT_CODE_UNITS = 60
MAX_GIT_CODE_UNITS_PER_COMMIT = 12
MAX_GIT_EMBEDDING_CHARACTERS = 54_000

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
MAX_EMBEDDING_CHARACTERS = 50_000


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


@dataclass(frozen=True, slots=True)
class _PendingAxisDocument:
    document_id: str
    source_id: UUID
    text: str
    locator: dict[str, object]
    criterion_id: UUID | None
    document_type: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class _PendingCodeDocument:
    unit: CandidateCodeUnit
    text: str
    locator: dict[str, object]
    ownership_confidence: float
    commit_sha: str
    content_hash: str


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

    def embed_many(
        self,
        context: TenantContext,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]:
        bounded_texts = tuple(text[:MAX_EMBEDDING_INPUT_CHARACTERS] for text in texts)
        batch_embed = getattr(self._text_embedder, "embed_many", None)
        if callable(batch_embed):
            return tuple(batch_embed(context, bounded_texts, dimensions=1024))
        return tuple(self.embed(context, text) for text in bounded_texts)

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
        except EmbeddingProviderError as error:
            raise RetryableAnalysisError("embedding_provider_unavailable") from error

    def _process_document(
        self,
        context: TenantContext,
        submission: Submission,
        job: AnalysisJob,
    ) -> AnalysisResult:
        if submission.content_hash is None:
            raise NonRetryableAnalysisError("document_integrity_metadata_missing")
        analyzing = self._to_analyzing(submission)
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
        vectors = self.embed_many(context, tuple(draft.text for draft in drafts))
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
                embedding_version=self._text_embedder.embedding_version,
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
        self._repository.save_submission(context, analyzing)
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
        for draft, chunk, vector in zip(drafts, chunks, vectors, strict=True):
            locator = chunk.source_location.model_dump(mode="json", exclude_none=True)
            self._search_index.add(
                SearchDocument(
                    document_id=chunk.index_document_id,
                    company_id=context.company_id,
                    applicant_id=submission.applicant_id,
                    source_id=chunk.chunk_id,
                    text=draft.text,
                    vector=vector,
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
                    embedding_version=self._text_embedder.embedding_version,
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
        for previous in self._repository.list_git_repository_analyses(
            context,
            frozenset({submission.submission_id}),
        ):
            if previous.status is GitAnalysisStatus.RUNNING:
                self._repository.save_git_repository_analysis(
                    context,
                    previous.model_copy(update={"status": GitAnalysisStatus.FAILED}),
                )
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
                    "max_code_units": MAX_GIT_CODE_UNITS,
                    "max_embedding_characters": MAX_GIT_EMBEDDING_CHARACTERS,
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
                        author_login=commit.author_login,
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
        pending_code_documents: list[_PendingCodeDocument] = []
        candidates: list[SourceReferenceCandidate] = []
        commit_by_sha = {
            commit.commit_sha: (commit, analysis)
            for commit, analysis in zip(snapshot.commits, commits, strict=True)
        }
        for commit_sha, (commit, commit_analysis) in commit_by_sha.items():
            commit_files = {**head_files, **files_by_commit.get(commit_sha, {})}
            for path, ranges in commit.changed_line_ranges.items():
                if path not in commit_files:
                    continue
                source = commit_files[path]
                related = {
                    candidate_path: related_source
                    for candidate_path, related_source in related_corpus.items()
                    if candidate_path != path
                }
                for expanded in expand_commit_code_units(
                    path=path,
                    source=source,
                    changed_line_ranges=ranges,
                    related_files=related,
                ):
                    excerpt = self._code_unit_excerpt(source, expanded.line_range)
                    document_text = "\n".join(
                        value
                        for value in (
                            f"커밋: {commit.message}" if commit.message else "",
                            f"파일: {expanded.path}",
                            excerpt,
                        )
                        if value
                    )
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
                    if commit.message:
                        locator["commit_message"] = commit.message
                    content_hash = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
                    pending_code_documents.append(
                        _PendingCodeDocument(
                            unit=unit,
                            text=document_text,
                            locator=locator,
                            ownership_confidence=commit_analysis.ownership_confidence,
                            commit_sha=commit_sha,
                            content_hash=content_hash,
                        )
                    )
        if not code_units:
            return self._record_partial_git(context, analyzing, job)
        discovered_code_unit_count = len(code_units)
        selection = select_git_evidence(
            tuple(
                GitEvidenceCandidate(
                    original_index=index,
                    commit_sha=document.commit_sha,
                    path=document.unit.path,
                    symbol=document.unit.symbol,
                    text=document.text,
                    content_hash=document.content_hash,
                    ownership_confidence=document.ownership_confidence,
                    line_range=document.unit.current_line_range,
                    candidate_owned_regions=document.unit.candidate_owned_regions,
                    related_test_paths=document.unit.related_test_ids,
                )
                for index, document in enumerate(pending_code_documents)
            ),
            max_units=MAX_GIT_CODE_UNITS,
            max_units_per_commit=MAX_GIT_CODE_UNITS_PER_COMMIT,
            max_characters=MAX_GIT_EMBEDDING_CHARACTERS,
            max_characters_per_unit=MAX_EMBEDDING_INPUT_CHARACTERS,
        )
        selected_units: list[CandidateCodeUnit] = []
        selected_documents: list[_PendingCodeDocument] = []
        for selected in selection:
            unit = code_units[selected.original_index]
            document = pending_code_documents[selected.original_index]
            locator = {
                **document.locator,
                "project_area": selected.project_area,
                "selection_score": selected.score,
                "selection_reasons": list(selected.selection_reasons),
            }
            selected_units.append(unit)
            selected_documents.append(replace(document, locator=locator))
            candidates.append(
                SourceReferenceCandidate(
                    source_id=unit.code_unit_id,
                    source_type="candidate_code_unit",
                    locator=locator,
                    content_hash=document.content_hash,
                    relevance_score=1.0,
                    ownership_confidence=document.ownership_confidence,
                )
            )
        code_units = selected_units
        pending_code_documents = selected_documents
        try:
            vectors = self.embed_many(
                context,
                tuple(document.text for document in pending_code_documents),
            )
        except EmbeddingProviderError:
            self._repository.save_git_repository_analysis(
                context,
                repository_analysis.model_copy(update={"status": GitAnalysisStatus.FAILED}),
            )
            raise
        for document, vector in zip(pending_code_documents, vectors, strict=True):
            self._search_index.add(
                SearchDocument(
                    document_id=str(document.unit.code_unit_id),
                    company_id=context.company_id,
                    applicant_id=submission.applicant_id,
                    source_id=document.unit.code_unit_id,
                    text=f"{document.unit.symbol}\n{document.text}",
                    vector=vector,
                    symbols=(document.unit.symbol,),
                    locator=document.locator,
                    ownership_confidence=document.ownership_confidence,
                    invitation_id=submission.invitation_id,
                    competency_model_version_id=axis.competency_model_version_id,
                    document_type="code_unit",
                    source_type="candidate_code_unit",
                    source_version=document.commit_sha,
                    content_hash=document.content_hash,
                    embedding_model=self._text_embedder.model_id,
                    embedding_version=self._text_embedder.embedding_version,
                    path=document.unit.path,
                    symbol=document.unit.symbol,
                )
            )
        self._repository.save_code_units(context, tuple(code_units))
        analysis = self._repository.save_analysis(
            context,
            SubmissionAnalysis(
                analysis_id=new_uuid7(occurred_at),
                company_id=context.company_id,
                submission_id=submission.submission_id,
                analysis_version=job.analysis_version,
                extractor_version="bounded-ranked-public-git-v3",
                chunk_config_version="ranked-commit-code-units-v3",
                claims=(
                    {
                        "type": "public_git_snapshot",
                        "analysis_basis": "candidate_commit_changes",
                        "commit_count": len(commits),
                        "code_unit_count": len(code_units),
                        "discovered_code_unit_count": discovered_code_unit_count,
                        "changed_file_count": len(
                            {
                                document.unit.path
                                for document in pending_code_documents
                            }
                        ),
                        "language_count": len(
                            {
                                document.unit.language
                                for document in pending_code_documents
                            }
                        ),
                        "project_area_count": len(
                            {
                                document.locator["project_area"]
                                for document in pending_code_documents
                            }
                        ),
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
    def _code_unit_excerpt(source: str, line_range: tuple[int, int]) -> str:
        lines = source.splitlines()
        start, end = line_range
        excerpt = "\n".join(lines[max(0, start - 1) : min(len(lines), end)]).strip()
        if not excerpt:
            raise NonRetryableAnalysisError("public_git_code_unit_empty")
        return excerpt[:MAX_EMBEDDING_CHARACTERS]

    def _index_criterion_axis(
        self,
        context: TenantContext,
        axis: AnalysisAxis,
    ) -> None:
        pending: list[_PendingAxisDocument] = []
        for criterion in axis.criteria:
            text = " ".join(
                (
                    criterion.name,
                    criterion.description,
                    *criterion.observable_dimensions,
                    *criterion.follow_up_directions,
                )
            )
            document_id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"{axis.competency_model_version_id}:criterion:{criterion.criterion_id}",
                )
            )
            content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if self._axis_document_is_current(context, document_id, content_hash):
                continue
            pending.append(
                _PendingAxisDocument(
                    document_id=document_id,
                    source_id=criterion.criterion_id,
                    text=text,
                    locator={"criterion_code": criterion.code},
                    criterion_id=criterion.criterion_id,
                    document_type="criterion_guide",
                    content_hash=content_hash,
                )
            )
        for requirement in axis.requirements:
            document_id = str(
                uuid5(
                    NAMESPACE_URL,
                    (
                        f"{axis.competency_model_version_id}:"
                        f"requirement:{requirement.job_requirement_id}"
                    ),
                )
            )
            content_hash = hashlib.sha256(requirement.statement.encode("utf-8")).hexdigest()
            if self._axis_document_is_current(context, document_id, content_hash):
                continue
            pending.append(
                _PendingAxisDocument(
                    document_id=document_id,
                    source_id=requirement.job_requirement_id,
                    text=requirement.statement,
                    locator={"criterion_code": requirement.criterion_code},
                    criterion_id=None,
                    document_type="job_requirement",
                    content_hash=content_hash,
                )
            )
        if not pending:
            return
        vectors = self.embed_many(context, tuple(item.text for item in pending))
        for item, vector in zip(pending, vectors, strict=True):
            self._search_index.add(
                SearchDocument(
                    document_id=item.document_id,
                    company_id=context.company_id,
                    applicant_id=UUID(int=0),
                    source_id=item.source_id,
                    text=item.text,
                    vector=vector,
                    symbols=(),
                    locator=item.locator,
                    ownership_confidence=1.0,
                    competency_model_version_id=axis.competency_model_version_id,
                    criterion_id=item.criterion_id,
                    document_type=item.document_type,
                    source_type=item.document_type,
                    source_version=str(axis.version_number),
                    content_hash=item.content_hash,
                    embedding_model=self._text_embedder.model_id,
                    embedding_version=self._text_embedder.embedding_version,
                )
            )

    def _axis_document_is_current(
        self,
        context: TenantContext,
        document_id: str,
        content_hash: str,
    ) -> bool:
        if not isinstance(self._search_index, CurrentDocumentLookup):
            return False
        return self._search_index.has_current_document(
            company_id=context.company_id,
            document_id=document_id,
            content_hash=content_hash,
            embedding_model=self._text_embedder.model_id,
            embedding_version=self._text_embedder.embedding_version,
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
        if submission.status not in {
            SubmissionStatus.RECEIVED,
            SubmissionStatus.VALIDATING,
            SubmissionStatus.ANALYZING,
        }:
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
        if submission.status is SubmissionStatus.VALIDATING:
            return submission.transition(SubmissionStatus.ANALYZING)
        if submission.status is SubmissionStatus.FAILED:
            return submission.transition(SubmissionStatus.VALIDATING).transition(
                SubmissionStatus.ANALYZING
            )
        if submission.status is SubmissionStatus.PARTIAL:
            return submission.transition(SubmissionStatus.ANALYZING)
        if submission.status is SubmissionStatus.ANALYZING:
            return submission
        raise NonRetryableAnalysisError("submission_state_not_analyzable")
