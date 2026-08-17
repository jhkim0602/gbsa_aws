"""The generator must send the rendered prompt, not a bare task dict."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID

import pytest
from interview_evidence.interview_engine.application.question_generator import (
    QuestionGenerationUnavailable,
    QuestionGenerator,
)
from interview_evidence.interview_engine.application.question_prompt import (
    DEFAULT_QUESTION_PROMPT,
    task_payload_of,
)
from interview_evidence.shared.interview_level import InterviewLevel
from interview_evidence.shared.tenant import ActorType, TenantContext

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000601")
ACTOR_ID = UUID("00000000-0000-7000-8000-000000000602")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000603")
SOURCE_ID = UUID("00000000-0000-7000-8000-000000000604")


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=ACTOR_ID,
        request_id=ACTOR_ID,
        trace_id="question-prompt",
    )


class RecordingModel:
    """Answers like Anthropic does: JSON inside a text content block."""

    def __init__(self, question: str = "복구를 판단한 근거는 무엇이었나요?") -> None:
        self.question = question
        self.inputs: list[Mapping[str, Any]] = []

    def generate(
        self,
        context: TenantContext,
        model_input: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        del context
        self.inputs.append(model_input)
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "text": self.question,
                            "target_criterion_id": str(CRITERION_ID),
                            "source_reference_ids": [str(SOURCE_ID)],
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }


def _generate(model: RecordingModel) -> Any:
    return QuestionGenerator(model).generate(
        _context(),
        target_criterion_id=CRITERION_ID,
        context_payload={
            "criterion_text": "장애 대응 경험",
            "retrieved_sources": [{"source_id": str(SOURCE_ID)}],
        },
        model_config_version="bedrock-claude-v1",
        retrieval_config_version="aurora-hybrid-v1",
    )


def test_generator_sends_a_system_prompt_and_token_limit() -> None:
    model = RecordingModel()

    draft = _generate(model)

    body = model.inputs[0]
    assert "system" in body
    assert body["max_tokens"] == DEFAULT_QUESTION_PROMPT.max_tokens
    assert draft.text == "복구를 판단한 근거는 무엇이었나요?"
    assert draft.source_reference_ids == (SOURCE_ID,)
    assert draft.model_config_version == "bedrock-claude-v1"


def test_generator_records_the_prompt_version_it_used() -> None:
    model = RecordingModel()
    generator = QuestionGenerator(model)

    generator.generate(
        _context(),
        target_criterion_id=CRITERION_ID,
        context_payload={},
        model_config_version="bedrock-claude-v1",
        retrieval_config_version="aurora-hybrid-v1",
        interview_level=InterviewLevel.SENIOR,
    )

    payload = task_payload_of(model.inputs[0])
    assert payload is not None
    expected = generator.prompt_for(InterviewLevel.SENIOR)
    assert payload["prompt_version"] == expected.prompt_version
    assert payload["interview_level"] == "senior"


def test_prompt_template_is_swappable_without_touching_the_call_site() -> None:
    model = RecordingModel()
    tuned = DEFAULT_QUESTION_PROMPT.model_copy(
        update={
            "prompt_version": "question-prompt-test",
            "max_tokens": 256,
            "temperature": 0.0,
        }
    )

    QuestionGenerator(model, prompt=tuned).generate(
        _context(),
        target_criterion_id=CRITERION_ID,
        context_payload={},
        model_config_version="bedrock-claude-v1",
        retrieval_config_version="aurora-hybrid-v1",
    )

    assert model.inputs[0]["max_tokens"] == 256
    assert model.inputs[0]["temperature"] == 0.0


class UnparsableModel:
    def generate(
        self,
        context: TenantContext,
        model_input: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        del context, model_input
        return {"content": [{"type": "text", "text": "죄송하지만 답할 수 없습니다."}]}


def test_a_non_json_answer_degrades_instead_of_crashing_the_turn() -> None:
    with pytest.raises(QuestionGenerationUnavailable) as error:
        QuestionGenerator(UnparsableModel()).generate(
            _context(),
            target_criterion_id=CRITERION_ID,
            context_payload={},
            model_config_version="bedrock-claude-v1",
            retrieval_config_version="aurora-hybrid-v1",
        )

    assert error.value.retryable
