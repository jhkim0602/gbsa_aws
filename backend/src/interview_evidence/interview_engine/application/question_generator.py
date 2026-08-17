from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from interview_evidence.interview_engine.application.question_policy import QuestionDraft
from interview_evidence.interview_engine.application.question_prompt import (
    QuestionPromptTemplate,
    build_question_prompt,
    parse_question_response,
    question_prompt_for,
)
from interview_evidence.shared.aws_clients.ports import AIModel
from interview_evidence.shared.interview_level import (
    DEFAULT_INTERVIEW_LEVEL,
    InterviewLevel,
)
from interview_evidence.shared.tenant import TenantContext


class QuestionGenerationUnavailable(RuntimeError):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class QuestionGenerator:
    def __init__(
        self,
        model: AIModel,
        *,
        prompt: QuestionPromptTemplate | None = None,
    ) -> None:
        self._model = model
        # An explicit template pins every level to it, which is what a tuning
        # experiment wants. Left unset, the position's interview level chooses.
        self._prompt = prompt

    def prompt_for(self, level: InterviewLevel) -> QuestionPromptTemplate:
        return self._prompt or question_prompt_for(level)

    def generate(
        self,
        context: TenantContext,
        *,
        target_criterion_id: UUID,
        context_payload: Mapping[str, Any],
        model_config_version: str,
        retrieval_config_version: str,
        interview_level: InterviewLevel = DEFAULT_INTERVIEW_LEVEL,
    ) -> QuestionDraft:
        try:
            response = self._model.generate(
                context,
                build_question_prompt(
                    self.prompt_for(interview_level),
                    target_criterion_id=target_criterion_id,
                    context_payload=context_payload,
                    model_config_version=model_config_version,
                ),
            )
            fields = parse_question_response(response)
            return QuestionDraft.model_validate(
                {
                    **dict(fields),
                    "target_criterion_id": fields.get("target_criterion_id", target_criterion_id),
                    "source_reference_ids": fields.get("source_reference_ids", ()),
                    "model_config_version": model_config_version,
                    "retrieval_config_version": retrieval_config_version,
                }
            )
        except (RuntimeError, ValidationError, TypeError, ValueError) as error:
            raise QuestionGenerationUnavailable(
                "question generation is temporarily unavailable",
                retryable=True,
            ) from error
