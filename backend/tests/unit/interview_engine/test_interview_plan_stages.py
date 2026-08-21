from typing import Any
from uuid import UUID

import pytest
from interview_evidence.interview_engine.application.interview_plan import (
    DEFAULT_INTERVIEW_STAGES,
    InterviewPlan,
    InterviewStage,
)

CRITERION_ID = UUID("00000000-0000-7000-8000-000000000001")


def _plan(**overrides: Any) -> InterviewPlan:
    values: dict[str, Any] = {
        "criterion_ids": (CRITERION_ID,),
        "initial_question": "자료에 근거한 첫 질문입니다?",
        "prohibited_topics": (),
        "fallback_question": "본인이 직접 수행한 내용을 설명해 주세요?",
        "remaining_time_seconds": 600,
        "model_config_version": "question-v1",
        "retrieval_config_version": "hybrid-v1",
        "voice_id": "Seoyeon",
    }
    values.update(overrides)
    return InterviewPlan(**values)


def test_plan_has_fixed_stages_and_a_separate_warm_up() -> None:
    plan = _plan()

    assert plan.stages == DEFAULT_INTERVIEW_STAGES
    assert plan.stages == (
        InterviewStage.TECHNICAL,
        InterviewStage.PROJECT_DEEP_DIVE,
        InterviewStage.BEHAVIORAL,
    )
    assert plan.opening_prompt.startswith("안녕하세요.")
    assert plan.is_warm_up_question(plan.opening_prompt)
    assert not plan.is_warm_up_question(plan.initial_question)


def test_plan_rejects_a_custom_stage_sequence() -> None:
    with pytest.raises(
        ValueError,
        match="fixed interview stage sequence",
    ):
        _plan(stages=(InterviewStage.TECHNICAL,))
