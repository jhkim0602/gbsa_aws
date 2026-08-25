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
    assert result.question.text == "최근 프로젝트에서 장애를 진단한 과정을 설명해 주세요."
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
        assert result.question.text == "문제를 해결한 과정을 설명해 주세요."
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


def test_policy_never_replays_an_already_used_fallback_question() -> None:
    previous = (
        "최근 프로젝트에서 장애를 진단한 과정을 설명해 주세요?",
        "문제를 해결한 과정을 설명해 주세요?",
    )

    result = QuestionPolicy().evaluate(
        draft("최근 프로젝트에서 장애를 진단한 과정을 설명해 주세요?"),
        allowed_criterion_ids=frozenset({CRITERION_A}),
        prohibited_topics=(),
        previous_questions=previous,
        fallback_question="문제를 해결한 과정을 설명해 주세요?",
        fallback_criterion_id=CRITERION_A,
    )

    assert result.accepted is False
    assert result.question.text not in previous
    assert result.question.text.endswith(".")


def test_policy_rejects_a_near_verbatim_question_rewrite() -> None:
    previous = (
        "Gemini Live와 Google Cloud Speech-to-Text를 함께 사용한 과정에서 직접 "
        "수행한 분석과 복구 작업을 구체적으로 설명해 주세요?",
    )

    result = QuestionPolicy().evaluate(
        draft(
            "Gemini Live와 Google Cloud Speech-to-Text를 함께 사용한 과정에서 "
            "지원자님이 직접 수행한 분석과 복구 작업을 구체적으로 설명해 주세요?"
        ),
        allowed_criterion_ids=frozenset({CRITERION_A}),
        prohibited_topics=(),
        previous_questions=previous,
        fallback_question="문제를 해결한 과정을 설명해 주세요?",
        fallback_criterion_id=CRITERION_A,
    )

    assert result.accepted is False
    assert "duplicate_question" in result.reason_codes


def test_policy_removes_a_repeated_submission_source_opening() -> None:
    result = QuestionPolicy().evaluate(
        draft(
            "제출하신 자료에 따르면, 자동 VAD 종료 문제에서 어떤 책임을 분리했는지 설명해 주세요?"
        ),
        allowed_criterion_ids=frozenset({CRITERION_A}),
        prohibited_topics=(),
        previous_questions=("제출하신 자료에 따르면, 장애 원인을 좁힌 과정을 설명해 주세요?",),
        fallback_question="문제를 해결한 과정을 설명해 주세요?",
        fallback_criterion_id=CRITERION_A,
    )

    assert result.accepted is True
    assert result.question.text == ("자동 VAD 종료 문제에서 어떤 책임을 분리했는지 설명해 주세요.")


def test_policy_keeps_the_first_submission_source_opening() -> None:
    question = "제출한 자료를 보면, 장애 원인을 좁힌 과정을 설명해 주세요?"

    result = QuestionPolicy().evaluate(
        draft(question),
        allowed_criterion_ids=frozenset({CRITERION_A}),
        prohibited_topics=(),
        previous_questions=(),
        fallback_question="문제를 해결한 과정을 설명해 주세요?",
        fallback_criterion_id=CRITERION_A,
    )

    assert result.accepted is True
    assert result.question.text == "제출한 자료를 보면, 장애 원인을 좁힌 과정을 설명해 주세요."


def test_policy_uses_a_period_for_a_polite_request_before_validation() -> None:
    result = QuestionPolicy().evaluate(
        draft("운영 문제를 해결하며 맡았던 역할을 설명해 주세요."),
        allowed_criterion_ids=frozenset({CRITERION_A}),
        prohibited_topics=(),
        previous_questions=(),
        fallback_question="문제를 해결한 과정을 설명해 주세요?",
        fallback_criterion_id=CRITERION_A,
    )

    assert result.accepted is True
    assert result.question.text == "운영 문제를 해결하며 맡았던 역할을 설명해 주세요."


def test_policy_replaces_a_question_that_does_not_match_the_interview_stage() -> None:
    result = QuestionPolicy().evaluate(
        draft("운영 장애의 기술적 원인과 복구 방법을 설명해 주세요."),
        allowed_criterion_ids=frozenset({CRITERION_A}),
        prohibited_topics=(),
        previous_questions=(),
        fallback_question="협업 경험을 설명해 주세요.",
        fallback_criterion_id=CRITERION_A,
        interview_stage="behavioral",
    )

    assert result.accepted is False
    assert "stage_mismatch" in result.reason_codes
    assert "팀원" in result.question.text or "협업" in result.question.text


def test_behavioral_follow_up_can_rely_on_the_previous_question_context() -> None:
    result = QuestionPolicy().evaluate(
        draft("그때 의견을 어떤 방식으로 조율했는지 말씀해 주세요."),
        allowed_criterion_ids=frozenset({CRITERION_A}),
        prohibited_topics=(),
        previous_questions=(),
        fallback_question="협업 경험을 설명해 주세요.",
        fallback_criterion_id=CRITERION_A,
        interview_stage="behavioral",
        question_type="follow_up",
    )

    assert result.accepted is True
