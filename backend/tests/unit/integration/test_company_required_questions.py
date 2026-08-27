from uuid import UUID

from interview_evidence.company_management.application.company_service import (
    CriterionSnapshot,
    JobRequirementSnapshot,
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


def _requirement(*, requirement_type: str = "required") -> JobRequirementSnapshot:
    return JobRequirementSnapshot(
        job_requirement_id=UUID("00000000-0000-7000-8000-000000000010"),
        requirement_type=requirement_type,
        statement="AWS ECS·S3·RDS 기반 서비스 운영 경험",
        priority=1,
        criterion_code="TECHNICAL_COMPETENCY",
    )


def test_company_questions_and_requirements_become_adaptive_targets() -> None:
    question = "최근 가장 어려웠던 기술적 판단은 무엇이었나요?"

    targets = _interview_targets(
        (_criterion(common_questions=(question,)),),
        (_requirement(),),
    )

    assert [target.target_type for target in targets] == [
        "company_required_question",
        "job_requirement_required",
    ]
    assert targets[0].common_question == question
    assert targets[0].objective == question
    assert targets[0].max_follow_ups == 1
    assert targets[1].criterion_text == "AWS ECS·S3·RDS 기반 서비스 운영 경험"
    assert targets[1].max_follow_ups == 2
    assert "제출 자료" in targets[1].objective


def test_no_company_configuration_keeps_a_legacy_fallback_target() -> None:
    targets = _interview_targets((_criterion(common_questions=()),), ())

    assert len(targets) == 1
    assert targets[0].target_type == "criterion_baseline"
