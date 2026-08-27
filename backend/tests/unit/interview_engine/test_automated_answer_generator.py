import json
from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import UUID

from interview_evidence.interview_engine.application.automated_answer_generator import (
    ANTHROPIC_BEDROCK_VERSION,
    AutomatedAnswerGenerator,
    AutomatedAnswerProfile,
)
from interview_evidence.interview_engine.application.interview_plan import InterviewStage
from interview_evidence.interview_engine.domain.session import InterviewSession
from interview_evidence.interview_engine.domain.turn import (
    InterviewTurn,
    QuestionSourceReference,
    TurnSpeaker,
    TurnStatus,
)
from interview_evidence.shared.aws_clients.ports import DeterministicAIModel
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 23, 10, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
QUESTION_ID = UUID("00000000-0000-7000-8000-000000000003")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000004")
SOURCE_ID = UUID("00000000-0000-7000-8000-000000000005")


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.APPLICANT,
        actor_id=UUID("00000000-0000-7000-8000-000000000006"),
        request_id=UUID("00000000-0000-7000-8000-000000000007"),
        trace_id="trace-generated-answer",
    )


def test_generated_answer_uses_the_current_questions_source_excerpts() -> None:
    session = InterviewSession(
        interview_session_id=SESSION_ID,
        company_id=COMPANY_ID,
        invitation_id=UUID("00000000-0000-7000-8000-000000000008"),
        applicant_id=UUID("00000000-0000-7000-8000-000000000006"),
        interview_strategy_id=UUID("00000000-0000-7000-8000-000000000009"),
        competency_model_version_id=UUID("00000000-0000-7000-8000-000000000010"),
        created_at=NOW,
    )
    previous_answer = InterviewTurn(
        turn_id=UUID("00000000-0000-7000-8000-000000000011"),
        company_id=COMPANY_ID,
        interview_session_id=SESSION_ID,
        sequence=2,
        speaker=TurnSpeaker.APPLICANT,
        status=TurnStatus.FINAL,
        text="이전 질문에는 장애 원인을 좁힌 과정을 답했습니다.",
        idempotency_key="answer-final-0001",
        finalized_at=NOW,
    )
    question = InterviewTurn(
        turn_id=QUESTION_ID,
        company_id=COMPANY_ID,
        interview_session_id=SESSION_ID,
        sequence=3,
        speaker=TurnSpeaker.INTERVIEWER,
        status=TurnStatus.FINAL,
        text="Google Cloud STT를 병렬로 사용한 이유를 설명해 주세요?",
        target_criterion_id=CRITERION_ID,
        idempotency_key="question-final-0001",
        model_config_version="model-v1",
        finalized_at=NOW,
    )
    source = QuestionSourceReference(
        source_reference_id=UUID("00000000-0000-7000-8000-000000000012"),
        company_id=COMPANY_ID,
        interview_session_id=SESSION_ID,
        question_turn_id=QUESTION_ID,
        source_id=SOURCE_ID,
        source_type="submission_chunk",
        locator={"material_type": "portfolio", "paragraph": 4},
        excerpt="Gemini Live 전사 누락을 보완하기 위해 Google Cloud STT를 병렬 처리했다.",
        relevance_score=0.92,
        ownership_confidence=0.9,
        retrieval_config_version="hybrid-v1",
        model_config_version="model-v1",
        created_at=NOW,
    )
    repository = Mock()
    repository.get_session.return_value = session
    repository.get_turn.return_value = question
    repository.list_final_turns.return_value = (previous_answer, question)
    repository.get_question_rationale.side_effect = LookupError
    repository.list_question_source_references.return_value = (source,)
    retrieval = Mock()
    model = DeterministicAIModel(
        {
            "answer": (
                "Gemini Live 전사에서 일부 사용자 자막이 누락되어 Google Cloud STT를 "
                "병렬로 사용했습니다. 두 결과를 비교해 부족한 후보만 보정했습니다."
            )
        }
    )
    generator = AutomatedAnswerGenerator(
        repository=repository,
        retrieval=retrieval,
        model=model,
    )

    generated = generator.generate(
        context(),
        session_id=SESSION_ID,
        question_turn_id=QUESTION_ID,
        retrieval_config_version="hybrid-v1",
        fallback_stage=InterviewStage.TECHNICAL,
    )

    assert generated.grounded is True
    assert generated.source_reference_count == 1
    assert "Google Cloud STT" in generated.text
    retrieval.retrieve.assert_not_called()
    prompt = model.calls[0][1]
    assert prompt["anthropic_version"] == ANTHROPIC_BEDROCK_VERSION
    payload = json.loads(prompt["messages"][0]["content"][0]["text"])
    assert payload["question"] == question.text
    assert payload["answer_profile"] == AutomatedAnswerProfile.STANDARD.value
    assert payload["provided_sources"][0]["excerpt"] == source.excerpt
    assert payload["recent_answers_for_repetition_avoidance"] == [previous_answer.text]

    entry_generated = generator.generate(
        context(),
        session_id=SESSION_ID,
        question_turn_id=QUESTION_ID,
        retrieval_config_version="hybrid-v1",
        fallback_stage=InterviewStage.TECHNICAL,
        answer_profile=AutomatedAnswerProfile.ENTRY_LOW,
    )

    entry_prompt = model.calls[1][1]
    entry_payload = json.loads(entry_prompt["messages"][0]["content"][0]["text"])
    assert entry_payload["answer_profile"] == AutomatedAnswerProfile.ENTRY_LOW.value
    assert "깊이와 구체성이" in str(entry_prompt["system"])
    assert "평가 가능한 내용" in str(entry_prompt["system"])
    assert "다른 대안과 결과 수치" in entry_generated.text

    generator.generate(
        context(),
        session_id=SESSION_ID,
        question_turn_id=QUESTION_ID,
        retrieval_config_version="hybrid-v1",
        fallback_stage=InterviewStage.TECHNICAL,
        answer_profile=AutomatedAnswerProfile.DEVELOPER_GUIDE,
    )

    guide_prompt = model.calls[2][1]
    guide_payload = json.loads(guide_prompt["messages"][0]["content"][0]["text"])
    assert guide_payload["answer_profile"] == AutomatedAnswerProfile.DEVELOPER_GUIDE.value
    assert guide_prompt["max_tokens"] == 320
    assert "짧은 2~3문장" in str(guide_prompt["system"])
    assert "어려운 전문 용어" in str(guide_prompt["system"])
