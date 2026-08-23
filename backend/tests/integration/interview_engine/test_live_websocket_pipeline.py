from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from interview_evidence.interview_engine.adapters.polly import SpeechSynthesisAdapter
from interview_evidence.interview_engine.adapters.recent_context import InMemoryRecentContext
from interview_evidence.interview_engine.adapters.retrieval_client import RetrievalClient
from interview_evidence.interview_engine.api.live_handlers import LiveInterviewHandler
from interview_evidence.interview_engine.api.websocket import (
    AudioChunkMetadata,
    ProtocolStreamHandler,
    WebSocketEnvelope,
)
from interview_evidence.interview_engine.application.authorization import (
    FakeInterviewAuthorization,
    InterviewAuthorization,
)
from interview_evidence.interview_engine.application.checkpoints import CheckpointService
from interview_evidence.interview_engine.application.context_builder import ContextBuilder
from interview_evidence.interview_engine.application.context_reconciliation import (
    ContextReconciler,
)
from interview_evidence.interview_engine.application.idempotency import InMemoryIdempotencyStore
from interview_evidence.interview_engine.application.interview_plan import (
    FIXED_INTERVIEW_DURATION_SECONDS,
    InterviewPlan,
    VerificationTargetPlan,
)
from interview_evidence.interview_engine.application.interview_service import InterviewService
from interview_evidence.interview_engine.application.question_generator import QuestionGenerator
from interview_evidence.interview_engine.application.question_policy import QuestionPolicy
from interview_evidence.interview_engine.application.recording_service import RecordingService
from interview_evidence.interview_engine.application.recovery_service import RecoveryService
from interview_evidence.interview_engine.application.session_service import (
    SessionApplicationService,
)
from interview_evidence.interview_engine.domain.session import (
    InterviewSession,
    InterviewSessionState,
)
from interview_evidence.interview_engine.domain.turn import (
    TurnSpeaker,
    VerificationProgressState,
)
from interview_evidence.interview_engine.repositories.postgres import (
    InMemoryInterviewRepository,
)
from interview_evidence.shared.aws_clients.ports import (
    DeterministicAIModel,
    DeterministicSpeechToText,
    DeterministicTextToSpeech,
    InMemoryObjectStorage,
)
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.messaging.outbox import InMemoryOutbox
from interview_evidence.shared.security.principals import ApplicantPrincipal
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 15, 13, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000003")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000004")
STRATEGY_ID = UUID("00000000-0000-7000-8000-000000000005")
MODEL_VERSION_ID = UUID("00000000-0000-7000-8000-000000000006")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000007")
ANSWER_TURN_ID = UUID("00000000-0000-7000-8000-000000000008")
SECOND_ANSWER_TURN_ID = UUID("00000000-0000-7000-8000-000000000012")
THIRD_ANSWER_TURN_ID = UUID("00000000-0000-7000-8000-000000000013")


class EmptyRetrieval:
    def retrieve_context(self, *args: object, **kwargs: object) -> tuple[()]:
        del args, kwargs
        return ()


class FixedPlanProvider:
    def get_interview_plan(
        self,
        context: TenantContext,
        *,
        strategy_id: UUID,
        competency_model_version_id: UUID,
    ) -> InterviewPlan:
        context.assert_company(COMPANY_ID)
        assert strategy_id == STRATEGY_ID
        assert competency_model_version_id == MODEL_VERSION_ID
        return InterviewPlan(
            criterion_ids=(CRITERION_ID,),
            initial_question="최근 해결한 기술 문제를 설명해 주세요?",
            prohibited_topics=("가족",),
            fallback_question="판단 과정을 구체적으로 설명해 주세요?",
            remaining_time_seconds=FIXED_INTERVIEW_DURATION_SECONDS,
            model_config_version="question-model-v1",
            retrieval_config_version="hybrid-v1",
            voice_id="Seoyeon",
            verification_targets=(
                VerificationTargetPlan(
                    verification_target_id=UUID("00000000-0000-7000-8000-000000000011"),
                    criterion_id=CRITERION_ID,
                    criterion_text="운영 장애에서 원인 분석과 복구 역할을 확인한다.",
                    target_type="detail_missing",
                    objective="자료에서 확인되지 않은 원인 분석과 직접 복구 역할을 확인한다.",
                    missing_dimensions=("원인 분석", "직접 복구"),
                    follow_up_directions=("본인이 직접 수행한 복구 작업",),
                    max_follow_ups=1,
                    common_question="최근 해결한 기술 문제를 설명해 주세요?",
                ),
            ),
        )


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.APPLICANT,
        actor_id=APPLICANT_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000009"),
        trace_id="trace-live-websocket",
    )


def principal() -> ApplicantPrincipal:
    return ApplicantPrincipal(
        company_id=COMPANY_ID,
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        session_id=SESSION_ID,
    )


def envelope(
    message_type: str,
    *,
    sequence: int,
    key: str,
    payload: Mapping[str, object] | None = None,
) -> WebSocketEnvelope:
    return WebSocketEnvelope(
        protocol_version="1.0",
        message_type=message_type,
        session_id=SESSION_ID,
        sequence=sequence,
        idempotency_key=key,
        correlation_id=UUID("00000000-0000-7000-8000-000000000010"),
        sent_at=NOW,
        payload=dict(payload or {}),
    )


def test_real_stream_handler_creates_initial_and_follow_up_questions() -> None:
    repository = InMemoryInterviewRepository()
    repository.save_session(
        context(),
        InterviewSession(
            interview_session_id=SESSION_ID,
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            interview_strategy_id=STRATEGY_ID,
            competency_model_version_id=MODEL_VERSION_ID,
            created_at=NOW,
        ),
    )
    idempotency = InMemoryIdempotencyStore()
    outbox = InMemoryOutbox()
    checkpoints = CheckpointService(repository, outbox)
    reconciler = ContextReconciler(repository, InMemoryRecentContext())
    recovery = RecoveryService(
        repository=repository,
        idempotency=idempotency,
        checkpoints=checkpoints,
        reconciler=reconciler,
    )
    session_service = SessionApplicationService(
        repository=repository,
        authorization=FakeInterviewAuthorization(
            InterviewAuthorization(
                company_id=COMPANY_ID,
                invitation_id=INVITATION_ID,
                applicant_id=APPLICANT_ID,
                strategy_id=STRATEGY_ID,
                competency_model_version_id=MODEL_VERSION_ID,
                partial_analysis=False,
            )
        ),
        idempotency=idempotency,
        checkpoints=checkpoints,
        reconciler=reconciler,
        recording=RecordingService(InMemoryObjectStorage()),
        clock=FrozenClock(NOW),
    )
    interview_service = InterviewService(
        repository=repository,
        idempotency=idempotency,
        recovery=recovery,
        checkpoints=checkpoints,
        context_builder=ContextBuilder(token_budget=600),
        retrieval=RetrievalClient(EmptyRetrieval()),
        generator=QuestionGenerator(
            DeterministicAIModel(
                {
                    "text": "선택한 해결책의 트레이드오프는 무엇이었나요?",
                    "target_criterion_id": str(CRITERION_ID),
                    "source_reference_ids": [],
                }
            )
        ),
        policy=QuestionPolicy(),
        speech=SpeechSynthesisAdapter(
            DeterministicTextToSpeech(
                {
                    "audio_url": None,
                    "audio_expires_at": None,
                    "speech_marks_url": None,
                }
            )
        ),
        outbox=outbox,
    )
    live = LiveInterviewHandler(
        repository=repository,
        session_service=session_service,
        interview_service=interview_service,
        plan_provider=FixedPlanProvider(),
        speech_to_text=DeterministicSpeechToText(
            {"text": "캐시 무효화 전략을 변경했습니다.", "confidence": 0.97}
        ),
        speech=SpeechSynthesisAdapter(DeterministicTextToSpeech({})),
        idempotency=idempotency,
        checkpoints=checkpoints,
        clock=FrozenClock(NOW),
    )
    protocol = ProtocolStreamHandler(
        session_service=session_service,
        start_handler=live,
        answer_handler=live,
        audio_handler=live,
    )

    initial = protocol.handle(
        context(),
        principal(),
        envelope("session.start", sequence=0, key="session-start-0001"),
    )
    assert initial.message_type == "question.ready"
    assert initial.payload["text"] == (
        "안녕하세요. 오늘은 기술, 프로젝트, 협업 경험을 중심으로 진행하겠습니다. "
        "먼저 간단한 자기소개와 지원 직무와 관련해 가장 자신 있는 경험을 말씀해 주세요?"
    )
    assert (
        repository.get_session(context(), SESSION_ID).state is InterviewSessionState.AWAITING_ANSWER
    )

    audio = b"\x01\x00\x02\x00"
    transcript = protocol.handle_audio(
        context(),
        principal(),
        envelope("audio.chunk.begin", sequence=initial.sequence, key="audio-chunk-0001"),
        AudioChunkMetadata(
            answer_turn_id=ANSWER_TURN_ID,
            chunk_sequence=1,
            codec="pcm_s16le",
            sample_rate_hz=16000,
            channel_count=1,
            byte_length=len(audio),
            sha256=sha256(audio).hexdigest(),
        ),
        audio,
    )
    assert transcript[0].message_type == "transcript.final"

    follow_up = protocol.handle(
        context(),
        principal(),
        envelope(
            "answer.complete",
            sequence=initial.sequence,
            key="answer-complete-0001",
            payload={
                "answer_turn_id": str(ANSWER_TURN_ID),
                "last_recording_chunk_sequence": 0,
            },
        ),
    )
    duplicate = protocol.handle(
        context(),
        principal(),
        envelope(
            "answer.complete",
            sequence=initial.sequence,
            key="answer-complete-0001",
            payload={
                "answer_turn_id": str(ANSWER_TURN_ID),
                "last_recording_chunk_sequence": 0,
            },
        ),
    )

    assert duplicate == follow_up
    assert follow_up.message_type == "question.ready"
    assert follow_up.payload["text"] == "선택한 해결책의 트레이드오프는 무엇이었나요?"
    assert (
        repository.get_session(context(), SESSION_ID).state is InterviewSessionState.AWAITING_ANSWER
    )
    progress = repository.list_verification_progress(context(), SESSION_ID)
    assert len(progress) == 1
    assert progress[0].state is VerificationProgressState.PENDING
    assert progress[0].follow_up_count == 0
    rationales = repository.list_question_rationales(context(), SESSION_ID)
    assert [rationale.question_type for rationale in rationales] == ["personalized"]
    assert rationales[0].objective.startswith("자료에서 확인되지 않은")
    final_turns = repository.list_final_turns(context(), SESSION_ID)
    assert [turn.speaker for turn in final_turns] == [
        TurnSpeaker.INTERVIEWER,
        TurnSpeaker.APPLICANT,
        TurnSpeaker.INTERVIEWER,
    ]

    second_transcript = protocol.handle_audio(
        context(),
        principal(),
        envelope(
            "audio.chunk.begin",
            sequence=follow_up.sequence,
            key="audio-chunk-0002",
        ),
        AudioChunkMetadata(
            answer_turn_id=SECOND_ANSWER_TURN_ID,
            chunk_sequence=2,
            codec="pcm_s16le",
            sample_rate_hz=16000,
            channel_count=1,
            byte_length=len(audio),
            sha256=sha256(audio).hexdigest(),
        ),
        audio,
    )
    assert second_transcript[0].message_type == "transcript.final"

    second_question = protocol.handle(
        context(),
        principal(),
        envelope(
            "answer.complete",
            sequence=follow_up.sequence,
            key="answer-complete-0002",
            payload={
                "answer_turn_id": str(SECOND_ANSWER_TURN_ID),
                "last_recording_chunk_sequence": 0,
            },
        ),
    )

    assert second_question.message_type == "question.ready"
    progress = repository.list_verification_progress(context(), SESSION_ID)
    assert progress[0].state is VerificationProgressState.IN_PROGRESS
    assert progress[0].follow_up_count == 1
    rationales = repository.list_question_rationales(context(), SESSION_ID)
    assert [rationale.question_type for rationale in rationales] == [
        "personalized",
        "follow_up",
    ]

    third_transcript = protocol.handle_audio(
        context(),
        principal(),
        envelope(
            "audio.chunk.begin",
            sequence=second_question.sequence,
            key="audio-chunk-0003",
        ),
        AudioChunkMetadata(
            answer_turn_id=THIRD_ANSWER_TURN_ID,
            chunk_sequence=3,
            codec="pcm_s16le",
            sample_rate_hz=16000,
            channel_count=1,
            byte_length=len(audio),
            sha256=sha256(audio).hexdigest(),
        ),
        audio,
    )
    assert third_transcript[0].message_type == "transcript.final"

    completed = protocol.handle(
        context(),
        principal(),
        envelope(
            "answer.complete",
            sequence=second_question.sequence,
            key="answer-complete-0003",
            payload={
                "answer_turn_id": str(THIRD_ANSWER_TURN_ID),
                "last_recording_chunk_sequence": 0,
            },
        ),
    )

    assert completed.message_type == "session.completed"
    assert repository.get_session(context(), SESSION_ID).state is InterviewSessionState.COMPLETED
    assert (
        repository.list_verification_progress(
            context(),
            SESSION_ID,
        )[0].state
        is VerificationProgressState.COMPLETED
    )
    completion_events = [
        event for event in outbox.pending() if event.event_type == "interview.completed"
    ]
    assert len(completion_events) == 1
    assert completion_events[0].payload["last_turn_id"] == str(THIRD_ANSWER_TURN_ID)
