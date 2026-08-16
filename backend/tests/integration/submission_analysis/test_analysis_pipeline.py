from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from interview_evidence.shared.aws_clients.ports import StaticTextEmbedder
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.messaging.outbox import InMemoryOutbox
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.adapters.search import InMemorySearchIndex
from interview_evidence.submission_analysis.domain.git_analysis import OwnershipClass
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
    GitFetchLimits,
    RepositoryCommit,
    RepositoryFile,
    RepositorySnapshot,
    StaticGitTransport,
)
from interview_evidence.workers.analysis.handlers import AnalysisJob, JobStatus
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
        source_candidates = model_input["source_candidates"]
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
    strategy = repository.latest_strategy(_context(), INVITATION_ID)
    assert strategy is not None
    assert strategy.competency_model_version_id == CRITERION_VERSION_ID
    assert outbox.pending()[-1].event_type == "strategy.ready"


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
