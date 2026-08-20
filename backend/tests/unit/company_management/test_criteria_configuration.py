import pytest
from interview_evidence.company_management.api.company_routes import (
    CompetencyModelVersionCreate,
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


def test_interviewer_voice_preset_is_kept_in_the_version_request() -> None:
    payload = _payload([_criterion("SYSTEM_DESIGN", 65), _criterion("OWNERSHIP", 35)])
    payload["persona_definition"] = {
        "name": "심층형 면접관",
        "tone": "concise",
        "voice_id": "Seoyeon",
    }

    request = CompetencyModelVersionCreate.model_validate(payload)

    assert request.persona_definition is not None
    assert request.persona_definition.model_dump(mode="json") == payload["persona_definition"]
