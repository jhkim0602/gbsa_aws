from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from interview_evidence.interview_engine.adapters.polly import SpeechSynthesisAdapter
from interview_evidence.interview_engine.adapters.recent_context import InMemoryRecentContext
from interview_evidence.interview_engine.adapters.retrieval_client import RetrievalClient
from interview_evidence.interview_engine.application.checkpoints import CheckpointService
from interview_evidence.interview_engine.application.context_builder import ContextBuilder
from interview_evidence.interview_engine.application.context_reconciliation import (
    ContextReconciler,
)
from interview_evidence.interview_engine.application.idempotency import InMemoryIdempotencyStore
from interview_evidence.interview_engine.application.interview_service import InterviewService
from interview_evidence.interview_engine.application.question_generator import QuestionGenerator
from interview_evidence.interview_engine.application.question_policy import QuestionPolicy
from interview_evidence.interview_engine.application.recovery_service import RecoveryService
from interview_evidence.interview_engine.domain.session import (
    InterviewSession,
    InterviewSessionState,
)
from interview_evidence.interview_engine.domain.turn import TurnSpeaker
from interview_evidence.interview_engine.repositories.postgres import (
    InMemoryInterviewRepository,
)
from interview_evidence.shared.aws_clients.ports import (
    DeterministicAIModel,
    DeterministicTextToSpeech,
)
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000003")
SOURCE_ID = UUID("00000000-0000-7000-8000-000000000004")
ANSWER_TURN_ID = UUID("00000000-0000-7000-8000-000000000005")


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.APPLICANT,
        actor_id=UUID("00000000-0000-7000-8000-000000000006"),
        request_id=UUID("00000000-0000-7000-8000-000000000007"),
        trace_id="trace-lane-c-orchestration",
    )


@dataclass(frozen=True, slots=True)
class RetrievalRecord:
    source_id: UUID
    score: float
    locator: dict[str, object]
    ownership_confidence: float


class ReadyRetrieval:
    def retrieve_context(
        self,
        _context: TenantContext,
        *,
        applicant_id: UUID,
        query: str,
        query_vector: tuple[float, ...],
        criterion_id: UUID,
        config_version: str,
        limit: int,
        exact_symbol: str | None = None,
    ) -> tuple[RetrievalRecord, ...]:
        del applicant_id, query, query_vector, criterion_id, config_version, limit, exact_symbol
        return (
            RetrievalRecord(
                source_id=SOURCE_ID,
                score=0.91,
                locator={"page_number": 2, "section": "프로젝트 경험"},
                ownership_confidence=1.0,
            ),
        )


class SafeModel(DeterministicAIModel):
    def generate(
        self,
        context: TenantContext,
        model_input: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        return super().generate(context, model_input)


def interview_session() -> InterviewSession:
    return InterviewSession(
        interview_session_id=SESSION_ID,
        company_id=COMPANY_ID,
        invitation_id=UUID("00000000-0000-7000-8000-000000000008"),
        applicant_id=context().actor_id,
        interview_strategy_id=UUID("00000000-0000-7000-8000-000000000009"),
        competency_model_version_id=UUID("00000000-0000-7000-8000-000000000010"),
        state=InterviewSessionState.AWAITING_ANSWER,
        session_sequence=3,
        created_at=NOW,
        started_at=NOW,
    )


def test_answer_pipeline_is_idempotent_and_stores_question_sources() -> None:
    repository = InMemoryInterviewRepository()
    repository.save_session(context(), interview_session())
    idempotency = InMemoryIdempotencyStore()
    checkpoints = CheckpointService(repository)
    recovery = RecoveryService(
        repository=repository,
        idempotency=idempotency,
        checkpoints=checkpoints,
        reconciler=ContextReconciler(repository, InMemoryRecentContext()),
    )
    service = InterviewService(
        repository=repository,
        idempotency=idempotency,
        recovery=recovery,
        checkpoints=checkpoints,
        context_builder=ContextBuilder(token_budget=600),
        retrieval=RetrievalClient(ReadyRetrieval()),
        generator=QuestionGenerator(
            SafeModel(
                {
                    "text": "해당 장애의 원인을 좁힌 순서를 설명해 주세요?",
                    "target_criterion_id": str(CRITERION_ID),
                    "source_reference_ids": [str(SOURCE_ID)],
                }
            )
        ),
        policy=QuestionPolicy(),
        speech=SpeechSynthesisAdapter(
            DeterministicTextToSpeech(
                {
                    "audio_url": "https://signed.invalid/question.mp3",
                    "audio_expires_at": "2026-08-15T09:05:00Z",
                    "speech_marks_url": "https://signed.invalid/question.json",
                }
            )
        ),
    )

    first = service.finalize_answer_and_generate(
        context(),
        session_id=SESSION_ID,
        expected_sequence=3,
        answer_turn_id=ANSWER_TURN_ID,
        answer_text="로그와 지표를 비교해 장애 범위를 좁혔습니다.",
        last_recording_chunk_sequence=2,
        idempotency_key="answer-pipeline-0001",
        target_criterion_id=CRITERION_ID,
        allowed_criterion_ids=frozenset({CRITERION_ID}),
        prohibited_topics=("가족",),
        previous_questions=(),
        fallback_question="문제를 해결한 판단 과정을 설명해 주세요?",
        remaining_criterion_ids=(CRITERION_ID,),
        remaining_time_seconds=300,
        query_vector=(0.1, 0.2),
        model_config_version="question-model-v1",
        retrieval_config_version="hybrid-v1",
        voice_id="Seoyeon",
        occurred_at=NOW,
    )
    duplicate = service.finalize_answer_and_generate(
        context(),
        session_id=SESSION_ID,
        expected_sequence=3,
        answer_turn_id=ANSWER_TURN_ID,
        answer_text="로그와 지표를 비교해 장애 범위를 좁혔습니다.",
        last_recording_chunk_sequence=2,
        idempotency_key="answer-pipeline-0001",
        target_criterion_id=CRITERION_ID,
        allowed_criterion_ids=frozenset({CRITERION_ID}),
        prohibited_topics=("가족",),
        previous_questions=(),
        fallback_question="문제를 해결한 판단 과정을 설명해 주세요?",
        remaining_criterion_ids=(CRITERION_ID,),
        remaining_time_seconds=300,
        query_vector=(0.1, 0.2),
        model_config_version="question-model-v1",
        retrieval_config_version="hybrid-v1",
        voice_id="Seoyeon",
        occurred_at=NOW,
    )

    assert duplicate == first
    turns = repository.list_final_turns(context(), SESSION_ID)
    assert len(turns) == 2
    assert turns[0].speaker is TurnSpeaker.APPLICANT
    assert turns[1].speaker is TurnSpeaker.INTERVIEWER
    references = repository.list_question_source_references(
        context(),
        question_turn_id=turns[1].turn_id,
    )
    assert len(references) == 1
    assert references[0].source_id == SOURCE_ID
    assert references[0].retrieval_config_version == "hybrid-v1"
    assert references[0].model_config_version == "question-model-v1"
    assert first.speech.text_only is False
    assert (
        repository.get_session(context(), SESSION_ID).state
        is InterviewSessionState.AWAITING_ANSWER
    )
