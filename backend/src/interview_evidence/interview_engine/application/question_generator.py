from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from interview_evidence.interview_engine.application.question_policy import QuestionDraft
from interview_evidence.shared.aws_clients.ports import AIModel
from interview_evidence.shared.tenant import TenantContext


class QuestionGenerationUnavailable(RuntimeError):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class QuestionGenerator:
    def __init__(self, model: AIModel) -> None:
        self._model = model

    def generate(
        self,
        context: TenantContext,
        *,
        target_criterion_id: UUID,
        context_payload: Mapping[str, Any],
        model_config_version: str,
        retrieval_config_version: str,
    ) -> QuestionDraft:
        try:
            response = self._model.generate(
                context,
                {
                    "task": "next_interview_question",
                    "target_criterion_id": str(target_criterion_id),
                    "context": dict(context_payload),
                    "output_schema": {
                        "text": "string",
                        "target_criterion_id": "uuid",
                        "source_reference_ids": ["uuid"],
                    },
                    "model_config_version": model_config_version,
                },
            )
            return QuestionDraft.model_validate(
                {
                    **dict(response),
                    "target_criterion_id": response.get("target_criterion_id", target_criterion_id),
                    "source_reference_ids": response.get("source_reference_ids", ()),
                    "model_config_version": model_config_version,
                    "retrieval_config_version": retrieval_config_version,
                }
            )
        except (RuntimeError, ValidationError, TypeError, ValueError) as error:
            raise QuestionGenerationUnavailable(
                "question generation is temporarily unavailable",
                retryable=True,
            ) from error
