from uuid import UUID

from interview_evidence.interview_engine.application.question_policy import (
    QuestionDraft,
    QuestionPolicy,
)

CRITERION_A = UUID("00000000-0000-7000-8000-000000000001")
CRITERION_B = UUID("00000000-0000-7000-8000-000000000002")


def draft(text: str, criterion_id: UUID = CRITERION_A) -> QuestionDraft:
    return QuestionDraft(
        text=text,
        target_criterion_id=criterion_id,
        source_reference_ids=(),
        model_config_version="question-model-v1",
        retrieval_config_version="hybrid-v1",
    )


def test_policy_accepts_one_short_question_on_fixed_axis() -> None:
    result = QuestionPolicy().evaluate(
        draft("최근 프로젝트에서 장애를 진단한 과정을 설명해 주세요?"),
        allowed_criterion_ids=frozenset({CRITERION_A, CRITERION_B}),
        prohibited_topics=("가족", "출신 지역"),
        previous_questions=(),
        fallback_question="문제를 해결한 과정을 설명해 주세요?",
        fallback_criterion_id=CRITERION_A,
    )

    assert result.accepted is True
    assert result.question.target_criterion_id == CRITERION_A
    assert result.reason_codes == ()


def test_policy_replaces_forbidden_duplicate_multi_question_or_axis_change() -> None:
    policy = QuestionPolicy()
    cases = (
        (draft("가족 구성은 어떻게 되나요?"), (), "forbidden_topic"),
        (
            draft("장애 원인은 무엇인가요? 해결 방법은 무엇인가요?"),
            (),
            "multiple_questions",
        ),
        (
            draft("최근 프로젝트에서 장애를 진단한 과정을 설명해 주세요?"),
            ("최근 프로젝트에서 장애를 진단한 과정을 설명해 주세요?",),
            "duplicate_question",
        ),
        (
            draft(
                "문제를 해결한 과정을 설명해 주세요?",
                UUID("00000000-0000-7000-8000-000000000099"),
            ),
            (),
            "criterion_axis_changed",
        ),
    )

    for candidate, previous, expected_reason in cases:
        result = policy.evaluate(
            candidate,
            allowed_criterion_ids=frozenset({CRITERION_A, CRITERION_B}),
            prohibited_topics=("가족", "출신 지역"),
            previous_questions=previous,
            fallback_question="문제를 해결한 과정을 설명해 주세요?",
            fallback_criterion_id=CRITERION_A,
        )
        assert result.accepted is False
        assert result.question.text == "문제를 해결한 과정을 설명해 주세요?"
        assert result.question.target_criterion_id == CRITERION_A
        assert expected_reason in result.reason_codes


def test_policy_blocks_non_question_and_overlong_output() -> None:
    result = QuestionPolicy(max_length=80).evaluate(
        draft("설명을 계속해 주세요." + ("매우 긴 문장" * 30)),
        allowed_criterion_ids=frozenset({CRITERION_A}),
        prohibited_topics=(),
        previous_questions=(),
        fallback_question="핵심 판단 과정을 설명해 주세요?",
        fallback_criterion_id=CRITERION_A,
    )

    assert result.accepted is False
    assert set(result.reason_codes) == {"not_a_question", "question_too_long"}
