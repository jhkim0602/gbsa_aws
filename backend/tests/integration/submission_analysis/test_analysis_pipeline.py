from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from interview_evidence.shared.aws_clients.ports import (
    EmbeddingProviderError,
    StaticTextEmbedder,
)
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.messaging.outbox import InMemoryOutbox
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.adapters.search import InMemorySearchIndex
from interview_evidence.submission_analysis.application.strategy_prompt import (
    strategy_task_payload_of,
)
from interview_evidence.submission_analysis.domain.git_analysis import (
    CommitIdentityInput,
    OwnershipClass,
)
from interview_evidence.submission_analysis.domain.submission import (
    SourceType,
    Submission,
    SubmissionStatus,
)
from interview_evidence.submission_analysis.repositories.postgres import (
    InMemorySubmissionRepository,
)
from interview_evidence.workers.analysis.document_extract import (
    DeterministicTextract,
    DocumentExtractionAdapter,
    TextractPage,
)
from interview_evidence.workers.analysis.git_fetch import (
    BoundedGitFetcher,
    GitFetchError,
    GitFetchLimits,
    RepositoryCommit,
    RepositoryFile,
    RepositorySnapshot,
    StaticGitTransport,
)
from interview_evidence.workers.analysis.handlers import (
    AnalysisJob,
    JobStatus,
    NonRetryableAnalysisError,
    RetryableAnalysisError,
)
from interview_evidence.workers.analysis.pipeline import (
    AnalysisAxis,
    SubmissionAnalysisPipeline,
)

NOW = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000201")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000202")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000203")
SUBMISSION_ID = UUID("00000000-0000-7000-8000-000000000204")
CRITERION_VERSION_ID = UUID("00000000-0000-7000-8000-000000000205")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000206")


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=APPLICANT_ID,
        request_id=SUBMISSION_ID,
        trace_id="analysis-pipeline",
    )


@dataclass(frozen=True, slots=True)
class StaticAxisProvider:
    def get_axis(
        self,
        _context: TenantContext,
        *,
        invitation_id: UUID,
    ) -> AnalysisAxis:
        assert invitation_id == INVITATION_ID
        return AnalysisAxis(
            competency_model_version_id=CRITERION_VERSION_ID,
            criterion_ids=(CRITERION_ID,),
        )


class SourceAwareModel:
    def generate(
        self,
        _context: TenantContext,
        model_input: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        payload = strategy_task_payload_of(model_input)
        assert payload is not None
        source_candidates = payload["provided_source_candidates"]
        assert isinstance(source_candidates, list)
        first_source = source_candidates[0]
        assert isinstance(first_source, dict)
        return {
            "common_topics": ["문제 해결"],
            "verification_points": [
                {
                    "criterion_id": str(CRITERION_ID),
                    "prompt": "장애 원인과 대안을 구체적으로 설명해 주세요.",
                    "source_ids": [first_source["source_id"]],
                }
            ],
            "follow_up_directions": {str(CRITERION_ID): ["대안의 트레이드오프 확인"]},
            "time_budget": {"total_seconds": 1800},
            "required_evidence_plan": {str(CRITERION_ID): 1},
        }


class UnavailableEmbedder:
    model_id = "unavailable-embedder"
    embedding_version = "unavailable-v1"

    def embed(
        self,
        _context: TenantContext,
        _text: str,
        *,
        dimensions: int = 1024,
    ) -> tuple[float, ...]:
        del dimensions
        raise EmbeddingProviderError("provider unavailable")


class BatchRecordingEmbedder(StaticTextEmbedder):
    def __init__(self, vector: tuple[float, ...]) -> None:
        super().__init__(vector)
        self.batch_calls: list[tuple[str, ...]] = []

    def embed_many(
        self,
        context: TenantContext,
        texts: tuple[str, ...],
        *,
        dimensions: int = 1024,
    ) -> tuple[tuple[float, ...], ...]:
        self.batch_calls.append(texts)
        return tuple(self.embed(context, text, dimensions=dimensions) for text in texts)


def test_document_event_creates_durable_chunks_search_records_and_strategy() -> None:
    repository = InMemorySubmissionRepository()
    repository.save_submission(
        _context(),
        Submission(
            submission_id=SUBMISSION_ID,
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            source_type=SourceType.PDF,
            source_uri=f"tenants/{COMPANY_ID}/original/{SUBMISSION_ID}",
            original_filename="resume.pdf",
            content_hash="a" * 64,
            byte_size=128,
            media_type="application/pdf",
            created_at=NOW,
        ),
    )
    search = InMemorySearchIndex()
    outbox = InMemoryOutbox()
    embedder = StaticTextEmbedder(tuple(1.0 if index == 0 else 0.0 for index in range(1024)))
    pipeline = SubmissionAnalysisPipeline(
        repository=repository,
        extractor=DocumentExtractionAdapter(
            DeterministicTextract(
                (
                    TextractPage(
                        page_number=1,
                        lines=("프로젝트", "결제 장애율을 30% 줄였습니다."),
                    ),
                )
            ),
            extractor_version="textract-v1",
        ),
        search_index=search,
        text_embedder=embedder,
        strategy_model=SourceAwareModel(),
        axis_provider=StaticAxisProvider(),
        outbox=outbox,
        clock=FrozenClock(NOW),
    )

    result = pipeline.process(
        _context(),
        AnalysisJob(
            submission_id=SUBMISSION_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            analysis_version=1,
            source_type=SourceType.PDF,
            source_object_id=SUBMISSION_ID,
            idempotency_key="analysis-request-0001",
        ),
    )

    assert result.status is JobStatus.READY
    submission = repository.get_submission(_context(), SUBMISSION_ID)
    assert submission.status is SubmissionStatus.READY
    chunks = repository.list_chunks(_context(), APPLICANT_ID)
    assert len(chunks) == 1
    assert search.candidates(
        _context(),
        applicant_id=APPLICANT_ID,
        query="결제 장애율",
        query_vector=embedder.embed(_context(), "결제 장애율"),
        exact_symbol=None,
    )
    assert pipeline.finalize_invitation(
        _context(),
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        submission_ids=frozenset({SUBMISSION_ID}),
    )
    strategy = repository.latest_strategy(_context(), INVITATION_ID)
    assert strategy is not None
    assert strategy.competency_model_version_id == CRITERION_VERSION_ID
    assert outbox.pending()[-1].event_type == "strategy.ready"


def test_embedding_provider_failure_uses_analysis_retry_contract() -> None:
    repository = InMemorySubmissionRepository()
    repository.save_submission(
        _context(),
        _pdf_submission(SUBMISSION_ID, "resume.pdf"),
    )
    pipeline = SubmissionAnalysisPipeline(
        repository=repository,
        extractor=DocumentExtractionAdapter(
            DeterministicTextract(
                (
                    TextractPage(
                        page_number=1,
                        lines=("결제 장애율을 30% 줄이고 재처리 큐를 설계했습니다.",),
                    ),
                )
            ),
            extractor_version="textract-v1",
        ),
        search_index=InMemorySearchIndex(),
        text_embedder=UnavailableEmbedder(),
        strategy_model=SourceAwareModel(),
        axis_provider=StaticAxisProvider(),
        outbox=InMemoryOutbox(),
        clock=FrozenClock(NOW),
    )

    with pytest.raises(RetryableAnalysisError, match="embedding_provider_unavailable"):
        pipeline.process(
            _context(),
            AnalysisJob(
                submission_id=SUBMISSION_ID,
                invitation_id=INVITATION_ID,
                applicant_id=APPLICANT_ID,
                analysis_version=1,
                source_type=SourceType.PDF,
                source_object_id=SUBMISSION_ID,
                idempotency_key="analysis-embedding-retry-0001",
            ),
        )

    assert repository.get_submission(_context(), SUBMISSION_ID).status is SubmissionStatus.RECEIVED
    assert repository.list_analyses(_context(), frozenset({SUBMISSION_ID})) == ()
    assert repository.list_chunks(_context(), APPLICANT_ID) == ()


def test_public_git_event_persists_code_units_and_exact_symbol_index() -> None:
    repository = InMemorySubmissionRepository()
    repository.save_submission(
        _context(),
        Submission(
            submission_id=SUBMISSION_ID,
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            source_type=SourceType.PUBLIC_GIT,
            source_uri="https://github.com/example/candidate-project",
            candidate_identity_inputs={"claimed_names": ("홍길동",)},
            created_at=NOW,
        ),
    )
    search = InMemorySearchIndex()
    embedder = StaticTextEmbedder(tuple(1.0 if index == 0 else 0.0 for index in range(1024)))
    pipeline = SubmissionAnalysisPipeline(
        repository=repository,
        extractor=DocumentExtractionAdapter(
            DeterministicTextract(()),
            extractor_version="textract-v1",
        ),
        search_index=search,
        text_embedder=embedder,
        strategy_model=SourceAwareModel(),
        axis_provider=StaticAxisProvider(),
        outbox=InMemoryOutbox(),
        clock=FrozenClock(NOW),
        git_fetcher=BoundedGitFetcher(
            StaticGitTransport(
                RepositorySnapshot(
                    repository_url="https://github.com/example/candidate-project",
                    default_branch="main",
                    pinned_head_sha="b" * 40,
                    files=(
                        RepositoryFile(
                            path="src/payment.py",
                            content=b"def retry_payment():\n    return True\n",
                        ),
                        RepositoryFile(
                            path="tests/test_payment.py",
                            content=b"def test_retry_payment():\n    retry_payment()\n",
                        ),
                    ),
                    commit_count=1,
                    commits=(
                        RepositoryCommit(
                            parent_sha="a" * 40,
                            commit_sha="b" * 40,
                            author_name="홍길동",
                            author_email="unverified@example.com",
                            changed_line_ranges={"src/payment.py": ((1, 2),)},
                        ),
                    ),
                )
            ),
            GitFetchLimits(),
        ),
    )

    result = pipeline.process(
        _context(),
        AnalysisJob(
            submission_id=SUBMISSION_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            analysis_version=1,
            source_type=SourceType.PUBLIC_GIT,
            source_object_id=SUBMISSION_ID,
            idempotency_key="analysis-git-request-0001",
        ),
    )

    assert result.status is JobStatus.READY
    repository_analyses = repository.list_git_repository_analyses(
        _context(), frozenset({SUBMISSION_ID})
    )
    commits = repository.list_git_commit_analyses(
        _context(),
        frozenset({repository_analyses[0].repository_analysis_id}),
    )
    assert commits[0].ownership_class is OwnershipClass.CONTEXT_ONLY
    units = repository.list_code_units(
        _context(),
        frozenset({commits[0].git_commit_analysis_id}),
    )
    assert units[0].symbol == "retry_payment"
    matches = search.candidates(
        _context(),
        applicant_id=APPLICANT_ID,
        query="retry payment",
        query_vector=embedder.embed(_context(), "retry payment"),
        exact_symbol="retry_payment",
    )
    assert matches[0].exact_symbol_score == 1.0
    assert matches[0].document.ownership_confidence < 0.5
    assert matches[0].document.locator["project_area"] == "src"
    assert matches[0].document.locator["selection_score"] > 0
    assert "related_tests" in matches[0].document.locator["selection_reasons"]


def test_public_git_limits_code_units_before_embedding() -> None:
    repository = InMemorySubmissionRepository()
    repository.save_submission(
        _context(),
        Submission(
            submission_id=SUBMISSION_ID,
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            source_type=SourceType.PUBLIC_GIT,
            source_uri="https://github.com/example/large-candidate-project",
            candidate_identity_inputs={"claimed_names": ("홍길동",)},
            created_at=NOW,
        ),
    )
    source = "\n\n".join(
        f"def candidate_function_{index}():\n    return {index}" for index in range(20)
    )
    embedder = BatchRecordingEmbedder(tuple(1.0 if index == 0 else 0.0 for index in range(1024)))
    pipeline = SubmissionAnalysisPipeline(
        repository=repository,
        extractor=DocumentExtractionAdapter(
            DeterministicTextract(()),
            extractor_version="textract-v1",
        ),
        search_index=InMemorySearchIndex(),
        text_embedder=embedder,
        strategy_model=SourceAwareModel(),
        axis_provider=StaticAxisProvider(),
        outbox=InMemoryOutbox(),
        clock=FrozenClock(NOW),
        git_fetcher=BoundedGitFetcher(
            StaticGitTransport(
                RepositorySnapshot(
                    repository_url="https://github.com/example/large-candidate-project",
                    default_branch="main",
                    pinned_head_sha="b" * 40,
                    files=(
                        RepositoryFile(
                            path="src/candidate.py",
                            content=source.encode(),
                        ),
                    ),
                    commit_count=1,
                    commits=(
                        RepositoryCommit(
                            parent_sha="a" * 40,
                            commit_sha="b" * 40,
                            author_name="홍길동",
                            author_email="applicant@example.com",
                            changed_line_ranges={
                                "src/candidate.py": ((1, source.count("\n") + 1),)
                            },
                        ),
                    ),
                )
            ),
            GitFetchLimits(),
        ),
    )

    result = pipeline.process(
        _context(),
        AnalysisJob(
            submission_id=SUBMISSION_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            analysis_version=1,
            source_type=SourceType.PUBLIC_GIT,
            source_object_id=SUBMISSION_ID,
            idempotency_key="analysis-git-limit-0001",
        ),
    )

    assert result.status is JobStatus.READY
    repository_analysis = repository.list_git_repository_analyses(
        _context(), frozenset({SUBMISSION_ID})
    )[0]
    commits = repository.list_git_commit_analyses(
        _context(), frozenset({repository_analysis.repository_analysis_id})
    )
    units = repository.list_code_units(_context(), frozenset({commits[0].git_commit_analysis_id}))
    assert len(units) == 12
    assert len(embedder.batch_calls) == 1
    assert len(embedder.batch_calls[0]) == 12
    assert repository_analysis.limits_applied["max_code_units"] == 60
    analysis = repository.list_analyses(_context(), frozenset({SUBMISSION_ID}))[0]
    snapshot_claim = next(
        claim for claim in analysis.claims if claim["type"] == "public_git_snapshot"
    )
    assert snapshot_claim["discovered_code_unit_count"] == 20
    assert snapshot_claim["code_unit_count"] == 12


def test_public_git_embedding_failure_marks_repository_attempt_failed() -> None:
    repository = InMemorySubmissionRepository()
    repository.save_submission(
        _context(),
        Submission(
            submission_id=SUBMISSION_ID,
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            source_type=SourceType.PUBLIC_GIT,
            source_uri="https://github.com/example/candidate-project",
            candidate_identity_inputs={"claimed_names": ("홍길동",)},
            created_at=NOW,
        ),
    )
    pipeline = SubmissionAnalysisPipeline(
        repository=repository,
        extractor=DocumentExtractionAdapter(
            DeterministicTextract(()),
            extractor_version="textract-v1",
        ),
        search_index=InMemorySearchIndex(),
        text_embedder=UnavailableEmbedder(),
        strategy_model=SourceAwareModel(),
        axis_provider=StaticAxisProvider(),
        outbox=InMemoryOutbox(),
        clock=FrozenClock(NOW),
        git_fetcher=BoundedGitFetcher(
            StaticGitTransport(
                RepositorySnapshot(
                    repository_url="https://github.com/example/candidate-project",
                    default_branch="main",
                    pinned_head_sha="b" * 40,
                    files=(
                        RepositoryFile(
                            path="src/payment.py",
                            content=b"def retry_payment():\n    return True\n",
                        ),
                    ),
                    commit_count=1,
                    commits=(
                        RepositoryCommit(
                            parent_sha="a" * 40,
                            commit_sha="b" * 40,
                            author_name="홍길동",
                            author_email="applicant@example.com",
                            changed_line_ranges={"src/payment.py": ((1, 2),)},
                        ),
                    ),
                )
            ),
            GitFetchLimits(),
        ),
    )

    with pytest.raises(RetryableAnalysisError, match="embedding_provider_unavailable"):
        pipeline.process(
            _context(),
            AnalysisJob(
                submission_id=SUBMISSION_ID,
                invitation_id=INVITATION_ID,
                applicant_id=APPLICANT_ID,
                analysis_version=1,
                source_type=SourceType.PUBLIC_GIT,
                source_object_id=SUBMISSION_ID,
                idempotency_key="analysis-git-embedding-failure-0001",
            ),
        )

    repository_analysis = repository.list_git_repository_analyses(
        _context(), frozenset({SUBMISSION_ID})
    )[0]
    assert repository_analysis.status.value == "failed"


def test_code_unit_embedding_excerpt_excludes_unrelated_file_content() -> None:
    source = "\n".join(
        (
            "UNRELATED_SECRET_LIKE_TEXT = 'do-not-embed-with-target'",
            "",
            "def target_function():",
            "    return 'candidate code'",
            "",
            "def unrelated_function():",
            "    return 'other code'",
        )
    )

    excerpt = SubmissionAnalysisPipeline._code_unit_excerpt(source, (3, 4))

    assert excerpt == "def target_function():\n    return 'candidate code'"
    assert "UNRELATED_SECRET_LIKE_TEXT" not in excerpt
    assert "unrelated_function" not in excerpt


def test_each_analyzed_commit_contributes_its_own_code_unit_evidence() -> None:
    """Evidence has to come from the history, not only from the newest commit.

    The transport now deep-fetches several commits, so the pipeline must key blobs by the
    commit they were read at. Keying by path alone would make every commit's evidence
    quote whichever version of the file happened to be stored last, and a question built
    on the wrong revision is a question the applicant cannot answer.
    """
    repository = InMemorySubmissionRepository()
    repository.save_submission(
        _context(),
        Submission(
            submission_id=SUBMISSION_ID,
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            source_type=SourceType.PUBLIC_GIT,
            source_uri="https://github.com/example/candidate-project",
            candidate_identity_inputs={"claimed_emails": ("applicant@example.com",)},
            created_at=NOW,
        ),
    )
    older_sha, newer_sha = "c" * 40, "b" * 40
    search = InMemorySearchIndex()
    embedder = BatchRecordingEmbedder(tuple(1.0 if index == 0 else 0.0 for index in range(1024)))
    pipeline = SubmissionAnalysisPipeline(
        repository=repository,
        extractor=DocumentExtractionAdapter(
            DeterministicTextract(()),
            extractor_version="textract-v1",
        ),
        search_index=search,
        text_embedder=embedder,
        strategy_model=SourceAwareModel(),
        axis_provider=StaticAxisProvider(),
        outbox=InMemoryOutbox(),
        clock=FrozenClock(NOW),
        git_fetcher=BoundedGitFetcher(
            StaticGitTransport(
                RepositorySnapshot(
                    repository_url="https://github.com/example/candidate-project",
                    default_branch="main",
                    pinned_head_sha=newer_sha,
                    files=(
                        # The same path at two revisions, which is exactly what two
                        # commits touching one file look like.
                        RepositoryFile(
                            path="src/payment.py",
                            content=b"def retry_payment():\n    return True\n",
                            commit_sha=newer_sha,
                        ),
                        RepositoryFile(
                            path="src/payment.py",
                            content=b"def charge_card():\n    return False\n",
                            commit_sha=older_sha,
                        ),
                    ),
                    commit_count=2,
                    commits=(
                        RepositoryCommit(
                            parent_sha=older_sha,
                            commit_sha=newer_sha,
                            author_name="홍길동",
                            author_email="applicant@example.com",
                            changed_line_ranges={"src/payment.py": ((1, 2),)},
                        ),
                        RepositoryCommit(
                            parent_sha="a" * 40,
                            commit_sha=older_sha,
                            author_name="홍길동",
                            author_email="applicant@example.com",
                            changed_line_ranges={"src/payment.py": ((1, 2),)},
                        ),
                    ),
                )
            ),
            GitFetchLimits(),
        ),
    )

    result = pipeline.process(
        _context(),
        AnalysisJob(
            submission_id=SUBMISSION_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            analysis_version=1,
            source_type=SourceType.PUBLIC_GIT,
            source_object_id=SUBMISSION_ID,
            idempotency_key="analysis-git-request-0002",
        ),
    )

    assert result.status is JobStatus.READY
    repository_analyses = repository.list_git_repository_analyses(
        _context(), frozenset({SUBMISSION_ID})
    )
    assert repository_analyses[0].limits_applied["analyzed_commits"] == 2
    commits = repository.list_git_commit_analyses(
        _context(),
        frozenset({repository_analyses[0].repository_analysis_id}),
    )
    assert {commit.commit_sha for commit in commits} == {newer_sha, older_sha}
    # A matching email alone is attributable but not conclusive -- the classifier wants a
    # matching name too before it calls a commit primarily the candidate's.
    assert all(commit.ownership_class is OwnershipClass.SHARED for commit in commits)
    symbols_by_sha = {
        commit.commit_sha: {
            unit.symbol
            for unit in repository.list_code_units(
                _context(),
                frozenset({commit.git_commit_analysis_id}),
            )
        }
        for commit in commits
    }
    # Each commit quotes the revision of the file it actually changed.
    assert symbols_by_sha[newer_sha] == {"retry_payment"}
    assert symbols_by_sha[older_sha] == {"charge_card"}
    assert len(embedder.batch_calls) == 1
    assert set(embedder.batch_calls[0]) == {
        "def retry_payment():\n    return True",
        "def charge_card():\n    return False",
    }


class IdentityRecordingGitTransport(StaticGitTransport):
    """A static transport that also remembers the identity it was asked to filter by."""

    def __init__(self, snapshot: RepositorySnapshot) -> None:
        super().__init__(snapshot)
        self.identities: list[CommitIdentityInput | None] = []

    def fetch(
        self,
        repository_url: str,
        *,
        limits: GitFetchLimits,
        identity: CommitIdentityInput | None = None,
    ) -> RepositorySnapshot:
        self.identities.append(identity)
        return super().fetch(repository_url, limits=limits, identity=identity)


def test_the_applicant_identity_reaches_the_transport_before_the_fetch() -> None:
    """The transport can only filter by author if the pipeline tells it who to look for.

    The identity used to be parsed after the fetch, purely to classify ownership. Passing
    it in first is what lets the GitHub listing be filtered server-side, so the API budget
    is spent on the applicant's own commits rather than on the branch's newest ones.
    """
    repository = InMemorySubmissionRepository()
    repository.save_submission(
        _context(),
        Submission(
            submission_id=SUBMISSION_ID,
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            source_type=SourceType.PUBLIC_GIT,
            source_uri="https://github.com/example/candidate-project",
            candidate_identity_inputs={
                "claimed_names": ("홍길동",),
                "claimed_emails": ("applicant@example.com",),
                "claimed_handles": ("hong",),
            },
            created_at=NOW,
        ),
    )
    transport = IdentityRecordingGitTransport(
        RepositorySnapshot(
            repository_url="https://github.com/example/candidate-project",
            default_branch="main",
            pinned_head_sha="b" * 40,
            files=(
                RepositoryFile(
                    path="src/payment.py",
                    content=b"def retry_payment():\n    return True\n",
                ),
            ),
            commit_count=1,
            commits=(
                RepositoryCommit(
                    parent_sha="a" * 40,
                    commit_sha="b" * 40,
                    author_name="홍길동",
                    author_email="applicant@example.com",
                    changed_line_ranges={"src/payment.py": ((1, 2),)},
                ),
            ),
        )
    )
    pipeline = SubmissionAnalysisPipeline(
        repository=repository,
        extractor=DocumentExtractionAdapter(
            DeterministicTextract(()),
            extractor_version="textract-v1",
        ),
        search_index=InMemorySearchIndex(),
        text_embedder=StaticTextEmbedder(
            tuple(1.0 if index == 0 else 0.0 for index in range(1024))
        ),
        strategy_model=SourceAwareModel(),
        axis_provider=StaticAxisProvider(),
        outbox=InMemoryOutbox(),
        clock=FrozenClock(NOW),
        git_fetcher=BoundedGitFetcher(transport, GitFetchLimits()),
    )

    result = pipeline.process(
        _context(),
        AnalysisJob(
            submission_id=SUBMISSION_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            analysis_version=1,
            source_type=SourceType.PUBLIC_GIT,
            source_object_id=SUBMISSION_ID,
            idempotency_key="analysis-git-request-0004",
        ),
    )

    assert result.status is JobStatus.READY
    assert transport.identities == [
        CommitIdentityInput(
            claimed_names=("홍길동",),
            claimed_emails=("applicant@example.com",),
            claimed_handles=("hong",),
        )
    ]


def test_a_file_that_does_not_parse_does_not_lose_the_rest_of_the_repository() -> None:
    """Real repositories contain Python this interpreter cannot parse.

    Analyzing many commits instead of one makes hitting such a file likely. It yields no
    evidence, but the readable commits must still produce theirs.
    """
    repository = InMemorySubmissionRepository()
    repository.save_submission(
        _context(),
        Submission(
            submission_id=SUBMISSION_ID,
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            source_type=SourceType.PUBLIC_GIT,
            source_uri="https://github.com/example/candidate-project",
            candidate_identity_inputs={"claimed_names": ("홍길동",)},
            created_at=NOW,
        ),
    )
    pipeline = SubmissionAnalysisPipeline(
        repository=repository,
        extractor=DocumentExtractionAdapter(
            DeterministicTextract(()),
            extractor_version="textract-v1",
        ),
        search_index=InMemorySearchIndex(),
        text_embedder=StaticTextEmbedder(
            tuple(1.0 if index == 0 else 0.0 for index in range(1024))
        ),
        strategy_model=SourceAwareModel(),
        axis_provider=StaticAxisProvider(),
        outbox=InMemoryOutbox(),
        clock=FrozenClock(NOW),
        git_fetcher=BoundedGitFetcher(
            StaticGitTransport(
                RepositorySnapshot(
                    repository_url="https://github.com/example/candidate-project",
                    default_branch="main",
                    pinned_head_sha="b" * 40,
                    files=(
                        RepositoryFile(
                            path="src/legacy.py",
                            content=b"print 'python 2 syntax'\n",
                        ),
                        RepositoryFile(
                            path="src/payment.py",
                            content=b"def retry_payment():\n    return True\n",
                        ),
                    ),
                    commit_count=1,
                    commits=(
                        RepositoryCommit(
                            parent_sha="a" * 40,
                            commit_sha="b" * 40,
                            author_name="홍길동",
                            author_email="applicant@example.com",
                            changed_line_ranges={
                                "src/legacy.py": ((1, 1),),
                                "src/payment.py": ((1, 2),),
                            },
                        ),
                    ),
                )
            ),
            GitFetchLimits(),
        ),
    )

    result = pipeline.process(
        _context(),
        AnalysisJob(
            submission_id=SUBMISSION_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            analysis_version=1,
            source_type=SourceType.PUBLIC_GIT,
            source_object_id=SUBMISSION_ID,
            idempotency_key="analysis-git-request-0003",
        ),
    )

    assert result.status is JobStatus.READY
    repository_analyses = repository.list_git_repository_analyses(
        _context(), frozenset({SUBMISSION_ID})
    )
    commits = repository.list_git_commit_analyses(
        _context(),
        frozenset({repository_analyses[0].repository_analysis_id}),
    )
    units = repository.list_code_units(
        _context(),
        frozenset({commits[0].git_commit_analysis_id}),
    )
    assert {unit.symbol for unit in units} == {"retry_payment"}


class FailingGitTransport:
    def __init__(self, failure_code: str) -> None:
        self._failure_code = failure_code

    def fetch(
        self,
        repository_url: str,
        *,
        limits: GitFetchLimits,
        identity: CommitIdentityInput | None = None,
    ) -> RepositorySnapshot:
        del repository_url, limits, identity
        raise GitFetchError(self._failure_code)


def _git_pipeline(
    repository: InMemorySubmissionRepository,
    transport: FailingGitTransport,
) -> SubmissionAnalysisPipeline:
    return SubmissionAnalysisPipeline(
        repository=repository,
        extractor=DocumentExtractionAdapter(
            DeterministicTextract(()),
            extractor_version="textract-v1",
        ),
        search_index=InMemorySearchIndex(),
        text_embedder=StaticTextEmbedder(
            tuple(1.0 if index == 0 else 0.0 for index in range(1024))
        ),
        strategy_model=SourceAwareModel(),
        axis_provider=StaticAxisProvider(),
        outbox=InMemoryOutbox(),
        clock=FrozenClock(NOW),
        git_fetcher=BoundedGitFetcher(transport, GitFetchLimits()),
    )


def _git_repository() -> InMemorySubmissionRepository:
    repository = InMemorySubmissionRepository()
    repository.save_submission(
        _context(),
        Submission(
            submission_id=SUBMISSION_ID,
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            source_type=SourceType.PUBLIC_GIT,
            source_uri="https://github.com/example/payments",
            created_at=NOW,
        ),
    )
    return repository


def _git_job() -> AnalysisJob:
    return AnalysisJob(
        submission_id=SUBMISSION_ID,
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        analysis_version=1,
        source_type=SourceType.PUBLIC_GIT,
        source_object_id=SUBMISSION_ID,
        idempotency_key="analysis-git-failure-0001",
    )


def test_transient_source_failure_is_retryable_and_never_escapes_the_processor() -> None:
    repository = _git_repository()
    pipeline = _git_pipeline(repository, FailingGitTransport("public_git_fetch_failed"))

    with pytest.raises(RetryableAnalysisError, match="public_git_fetch_failed"):
        pipeline.process(_context(), _git_job())

    # A retryable attempt keeps the submission analyzable for the next delivery.
    assert repository.get_submission(_context(), SUBMISSION_ID).status is (
        SubmissionStatus.ANALYZING
    )


def test_permanent_source_failure_records_a_terminal_submission_state() -> None:
    repository = _git_repository()
    pipeline = _git_pipeline(repository, FailingGitTransport("github_repository_url_invalid"))

    with pytest.raises(NonRetryableAnalysisError, match="github_repository_url_invalid"):
        pipeline.process(_context(), _git_job())

    submission = repository.get_submission(_context(), SUBMISSION_ID)
    assert submission.status is SubmissionStatus.FAILED
    assert submission.failure_code == "github_repository_url_invalid"
    assert submission.impact_summary is not None


def test_document_extraction_failure_records_a_terminal_submission_state() -> None:
    repository = InMemorySubmissionRepository()
    repository.save_submission(
        _context(),
        Submission(
            submission_id=SUBMISSION_ID,
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            source_type=SourceType.PDF,
            source_uri=f"tenants/{COMPANY_ID}/original/{SUBMISSION_ID}",
            original_filename="resume.pdf",
            content_hash="a" * 64,
            byte_size=128,
            media_type="application/pdf",
            created_at=NOW,
        ),
    )
    pipeline = SubmissionAnalysisPipeline(
        repository=repository,
        extractor=DocumentExtractionAdapter(
            DeterministicTextract(()),
            extractor_version="textract-v1",
        ),
        search_index=InMemorySearchIndex(),
        text_embedder=StaticTextEmbedder(
            tuple(1.0 if index == 0 else 0.0 for index in range(1024))
        ),
        strategy_model=SourceAwareModel(),
        axis_provider=StaticAxisProvider(),
        outbox=InMemoryOutbox(),
        clock=FrozenClock(NOW),
    )

    with pytest.raises(
        NonRetryableAnalysisError,
        match="document_contains_no_extractable_text",
    ):
        pipeline.process(
            _context(),
            AnalysisJob(
                submission_id=SUBMISSION_ID,
                invitation_id=INVITATION_ID,
                applicant_id=APPLICANT_ID,
                analysis_version=1,
                source_type=SourceType.PDF,
                source_object_id=SUBMISSION_ID,
                idempotency_key="analysis-document-failure-0001",
            ),
        )

    submission = repository.get_submission(_context(), SUBMISSION_ID)
    assert submission.status is SubmissionStatus.FAILED
    assert submission.failure_code == "document_contains_no_extractable_text"


def _pdf_submission(submission_id: UUID, filename: str) -> Submission:
    return Submission(
        submission_id=submission_id,
        company_id=COMPANY_ID,
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        source_type=SourceType.PDF,
        source_uri=f"tenants/{COMPANY_ID}/original/{submission_id}",
        original_filename=filename,
        content_hash="a" * 64,
        byte_size=128,
        media_type="application/pdf",
        created_at=NOW,
    )


def test_multiple_submissions_build_one_combined_strategy_after_analysis() -> None:
    """Finalization combines all completed materials into one strategy generation."""
    second_submission_id = UUID("00000000-0000-7000-8000-000000000207")
    repository = InMemorySubmissionRepository()
    repository.save_submission(_context(), _pdf_submission(SUBMISSION_ID, "resume.pdf"))
    repository.save_submission(
        _context(), _pdf_submission(second_submission_id, "cover-letter.pdf")
    )
    outbox = InMemoryOutbox()
    pipeline = SubmissionAnalysisPipeline(
        repository=repository,
        extractor=DocumentExtractionAdapter(
            DeterministicTextract(
                (TextractPage(page_number=1, lines=("프로젝트", "결제 장애율을 30% 줄였습니다.")),)
            ),
            extractor_version="textract-v1",
        ),
        search_index=InMemorySearchIndex(),
        text_embedder=StaticTextEmbedder(
            tuple(1.0 if index == 0 else 0.0 for index in range(1024))
        ),
        strategy_model=SourceAwareModel(),
        axis_provider=StaticAxisProvider(),
        outbox=outbox,
        clock=FrozenClock(NOW),
    )

    for index, submission_id in enumerate((SUBMISSION_ID, second_submission_id), start=1):
        result = pipeline.process(
            _context(),
            AnalysisJob(
                submission_id=submission_id,
                invitation_id=INVITATION_ID,
                applicant_id=APPLICANT_ID,
                analysis_version=1,
                source_type=SourceType.PDF,
                source_object_id=submission_id,
                idempotency_key=f"analysis-second-submission-{index:04d}",
            ),
        )
        assert result.status is JobStatus.READY

    assert pipeline.finalize_invitation(
        _context(),
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        submission_ids=frozenset({SUBMISSION_ID, second_submission_id}),
    )
    strategy = repository.latest_strategy(_context(), INVITATION_ID)
    assert strategy is not None
    assert strategy.strategy_version == 1
    versions = sorted(
        value.strategy_version
        for value in repository.strategies.values()
        if value.invitation_id == INVITATION_ID
    )
    assert versions == [1]
    assert [
        event.payload["strategy_version"]
        for event in outbox.pending()
        if event.event_type == "strategy.ready"
    ] == [1]
