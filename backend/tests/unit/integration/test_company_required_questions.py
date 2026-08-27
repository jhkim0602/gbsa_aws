from uuid import UUID

from interview_evidence.company_management.application.company_service import (
    CriterionSnapshot,
)
from interview_evidence.integration.submission_interview import _interview_targets


def _criterion(*, common_questions: tuple[str, ...]) -> CriterionSnapshot:
    return CriterionSnapshot(
        criterion_id=UUID("00000000-0000-7000-8000-000000000001"),
        code="TECHNICAL_COMPETENCY",
        name="기술 역량",
        description="기술 선택과 구현 근거를 확인합니다.",
        weight=30,
        verification_guide={
            "observable_dimensions": ["기술 선택 이유"],
            "follow_up_directions": ["선택 근거"],
            "max_follow_ups": 2,
            "time_budget_seconds": 540,
        },
        abstain_guidance="근거가 없으면 판단을 유보합니다.",
        common_questions=common_questions,
        required=True,
    )


def test_company_questions_are_prioritized_without_turning_requirements_into_targets() -> None:
    question = "최근 가장 어려웠던 기술적 판단은 무엇이었나요?"

    targets = _interview_targets((_criterion(common_questions=(question,)),))

    assert [target.target_type for target in targets] == [
        "company_required_question",
        "criterion_baseline",
    ]
    assert targets[0].common_question == question
    assert targets[0].objective == question
    assert targets[0].max_follow_ups == 0
    assert targets[1].objective == "기술 역량을 일반적인 직무 면접 질문으로 확인합니다."


def test_no_company_question_creates_only_the_stable_stage_target() -> None:
    targets = _interview_targets((_criterion(common_questions=()),))

    assert len(targets) == 1
    assert targets[0].target_type == "criterion_baseline"
