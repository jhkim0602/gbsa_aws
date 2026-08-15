from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.company_management.domain.criteria import (
    CompetencyModelVersion,
    EvaluationCriterion,
    PublishedVersionImmutableError,
)
from interview_evidence.company_management.domain.hiring import (
    Campaign,
    CampaignCriterionVersionImmutableError,
)

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
POSITION_ID = UUID("00000000-0000-7000-8000-000000000002")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000003")
CAMPAIGN_ID = UUID("00000000-0000-7000-8000-000000000004")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def criterion_version() -> CompetencyModelVersion:
    criterion = EvaluationCriterion(
        criterion_id=UUID("00000000-0000-7000-8000-000000000005"),
        code="PROBLEM_SOLVING",
        name="문제 해결",
        description="근거를 바탕으로 문제를 해결한다.",
        weight=1,
        good_evidence={"signal": "대안을 비교한다"},
        weak_evidence={"signal": "근거가 없다"},
        abstain_guidance="근거가 없으면 판단을 보류한다.",
        common_questions=("어떤 대안을 검토했나요?",),
        required=True,
    )
    return CompetencyModelVersion.create(
        competency_model_version_id=VERSION_ID,
        company_id=COMPANY_ID,
        position_id=POSITION_ID,
        version_number=1,
        criteria=(criterion,),
        prohibited_topics=("가족관계",),
        interview_duration_minutes=30,
        persona_definition={"name": "GBSA 면접관", "tone": "차분함"},
    )


def test_published_criterion_version_is_immutable() -> None:
    draft = criterion_version()
    published = draft.publish(expected_version=1, published_at=NOW)

    assert published.status == "published"
    assert published.published_at == NOW
    assert published.row_version == 2

    with pytest.raises(PublishedVersionImmutableError):
        published.replace_persona({"name": "변경된 면접관"})


def test_campaign_pins_the_published_criterion_version() -> None:
    published = criterion_version().publish(expected_version=1, published_at=NOW)
    campaign = Campaign.create(
        campaign_id=CAMPAIGN_ID,
        company_id=COMPANY_ID,
        position_id=POSITION_ID,
        competency_model_version=published,
        name="2026 백엔드 채용",
        candidate_instructions="조용한 환경에서 면접을 진행해 주세요.",
    )

    assert campaign.competency_model_version_id == VERSION_ID

    with pytest.raises(CampaignCriterionVersionImmutableError):
        campaign.pin_criterion_version(UUID("00000000-0000-7000-8000-000000000099"))
