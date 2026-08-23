from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from interview_evidence.recruiting_assistant.domain import AssistantSearchResult

TASK_RECRUITING_ASSISTANT: Final = "answer_recruiting_question"
ANTHROPIC_BEDROCK_VERSION: Final = "bedrock-2023-05-31"

_SYSTEM_PROMPT: Final = """\
당신은 채용 담당자와 자연스럽게 대화하는 AI 채용 어시스턴트입니다.

답변 원칙:
1. 질문과 정확히 일치하는 근거가 있으면 지원자 이름과 구체적인 행동을 들어 바로 답합니다.
2. 정확히 일치하는 근거는 없지만 관련되거나 비슷한 사례가 있으면, 없다고만 끝내지 말고
   "직접 확인되지는 않지만 비슷한 사례로는"처럼 구분한 뒤 도움이 되는 내용을 설명합니다.
3. 제공된 자료에 없는 사실을 새로 만들지는 않되,
   불필요한 경고나 딱딱한 정책 문구는 반복하지 않습니다.
4. 실제로 답변에 활용한 source_id를 source_ids에 넣습니다. ID 선택이 확실하지 않다면 비워도 됩니다.
5. 한국어 존댓말로 친절하고 자연스럽게 작성하며, 필요하면 짧은 목록을 사용합니다.
6. archived_scope가 true이면 종료된 채용의 과거 분석임을 밝히고,
   현재 모집 중인 것처럼 표현하지 않습니다.

설명이나 머리말 없이 다음 JSON 객체 하나만 출력합니다:
{
  "answer": "근거에 기반한 한국어 답변",
  "source_ids": ["실제로 사용한 source_id"]
}"""


class AssistantAnswerVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    answer: str = Field(min_length=1, max_length=10_000)
    source_ids: tuple[UUID, ...] = ()


def build_answer_prompt(
    *,
    query: str,
    scope: str,
    position_id: UUID | None,
    archived_scope: bool,
    sources: Sequence[AssistantSearchResult],
) -> dict[str, Any]:
    payload = {
        "task": TASK_RECRUITING_ASSISTANT,
        "scope": scope,
        "position_id": str(position_id) if position_id is not None else None,
        "archived_scope": archived_scope,
        "question": query,
        "provided_sources": [
            {
                "source_id": str(source.assistant_document_id),
                "position_id": str(source.position_id),
                "applicant_id": str(source.applicant_id),
                "invitation_id": str(source.invitation_id),
                "report_id": str(source.report_id),
                "report_item_id": (
                    str(source.report_item_id) if source.report_item_id is not None else None
                ),
                "criterion_id": (
                    str(source.criterion_id) if source.criterion_id is not None else None
                ),
                "document_type": source.document_type,
                "excerpt": source.excerpt,
                "relevance_score": source.score,
                "score_components": source.score_components,
                "metadata": source.metadata,
            }
            for source in sources
        ],
    }
    return {
        "anthropic_version": ANTHROPIC_BEDROCK_VERSION,
        "system": _SYSTEM_PROMPT,
        "max_tokens": 1600,
        "temperature": 0.3,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(payload, ensure_ascii=False),
                    }
                ],
            }
        ],
    }


def parse_answer_response(response: Mapping[str, Any]) -> AssistantAnswerVerdict:
    if "answer" in response:
        return AssistantAnswerVerdict.model_validate(response)
    content = response.get("content")
    if not isinstance(content, list):
        raise ValueError("assistant response has neither answer nor content blocks")
    joined = "".join(
        block.get("text", "")
        for block in content
        if isinstance(block, Mapping) and block.get("type", "text") == "text"
    ).strip()
    decoded = json.loads(_unwrapped(joined))
    if not isinstance(decoded, Mapping):
        raise ValueError("assistant response body is not a JSON object")
    return AssistantAnswerVerdict.model_validate(decoded)


def _unwrapped(text: str) -> str:
    if not text.startswith("```"):
        return text
    without_open = text.split("\n", 1)[1] if "\n" in text else ""
    return without_open.rsplit("```", 1)[0].strip()
