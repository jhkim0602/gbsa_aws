from __future__ import annotations

_MIN_SUBSTANTIVE_ANSWER_CHARS = 100

_STAGE_EVIDENCE_SIGNALS = {
    "technical": (
        (
            "구체적인 기술 수행 내용",
            (
                "구현",
                "적용",
                "변경",
                "수정",
                "분석",
                "비교",
                "테스트",
                "측정",
                "복구",
                "설계",
                "처리",
            ),
        ),
        (
            "기술 선택의 판단 근거",
            (
                "이유",
                "때문",
                "기준",
                "판단",
                "고려",
                "선택",
                "트레이드오프",
                "제약",
                "대안",
            ),
        ),
        (
            "결과 확인 또는 검증 방법",
            (
                "결과",
                "개선",
                "감소",
                "증가",
                "확인",
                "측정",
                "검증",
                "안정",
                "해결",
                "효과",
            ),
        ),
    ),
    "project_deep_dive": (
        (
            "프로젝트 목표와 문제 맥락",
            ("프로젝트", "서비스", "기능", "목표", "요구사항", "문제", "사용자"),
        ),
        (
            "본인이 맡은 역할과 수행 범위",
            ("제가", "본인", "직접", "담당", "맡", "구현", "설계", "기여"),
        ),
        (
            "프로젝트 결과 또는 회고",
            ("결과", "성과", "개선", "배웠", "회고", "이후", "효과", "검증"),
        ),
    ),
    "behavioral": (
        (
            "협업 상대와 상황",
            ("팀", "팀원", "동료", "협업", "상대", "구성원", "리뷰어", "이해관계자"),
        ),
        (
            "소통하거나 조율한 행동",
            ("의견", "조율", "소통", "피드백", "합의", "설득", "공유", "갈등", "역할", "책임"),
        ),
        (
            "협업 결과 또는 배운 점",
            ("결과", "합의", "해결", "개선", "배웠", "관계", "이후", "회고", "효과"),
        ),
    ),
}


def missing_answer_evidence(text: str, interview_stage: str) -> tuple[str, ...]:
    normalized = text.casefold().strip()
    signals = _STAGE_EVIDENCE_SIGNALS.get(interview_stage, ())
    return tuple(
        label
        for label, terms in signals
        if not any(term.casefold() in normalized for term in terms)
    )


def answer_needs_follow_up(text: str, interview_stage: str) -> bool:
    normalized = text.strip()
    if len(normalized) < _MIN_SUBSTANTIVE_ANSWER_CHARS:
        return True
    return len(missing_answer_evidence(normalized, interview_stage)) >= 2
