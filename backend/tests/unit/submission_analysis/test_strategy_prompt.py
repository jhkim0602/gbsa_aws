from __future__ import annotations

import json
from uuid import UUID

from interview_evidence.submission_analysis.application.strategy_prompt import (
    build_strategy_prompt,
    parse_strategy_response,
    strategy_task_payload_of,
)
from interview_evidence.submission_analysis.domain.source import SourceReferenceCandidate

INVITATION_ID = UUID("00000000-0000-7000-8000-000000000001")
MODEL_VERSION_ID = UUID("00000000-0000-7000-8000-000000000002")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000003")
SOURCE_ID = UUID("00000000-0000-7000-8000-000000000004")


def test_strategy_prompt_is_a_valid_anthropic_messages_request() -> None:
    prompt = build_strategy_prompt(
        invitation_id=INVITATION_ID,
        competency_model_version_id=MODEL_VERSION_ID,
        criterion_ids=(CRITERION_ID,),
        source_candidates=(_source_candidate(),),
        model_config_version="strategy-v1",
    )

    assert prompt["anthropic_version"] == "bedrock-2023-05-31"
    assert prompt["max_tokens"] == 2_048
    payload = strategy_task_payload_of(prompt)
    assert payload is not None
    assert payload["provided_criterion_ids"] == [str(CRITERION_ID)]
    assert payload["provided_source_candidates"][0]["source_id"] == str(SOURCE_ID)


def test_strategy_response_parses_anthropic_json_content() -> None:
    result = {
        "common_topics": ["문제 해결"],
        "verification_points": [
            {
                "criterion_id": str(CRITERION_ID),
                "prompt": "장애 대응 과정을 확인합니다.",
                "source_ids": [str(SOURCE_ID)],
            }
        ],
        "follow_up_directions": {str(CRITERION_ID): ["대안을 확인합니다."]},
        "time_budget": {"total_seconds": 1_800},
        "required_evidence_plan": {str(CRITERION_ID): 1},
    }

    parsed = parse_strategy_response(
        {
            "content": [
                {
                    "type": "text",
                    "text": f"```json\n{json.dumps(result, ensure_ascii=False)}\n```",
                }
            ]
        }
    )

    assert parsed == result


def _source_candidate() -> SourceReferenceCandidate:
    return SourceReferenceCandidate(
        source_id=SOURCE_ID,
        source_type="submission_chunk",
        locator={"page_number": 1},
        content_hash="a" * 64,
        relevance_score=1,
        ownership_confidence=1,
    )
