from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.interview_engine.application.interview_plan import (
    FIXED_INTERVIEW_DURATION_SECONDS,
    InterviewPlan,
    VerificationTargetPlan,
)
from interview_evidence.interview_engine.domain.session import InterviewSession
from interview_evidence.interview_engine.domain.turn import (
    QuestionRationale,
    VerificationProgress,
    VerificationProgressState,
)
from interview_evidence.interview_engine.repositories.postgres import (
    InMemoryInterviewRepository,
)
from interview_evidence.shared.interview_level import InterviewLevel
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 15, 15, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000003")
FIRST_TARGET_ID = UUID("00000000-0000-7000-8000-000000000004")
SECOND_TARGET_ID = UUID("00000000-0000-7000-8000-000000000005")
FIRST_CRITERION_ID = UUID("00000000-0000-7000-8000-000000000006")
SECOND_CRITERION_ID = UUID("00000000-0000-7000-8000-000000000007")


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.APPLICANT,
        actor_id=APPLICANT_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000008"),
        trace_id="verification-progress",
    )


def _target(
    target_id: UUID,
    criterion_id: UUID,
    *,
    max_follow_ups: int,
    time_budget_seconds: int = 300,
) -> VerificationTargetPlan:
    return VerificationTargetPlan(
        verification_target_id=target_id,
        criterion_id=criterion_id,
        criterion_text="ECS 운영 장애 대응 경험",
        target_type="detail_missing",
        objective="실제 장애의 원인 분석과 복구 과정에서 본인 역할을 확인합니다.",
        missing_dimensions=("원인 분석", "복구", "재발 방지"),
        follow_up_directions=("본인이 직접 수행한 복구 작업",),
        max_follow_ups=max_follow_ups,
        common_question="운영 장애를 해결한 경험을 설명해 주세요?",
        time_budget_seconds=time_budget_seconds,
    )


def _plan() -> InterviewPlan:
    return InterviewPlan(
        criterion_ids=(FIRST_CRITERION_ID, SECOND_CRITERION_ID),
        initial_question="운영 장애를 해결한 경험을 설명해 주세요?",
        prohibited_topics=(),
        fallback_question="본인이 직접 수행한 작업을 설명해 주세요?",
        remaining_time_seconds=FIXED_INTERVIEW_DURATION_SECONDS,
        model_config_version="question-v2",
        retrieval_config_version="aurora-hybrid-v1",
        voice_id="Seoyeon",
        verification_targets=(
            _target(FIRST_TARGET_ID, FIRST_CRITERION_ID, max_follow_ups=1),
            _target(SECOND_TARGET_ID, SECOND_CRITERION_ID, max_follow_ups=0),
        ),
    )


def test_plan_bounds_follow_ups_and_advances_to_next_target() -> None:
    plan = _plan()

    assert (
        plan.next_target_after_answer(
            answered_target_id=FIRST_TARGET_ID,
            follow_up_count=0,
            completed_target_ids=frozenset(),
        ).verification_target_id
        == FIRST_TARGET_ID
    )
    assert (
        plan.next_target_after_answer(
            answered_target_id=FIRST_TARGET_ID,
            follow_up_count=1,
            completed_target_ids=frozenset(),
        ).verification_target_id
        == SECOND_TARGET_ID
    )
    assert (
        plan.next_target_after_answer(
            answered_target_id=SECOND_TARGET_ID,
            follow_up_count=0,
            completed_target_ids=frozenset({FIRST_TARGET_ID}),
        )
        is None
    )


def test_repository_persists_final_answer_progress_and_question_rationale() -> None:
    repository = InMemoryInterviewRepository()
    repository.save_session(
        _context(),
        InterviewSession(
            interview_session_id=SESSION_ID,
            company_id=COMPANY_ID,
            invitation_id=UUID("00000000-0000-7000-8000-000000000009"),
            applicant_id=APPLICANT_ID,
            interview_strategy_id=UUID("00000000-0000-7000-8000-000000000010"),
            competency_model_version_id=UUID("00000000-0000-7000-8000-000000000011"),
            created_at=NOW,
        ),
    )
    answer_turn_id = UUID("00000000-0000-7000-8000-000000000012")
    question_turn_id = UUID("00000000-0000-7000-8000-000000000013")
    progress = VerificationProgress(
        verification_progress_id=UUID("00000000-0000-7000-8000-000000000014"),
        company_id=COMPANY_ID,
        interview_session_id=SESSION_ID,
        applicant_id=APPLICANT_ID,
        verification_target_id=FIRST_TARGET_ID,
        criterion_id=FIRST_CRITERION_ID,
        state=VerificationProgressState.IN_PROGRESS,
        follow_up_count=1,
        final_answer_turn_ids=(answer_turn_id,),
        updated_at=NOW,
    )
    rationale = QuestionRationale(
        question_rationale_id=UUID("00000000-0000-7000-8000-000000000015"),
        company_id=COMPANY_ID,
        interview_session_id=SESSION_ID,
        question_turn_id=question_turn_id,
        applicant_id=APPLICANT_ID,
        competency_model_version_id=UUID("00000000-0000-7000-8000-000000000011"),
        criterion_id=FIRST_CRITERION_ID,
        verification_target_id=FIRST_TARGET_ID,
        verification_target_type="detail_missing",
        objective="원인 분석과 복구 과정 확인",
        question_type="follow_up",
        retrieval_version="aurora-hybrid-v1",
        generation_version="question-v2",
        policy_result="accepted",
        source_reference_ids=(),
        created_at=NOW,
    )

    repository.save_verification_progress(_context(), progress)
    repository.save_question_rationale(_context(), rationale)

    assert repository.list_verification_progress(_context(), SESSION_ID) == (progress,)
    assert (
        repository.get_question_rationale(
            _context(),
            question_turn_id=question_turn_id,
        )
        == rationale
    )


def _leveled_plan(
    level: InterviewLevel,
    *,
    second_budget_seconds: int = 300,
) -> InterviewPlan:
    return InterviewPlan(
        criterion_ids=(FIRST_CRITERION_ID, SECOND_CRITERION_ID),
        initial_question="운영 장애를 해결한 경험을 설명해 주세요?",
        prohibited_topics=(),
        fallback_question="본인이 직접 수행한 작업을 설명해 주세요?",
        remaining_time_seconds=FIXED_INTERVIEW_DURATION_SECONDS,
        model_config_version="question-v2",
        retrieval_config_version="aurora-hybrid-v1",
        voice_id="Seoyeon",
        verification_targets=(
            _target(FIRST_TARGET_ID, FIRST_CRITERION_ID, max_follow_ups=2),
            _target(
                SECOND_TARGET_ID,
                SECOND_CRITERION_ID,
                max_follow_ups=2,
                time_budget_seconds=second_budget_seconds,
            ),
        ),
        interview_level=level,
    )


def test_every_level_uses_the_same_configured_follow_up_budget() -> None:
    entry = _leveled_plan(InterviewLevel.ENTRY)
    senior = _leveled_plan(InterviewLevel.SENIOR)

    assert (
        entry.next_target_after_answer(
            answered_target_id=FIRST_TARGET_ID,
            follow_up_count=1,
            completed_target_ids=frozenset(),
        ).verification_target_id
        == FIRST_TARGET_ID
    )
    assert (
        senior.next_target_after_answer(
            answered_target_id=FIRST_TARGET_ID,
            follow_up_count=1,
            completed_target_ids=frozenset(),
        ).verification_target_id
        == FIRST_TARGET_ID
    )
    assert entry.follow_up_budget(entry.verification_targets[0]) == 2
    assert senior.follow_up_budget(senior.verification_targets[0]) == 2


def test_the_plan_refuses_to_open_a_criterion_the_clock_cannot_finish() -> None:
    """A half-verified criterion is worse evidence than ending the interview.

    ``time_budget_seconds`` was stored on the verification guide but never read, so
    the loop would open a fifth topic with a minute left and collect one shallow
    answer for it.
    """
    plan = _leveled_plan(
        InterviewLevel.JUNIOR,
        second_budget_seconds=300,
    )

    # 350 seconds left is not enough for a 300 second criterion plus any answer.
    assert (
        plan.next_target_after_answer(
            answered_target_id=FIRST_TARGET_ID,
            follow_up_count=2,
            completed_target_ids=frozenset(),
            elapsed_seconds=1600,
        )
        is None
    )
    # With the slot barely started the same call opens the next criterion.
    assert (
        plan.next_target_after_answer(
            answered_target_id=FIRST_TARGET_ID,
            follow_up_count=2,
            completed_target_ids=frozenset(),
            elapsed_seconds=100,
        ).verification_target_id
        == SECOND_TARGET_ID
    )


def test_a_spent_clock_ends_the_interview_even_mid_criterion() -> None:
    plan = _leveled_plan(InterviewLevel.SENIOR)

    assert (
        plan.next_target_after_answer(
            answered_target_id=FIRST_TARGET_ID,
            follow_up_count=0,
            completed_target_ids=frozenset(),
            elapsed_seconds=FIXED_INTERVIEW_DURATION_SECONDS,
        )
        is None
    )
