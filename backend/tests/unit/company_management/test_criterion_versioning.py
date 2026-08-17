from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.company_management.domain.criteria import (
    CompetencyModelVersion,
    CriterionVerificationGuide,
    EvaluationCriterion,
    JobRequirement,
    PublishedVersionImmutableError,
    RequirementType,
)
from interview_evidence.company_management.domain.hiring import Invitation

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
POSITION_ID = UUID("00000000-0000-7000-8000-000000000002")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000003")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000004")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000006")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def criterion_version() -> CompetencyModelVersion:
    guide = CriterionVerificationGuide(
        observable_dimensions=("상황", "원인 분석", "직접 수행", "재발 방지"),
        strong_answer_signals=("본인 행동과 판단 근거가 구체적이다.",),
        weak_answer_signals=("팀 활동만 언급한다.",),
        follow_up_directions=("직접 수행한 복구 작업",),
        max_follow_ups=2,
        time_budget_seconds=300,
    )
    criterion = EvaluationCriterion(
        criterion_id=UUID("00000000-0000-7000-8000-000000000005"),
        code="PROBLEM_SOLVING",
        name="문제 해결",
        description="근거를 바탕으로 문제를 해결한다.",
        weight=1,
        verification_guide=guide,
        abstain_guidance="근거가 없으면 판단을 보류한다.",
        common_questions=("어떤 대안을 검토했나요?",),
        required=True,
    )
    return CompetencyModelVersion.create(
        competency_model_version_id=VERSION_ID,
        company_id=COMPANY_ID,
        position_id=POSITION_ID,
        version_number=1,
        job_requirements=(
            JobRequirement(
                job_requirement_id=UUID("00000000-0000-7000-8000-000000000007"),
                requirement_type=RequirementType.PREFERRED,
                statement="ECS 운영 장애 대응 경험",
                priority=2,
                criterion_code="PROBLEM_SOLVING",
            ),
        ),
        criteria=(criterion,),
        prohibited_topics=("가족관계",),
        interview_duration_minutes=30,
    )


def test_published_criterion_version_is_immutable() -> None:
    draft = criterion_version()
    published = draft.publish(expected_version=1, published_at=NOW)

    assert published.status == "published"
    assert published.published_at == NOW
    assert published.row_version == 2

    with pytest.raises(PublishedVersionImmutableError):
        published.replace_persona({"name": "변경된 면접관"})


def test_invitation_pins_the_published_criterion_version() -> None:
    published = criterion_version().publish(expected_version=1, published_at=NOW)
    invitation = Invitation.create(
        invitation_id=INVITATION_ID,
        company_id=COMPANY_ID,
        position_id=POSITION_ID,
        competency_model_version_id=published.competency_model_version_id,
        applicant_id=APPLICANT_ID,
        applicant_email="applicant@example.com",
        applicant_display_name="지원자",
        token_hash="a" * 64,
        expires_at=NOW,
    )

    assert invitation.competency_model_version_id == VERSION_ID
    assert (
        invitation.transition(
            "identity_verified",
            actor_type="applicant",
            occurred_at=NOW,
            expected_version=1,
        ).competency_model_version_id
        == VERSION_ID
    )


def test_requirement_must_reference_a_criterion_in_the_same_version() -> None:
    with pytest.raises(ValueError, match="criterion"):
        criterion_version().model_copy(
            update={
                "job_requirements": (
                    JobRequirement(
                        job_requirement_id=UUID("00000000-0000-7000-8000-000000000008"),
                        requirement_type=RequirementType.REQUIRED,
                        statement="직무와 연결된 요구사항",
                        priority=1,
                        criterion_code="UNKNOWN_CRITERION",
                    ),
                )
            }
        ).model_validate(
            criterion_version().model_copy(
                update={
                    "job_requirements": (
                        JobRequirement(
                            job_requirement_id=UUID("00000000-0000-7000-8000-000000000008"),
                            requirement_type=RequirementType.REQUIRED,
                            statement="직무와 연결된 요구사항",
                            priority=1,
                            criterion_code="UNKNOWN_CRITERION",
                        ),
                    )
                }
            )
        )
