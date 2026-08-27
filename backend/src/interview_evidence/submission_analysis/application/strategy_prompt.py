from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Final
from uuid import UUID

from interview_evidence.submission_analysis.domain.source import SourceReferenceCandidate

TASK_BUILD_INTERVIEW_STRATEGY: Final = "build_interview_strategy"
ANTHROPIC_BEDROCK_VERSION: Final = "bedrock-2023-05-31"
MAX_STRATEGY_OUTPUT_TOKENS: Final = 8_192

OUTPUT_SCHEMA: Final[Mapping[str, Any]] = {
    "common_topics": ["string"],
    "verification_points": [
        {
            "criterion_id": "uuid from provided criterion_ids",
            "prompt": "Korean verification objective",
            "source_ids": ["uuid from provided source_candidates"],
        }
    ],
    "follow_up_directions": {"criterion uuid": ["Korean follow-up direction"]},
    "time_budget": {"total_seconds": "positive integer"},
    "required_evidence_plan": {"criterion uuid": "positive integer"},
}

_SYSTEM_PROMPT: Final = """\
당신은 채용 면접 전략을 설계하는 분석가입니다. 기업이 등록한 필수·우대 자격요건과 지원자
제출 자료의 출처 목록을 연결해, 실제 면접에서 각 자격요건을 확인할 검증 계획을 만듭니다.

고정된 공통 역량 축을 새로 만들지 않습니다. 제공된 criterion_id는 기업이 등록한 자격요건을
추적하기 위한 식별자로만 사용하고, 검증 포인트는 해당 자격요건의 충족 근거에 집중합니다.
하나의 검증 포인트에는 하나의 자격요건만 연결합니다. 제출 자료에 관련 내용이 있으면 지원자가
직접 수행한 범위와 결과를 확인하고, 내용이 없으면 미충족으로 단정하지 않고 열린 질문으로
확인합니다. 직무와 무관한 암기식 이론이나 입력에 없는 일반 역량은 검증 계획에 추가하지 않습니다.

지원자를 시험하듯 바로 본론을 묻지 말고, 단계 시작이나 새로운 자료로 전환할 때만 출처를 짧게
밝힙니다. 같은 주제의 후속 검증은 출처를 반복하지 않고 직전 답변에서 자연스럽게 이어지도록
설계합니다. "제출하신 자료에서" 같은 고정 도입 표현을 검증 포인트마다 반복하지 않습니다.
입력에 없는 세부 내용을 연결 문장으로 만들어 내거나 검증되지 않은 사실을 확정적으로 말하지 않습니다.
자료 근거는 말로 매번 고지하지 않더라도 source_id로 계속 유지합니다.

반드시 지켜야 할 규칙:
1. criterion_id는 provided_criterion_ids에 있는 값만 사용합니다.
2. source_id는 provided_source_candidates에 있는 값만 사용합니다.
3. 모든 verification_point에는 최소 하나의 source_id를 지정합니다.
4. 입력에 없는 경력, 성과, 기술 또는 수치를 만들어 내지 않습니다.
5. prompt와 follow_up_directions는 압박적이거나 시험식이지 않은 자연스러운 한국어로 작성합니다.
6. time_budget.total_seconds는 양의 정수로 작성합니다.
7. 설명이나 마크다운 없이 output_schema와 일치하는 JSON 객체 하나만 출력합니다.
"""


def build_strategy_prompt(
    *,
    invitation_id: UUID,
    competency_model_version_id: UUID,
    criterion_ids: Sequence[UUID],
    source_candidates: Sequence[SourceReferenceCandidate],
    model_config_version: str,
) -> dict[str, Any]:
    task_payload = {
        "task": TASK_BUILD_INTERVIEW_STRATEGY,
        "invitation_id": str(invitation_id),
        "competency_model_version_id": str(competency_model_version_id),
        "provided_criterion_ids": [str(value) for value in criterion_ids],
        "provided_source_candidates": [
            candidate.model_dump(mode="json") for candidate in source_candidates
        ],
        "output_schema": dict(OUTPUT_SCHEMA),
        "model_config_version": model_config_version,
    }
    return {
        "anthropic_version": ANTHROPIC_BEDROCK_VERSION,
        "system": _SYSTEM_PROMPT,
        "max_tokens": MAX_STRATEGY_OUTPUT_TOKENS,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(task_payload, ensure_ascii=False),
                    }
                ],
            }
        ],
    }


def parse_strategy_response(response: Mapping[str, Any]) -> Mapping[str, Any]:
    if "verification_points" in response:
        return response
    content = response.get("content")
    if not isinstance(content, list):
        raise ValueError("strategy response has neither fields nor content blocks")
    joined = "".join(
        block.get("text", "")
        for block in content
        if isinstance(block, Mapping) and block.get("type", "text") == "text"
    ).strip()
    decoded = json.loads(_unwrapped(joined))
    if not isinstance(decoded, Mapping):
        raise ValueError("strategy response body is not a JSON object")
    return decoded


def strategy_task_payload_of(model_input: Mapping[str, Any]) -> Mapping[str, Any] | None:
    messages = model_input.get("messages")
    if not isinstance(messages, list) or not messages:
        return None
    last_message = messages[-1]
    if not isinstance(last_message, Mapping):
        return None
    content = last_message.get("content")
    if not isinstance(content, list) or not content:
        return None
    first_block = content[0]
    if not isinstance(first_block, Mapping):
        return None
    text = first_block.get("text")
    if not isinstance(text, str):
        return None
    decoded = json.loads(text)
    return decoded if isinstance(decoded, Mapping) else None


def _unwrapped(text: str) -> str:
    if not text.startswith("```"):
        return text
    without_open = text.split("\n", 1)[1] if "\n" in text else ""
    return without_open.rsplit("```", 1)[0].strip()
