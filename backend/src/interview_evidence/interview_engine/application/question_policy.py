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

_POLITE_REQUEST_ENDINGS = ("주세요", "주십시오", "바랍니다")

_STAGE_SIGNAL_GROUPS = {
    "technical": (
        (
            "기술",
            "구현",
            "설계",
            "코드",
            "성능",
            "장애",
            "오류",
            "테스트",
            "검증",
            "데이터",
            "구조",
            "api",
            "알고리즘",
            "트레이드오프",
            "대안",
            "선택",
            "운영",
            "시스템",
            "배포",
            "원인",
            "원리",
            "네트워크",
            "프로토콜",
            "동시성",
            "트랜잭션",
            "중복",
            "순서",
        ),
    ),
    "project_deep_dive": (
        ("프로젝트", "서비스", "기능", "저장소", "github", "개발", "작업", "경험"),
        ("목표", "역할", "담당", "직접", "설계", "구현", "범위", "결과", "성과", "회고", "기여"),
    ),
    "behavioral": (
        ("팀", "팀원", "동료", "협업", "상대", "구성원", "리뷰어", "이해관계자", "다른 사람"),
        ("의견", "조율", "소통", "피드백", "합의", "설득", "공유", "갈등", "역할", "책임"),
    ),
}

_STAGE_FALLBACK_QUESTIONS = {
    "technical": (
        "기술적으로 가장 어려웠던 지점과 해결 방식을 설명해 주세요.",
        "그 기술 방식을 선택한 기준과 검증 결과를 설명해 주세요.",
        "구현 과정에서 검토한 대안과 최종 선택의 이유를 설명해 주세요.",
    ),
    "project_deep_dive": (
        "이 프로젝트의 목표와 본인이 직접 맡은 역할을 설명해 주세요.",
        "프로젝트에서 본인이 내린 핵심 설계 결정과 그 결과를 설명해 주세요.",
        "프로젝트 진행 중 맡은 범위와 결과를 확인한 방법을 설명해 주세요.",
    ),
    "behavioral": (
        "팀원과 의견이 달랐던 상황이 있었다면 어떻게 조율했는지 말씀해 주세요.",
        "협업 과정에서 책임을 나눠 맡은 경험이 있었다면 본인의 역할과 결과를 설명해 주세요.",
        "다른 사람과 역할을 맞춰야 했던 상황이 있었다면 소통한 과정을 말씀해 주세요.",
    ),
}

_FUNDAMENTALS_FALLBACK_QUESTIONS = (
    "제출 자료에 언급한 기술 하나를 골라, 그 기술의 동작 원리가 구현 방식에 어떻게 "
    "반영됐는지 설명해 주세요.",
    "앞서 언급한 기술에서 데이터의 중복이나 순서를 어떤 원리로 처리했는지 설명해 주세요.",
)

_FUNDAMENTALS_SIGNALS = (
    "원리",
    "동작",
    "자료구조",
    "알고리즘",
    "네트워크",
    "프로토콜",
    "동시성",
    "트랜잭션",
    "일관성",
    "중복",
    "순서",
    "복잡도",
    "메모리",
    "스레드",
    "인덱스",
)


def _prompt_body(text: str) -> str:
    return text.strip().rstrip(".!?！？。 ")


def _is_polite_request(text: str) -> bool:
    body = _prompt_body(text)
    return any(body.endswith(ending) for ending in _POLITE_REQUEST_ENDINGS)


def normalize_interview_prompt(text: str) -> str:
    stripped = text.strip()
    body = _prompt_body(stripped)
    if not body:
        return stripped
    if _is_polite_request(body):
        return f"{body}."
    if stripped.endswith(("?", "？")):
        return f"{body}?"
    return stripped


def is_interview_prompt(text: str) -> bool:
    stripped = text.strip()
    question_mark_count = stripped.count("?") + stripped.count("？")
    if question_mark_count == 1 and stripped.endswith(("?", "？")):
        return True
    return (
        question_mark_count == 0 and stripped.endswith((".", "。")) and _is_polite_request(stripped)
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
    candidates = tuple(
        normalize_interview_prompt(candidate) for candidate in (base, *_FALLBACK_QUESTIONS)
    )
    return next(
        (
            candidate
            for candidate in candidates
            if not any(_is_duplicate(candidate, previous) for previous in previous_questions)
        ),
        normalize_interview_prompt(_FALLBACK_QUESTIONS[-1]),
    )


def _stage_aligned(
    text: str,
    interview_stage: str,
    *,
    question_type: str = "core",
) -> bool:
    normalized = text.casefold()
    groups = _STAGE_SIGNAL_GROUPS.get(interview_stage)
    if groups is None:
        return True
    if question_type == "follow_up" and interview_stage in {
        "project_deep_dive",
        "behavioral",
    }:
        groups = groups[-1:]
    return all(any(term in normalized for term in group) for group in groups)


def stage_fallback_question(
    interview_stage: str,
    *,
    previous_questions: tuple[str, ...] = (),
    default: str = "",
    required_assessment_axis: str | None = None,
) -> str:
    stage_candidates = (
        _FUNDAMENTALS_FALLBACK_QUESTIONS
        if required_assessment_axis == "fundamentals"
        else _STAGE_FALLBACK_QUESTIONS.get(interview_stage, ())
    )
    candidates = tuple(
        normalize_interview_prompt(candidate)
        for candidate in (*stage_candidates, default, *_FALLBACK_QUESTIONS)
        if candidate.strip()
    )
    return next(
        (
            candidate
            for candidate in candidates
            if _stage_aligned(candidate, interview_stage)
            and not any(_is_duplicate(candidate, previous) for previous in previous_questions)
        ),
        normalize_interview_prompt(stage_candidates[-1] if stage_candidates else default),
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
        interview_stage: str | None = None,
        question_type: str = "core",
        required_assessment_axis: str | None = None,
    ) -> QuestionPolicyResult:
        reasons: list[str] = []
        candidate = candidate.model_copy(
            update={
                "text": _soften_repeated_source_opening(
                    normalize_interview_prompt(candidate.text),
                    previous_questions,
                )
            }
        )
        normalized = _normalized(candidate.text)

        if candidate.target_criterion_id not in allowed_criterion_ids:
            reasons.append("criterion_axis_changed")
        if any(_normalized(topic) in normalized for topic in prohibited_topics if topic.strip()):
            reasons.append("forbidden_topic")
        question_mark_count = candidate.text.count("?") + candidate.text.count("？")
        if question_mark_count > 1:
            reasons.append("multiple_questions")
        elif not is_interview_prompt(candidate.text):
            reasons.append("not_a_question")
        if len(candidate.text) > self._max_length:
            reasons.append("question_too_long")
        if any(_is_duplicate(candidate.text, question) for question in previous_questions):
            reasons.append("duplicate_question")
        if interview_stage is not None and not _stage_aligned(
            candidate.text,
            interview_stage,
            question_type=question_type,
        ):
            reasons.append("stage_mismatch")
        if required_assessment_axis == "fundamentals" and not any(
            signal in candidate.text.casefold() for signal in _FUNDAMENTALS_SIGNALS
        ):
            reasons.append("assessment_axis_mismatch")

        if not reasons:
            return QuestionPolicyResult(accepted=True, question=candidate)

        fallback = candidate.model_copy(
            update={
                "text": (
                    stage_fallback_question(
                        interview_stage,
                        previous_questions=previous_questions,
                        default=fallback_question,
                        required_assessment_axis=required_assessment_axis,
                    )
                    if interview_stage is not None
                    else _non_repeating_fallback(fallback_question, previous_questions)
                ),
                "target_criterion_id": fallback_criterion_id,
                "source_reference_ids": (),
            }
        )
        return QuestionPolicyResult(
            accepted=False,
            question=fallback,
            reason_codes=tuple(reasons),
        )
