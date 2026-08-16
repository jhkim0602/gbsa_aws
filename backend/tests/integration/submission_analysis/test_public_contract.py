from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.shared.ids import CommandMeta, FrozenClock
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.adapters.search import (
    InMemorySearchIndex,
    SearchDocument,
)
from interview_evidence.submission_analysis.application.deletion_targets import (
    InMemorySubmissionTargetDeleter,
    SubmissionDeletionTargets,
)
from interview_evidence.submission_analysis.application.public import (
    SubmissionAnalysisPublic,
)
from interview_evidence.submission_analysis.application.retrieval import (
    HybridRetrievalConfig,
    HybridRetriever,
)
from interview_evidence.submission_analysis.domain.git_analysis import (
    CandidateCodeUnit,
    GitCommitAnalysis,
    OwnershipClass,
)
from interview_evidence.submission_analysis.domain.source import (
    SourceLocation,
    SubmissionChunk,
)
from interview_evidence.submission_analysis.domain.strategy import (
    InterviewStrategy,
    StrategyStatus,
)
from interview_evidence.submission_analysis.domain.submission import (
    SourceType,
    Submission,
    SubmissionStatus,
)
from interview_evidence.submission_analysis.repositories.postgres import (
    InMemorySubmissionRepository,
)

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000002")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000003")
SUBMISSION_ID = UUID("00000000-0000-7000-8000-000000000004")
CHUNK_ID = UUID("00000000-0000-7000-8000-000000000005")
STRATEGY_ID = UUID("00000000-0000-7000-8000-000000000006")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000009")
COMMIT_ANALYSIS_ID = UUID("00000000-0000-7000-8000-000000000011")
CODE_UNIT_ID = UUID("00000000-0000-7000-8000-000000000012")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=APPLICANT_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000007"),
        trace_id="lane-b-public-contract",
    )


def public_contract() -> tuple[
    SubmissionAnalysisPublic,
    InMemorySubmissionTargetDeleter,
]:
    repository = InMemorySubmissionRepository()
    repository.save_submission(
        context(),
        Submission(
            submission_id=SUBMISSION_ID,
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            source_type=SourceType.PDF,
            source_uri=f"tenants/{COMPANY_ID}/submission-original/{SUBMISSION_ID}",
            original_filename="resume.pdf",
            content_hash="a" * 64,
            byte_size=1024,
            media_type="application/pdf",
            status=SubmissionStatus.READY,
            created_at=NOW,
        ),
    )
    repository.save_chunks(
        context(),
        (
            SubmissionChunk(
                chunk_id=CHUNK_ID,
                company_id=COMPANY_ID,
                applicant_id=APPLICANT_ID,
                submission_id=SUBMISSION_ID,
                analysis_id=UUID("00000000-0000-7000-8000-000000000008"),
                source_location=SourceLocation(
                    page_number=2,
                    section="성과",
                    start_line=3,
                    end_line=4,
                ),
                text_object_key=f"tenants/{COMPANY_ID}/derived/chunk.txt",
                source_hash="a" * 64,
                chunk_hash="b" * 64,
                embedding_model="embed-v1",
                embedding_version="1",
                index_document_id="chunk-index-1",
            ),
        ),
    )
    repository.save_strategy(
        context(),
        InterviewStrategy(
            interview_strategy_id=STRATEGY_ID,
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            competency_model_version_id=VERSION_ID,
            strategy_version=1,
            common_topics=("문제 해결",),
            verification_points=(),
            follow_up_directions={},
            time_budget={"total_seconds": 1800},
            required_evidence_plan={},
            source_reference_candidates=(),
            model_config_version="strategy-v1",
            status=StrategyStatus.READY,
        ),
    )
    repository.save_git_commit_analyses(
        context(),
        (
            GitCommitAnalysis(
                git_commit_analysis_id=COMMIT_ANALYSIS_ID,
                company_id=COMPANY_ID,
                repository_analysis_id=UUID("00000000-0000-7000-8000-000000000013"),
                parent_sha="a" * 40,
                commit_sha="b" * 40,
                author_match_inputs={"claimed_names": ["홍길동"]},
                change_summary_object_key=f"tenants/{COMPANY_ID}/git/diff.json",
                ownership_confidence=0.35,
                ownership_class=OwnershipClass.CONTEXT_ONLY,
                ownership_explanation=("author_name_match",),
            ),
        ),
    )
    repository.save_code_units(
        context(),
        (
            CandidateCodeUnit(
                code_unit_id=CODE_UNIT_ID,
                company_id=COMPANY_ID,
                git_commit_analysis_id=COMMIT_ANALYSIS_ID,
                path="src/payment.py",
                language="python",
                symbol="retry_payment",
                original_line_range=(1, 2),
                current_line_range=(1, 2),
                authored_snapshot_key=f"tenants/{COMPANY_ID}/git/authored.txt",
                current_snapshot_key=f"tenants/{COMPANY_ID}/git/current.txt",
                candidate_owned_regions=((1, 2),),
                related_test_ids=("tests/test_payment.py",),
                index_document_ids=("code-unit-1",),
            ),
        ),
    )
    index = InMemorySearchIndex()
    index.add(
        SearchDocument(
            document_id="chunk-index-1",
            company_id=COMPANY_ID,
            applicant_id=APPLICANT_ID,
            source_id=CHUNK_ID,
            text="결제 장애 재처리",
            vector=(1.0, 0.0),
            symbols=(),
            locator={"page_number": 2, "section": "성과"},
            ownership_confidence=1,
            invitation_id=INVITATION_ID,
            competency_model_version_id=VERSION_ID,
        )
    )
    deleter = InMemorySubmissionTargetDeleter()
    return (
        SubmissionAnalysisPublic(
            repository=repository,
            retriever=HybridRetriever(index, HybridRetrievalConfig()),
            deletion_targets=SubmissionDeletionTargets(repository),
            target_deleter=deleter,
        ),
        deleter,
    )


def test_public_contract_returns_snapshots_without_raw_source_text() -> None:
    public, _ = public_contract()

    status = public.get_analysis_status(context(), invitation_id=INVITATION_ID)
    strategy = public.get_strategy_snapshot(context(), strategy_id=STRATEGY_ID)
    results = public.retrieve_context(
        context(),
        applicant_id=APPLICANT_ID,
        invitation_id=INVITATION_ID,
        competency_model_version_id=VERSION_ID,
        query="결제 장애",
        query_vector=(1.0, 0.0),
        criterion_id=UUID("00000000-0000-7000-8000-000000000010"),
        config_version="retrieval-v1",
        limit=5,
    )
    source = public.resolve_source_reference(
        context(),
        source_id=CHUNK_ID,
    )
    code_source = public.resolve_source_reference(
        context(),
        source_id=CODE_UNIT_ID,
    )

    assert status.strategy_ready is True
    assert status.submissions[0].status == "ready"
    assert strategy.interview_strategy_id == STRATEGY_ID
    assert results[0].source_id == CHUNK_ID
    assert not hasattr(results[0], "text")
    assert source.locator["page_number"] == 2
    assert source.content_hash == "b" * 64
    assert code_source.source_type == "candidate_code_unit"
    assert code_source.locator["symbol"] == "retry_payment"
    assert code_source.locator["commit_sha"] == "b" * 40
    assert code_source.ownership_confidence == 0.35
    assert code_source.content_hash is None


def test_public_contract_delegates_owned_deletion_and_verifies_absence() -> None:
    public, deleter = public_contract()
    target = next(
        target
        for target in public.enumerate_submission_deletion_targets(
            context(),
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
        )
        if target.store == "retrieval"
    )

    receipt = public.delete_submission_target(
        context(),
        target=target,
        meta=CommandMeta.create(
            "delete-submission-target",
            clock=FrozenClock(NOW),
        ),
    )

    assert receipt.verified_absent is True
    assert deleter.calls == [target]
