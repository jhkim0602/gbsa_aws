from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.shared.submission_materials import SubmissionMaterialType
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.application.strategy_freshness import (
    strategy_matches_latest_analyses,
)
from interview_evidence.submission_analysis.domain.source import SourceReferenceCandidate
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
    InMemorySubmissionRepository,
)

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000002")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000003")
SUBMISSION_ID = UUID("00000000-0000-7000-8000-000000000004")
NOW = datetime(2026, 8, 24, tzinfo=UTC)


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.APPLICANT,
        actor_id=APPLICANT_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000005"),
        trace_id="strategy-freshness",
    )


def _candidate(source_id: UUID) -> SourceReferenceCandidate:
    return SourceReferenceCandidate(
        source_id=source_id,
        source_type="candidate_code_unit",
        locator={"path": "src/service.py", "symbol": "Service"},
        content_hash=f"{source_id.int:064x}",
        relevance_score=1,
        ownership_confidence=1,
    )


def _analysis(version: int, candidate: SourceReferenceCandidate) -> SubmissionAnalysis:
    return SubmissionAnalysis(
        analysis_id=UUID(int=100 + version),
        company_id=COMPANY_ID,
        submission_id=SUBMISSION_ID,
        analysis_version=version,
        extractor_version="bounded-ranked-public-git-v2",
        chunk_config_version="ranked-code-units-v2",
        claims=(
            {
                "type": "source_reference_candidate",
                "candidate": candidate.model_dump(mode="json"),
            },
        ),
        status=AnalysisStatus.READY,
        created_at=NOW,
    )


def _strategy(candidate: SourceReferenceCandidate) -> InterviewStrategy:
    return InterviewStrategy(
        interview_strategy_id=UUID("00000000-0000-7000-8000-000000000020"),
        company_id=COMPANY_ID,
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        competency_model_version_id=UUID("00000000-0000-7000-8000-000000000021"),
        strategy_version=1,
        common_topics=(),
        verification_points=(),
        follow_up_directions={},
        time_budget={"total_seconds": 1800},
        required_evidence_plan={},
        source_reference_candidates=(candidate,),
        model_config_version="strategy-v1",
        status=StrategyStatus.READY,
    )


def test_strategy_is_stale_until_it_contains_latest_analysis_sources() -> None:
    repository = InMemorySubmissionRepository()
    submission = Submission(
        submission_id=SUBMISSION_ID,
        company_id=COMPANY_ID,
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        material_type=SubmissionMaterialType.PROJECTS,
        source_type=SourceType.PUBLIC_GIT,
        source_uri="https://github.com/example/project",
        candidate_identity_inputs={"claimed_handles": ("candidate",)},
        status=SubmissionStatus.READY,
        created_at=NOW,
    )
    repository.save_submission(_context(), submission)
    first_candidate = _candidate(UUID("00000000-0000-7000-8000-000000000030"))
    latest_candidate = _candidate(UUID("00000000-0000-7000-8000-000000000031"))
    repository.save_analysis(_context(), _analysis(1, first_candidate))
    strategy = _strategy(first_candidate)

    assert strategy_matches_latest_analyses(
        repository,
        _context(),
        submissions=(submission,),
        strategy=strategy,
    )

    repository.save_analysis(_context(), _analysis(2, latest_candidate))

    assert not strategy_matches_latest_analyses(
        repository,
        _context(),
        submissions=(submission,),
        strategy=strategy,
    )
