from interview_evidence.interview_engine.application.answer_evidence import (
    answer_needs_follow_up,
    missing_answer_evidence,
)


def test_short_answer_needs_a_follow_up() -> None:
    assert answer_needs_follow_up("제가 직접 수정했습니다.", "technical") is True


def test_concrete_technical_answer_has_enough_evidence() -> None:
    answer = (
        "로그와 사용자 흐름을 비교해 원인을 분석했고, 변경 범위를 줄이기 위해 기존 구조를 "
        "유지하는 방식을 선택했습니다. 수정 후 회귀 테스트와 지표 측정으로 오류가 감소한 결과를 "
        "확인하고 배포했습니다."
    )

    assert missing_answer_evidence(answer, "technical") == ()
    assert answer_needs_follow_up(answer, "technical") is False


def test_behavioral_answer_reports_the_missing_evidence_groups() -> None:
    answer = "팀원과 함께 기능을 구현했습니다."

    assert missing_answer_evidence(answer, "behavioral") == (
        "소통하거나 조율한 행동",
        "협업 결과 또는 배운 점",
    )
