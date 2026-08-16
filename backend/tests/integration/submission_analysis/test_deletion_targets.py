from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.application.deletion_targets import (
    SubmissionDeletionTargets,
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
    SubmissionChunk,
)
from interview_evidence.submission_analysis.domain.strategy import (
    InterviewStrategy,
    StrategyStatus,
)
from interview_evidence.submission_analysis.domain.submission import (
    SourceType,
    Submission,
)
from interview_evidence.submission_analysis.repositories.postgres import (
    InMemorySubmissionRepository,
)

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000002")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000003")
SUBMISSION_ID = UUID("00000000-0000-7000-8000-000000000004")
ANALYSIS_ID = UUID("00000000-0000-7000-8000-000000000005")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000009")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000010")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=APPLICANT_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000006"),
        trace_id="lane-b-deletion",
    )


def test_deletion_enumerates_each_owned_durable_and_derived_target() -> None:
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
            created_at=NOW,
        ),
    )
    repository.save_chunks(
        context(),
        (
            SubmissionChunk(
                chunk_id=UUID("00000000-0000-7000-8000-000000000007"),
                company_id=COMPANY_ID,
                applicant_id=APPLICANT_ID,
                submission_id=SUBMISSION_ID,
                analysis_id=ANALYSIS_ID,
                source_location=SourceLocation(page_number=1, section="경력"),
                text_object_key=f"tenants/{COMPANY_ID}/submission-derived/chunk.txt",
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
            interview_strategy_id=UUID("00000000-0000-7000-8000-000000000008"),
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            competency_model_version_id=VERSION_ID,
            strategy_version=1,
            common_topics=(),
            verification_points=(),
            follow_up_directions={},
            time_budget={"total_seconds": 1800},
            required_evidence_plan={},
            source_reference_candidates=(),
            model_config_version="strategy-v1",
            status=StrategyStatus.PARTIAL,
        ),
    )
    claim = CandidateClaim(
        candidate_claim_id=UUID("00000000-0000-7000-8000-000000000011"),
        company_id=COMPANY_ID,
        applicant_id=APPLICANT_ID,
        invitation_id=INVITATION_ID,
        competency_model_version_id=VERSION_ID,
        criterion_id=CRITERION_ID,
        claim_type="material_mention",
        neutral_text="자료에 운영 경험이 언급되어 있습니다.",
        source_id=UUID("00000000-0000-7000-8000-000000000007"),
        locator={"page": 1},
        content_hash="c" * 64,
        extraction_version="rules-v1",
        confidence=0.8,
    )
    repository.save_candidate_claims(context(), (claim,))
    conflict = ClaimConflict(
        claim_conflict_id=UUID("00000000-0000-7000-8000-000000000012"),
        company_id=COMPANY_ID,
        applicant_id=APPLICANT_ID,
        invitation_id=INVITATION_ID,
        criterion_id=CRITERION_ID,
        left_claim_id=claim.candidate_claim_id,
        right_claim_id=UUID("00000000-0000-7000-8000-000000000013"),
        conflict_type="material_difference",
        verification_objective="자료 사이의 차이를 실제 답변으로 확인합니다.",
    )
    repository.save_claim_conflicts(context(), (conflict,))
    verification_target = VerificationTarget(
        verification_target_id=UUID("00000000-0000-7000-8000-000000000014"),
        company_id=COMPANY_ID,
        applicant_id=APPLICANT_ID,
        invitation_id=INVITATION_ID,
        competency_model_version_id=VERSION_ID,
        criterion_id=CRITERION_ID,
        target_type=VerificationTargetType.SOURCE_CONFLICT,
        objective=conflict.verification_objective,
        priority=1,
        max_follow_ups=1,
    )
    repository.save_verification_targets(context(), (verification_target,))
    verification_map = CandidateVerificationMap(
        candidate_verification_map_id=UUID("00000000-0000-7000-8000-000000000015"),
        company_id=COMPANY_ID,
        applicant_id=APPLICANT_ID,
        invitation_id=INVITATION_ID,
        competency_model_version_id=VERSION_ID,
        criterion_version=1,
        material_version="analysis-1",
        retrieval_version="aurora-hybrid-v1",
        embedding_model="amazon.titan-embed-text-v2:0",
        embedding_version="titan-v2",
        generation_version="rules-v1",
        ordered_target_ids=(verification_target.verification_target_id,),
        time_budget_seconds=300,
        readiness_state="ready",
        created_at=NOW,
    )
    repository.save_verification_map(context(), verification_map)

    targets = SubmissionDeletionTargets(repository).enumerate_owned_targets(
        context(),
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
    )

    identities = {(target.store, target.resource_type, target.resource_id) for target in targets}
    assert (
        "s3",
        "submission_original",
        f"tenants/{COMPANY_ID}/submission-original/{SUBMISSION_ID}",
    ) in identities
    assert (
        "s3",
        "submission_chunk_text",
        f"tenants/{COMPANY_ID}/submission-derived/chunk.txt",
    ) in identities
    assert ("retrieval", "submission_chunk_index", "chunk-index-1") in identities
    assert ("aurora", "submission", str(SUBMISSION_ID)) in identities
    assert (
        "aurora",
        "interview_strategy",
        "00000000-0000-7000-8000-000000000008",
    ) in identities
    assert (
        "aurora",
        "candidate_claim",
        str(claim.candidate_claim_id),
    ) in identities
    assert (
        "aurora",
        "claim_conflict",
        str(conflict.claim_conflict_id),
    ) in identities
    assert (
        "aurora",
        "verification_target",
        str(verification_target.verification_target_id),
    ) in identities
    assert (
        "aurora",
        "candidate_verification_map",
        str(verification_map.candidate_verification_map_id),
    ) in identities
    assert all(target.company_id == COMPANY_ID for target in targets)
    assert all(target.verification_required for target in targets)
