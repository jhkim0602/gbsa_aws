from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.interview_engine.application.checkpoints import CheckpointService
from interview_evidence.interview_engine.application.deletion_targets import (
    InterviewDeletionTargets,
)
from interview_evidence.interview_engine.domain.session import InterviewSession
from interview_evidence.interview_engine.domain.turn import (
    HotViewSyncStatus,
    InterviewTurn,
    QuestionRationale,
    QuestionSourceReference,
    RecordingChunk,
    RecordingUploadStatus,
    TurnSpeaker,
    TurnStatus,
    VerificationProgress,
    VerificationProgressState,
)
from interview_evidence.interview_engine.repositories.postgres import (
    InMemoryInterviewRepository,
)
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
TURN_ID = UUID("00000000-0000-7000-8000-000000000003")


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=UUID("00000000-0000-7000-8000-000000000004"),
        request_id=UUID("00000000-0000-7000-8000-000000000005"),
        trace_id="trace-lane-c-deletion",
    )


def test_deletion_enumerates_all_lane_c_durable_and_derived_targets() -> None:
    repository = InMemoryInterviewRepository()
    repository.save_session(
        context(),
        InterviewSession(
            interview_session_id=SESSION_ID,
            company_id=COMPANY_ID,
            invitation_id=UUID("00000000-0000-7000-8000-000000000006"),
            applicant_id=UUID("00000000-0000-7000-8000-000000000007"),
            interview_strategy_id=UUID("00000000-0000-7000-8000-000000000008"),
            competency_model_version_id=UUID("00000000-0000-7000-8000-000000000009"),
            created_at=NOW,
        ),
    )
    repository.save_turn(
        context(),
        InterviewTurn(
            turn_id=TURN_ID,
            company_id=COMPANY_ID,
            interview_session_id=SESSION_ID,
            sequence=1,
            speaker=TurnSpeaker.INTERVIEWER,
            status=TurnStatus.FINAL,
            text="경험을 설명해 주세요?",
            target_criterion_id=UUID("00000000-0000-7000-8000-000000000010"),
            idempotency_key="question-turn-0001",
            model_config_version="question-model-v1",
            finalized_at=NOW,
        ),
    )
    repository.save_question_source_references(
        context(),
        (
            QuestionSourceReference(
                source_reference_id=UUID("00000000-0000-7000-8000-000000000011"),
                company_id=COMPANY_ID,
                interview_session_id=SESSION_ID,
                question_turn_id=TURN_ID,
                source_id=UUID("00000000-0000-7000-8000-000000000012"),
                source_type="submission_chunk",
                locator={"page_number": 1},
                relevance_score=0.8,
                ownership_confidence=1,
                retrieval_config_version="hybrid-v1",
                model_config_version="question-model-v1",
                created_at=NOW,
            ),
        ),
    )
    repository.save_verification_progress(
        context(),
        VerificationProgress(
            verification_progress_id=UUID("00000000-0000-7000-8000-000000000014"),
            company_id=COMPANY_ID,
            interview_session_id=SESSION_ID,
            applicant_id=UUID("00000000-0000-7000-8000-000000000007"),
            verification_target_id=UUID("00000000-0000-7000-8000-000000000015"),
            criterion_id=UUID("00000000-0000-7000-8000-000000000010"),
            state=VerificationProgressState.IN_PROGRESS,
            follow_up_count=1,
            final_answer_turn_ids=(),
            updated_at=NOW,
        ),
    )
    repository.save_question_rationale(
        context(),
        QuestionRationale(
            question_rationale_id=UUID("00000000-0000-7000-8000-000000000016"),
            company_id=COMPANY_ID,
            interview_session_id=SESSION_ID,
            question_turn_id=TURN_ID,
            applicant_id=UUID("00000000-0000-7000-8000-000000000007"),
            competency_model_version_id=UUID("00000000-0000-7000-8000-000000000009"),
            criterion_id=UUID("00000000-0000-7000-8000-000000000010"),
            verification_target_id=UUID("00000000-0000-7000-8000-000000000015"),
            verification_target_type="detail_missing",
            objective="원인 분석과 복구 역할 확인",
            question_type="follow_up",
            retrieval_version="aurora-hybrid-v1",
            generation_version="question-model-v2",
            policy_result="accepted",
            source_reference_ids=(UUID("00000000-0000-7000-8000-000000000011"),),
            created_at=NOW,
        ),
    )
    CheckpointService(repository).create(
        context(),
        session_id=SESSION_ID,
        last_final_turn_id=TURN_ID,
        last_media_chunk_sequence=1,
        pending_turn_id=TURN_ID,
        hot_view_sync_status=HotViewSyncStatus.SYNCED,
        occurred_at=NOW,
    )
    repository.save_recording_chunk(
        context(),
        RecordingChunk(
            recording_chunk_id=UUID("00000000-0000-7000-8000-000000000013"),
            company_id=COMPANY_ID,
            interview_session_id=SESSION_ID,
            sequence=1,
            object_key=(f"companies/{COMPANY_ID}/sessions/{SESSION_ID}/recording/chunks/000001"),
            content_hash="a" * 64,
            byte_size=1024,
            session_start_ms=0,
            session_end_ms=2000,
            upload_status=RecordingUploadStatus.VERIFIED,
            idempotency_key="recording-upload-0001",
            created_at=NOW,
        ),
    )

    targets = InterviewDeletionTargets(repository).enumerate_owned_targets(
        context(),
        session_id=SESSION_ID,
    )
    identities = {(target.store, target.resource_type) for target in targets}

    assert ("aurora", "interview_session") in identities
    assert ("aurora", "interview_turn") in identities
    assert ("aurora", "session_checkpoint") in identities
    assert ("aurora", "question_source_reference") in identities
    assert ("aurora", "recording_chunk") in identities
    assert ("aurora", "verification_progress") in identities
    assert ("aurora", "question_rationale") in identities
    assert ("dynamodb", "interview_hot_view") in identities
    assert ("s3", "recording_chunk_object") in identities
    assert all(target.owner_lane == "C" for target in targets)
    assert all(target.verification_required for target in targets)
