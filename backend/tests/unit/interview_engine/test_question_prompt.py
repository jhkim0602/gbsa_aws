"""The prompt layer must produce a body a real Bedrock model would accept.

Before T272 the generator handed the adapter a bare dict of task fields with no
system prompt, persona or decoding limits, so there was nothing to tune and the
request would have been rejected by the Anthropic schema.
"""

from __future__ import annotations

import json
from uuid import UUID

import pytest
from interview_evidence.interview_engine.application.question_prompt import (
    ANTHROPIC_BEDROCK_VERSION,
    DEFAULT_QUESTION_PROMPT,
    TASK_NEXT_QUESTION,
    build_question_prompt,
    parse_question_response,
    question_prompt_for,
    task_payload_of,
)
from interview_evidence.shared.interview_level import InterviewLevel

CRITERION_ID = UUID("00000000-0000-7000-8000-000000000501")
SOURCE_ID = UUID("00000000-0000-7000-8000-000000000502")

CONTEXT_PAYLOAD = {
    "criterion_text": "장애 상황에서 원인을 좁히고 복구를 주도한 경험",
    "verification_objective": "원인 분석 절차와 본인 기여 확인",
    "missing_dimensions": ["복구 판단 근거"],
    "retrieved_sources": [
        {
            "source_id": str(SOURCE_ID),
            "source_type": "submission_chunk",
            "locator": {"page_number": 2},
            "excerpt": "ECS 배포 경험은 있으나 장애 대응 설명은 없습니다.",
            "score": 0.82,
        }
    ],
}


def _prompt() -> dict[str, object]:
    return build_question_prompt(
        DEFAULT_QUESTION_PROMPT,
        target_criterion_id=CRITERION_ID,
        context_payload=CONTEXT_PAYLOAD,
        model_config_version="bedrock-claude-v1",
    )


def test_prompt_body_is_a_valid_anthropic_messages_request() -> None:
    body = _prompt()

    assert body["anthropic_version"] == ANTHROPIC_BEDROCK_VERSION
    assert body["max_tokens"] == DEFAULT_QUESTION_PROMPT.max_tokens
    assert body["temperature"] == DEFAULT_QUESTION_PROMPT.temperature
    assert isinstance(body["system"], str) and body["system"].strip()
    messages = body["messages"]
    assert isinstance(messages, list) and len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"][0]["type"] == "text"

    # The Anthropic schema rejects unknown top-level fields, so the task payload
    # must not leak out of the message.
    assert set(body) == {
        "anthropic_version",
        "system",
        "max_tokens",
        "temperature",
        "messages",
    }


def test_system_prompt_carries_the_persona_and_the_policy_limits() -> None:
    system = str(_prompt()["system"])

    assert DEFAULT_QUESTION_PROMPT.persona in system
    # The model is told the exact length the policy will judge it by.
    assert str(DEFAULT_QUESTION_PROMPT.max_question_length) in system
    assert "source_reference_ids" in system


def test_system_prompt_uses_grounded_conversational_bridges_and_natural_axis_coverage() -> None:
    system = str(_prompt()["system"])

    assert "단계가 시작되거나 새로운 자료·주제로 전환될 때만" in system
    assert '"제출하신 자료에서", "작성해 주신 내용에서"' in system
    assert "매 질문마다 또는\n    연속해서 사용하지 않습니다" in system
    assert "source_reference_ids에 유지합니다" in system
    assert "지원자의 답변을 미리 평가하거나 정답을 암시하지 않으며" in system
    assert '"설명해 주세요", "말씀해 주세요" 같은 요청형은' in system
    assert "실제 의문형만 물음표로 끝냅니다" in system
    for label in ("정확성", "깊이", "CS 기본기", "본인 기여", "설명력"):
        assert label in system
    assert "한 질문에 다섯 관점을 모두 담지 않습니다" in system
    assert "기술 구현, 장애 해결, 성능 개선만 묻는 질문은 만들지 않습니다" in system
    assert "answer_evidence_gaps" in system
    assert "stage_alignment_retry" in system
    assert "required_assessment_axis가 fundamentals이면" in system
    assert "주요 구성 요소와 책임 경계" in system
    assert "특정 파일명·함수명·메서드명·클래스명" in system
    assert "코드는 구조를 추론하는 근거로만 사용합니다" in system


def test_task_payload_round_trips_through_the_message() -> None:
    payload = task_payload_of(_prompt())

    assert payload is not None
    assert payload["task"] == TASK_NEXT_QUESTION
    assert payload["target_criterion_id"] == str(CRITERION_ID)
    assert payload["prompt_version"] == DEFAULT_QUESTION_PROMPT.prompt_version
    assert payload["model_config_version"] == "bedrock-claude-v1"
    assert payload["context"] == CONTEXT_PAYLOAD


def test_criterion_text_and_excerpts_reach_the_model() -> None:
    # The constitution forbids passing only identifiers to question generation.
    serialized = json.dumps(_prompt(), ensure_ascii=False)

    assert "ECS 배포 경험은 있으나 장애 대응 설명은 없습니다." in serialized
    assert "장애 상황에서 원인을 좁히고 복구를 주도한 경험" in serialized


def test_task_payload_of_ignores_a_body_without_a_json_message() -> None:
    assert task_payload_of({"messages": [{"role": "user", "content": "hello"}]}) is None
    assert task_payload_of({"task": "legacy"}) is None


def test_parse_question_response_decodes_anthropic_content_blocks() -> None:
    fields = parse_question_response(
        {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "text": "복구를 판단한 근거는 무엇이었나요?",
                            "target_criterion_id": str(CRITERION_ID),
                            "source_reference_ids": [str(SOURCE_ID)],
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }
    )

    assert fields["text"] == "복구를 판단한 근거는 무엇이었나요?"
    assert fields["source_reference_ids"] == [str(SOURCE_ID)]


def test_parse_question_response_survives_a_fenced_code_block() -> None:
    fenced = '```json\n{"text": "왜 그렇게 판단했나요?"}\n```'

    fields = parse_question_response({"content": [{"type": "text", "text": fenced}]})

    assert fields["text"] == "왜 그렇게 판단했나요?"


def test_parse_question_response_passes_through_a_flat_body() -> None:
    flat = {"text": "무엇을 우선했나요?", "source_reference_ids": []}

    assert parse_question_response(flat) is flat


def test_parse_question_response_rejects_an_unusable_body() -> None:
    with pytest.raises(ValueError):
        parse_question_response({"stop_reason": "max_tokens"})


def test_each_level_gets_its_own_prompt_version_and_depth_instructions() -> None:
    """The level has to reach the model, not only the follow-up counter.

    A numeric dial cannot express that an org-design question is unfair to a 신입 and
    expected of a 시니어, so the toggle selects a template and the template carries the
    prose. Distinct versions keep a stored rationale traceable to what was asked.
    """
    versions = {level: question_prompt_for(level).prompt_version for level in InterviewLevel}

    assert len(set(versions.values())) == len(InterviewLevel)
    for level in InterviewLevel:
        template = question_prompt_for(level)
        assert template.interview_level is level
        assert level.value in template.prompt_version
        system = template.rendered_system_prompt()
        assert template.depth_guidance in system


def test_entry_and_senior_depth_guidance_forbid_the_other_level_s_questions() -> None:
    entry = question_prompt_for(InterviewLevel.ENTRY).depth_guidance
    senior = question_prompt_for(InterviewLevel.SENIOR).depth_guidance

    assert entry != senior
    # 신입 cannot have run a large deployment, so the template says not to ask.
    assert "묻지 않습니다" in entry
    # 시니어 is past terminology checks; the value is in the trade-off.
    assert "트레이드오프" in senior
    # A 신입 question that sprawls is two questions in one sentence, so the entry
    # template stays well inside the length the policy judges by.
    assert (
        question_prompt_for(InterviewLevel.ENTRY).max_question_length
        < question_prompt_for(InterviewLevel.SENIOR).max_question_length
    )


def test_task_payload_records_the_level_the_question_was_generated_at() -> None:
    body = build_question_prompt(
        question_prompt_for(InterviewLevel.ENTRY),
        target_criterion_id=CRITERION_ID,
        context_payload=CONTEXT_PAYLOAD,
        model_config_version="bedrock-claude-v1",
    )
    payload = task_payload_of(body)

    assert payload is not None
    assert payload["interview_level"] == "entry"
    # The level rides inside the user message like the rest of the task payload;
    # the Anthropic schema would reject it as a top-level field.
    assert "interview_level" not in body
