from uuid import UUID

import pytest
from interview_evidence.integration.submission_interview import SubmissionInterviewBoundary
from interview_evidence.interview_engine.adapters.retrieval_client import RetrievalClient
from interview_evidence.interview_engine.application.authorization import (
    InterviewAuthorizationDenied,
)
from interview_evidence.shared.security.principals import ApplicantPrincipal
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.adapters.search import (
    InMemorySearchIndex,
    SearchDocument,
)
from interview_evidence.submission_analysis.application.deletion_targets import (
    InMemorySubmissionTargetDeleter,
    SubmissionDeletionTargets,
)
from interview_evidence.submission_analysis.application.public import SubmissionAnalysisPublic
from interview_evidence.submission_analysis.application.retrieval import (
    HybridRetrievalConfig,
    HybridRetriever,
)
from interview_evidence.submission_analysis.domain.strategy import (
    InterviewStrategy,
    StrategyStatus,
)
from interview_evidence.submission_analysis.repositories.postgres import (
    InMemorySubmissionRepository,
)

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000002")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000003")
STRATEGY_ID = UUID("00000000-0000-7000-8000-000000000004")
CRITERION_VERSION_ID = UUID("00000000-0000-7000-8000-000000000005")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000006")
SOURCE_ID = UUID("00000000-0000-7000-8000-000000000007")


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.APPLICANT,
        actor_id=APPLICANT_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000008"),
        trace_id="cross-b-to-c",
    )


def principal() -> ApplicantPrincipal:
    return ApplicantPrincipal(
        company_id=COMPANY_ID,
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        session_id=UUID("00000000-0000-7000-8000-000000000009"),
    )


def boundary(status: StrategyStatus) -> SubmissionInterviewBoundary:
    repository = InMemorySubmissionRepository()
    repository.save_strategy(
        context(),
        InterviewStrategy(
            interview_strategy_id=STRATEGY_ID,
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            competency_model_version_id=CRITERION_VERSION_ID,
            strategy_version=1,
            common_topics=("problem solving",),
            verification_points=(),
            follow_up_directions={},
            time_budget={"total_seconds": 1800},
            required_evidence_plan={},
            source_reference_candidates=(),
            model_config_version="strategy-v1",
            status=status,
        ),
    )
    index = InMemorySearchIndex()
    index.add(
        SearchDocument(
            document_id="source-1",
            company_id=COMPANY_ID,
            applicant_id=APPLICANT_ID,
            source_id=SOURCE_ID,
            text="payment retry incident",
            vector=(1.0, 0.0),
            symbols=("retry_payment",),
            locator={"page_number": 2},
            ownership_confidence=1.0,
            invitation_id=INVITATION_ID,
            competency_model_version_id=CRITERION_VERSION_ID,
            criterion_id=CRITERION_ID,
        )
    )
    public = SubmissionAnalysisPublic(
        repository=repository,
        retriever=HybridRetriever(index, HybridRetrievalConfig()),
        deletion_targets=SubmissionDeletionTargets(repository),
        target_deleter=InMemorySubmissionTargetDeleter(),
    )
    return SubmissionInterviewBoundary(public)


def test_lane_c_uses_real_strategy_and_retrieval_boundary() -> None:
    provider = boundary(StrategyStatus.READY)
    authorization = provider.authorize_start(
        context(),
        principal(),
        strategy_id=STRATEGY_ID,
        acknowledged_partial_analysis=False,
    )
    retrieval = RetrievalClient(provider).retrieve(
        context(),
        applicant_id=APPLICANT_ID,
        invitation_id=INVITATION_ID,
        competency_model_version_id=CRITERION_VERSION_ID,
        session_id=UUID("00000000-0000-7000-8000-000000000010"),
        query="payment retry",
        query_vector=(1.0, 0.0),
        criterion_id=CRITERION_ID,
        config_version="hybrid-v1",
        exact_symbol="retry_payment",
    )

    assert authorization.competency_model_version_id == CRITERION_VERSION_ID
    assert authorization.partial_analysis is False
    assert retrieval.degraded_mode is None
    assert retrieval.hits[0].source_id == SOURCE_ID
    assert retrieval.hits[0].locator == {"page_number": 2}


def test_partial_strategy_requires_explicit_applicant_acknowledgement() -> None:
    provider = boundary(StrategyStatus.PARTIAL)

    with pytest.raises(InterviewAuthorizationDenied):
        provider.authorize_start(
            context(),
            principal(),
            strategy_id=STRATEGY_ID,
            acknowledged_partial_analysis=False,
        )

    authorized = provider.authorize_start(
        context(),
        principal(),
        strategy_id=STRATEGY_ID,
        acknowledged_partial_analysis=True,
    )
    assert authorized.partial_analysis is True
