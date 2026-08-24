from __future__ import annotations

import re
from difflib import SequenceMatcher
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


_SOURCE_OPENING_PATTERN = re.compile(
    r"^\s*(?:제출하신|제출한|제출)\s*(?:자료|내용)"
    r"(?:에\s*따르면|를\s*보면|에서\s*확인되는\s*내용에\s*따르면)\s*[,，:]?\s*"
)


def _soften_repeated_source_opening(
    candidate: str,
    previous_questions: tuple[str, ...],
) -> str:
    if _SOURCE_OPENING_PATTERN.match(candidate) is None:
        return candidate
    if not any(_SOURCE_OPENING_PATTERN.match(question) for question in previous_questions):
        return candidate
    softened = _SOURCE_OPENING_PATTERN.sub("", candidate, count=1).strip()
    return softened or candidate


_FALLBACK_QUESTIONS = (
    "앞서 말씀하신 내용에서 본인이 직접 판단하고 수행한 부분을 구체적으로 설명해 주세요?",
    "그 과정에서 검토한 대안과 최종 선택의 기준을 설명해 주세요?",
    "실행 과정에서 예상과 달랐던 점과 그에 대응한 방법을 설명해 주세요?",
    "결과가 좋아졌다고 판단한 근거와 확인 방법을 설명해 주세요?",
    "가장 어려웠던 제약 조건과 이를 다룬 방식을 설명해 주세요?",
    "처음 시도한 방법이 충분하지 않았다면 무엇을 바꾸었는지 설명해 주세요?",
    "팀원과 의견이 달랐던 지점과 합의에 이른 과정을 설명해 주세요?",
    "같은 상황을 다시 맡는다면 다르게 선택할 부분을 설명해 주세요?",
    "문제를 더 일찍 발견하기 위해 추가한 점검 방법을 설명해 주세요?",
    "해당 경험에서 가장 중요한 기술적 판단 하나와 그 이유를 설명해 주세요?",
    "성과에 가장 크게 기여한 본인의 행동 하나를 구체적으로 설명해 주세요?",
    "당시 결정에서 감수한 위험과 이를 줄인 방법을 설명해 주세요?",
    "우선순위를 정할 때 사용한 기준과 포기한 선택지를 설명해 주세요?",
    "작은 범위의 검증에서 확인한 내용과 전체 적용 기준을 설명해 주세요?",
    "작업 이후 재발 방지를 위해 남긴 변화와 효과를 설명해 주세요?",
    "사용자나 운영 환경에 미친 영향을 어떻게 확인했는지 설명해 주세요?",
    "진행 중 가장 불확실했던 가설과 이를 검증한 방법을 설명해 주세요?",
    "본인의 판단이 틀릴 가능성을 어떤 방식으로 확인했는지 설명해 주세요?",
    "동료에게 공유하거나 인계한 핵심 내용과 그 이유를 설명해 주세요?",
    "이 경험에서 얻은 교훈을 이후 작업에 적용한 사례를 설명해 주세요?",
)


def _is_duplicate(candidate: str, previous: str) -> bool:
    normalized_candidate = _normalized(candidate)
    normalized_previous = _normalized(previous)
    if normalized_candidate == normalized_previous:
        return True
    return SequenceMatcher(None, normalized_candidate, normalized_previous).ratio() >= 0.9


def _non_repeating_fallback(base: str, previous_questions: tuple[str, ...]) -> str:
    candidates = (base, *_FALLBACK_QUESTIONS)
    return next(
        (
            candidate
            for candidate in candidates
            if not any(_is_duplicate(candidate, previous) for previous in previous_questions)
        ),
        _FALLBACK_QUESTIONS[-1],
    )


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
        candidate = candidate.model_copy(
            update={
                "text": _soften_repeated_source_opening(
                    candidate.text,
                    previous_questions,
                )
            }
        )
        normalized = _normalized(candidate.text)

        if candidate.target_criterion_id not in allowed_criterion_ids:
            reasons.append("criterion_axis_changed")
        if any(_normalized(topic) in normalized for topic in prohibited_topics if topic.strip()):
            reasons.append("forbidden_topic")
        if candidate.text.count("?") != 1:
            reasons.append("not_a_question" if "?" not in candidate.text else "multiple_questions")
        if len(candidate.text) > self._max_length:
            reasons.append("question_too_long")
        if any(_is_duplicate(candidate.text, question) for question in previous_questions):
            reasons.append("duplicate_question")

        if not reasons:
            return QuestionPolicyResult(accepted=True, question=candidate)

        fallback = candidate.model_copy(
            update={
                "text": _non_repeating_fallback(fallback_question, previous_questions),
                "target_criterion_id": fallback_criterion_id,
                "source_reference_ids": (),
            }
        )
        return QuestionPolicyResult(
            accepted=False,
            question=fallback,
            reason_codes=tuple(reasons),
        )
