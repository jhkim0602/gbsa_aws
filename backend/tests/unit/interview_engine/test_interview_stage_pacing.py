from dataclasses import replace
from uuid import UUID

from interview_evidence.interview_engine.application.interview_plan import (
    FIXED_INTERVIEW_DURATION_SECONDS,
    InterviewPlan,
    InterviewStage,
    StageQuestionDecision,
    VerificationTargetPlan,
)
from interview_evidence.interview_engine.application.interview_service import (
    _company_question_with_bridge,
)

CRITERION_ID = UUID("00000000-0000-7000-8000-000000000001")
TARGET_ID = UUID("00000000-0000-7000-8000-000000000002")
PROJECT_CRITERION_ID = UUID("00000000-0000-7000-8000-000000000003")
PROJECT_TARGET_ID = UUID("00000000-0000-7000-8000-000000000004")
BEHAVIORAL_CRITERION_ID = UUID("00000000-0000-7000-8000-000000000005")
BEHAVIORAL_TARGET_ID = UUID("00000000-0000-7000-8000-000000000006")


def _target() -> VerificationTargetPlan:
    return VerificationTargetPlan(
        verification_target_id=TARGET_ID,
        criterion_id=CRITERION_ID,
        criterion_text="지원자가 직접 수행한 경험",
        target_type="detail_missing",
        objective="본인의 역할과 판단 근거를 확인한다.",
        missing_dimensions=("본인 역할", "판단 근거"),
        follow_up_directions=(),
        max_follow_ups=2,
        common_question="직접 수행한 경험을 설명해 주세요?",
    )


def _plan() -> InterviewPlan:
    return InterviewPlan(
        criterion_ids=(CRITERION_ID,),
        initial_question="직접 수행한 경험을 설명해 주세요?",
        prohibited_topics=(),
        fallback_question="판단 근거를 설명해 주세요?",
        remaining_time_seconds=FIXED_INTERVIEW_DURATION_SECONDS,
        model_config_version="question-v1",
        retrieval_config_version="stage-aware-hybrid-v1",
        voice_id="Seoyeon",
        verification_targets=(_target(),),
        stages=(
            InterviewStage.TECHNICAL,
            InterviewStage.PROJECT_DEEP_DIVE,
            InterviewStage.BEHAVIORAL,
        ),
    )


def _next(
    plan: InterviewPlan,
    *,
    current_stage: InterviewStage,
    stage_core_question_count: int,
    stage_elapsed_seconds: int,
    total_elapsed_seconds: int,
    last_question_was_final: bool,
    consecutive_follow_up_count: int = 0,
    answer_needs_follow_up: bool = False,
    follow_up_limit: int = 2,
) -> StageQuestionDecision:
    return plan.next_stage_question(
        current_stage=current_stage,
        stage_core_question_count=stage_core_question_count,
        consecutive_follow_up_count=consecutive_follow_up_count,
        stage_elapsed_seconds=stage_elapsed_seconds,
        total_elapsed_seconds=total_elapsed_seconds,
        last_question_was_final=last_question_was_final,
        answer_needs_follow_up=answer_needs_follow_up,
        follow_up_limit=follow_up_limit,
    )


def test_stage_time_budgets_split_the_fixed_thirty_minutes() -> None:
    plan = _plan()

    assert plan.remaining_time_seconds == 1800
    assert tuple(plan.stage_time_budget_seconds(stage) for stage in plan.stages) == (
        540,
        720,
        540,
    )
    assert tuple(plan.stage_question_limit(stage) for stage in plan.stages) == (6, 8, 6)


def test_company_question_is_spoken_with_a_natural_transition() -> None:
    spoken = _company_question_with_bridge(
        "협업 과정에서 의견이 달랐을 때 어떻게 조율했나요?",
        previous_question_count=1,
    )

    assert spoken == (
        "좋습니다. 이제 회사에서 꼭 확인하고 싶은 내용을 하나 여쭤보겠습니다. "
        "협업 과정에서 의견이 달랐을 때 어떻게 조율했나요?"
    )


def test_adaptive_interview_finishes_early_when_all_target_evidence_is_sufficient() -> None:
    plan = replace(_plan(), stages=(InterviewStage.ADAPTIVE,))

    assert plan.has_sufficient_evidence_for_all_targets(
        answered_target_id=TARGET_ID,
        answer_needs_follow_up=False,
        follow_up_count=0,
        completed_target_ids=frozenset(),
    )
    assert not plan.has_sufficient_evidence_for_all_targets(
        answered_target_id=TARGET_ID,
        answer_needs_follow_up=True,
        follow_up_count=0,
        completed_target_ids=frozenset(),
    )


def test_fast_answers_use_question_limits_instead_of_looping_forever() -> None:
    plan = _plan()

    opening = _next(
        plan,
        current_stage=InterviewStage.TECHNICAL,
        stage_core_question_count=0,
        stage_elapsed_seconds=0,
        total_elapsed_seconds=0,
        last_question_was_final=False,
    )
    final = _next(
        plan,
        current_stage=InterviewStage.TECHNICAL,
        stage_core_question_count=5,
        stage_elapsed_seconds=10,
        total_elapsed_seconds=10,
        last_question_was_final=False,
    )
    project = _next(
        plan,
        current_stage=InterviewStage.TECHNICAL,
        stage_core_question_count=6,
        stage_elapsed_seconds=20,
        total_elapsed_seconds=20,
        last_question_was_final=True,
    )

    assert opening.question_type == "stage_opening"
    assert final.question_type == "stage_final"
    assert project.stage is InterviewStage.PROJECT_DEEP_DIVE
    assert project.question_type == "stage_opening"


def test_long_answer_moves_to_next_stage_after_it_finishes() -> None:
    plan = _plan()

    decision = _next(
        plan,
        current_stage=InterviewStage.TECHNICAL,
        stage_core_question_count=1,
        stage_elapsed_seconds=550,
        total_elapsed_seconds=550,
        last_question_was_final=False,
    )

    assert decision.stage is InterviewStage.PROJECT_DEEP_DIVE
    assert decision.question_type == "stage_opening"


def test_stage_asks_a_final_question_before_moving_on_at_the_time_boundary() -> None:
    plan = _plan()

    final = _next(
        plan,
        current_stage=InterviewStage.TECHNICAL,
        stage_core_question_count=2,
        stage_elapsed_seconds=480,
        total_elapsed_seconds=480,
        last_question_was_final=False,
    )
    project = _next(
        plan,
        current_stage=InterviewStage.TECHNICAL,
        stage_core_question_count=3,
        stage_elapsed_seconds=570,
        total_elapsed_seconds=570,
        last_question_was_final=True,
    )

    assert final.stage is InterviewStage.TECHNICAL
    assert final.question_type == "stage_final"
    assert project.stage is InterviewStage.PROJECT_DEEP_DIVE
    assert project.question_type == "stage_opening"


def test_expired_total_time_still_preserves_one_question_in_later_stages() -> None:
    plan = _plan()

    project = _next(
        plan,
        current_stage=InterviewStage.TECHNICAL,
        stage_core_question_count=1,
        stage_elapsed_seconds=1800,
        total_elapsed_seconds=1800,
        last_question_was_final=False,
    )
    behavioral = _next(
        plan,
        current_stage=InterviewStage.PROJECT_DEEP_DIVE,
        stage_core_question_count=1,
        stage_elapsed_seconds=60,
        total_elapsed_seconds=1860,
        last_question_was_final=False,
    )
    completed = _next(
        plan,
        current_stage=InterviewStage.BEHAVIORAL,
        stage_core_question_count=1,
        stage_elapsed_seconds=60,
        total_elapsed_seconds=1920,
        last_question_was_final=False,
    )

    assert project.stage is InterviewStage.PROJECT_DEEP_DIVE
    assert behavioral.stage is InterviewStage.BEHAVIORAL
    assert completed.completes_interview


def test_follow_ups_do_not_consume_the_core_question_limit() -> None:
    plan = _plan()

    first_follow_up = _next(
        plan,
        current_stage=InterviewStage.TECHNICAL,
        stage_core_question_count=1,
        consecutive_follow_up_count=0,
        stage_elapsed_seconds=60,
        total_elapsed_seconds=60,
        last_question_was_final=False,
        answer_needs_follow_up=True,
        follow_up_limit=2,
    )
    second_follow_up = _next(
        plan,
        current_stage=InterviewStage.TECHNICAL,
        stage_core_question_count=1,
        consecutive_follow_up_count=1,
        stage_elapsed_seconds=120,
        total_elapsed_seconds=120,
        last_question_was_final=False,
        answer_needs_follow_up=True,
        follow_up_limit=2,
    )
    next_core = _next(
        plan,
        current_stage=InterviewStage.TECHNICAL,
        stage_core_question_count=1,
        consecutive_follow_up_count=2,
        stage_elapsed_seconds=180,
        total_elapsed_seconds=180,
        last_question_was_final=False,
        answer_needs_follow_up=True,
        follow_up_limit=2,
    )

    assert first_follow_up.question_type == "follow_up"
    assert second_follow_up.question_type == "follow_up"
    assert next_core.question_type == "core"


def test_target_exhaustion_does_not_end_the_interview() -> None:
    plan = _plan()

    target = plan.next_target_for_question(
        answered_target_id=TARGET_ID,
        follow_up_count=2,
        completed_target_ids=frozenset({TARGET_ID}),
        prefer_new_target=True,
    )

    assert target.verification_target_id == TARGET_ID


def test_each_stage_uses_the_matching_evaluation_criterion() -> None:
    technical = replace(_target(), criterion_text="기술 역량\n구현 원리를 평가")
    project = replace(
        _target(),
        verification_target_id=PROJECT_TARGET_ID,
        criterion_id=PROJECT_CRITERION_ID,
        criterion_text="프로젝트 실행 역량\n프로젝트 목표와 결과를 평가",
    )
    behavioral = replace(
        _target(),
        verification_target_id=BEHAVIORAL_TARGET_ID,
        criterion_id=BEHAVIORAL_CRITERION_ID,
        criterion_text="협업·행동 역량\n의견 조율과 소통을 평가",
    )
    plan = InterviewPlan(
        criterion_ids=(CRITERION_ID, PROJECT_CRITERION_ID, BEHAVIORAL_CRITERION_ID),
        initial_question="직접 수행한 경험을 설명해 주세요?",
        prohibited_topics=(),
        fallback_question="판단 근거를 설명해 주세요?",
        remaining_time_seconds=FIXED_INTERVIEW_DURATION_SECONDS,
        model_config_version="question-v1",
        retrieval_config_version="stage-aware-hybrid-v1",
        voice_id="Seoyeon",
        verification_targets=(technical, project, behavioral),
        stages=(
            InterviewStage.TECHNICAL,
            InterviewStage.PROJECT_DEEP_DIVE,
            InterviewStage.BEHAVIORAL,
        ),
    )

    assert plan.initial_target_for_stage(InterviewStage.TECHNICAL) == technical
    assert plan.initial_target_for_stage(InterviewStage.PROJECT_DEEP_DIVE) == project
    assert plan.initial_target_for_stage(InterviewStage.BEHAVIORAL) == behavioral
    assert (
        plan.next_target_for_question(
            answered_target_id=PROJECT_TARGET_ID,
            follow_up_count=0,
            completed_target_ids=frozenset({PROJECT_TARGET_ID}),
            prefer_new_target=True,
            interview_stage=InterviewStage.BEHAVIORAL,
        )
        == behavioral
    )
