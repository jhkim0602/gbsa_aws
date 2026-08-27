"""The prompt layer for interview question generation.

Before this module the generator handed ``AwsBedrockModel`` a bare dict of task
fields, which the adapter serialized straight into the Bedrock request body. That
body carried no system prompt, no interviewer persona and no ``max_tokens``, so
there was nothing to tune and nothing a real Anthropic model would accept.

Everything that shapes an interview question now lives in ``QuestionPromptTemplate``:
the persona, the rules the model must follow, the decoding limits and a version
string that is recorded with every generated question. Swapping a template is
therefore a reviewable change with an auditable version, not an edit buried in a
call site.

The rendered body is a valid Anthropic Messages request. The structured task
payload travels *inside* the user message rather than as extra top-level keys,
because Bedrock rejects unknown fields on the Anthropic schema; keeping it as JSON
also lets the local deterministic substitute route on the same task marker.

The 신입/주니어/시니어 toggle is one template per level. A level is not a numeric dial
on one prompt because what changes between levels is which questions are fair to ask
at all, which only prose can say; the numeric part of the toggle is the follow-up
budget in ``shared.interview_level``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from interview_evidence.shared.interview_level import (
    DEFAULT_INTERVIEW_LEVEL,
    InterviewLevel,
)

TASK_NEXT_QUESTION: Final = "next_interview_question"

#: Bedrock requires this literal on every Anthropic Messages request.
ANTHROPIC_BEDROCK_VERSION: Final = "bedrock-2023-05-31"

#: Shape the model must return. Kept beside the prompt so the two cannot drift.
OUTPUT_SCHEMA: Final[Mapping[str, Any]] = {
    "text": "string, exactly one interview prompt in Korean",
    "target_criterion_id": "uuid, must equal the requested criterion",
    "source_reference_ids": ["uuid of each provided excerpt the question relies on"],
}

_SYSTEM_PROMPT: Final = """\
당신은 실제 채용 면접을 진행하는 면접관입니다. 지원자의 제출 자료에서 확인된 근거를 바탕으로
평가 기준을 검증하는 질문 하나를 만듭니다.

반드시 지켜야 할 규칙:
1. 제공된 criterion_text와 verification_objective가 요구하는 내용만 검증합니다.
2. 질문 근거는 제공된 retrieved_sources의 발췌문에서만 가져옵니다. 발췌문에 없는 사실을
   지원자가 말했다고 가정하거나 새로 만들어 내지 않습니다.
3. 질문이나 답변 요청은 정확히 하나만 작성합니다. "설명해 주세요", "말씀해 주세요" 같은 요청형은
   마침표로 끝내고, "어떻게 해결하셨나요?" 같은 실제 의문형만 물음표로 끝냅니다.
4. 질문은 한국어 존댓말로 작성하고 {max_question_length}자를 넘기지 않습니다.
5. missing_dimensions에 남은 항목이 있으면 그중 하나를 좁혀 묻습니다.
6. recent_turns에 이미 나온 질문을 다시 묻지 않습니다.
7. 개인 신상, 가족, 종교, 정치, 출신 지역 등 직무와 무관한 주제는 묻지 않습니다.
8. 질문에 실제로 활용한 발췌문의 source_id만 source_reference_ids에 담습니다.
9. interview_stage와 interview_stage_focus를 따라 현재 단계의 목적에 맞는 질문을 만듭니다.
   - adaptive: 회사가 설정한 자격요건 또는 필수 질문을 verification_objective로 삼고,
     retrieved_sources와 직전 답변을 연결해 지원자마다 다른 질문을 만듭니다.
     미리 정한 기술·프로젝트·협업 순서를 가정하지 않습니다.
   - technical: 기술 선택, 구현 방식, 원리, 대안, 트레이드오프, 검증 중 하나를 직접 확인합니다.
     협업 방식만 묻는 질문은 만들지 않습니다.
   - project_deep_dive: 하나의 실제 프로젝트를 기준으로 목표, 주요 구성 요소와 책임 경계,
     요청·데이터 흐름, 설계 결정과 트레이드오프, 운영·확장 방식, 본인 기여를 연결합니다.
     retrieved_sources가 Git 코드 조각이어도 코드는 구조를 추론하는 근거로만 사용합니다.
     특정 파일명·함수명·메서드명·클래스명, 매개변수, 반환값, 내부 분기나 코드 문법을 직접
     기억하거나 설명하게 하는 질문은 만들지 않습니다.
   - behavioral: 반드시 함께 일한 사람과의 소통, 역할 조율, 의견 차이, 피드백, 책임 중 하나를
     확인합니다. 기술 구현, 장애 해결, 성능 개선만 묻는 질문은 만들지 않습니다.
10. next_question_type에 맞춰 질문 역할을 구분합니다.
    - stage_opening: 짧은 주제 전환 표현 뒤 첫 핵심 질문을 합니다.
    - core: 다음 자격요건 또는 기업 질문의 새로운 핵심 근거를 확인합니다.
    - follow_up: 직전 답변에서 answer_evidence_gaps로 표시된 항목 하나만 좁혀 묻습니다.
    - stage_final: 남은 기업 기준 중 아직 확인하지 못한 가장 중요한 내용 하나를 묻습니다.
11. 갑자기 본론만 묻지 말고, 필요할 때만 질문 앞에 짧은 맥락 연결 문장을 둡니다.
    - 새로운 자격요건이나 자료·주제로 전환될 때만 출처를 자연스럽게 한 번 밝힙니다.
      예: "이번에는 GitHub 프로젝트를 바탕으로 여쭤보겠습니다."
    - 같은 주제의 후속 질문은 출처를 다시 말하지 않고 "그 과정에서", "앞서 말씀하신 내용과
      관련해"처럼 직전 답변에서 자연스럽게 이어갑니다.
    - 맥락을 다시 설명할 필요가 없으면 연결 문장 없이 질문을 바로 시작해도 됩니다.
    연결 문장은 지원자의 답변을 미리 평가하거나 정답을 암시하지 않으며, 제공된 발췌문과 이전 답변에
    있는 정보만 자연스럽게 반복합니다.
12. recent_turns의 최근 면접관 질문을 확인해 같은 도입 표현을 반복하지 않습니다. 특히
    "제출하신 자료에서", "작성해 주신 내용에서" 같은 출처 고지형 표현을 매 질문마다 또는
    연속해서 사용하지 않습니다. 말로 출처를 언급하지 않은 질문도 실제 근거의 source_id는 반드시
    source_reference_ids에 유지합니다.
13. stage_evidence_available이 false이면 자료에 협업이나 역할 조율 경험이 있다고 단정하지 않습니다.
    behavioral 단계에서는 "함께 조율해야 했던 상황이 있었다면"처럼 사실을 열어 둔 질문으로
    확인하고, 없다는 답변도 허용합니다.
14. context에 stage_alignment_retry가 있으면 rejected_question이 현재 단계와 맞지 않거나,
    프로젝트 단계에서 지나치게 코드 수준이라 거절된 질문입니다.
    같은 내용을 고쳐 쓰지 말고 reason_codes와 현재 단계 규칙에 맞는 새 질문을 만듭니다.

필수·우대 자격요건의 문장을 질문으로 바꾸지 않습니다. 자격요건은 면접 후 제출 자료와 답변을
판정하는 리포트 기준이며, 질문은 현재 단계의 역량 기준과 제공된 지원자 자료를 바탕으로 만듭니다.
기업이 직접 지정한 필수 질문은 이 생성 프롬프트를 거치지 않고 별도 질문으로 그대로 진행됩니다.

질문 깊이:
{depth_guidance}

설명이나 머리말 없이 다음 JSON 객체 하나만 출력합니다:
{output_schema}"""

_PERSONA: Final = (
    "차분하고 분석적인 시니어 엔지니어 면접관입니다. 지원자를 압박하지 않으면서도 "
    "주장의 근거와 본인의 기여를 구체적으로 확인합니다."
)

#: What the 신입/주니어/시니어 toggle actually changes about a question. The level does
#: not change *whether* a criterion is verified -- only how far down the question digs,
#: which is the difference a recruiter is choosing between.
_DEPTH_GUIDANCE: Final[Mapping[InterviewLevel, str]] = {
    InterviewLevel.ENTRY: (
        "- 실무 경력이 없는 신입 지원자입니다. 학습 과정, 직접 해 본 시도, "
        "왜 그렇게 했는지를 묻습니다.\n"
        "- 발췌문에 있는 내용을 한 단계만 파고듭니다. 답변에 없는 상위 개념을 전제하지 않습니다.\n"
        "- 대규모 운영 경험, 조직 설계, 기술 선택의 장기 비용처럼 신입이 겪을 수 없는 "
        "상황은 묻지 않습니다.\n"
        "- 한 질문에 하나의 사실만 확인합니다."
    ),
    InterviewLevel.JUNIOR: (
        "- 1~3년 경력의 주니어 지원자입니다. 본인이 직접 수행한 작업과 그 판단 근거를 확인합니다.\n"
        "- 발췌문에 드러난 선택 하나를 골라 대안과 비교하게 만듭니다.\n"
        "- 팀의 성과와 본인의 기여가 섞여 있으면 본인 몫을 분리해 묻습니다."
    ),
    InterviewLevel.SENIOR: (
        "- 시니어 지원자입니다. 결과가 아니라 그 결과에 이르게 한 트레이드오프와 "
        "실패 대비를 확인합니다.\n"
        "- 발췌문의 선택을 제약 조건과 함께 묻습니다. 무엇을 포기했고 그 대가를 "
        "어떻게 감당했는지 확인합니다.\n"
        "- 첫 답변이 타당해 보여도 한 단계 더 들어가 근거의 한계나 측정 방법을 묻습니다.\n"
        "- 단순한 용어 확인이나 개념 설명 요청은 하지 않습니다."
    ),
}


class QuestionPromptTemplate(BaseModel):
    """Every knob that changes a generated question, versioned as one unit."""

    model_config = ConfigDict(frozen=True)

    prompt_version: str = Field(min_length=1, max_length=60)
    interview_level: InterviewLevel = DEFAULT_INTERVIEW_LEVEL
    persona: str = Field(min_length=1, max_length=1_000)
    system_prompt: str = Field(min_length=1, max_length=8_000)
    #: How deep this level digs. Rendered into the system prompt, so a level change is
    #: visible to the model rather than only to the follow-up counter.
    depth_guidance: str = Field(min_length=1, max_length=2_000)
    max_tokens: int = Field(ge=64, le=4_096)
    temperature: float = Field(ge=0.0, le=1.0)
    #: Mirrors QuestionPolicy.max_length so the model is told the limit it is judged by.
    max_question_length: int = Field(default=240, ge=40, le=1_000)

    def rendered_system_prompt(self) -> str:
        return "\n\n".join(
            (
                self.persona,
                self.system_prompt.format(
                    max_question_length=self.max_question_length,
                    depth_guidance=self.depth_guidance,
                    output_schema=json.dumps(OUTPUT_SCHEMA, ensure_ascii=False, indent=2),
                ),
            )
        )


def _template_for(level: InterviewLevel) -> QuestionPromptTemplate:
    return QuestionPromptTemplate(
        prompt_version=f"question-prompt-v6-{level.value}",
        interview_level=level,
        persona=_PERSONA,
        system_prompt=_SYSTEM_PROMPT,
        depth_guidance=_DEPTH_GUIDANCE[level],
        max_tokens=512,
        # Low but non-zero: identical context should not produce a verbatim identical
        # interview, while the policy still has to accept the result.
        temperature=0.3,
        # A 신입 question that sprawls is usually two questions wearing one sentence,
        # so the entry template is told to stay well inside the policy limit.
        max_question_length=160 if level is InterviewLevel.ENTRY else 240,
    )


QUESTION_PROMPTS: Final[Mapping[InterviewLevel, QuestionPromptTemplate]] = {
    level: _template_for(level) for level in InterviewLevel
}

DEFAULT_QUESTION_PROMPT: Final = QUESTION_PROMPTS[DEFAULT_INTERVIEW_LEVEL]


def question_prompt_for(level: InterviewLevel) -> QuestionPromptTemplate:
    """The template a given interview level is conducted with."""
    return QUESTION_PROMPTS[level]


def build_question_prompt(
    template: QuestionPromptTemplate,
    *,
    target_criterion_id: UUID,
    context_payload: Mapping[str, Any],
    model_config_version: str,
) -> dict[str, Any]:
    """Render an Anthropic Messages body for one question turn."""
    task_payload = {
        "task": TASK_NEXT_QUESTION,
        "target_criterion_id": str(target_criterion_id),
        "context": dict(context_payload),
        "output_schema": dict(OUTPUT_SCHEMA),
        "model_config_version": model_config_version,
        "prompt_version": template.prompt_version,
        "interview_level": template.interview_level.value,
    }
    return {
        "anthropic_version": ANTHROPIC_BEDROCK_VERSION,
        "system": template.rendered_system_prompt(),
        "max_tokens": template.max_tokens,
        "temperature": template.temperature,
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


def task_payload_of(model_input: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Recover the structured task payload from a rendered prompt body.

    The deterministic local model and the contract tests both need to know what was
    asked without re-implementing the message layout.
    """
    messages = model_input.get("messages")
    if not isinstance(messages, list) or not messages:
        return None
    content = messages[-1].get("content") if isinstance(messages[-1], Mapping) else None
    if isinstance(content, str):
        text = content
    elif isinstance(content, list) and content and isinstance(content[0], Mapping):
        raw_text = content[0].get("text")
        text = raw_text if isinstance(raw_text, str) else ""
    else:
        return None
    try:
        decoded = json.loads(text)
    except (TypeError, ValueError):
        return None
    return decoded if isinstance(decoded, Mapping) else None


def parse_question_response(response: Mapping[str, Any]) -> Mapping[str, Any]:
    """Read the question fields out of a model response.

    Anthropic returns the answer as text blocks, so the JSON the prompt asked for
    arrives as a string that still has to be decoded. A response that already has
    the flat fields is passed through, which is what the deterministic local model
    and the in-memory test doubles return.
    """
    if "text" in response:
        return response
    content = response.get("content")
    if not isinstance(content, list):
        raise ValueError("model response has neither question text nor content blocks")
    joined = "".join(
        block.get("text", "")
        for block in content
        if isinstance(block, Mapping) and block.get("type", "text") == "text"
    ).strip()
    decoded = json.loads(_unwrapped(joined))
    if not isinstance(decoded, Mapping):
        raise ValueError("model response body is not a JSON object")
    return decoded


def _unwrapped(text: str) -> str:
    """Strip a ```json fence, which models emit even when told not to."""
    if not text.startswith("```"):
        return text
    without_open = text.split("\n", 1)[1] if "\n" in text else ""
    return without_open.rsplit("```", 1)[0].strip()
