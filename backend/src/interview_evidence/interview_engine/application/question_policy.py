from __future__ import annotations

import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QuestionDraft(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1)
    target_criterion_id: UUID
    source_reference_ids: tuple[UUID, ...]
    model_config_version: str = Field(min_length=1)
    retrieval_config_version: str = Field(min_length=1)


class QuestionPolicyResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    accepted: bool
    question: QuestionDraft
    reason_codes: tuple[str, ...] = ()


def _normalized(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.casefold())


class QuestionPolicy:
    def __init__(self, *, max_length: int = 240) -> None:
        self._max_length = max_length

    def evaluate(
        self,
        candidate: QuestionDraft,
        *,
        allowed_criterion_ids: frozenset[UUID],
        prohibited_topics: tuple[str, ...],
        previous_questions: tuple[str, ...],
        fallback_question: str,
        fallback_criterion_id: UUID,
    ) -> QuestionPolicyResult:
        reasons: list[str] = []
        normalized = _normalized(candidate.text)

        if candidate.target_criterion_id not in allowed_criterion_ids:
            reasons.append("criterion_axis_changed")
        if any(_normalized(topic) in normalized for topic in prohibited_topics if topic.strip()):
            reasons.append("forbidden_topic")
        if candidate.text.count("?") != 1:
            reasons.append("not_a_question" if "?" not in candidate.text else "multiple_questions")
        if len(candidate.text) > self._max_length:
            reasons.append("question_too_long")
        if normalized in {_normalized(question) for question in previous_questions}:
            reasons.append("duplicate_question")

        if not reasons:
            return QuestionPolicyResult(accepted=True, question=candidate)

        fallback = candidate.model_copy(
            update={
                "text": fallback_question,
                "target_criterion_id": fallback_criterion_id,
                "source_reference_ids": (),
            }
        )
        return QuestionPolicyResult(
            accepted=False,
            question=fallback,
            reason_codes=tuple(reasons),
        )
