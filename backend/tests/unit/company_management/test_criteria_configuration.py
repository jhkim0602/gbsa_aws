import pytest
from interview_evidence.company_management.api.company_routes import (
    CompetencyModelVersionCreate,
    PositionCreate,
)
from pydantic import ValidationError


def _criterion(code: str, weight: int) -> dict[str, object]:
    return {
        "code": code,
        "name": code,
        "description": "면접 결과 평가 기준",
        "weight": weight,
        "verification_guide": {
            "observable_dimensions": ["상황"],
            "strong_answer_signals": ["근거가 구체적임"],
            "weak_answer_signals": ["본인 행동이 불명확함"],
            "follow_up_directions": ["직접 수행한 행동"],
            "max_follow_ups": 2,
            "time_budget_seconds": 300,
        },
        "abstain_guidance": "근거가 부족하면 판단을 유보합니다.",
        "required": True,
    }


def _payload(criteria: list[dict[str, object]]) -> dict[str, object]:
    return {
        "criteria": criteria,
        "job_requirements": [
            {
                "requirement_type": "required",
                "statement": "대규모 트래픽 설계 경험",
                "priority": 1,
                "criterion_code": str(criteria[0]["code"]),
            }
        ],
        "prohibited_topics": [],
        "interview_duration_minutes": 30,
    }


def test_criterion_weights_must_total_one_hundred() -> None:
    with pytest.raises(ValidationError, match="criterion weights must total 100"):
        CompetencyModelVersionCreate.model_validate(_payload([_criterion("SYSTEM_DESIGN", 90)]))


@pytest.mark.parametrize("duration", [10, 20, 45, 120])
def test_new_interview_duration_is_fixed_at_thirty_minutes(duration: int) -> None:
    payload = _payload([_criterion("SYSTEM_DESIGN", 100)])
    payload["interview_duration_minutes"] = duration

    with pytest.raises(ValidationError, match="Input should be 30"):
        CompetencyModelVersionCreate.model_validate(payload)


def test_position_capacity_cannot_exceed_the_guaranteed_api_ceiling() -> None:
    with pytest.raises(ValidationError, match="less than or equal to 400"):
        PositionCreate.model_validate(
            {
                "title": "대규모 면접",
                "description": "예약 용량 한도를 검증합니다.",
                "interview_capacity": 401,
            }
        )


def test_position_interview_time_requires_an_explicit_timezone() -> None:
    with pytest.raises(ValidationError, match="must include a timezone"):
        PositionCreate.model_validate(
            {
                "title": "시간대 없는 면접",
                "description": "예약 시각의 기준 지역이 필요합니다.",
                "interview_at": "2026-09-15T14:00:00",
            }
        )


def test_interviewer_voice_preset_is_kept_in_the_version_request() -> None:
    payload = _payload([_criterion("SYSTEM_DESIGN", 65), _criterion("OWNERSHIP", 35)])
    payload["persona_definition"] = {
        "name": "심층형 면접관",
        "tone": "concise",
        "voice_id": "Seoyeon",
        "system_prompt": "당신은 설계 근거를 차분히 확인하는 면접관입니다.",
    }

    request = CompetencyModelVersionCreate.model_validate(payload)

    assert request.persona_definition is not None
    assert request.persona_definition.model_dump(mode="json") == payload["persona_definition"]
