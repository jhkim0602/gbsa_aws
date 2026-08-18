"""Live interview HTTP and WebSocket protocol routes."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import FastAPI
from sqlalchemy.orm import Session

from interview_evidence.interview_engine.adapters.polly import SpeechSynthesisAdapter
from interview_evidence.interview_engine.adapters.recent_context import (
    InMemoryRecentContext,
    RecentContextPort,
)
from interview_evidence.interview_engine.adapters.retrieval_client import (
    RetrievalClient,
    SubmissionRetrieval,
)
from interview_evidence.interview_engine.api.applicant_routes import (
    create_applicant_interview_router,
)
from interview_evidence.interview_engine.api.live_handlers import LiveInterviewHandler
from interview_evidence.interview_engine.api.websocket import (
    ProtocolStreamHandler,
    create_interview_websocket_router,
)
from interview_evidence.interview_engine.application.authorization import (
    InterviewAuthorizationPort,
)
from interview_evidence.interview_engine.application.checkpoints import CheckpointService
from interview_evidence.interview_engine.application.context_builder import ContextBuilder
from interview_evidence.interview_engine.application.context_reconciliation import (
    ContextReconciler,
)
from interview_evidence.interview_engine.application.idempotency import (
    IdempotencyStore,
    InMemoryIdempotencyStore,
)
from interview_evidence.interview_engine.application.interview_plan import (
    InterviewPlanProvider,
)
from interview_evidence.interview_engine.application.interview_service import InterviewService
from interview_evidence.interview_engine.application.question_generator import QuestionGenerator
from interview_evidence.interview_engine.application.question_policy import QuestionPolicy
from interview_evidence.interview_engine.application.recording_service import (
    RecordingService,
    StorageRecordingVerifier,
    VerifiableObjectStorage,
)
from interview_evidence.interview_engine.application.recovery_service import RecoveryService
from interview_evidence.interview_engine.application.session_service import (
    SessionApplicationService,
)
from interview_evidence.interview_engine.domain.session import (
    InterviewSession,
    InterviewSessionState,
)
from interview_evidence.interview_engine.domain.turn import (
    InterviewTurn,
    QuestionRationale,
    QuestionSourceReference,
    RecordingChunk,
    RecordingUploadStatus,
    TurnSpeaker,
    TurnStatus,
)
from interview_evidence.interview_engine.repositories.postgres import (
    InMemoryInterviewRepository,
    InterviewRepository,
    SqlAlchemyInterviewRepository,
    TenantScopedInterviewNotFound,
)
from interview_evidence.main import create_app
from interview_evidence.shared.audit import AuditAppender, InMemoryAuditAppender
from interview_evidence.shared.aws_clients.ports import (
    AIModel,
    InMemoryObjectStorage,
    ObjectStorage,
    SpeechToText,
    TextEmbedder,
    TextToSpeech,
)
from interview_evidence.shared.ids import Clock, SystemClock
from interview_evidence.shared.messaging.outbox import InMemoryOutbox, Outbox
from interview_evidence.shared.security.principals import PrincipalProvider
from interview_evidence.shared.tenant import ActorType, TenantContext


@dataclass(frozen=True, slots=True)
class LaneCRuntime:
    app: FastAPI
    repository: InterviewRepository
    service: SessionApplicationService
    idempotency: IdempotencyStore
    hot_view: RecentContextPort
    audit: AuditAppender
    outbox: Outbox
    stream_handler: ProtocolStreamHandler


@dataclass(frozen=True, slots=True)
class LocalDemoAnswer:
    """One seeded question and its final answer, with the video range it occupies."""

    turn_id: UUID
    #: The Turn the question was spoken on. Lane D has to project the transcript against
    #: this id, not one derived from the answer, or the question rationale written here
    #: has nothing to attach to on the review timeline.
    question_turn_id: UUID
    question_text: str
    answer_text: str
    session_start_ms: int
    session_end_ms: int


@dataclass(frozen=True, slots=True)
class LocalDemoInterviewSession:
    interview_session_id: UUID
    answers: tuple[LocalDemoAnswer, ...]
    #: The chunk the applicant's recorder would have uploaded. Evidence cites this, so the
    #: caller has to put the same bytes here that it hashed to fill the two fields below.
    recording_object_key: str
    recording_duration_ms: int
    recording_byte_size: int
    recording_content_hash: str


#: One criterion asked three ways, the shape a junior interview actually takes: an opening
#: question and the follow-ups its answer earned. The answers are deliberately uneven so a
#: reviewer reading the seeded report sees scored and unscored axes side by side.
_DEMO_EXCHANGES: tuple[tuple[str, str, int], ...] = (
    (
        "운영 중인 서비스에서 장애를 직접 분석하고 복구한 경험을 설명해 주세요.",
        "결제 API 응답이 갑자기 느려진 적이 있습니다. 대시보드에서 p99 지연이 30초까지 "
        "올라간 걸 보고 먼저 데이터베이스 커넥션 풀을 확인했는데, 대기 중인 커넥션이 "
        "풀 크기만큼 쌓여 있었습니다. 풀 크기를 늘려서 급하게 막고, 이후에 원인이 된 "
        "쿼리를 찾아 인덱스를 추가했습니다.",
        20_000,
    ),
    (
        "풀 크기를 늘리는 것으로 먼저 막았다고 하셨는데, 그 판단의 근거는 무엇이었나요?",
        "당시에는 트래픽이 몰리는 시간대여서 우선 응답을 살리는 게 급했습니다. 풀을 "
        "늘리면 대기가 줄어들 거라고 봤고, 실제로 지연이 내려갔습니다. 다만 근본 원인은 "
        "아니라는 걸 알고 있었기 때문에 같은 날 쿼리 실행 계획을 다시 봤습니다.",
        70_000,
    ),
    (
        "추가한 인덱스가 다른 쿼리에 준 영향은 어떻게 확인하셨나요?",
        "쓰기 지연이 늘어날 수 있다는 건 알고 있었지만, 그 부분은 제가 직접 측정하지 "
        "못했습니다. 배포 후 전체 지표가 정상이었다는 것만 확인했습니다.",
        120_000,
    ),
)

#: The submitted material the seeded questions were drawn from, keyed so more than one
#: question can cite the same piece. Retrieval normally produces these from a real upload,
#: which a seed cannot, so they are written out as applicant-submitted text -- a resume
#: line and two code units. None of this is an answer, and the console keeps it in its own
#: section for exactly that reason.
_DEMO_QUESTION_SOURCES: dict[str, tuple[str, dict[str, object], str, float]] = {
    "resume-payment-role": (
        "submission_chunk",
        {"page_number": 2},
        "결제 시스템 백엔드를 담당하며 일 300만 건 트래픽 증가에 대응했습니다.",
        0.58,
    ),
    "pool-config": (
        "candidate_code_unit",
        {"path": "app/db/session.py", "symbol": "build_engine"},
        "pool_size=20, max_overflow=0 으로 커넥션 풀을 구성하는 함수입니다.",
        0.93,
    ),
    "payment-index-migration": (
        "candidate_code_unit",
        {"path": "migrations/0031_add_payments_created_at_index.sql", "symbol": "up"},
        "payments(created_at) 인덱스를 추가하는 마이그레이션입니다.",
        0.91,
    ),
}

#: Why each seeded question was asked, aligned with `_DEMO_EXCHANGES`. The opening question
#: comes from a gap in the submitted material; the two after it are follow-ups the previous
#: answer earned, which is the shape the live path produces. The resume line is cited twice
#: on purpose -- one piece of material can motivate several questions.
_DEMO_RATIONALES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "detail_missing",
        "이력서에 결제 시스템 담당 이력은 있으나 장애를 직접 분석하고 복구한 과정이 "
        "적혀 있지 않아, 그 경험이 실제로 있는지 확인합니다.",
        "personalized",
        ("resume-payment-role",),
    ),
    (
        "ownership_uncertain",
        "커넥션 풀 설정을 바꾼 코드가 제출물에 있으나 그 판단을 본인이 했는지 확인되지 "
        "않아, 임시 조치를 고른 근거를 직접 듣습니다.",
        "follow_up",
        ("resume-payment-role", "pool-config"),
    ),
    (
        "detail_missing",
        "인덱스 추가 마이그레이션은 제출되었지만 쓰기 경로 영향을 확인한 흔적이 없어, "
        "조치 이후의 검증 범위를 확인합니다.",
        "follow_up",
        ("payment-index-migration",),
    ),
)


def create_lane_c_runtime(
    *,
    principal_provider: PrincipalProvider,
    authorization: InterviewAuthorizationPort,
    repository: InterviewRepository | None = None,
    object_storage: ObjectStorage | None = None,
    audit: AuditAppender | None = None,
    clock: Clock | None = None,
    idempotency: IdempotencyStore | None = None,
    hot_view: RecentContextPort | None = None,
    outbox: Outbox | None = None,
    plan_provider: InterviewPlanProvider | None = None,
    retrieval_provider: SubmissionRetrieval | None = None,
    model: AIModel | None = None,
    text_embedder: TextEmbedder | None = None,
    speech_to_text: SpeechToText | None = None,
    text_to_speech: TextToSpeech | None = None,
) -> LaneCRuntime:
    active_repository = repository or InMemoryInterviewRepository()
    active_storage = object_storage or InMemoryObjectStorage()
    active_audit = audit or InMemoryAuditAppender()
    active_clock = clock or SystemClock()
    active_idempotency = idempotency or InMemoryIdempotencyStore()
    active_hot_view = hot_view or InMemoryRecentContext()
    active_outbox = outbox or InMemoryOutbox()
    checkpoints = CheckpointService(active_repository, active_outbox)
    reconciler = ContextReconciler(active_repository, active_hot_view)
    service = SessionApplicationService(
        repository=active_repository,
        authorization=authorization,
        idempotency=active_idempotency,
        checkpoints=checkpoints,
        reconciler=reconciler,
        # Without the repository, idempotency store and verifier a confirmed upload
        # raises instead of recording the chunk, which left every session with no
        # verified recording and therefore no timeline video and no report.
        recording=RecordingService(
            active_storage,
            repository=active_repository,
            idempotency=active_idempotency,
            verifier=StorageRecordingVerifier(cast(VerifiableObjectStorage, active_storage)),
        ),
        clock=active_clock,
    )
    stream_handler = ProtocolStreamHandler(session_service=service)
    live_dependencies = (
        plan_provider,
        retrieval_provider,
        model,
        speech_to_text,
        text_to_speech,
    )
    if any(dependency is not None for dependency in live_dependencies):
        if not all(dependency is not None for dependency in live_dependencies):
            raise ValueError("all live interview dependencies must be configured together")
        recovery = RecoveryService(
            repository=active_repository,
            idempotency=active_idempotency,
            checkpoints=checkpoints,
            reconciler=reconciler,
        )
        interview_service = InterviewService(
            repository=active_repository,
            idempotency=active_idempotency,
            recovery=recovery,
            checkpoints=checkpoints,
            context_builder=ContextBuilder(token_budget=2400),
            retrieval=RetrievalClient(
                cast(SubmissionRetrieval, retrieval_provider),
                embedder=text_embedder,
            ),
            generator=QuestionGenerator(cast(AIModel, model)),
            policy=QuestionPolicy(),
            speech=SpeechSynthesisAdapter(cast(TextToSpeech, text_to_speech)),
            outbox=active_outbox,
        )
        live_handler = LiveInterviewHandler(
            repository=active_repository,
            session_service=service,
            interview_service=interview_service,
            plan_provider=cast(InterviewPlanProvider, plan_provider),
            speech_to_text=cast(SpeechToText, speech_to_text),
            speech=SpeechSynthesisAdapter(cast(TextToSpeech, text_to_speech)),
            idempotency=active_idempotency,
            checkpoints=checkpoints,
            clock=active_clock,
        )
        stream_handler = ProtocolStreamHandler(
            session_service=service,
            start_handler=live_handler,
            answer_handler=live_handler,
            audio_handler=live_handler,
        )
    router = create_applicant_interview_router(
        principal_provider=principal_provider,
        service=service,
        audit=active_audit,
    )
    websocket_router = create_interview_websocket_router(
        principal_provider=principal_provider,
        handler=stream_handler,
    )
    return LaneCRuntime(
        app=create_app([router, websocket_router]),
        repository=active_repository,
        service=service,
        idempotency=active_idempotency,
        hot_view=active_hot_view,
        audit=active_audit,
        outbox=active_outbox,
        stream_handler=stream_handler,
    )


def create_lane_c_app(
    *,
    principal_provider: PrincipalProvider,
    authorization: InterviewAuthorizationPort,
    repository: InterviewRepository | None = None,
    object_storage: ObjectStorage | None = None,
    audit: AuditAppender | None = None,
    clock: Clock | None = None,
    idempotency: IdempotencyStore | None = None,
    hot_view: RecentContextPort | None = None,
    outbox: Outbox | None = None,
    plan_provider: InterviewPlanProvider | None = None,
    retrieval_provider: SubmissionRetrieval | None = None,
    model: AIModel | None = None,
    text_embedder: TextEmbedder | None = None,
    speech_to_text: SpeechToText | None = None,
    text_to_speech: TextToSpeech | None = None,
) -> FastAPI:
    return create_lane_c_runtime(
        principal_provider=principal_provider,
        authorization=authorization,
        repository=repository,
        object_storage=object_storage,
        audit=audit,
        clock=clock,
        idempotency=idempotency,
        hot_view=hot_view,
        outbox=outbox,
        plan_provider=plan_provider,
        retrieval_provider=retrieval_provider,
        model=model,
        text_embedder=text_embedder,
        speech_to_text=speech_to_text,
        text_to_speech=text_to_speech,
    ).app


def create_sql_repository(session: Session) -> InterviewRepository:
    return SqlAlchemyInterviewRepository(session)


def ensure_local_demo_interview_session(
    session: Session,
    *,
    company_id: UUID,
    company_user_id: UUID,
    invitation_id: UUID,
    applicant_id: UUID,
    competency_model_version_id: UUID,
    criterion_id: UUID,
    interview_strategy_id: UUID,
    recording: bytes,
    now: datetime,
) -> LocalDemoInterviewSession:
    """Seed one local-only finished interview session for the demo invitation.

    The live path reaches this state through the WebSocket protocol and a verified media
    upload, which a seed cannot replay. So this writes the same rows that path leaves
    behind -- a REVIEWABLE session, its question and answer Turns, the rationale and
    submitted-material references behind each question, and one verified recording chunk
    -- and returns the ranges Lane D needs to project them, which is why the answer ranges
    are returned rather than recomputed on the other side.

    ``recording`` is the chunk's bytes. The chunk row records their real length and digest
    so an upload of the same bytes passes ``verify_uploaded_object``; the caller owns the
    upload itself, because a lane helper writing to a bucket would put storage credentials
    behind a database seed.
    """
    context = TenantContext(
        company_id=company_id,
        actor_type=ActorType.COMPANY_USER,
        actor_id=company_user_id,
        request_id=uuid5(NAMESPACE_URL, f"local-interview-demo:{invitation_id}"),
        trace_id="local-interview-demo",
    )
    repository = SqlAlchemyInterviewRepository(session)
    session_id = uuid5(NAMESPACE_URL, f"local-interview-demo-session:{invitation_id}")
    answers = tuple(
        LocalDemoAnswer(
            turn_id=uuid5(NAMESPACE_URL, f"{session_id}:answer:{index}"),
            question_turn_id=uuid5(NAMESPACE_URL, f"{session_id}:question:{index}"),
            question_text=question,
            answer_text=answer,
            session_start_ms=start_ms,
            session_end_ms=start_ms + 40_000,
        )
        for index, (question, answer, start_ms) in enumerate(_DEMO_EXCHANGES, start=1)
    )
    # The layout `RecordingService` composes for a live upload: the namespace it builds
    # plus the object id the storage adapter appends. A seed with its own layout hides the
    # production key from every local run, so a change here is only found after deploying.
    chunk_object_key = (
        f"tenants/{company_id}/sessions/{session_id}/recording/chunks/{0:06d}/"
        f"{uuid5(NAMESPACE_URL, f'{session_id}:chunk-object:0')}"
    )
    demo = LocalDemoInterviewSession(
        interview_session_id=session_id,
        answers=answers,
        recording_object_key=chunk_object_key,
        recording_duration_ms=answers[-1].session_end_ms,
        recording_byte_size=len(recording),
        recording_content_hash=sha256(recording).hexdigest(),
    )

    try:
        repository.get_session(context, session_id)
        seeded = True
    except TenantScopedInterviewNotFound:
        seeded = False

    if not seeded:
        _save_local_demo_session(
            repository,
            context,
            session_id=session_id,
            company_id=company_id,
            invitation_id=invitation_id,
            applicant_id=applicant_id,
            competency_model_version_id=competency_model_version_id,
            criterion_id=criterion_id,
            interview_strategy_id=interview_strategy_id,
            demo=demo,
            now=now,
        )
    # Written on every run, not only the first. Question rationales were added after local
    # databases had already been seeded, and the guard above would leave those machines with
    # a review screen whose 질문 근거 자료 section is permanently empty. Every id here is
    # derived from the session, so repeating the write is a no-op.
    _save_local_demo_question_rationales(
        repository,
        context,
        session_id=session_id,
        company_id=company_id,
        applicant_id=applicant_id,
        competency_model_version_id=competency_model_version_id,
        criterion_id=criterion_id,
        answers=answers,
        now=now,
    )
    return demo


def _save_local_demo_session(
    repository: SqlAlchemyInterviewRepository,
    context: TenantContext,
    *,
    session_id: UUID,
    company_id: UUID,
    invitation_id: UUID,
    applicant_id: UUID,
    competency_model_version_id: UUID,
    criterion_id: UUID,
    interview_strategy_id: UUID,
    demo: LocalDemoInterviewSession,
    now: datetime,
) -> None:
    """Write the session, its Turns and its verified recording chunk."""
    answers = demo.answers
    repository.save_session(
        context,
        InterviewSession(
            interview_session_id=session_id,
            company_id=company_id,
            invitation_id=invitation_id,
            applicant_id=applicant_id,
            interview_strategy_id=interview_strategy_id,
            competency_model_version_id=competency_model_version_id,
            state=InterviewSessionState.REVIEWABLE,
            session_sequence=len(answers) * 2,
            row_version=len(answers) * 2 + 1,
            created_at=now - timedelta(hours=2),
            started_at=now - timedelta(hours=2),
            completed_at=now - timedelta(hours=1),
        ),
    )
    for index, answer in enumerate(answers, start=1):
        repository.save_turn(
            context,
            InterviewTurn(
                turn_id=answer.question_turn_id,
                company_id=company_id,
                interview_session_id=session_id,
                sequence=index * 2 - 1,
                speaker=TurnSpeaker.INTERVIEWER,
                status=TurnStatus.FINAL,
                text=answer.question_text,
                target_criterion_id=criterion_id,
                idempotency_key=f"local-demo-question-{index}",
                model_config_version="local-demo",
                finalized_at=(
                    now - timedelta(hours=2) + timedelta(milliseconds=answer.session_start_ms)
                ),
            ),
        )
        repository.save_turn(
            context,
            InterviewTurn(
                turn_id=answer.turn_id,
                company_id=company_id,
                interview_session_id=session_id,
                sequence=index * 2,
                speaker=TurnSpeaker.APPLICANT,
                status=TurnStatus.FINAL,
                text=answer.answer_text,
                idempotency_key=f"local-demo-answer-{index}",
                model_config_version="local-demo",
                finalized_at=(
                    now - timedelta(hours=2) + timedelta(milliseconds=answer.session_end_ms)
                ),
            ),
        )
    repository.save_recording_chunk(
        context,
        RecordingChunk(
            recording_chunk_id=uuid5(NAMESPACE_URL, f"{session_id}:chunk:0"),
            company_id=company_id,
            interview_session_id=session_id,
            sequence=0,
            object_key=demo.recording_object_key,
            # The digest and length of the bytes the caller uploads, not a stand-in. A
            # made-up pair makes `verify_uploaded_object` reject the very object the seed
            # just wrote, which is indistinguishable from a corrupted upload.
            content_hash=demo.recording_content_hash,
            byte_size=demo.recording_byte_size,
            session_start_ms=0,
            session_end_ms=demo.recording_duration_ms,
            upload_status=RecordingUploadStatus.VERIFIED,
            idempotency_key="local-demo-recording-0",
            created_at=now - timedelta(hours=1),
        ),
    )


def _save_local_demo_question_rationales(
    repository: SqlAlchemyInterviewRepository,
    context: TenantContext,
    *,
    session_id: UUID,
    company_id: UUID,
    applicant_id: UUID,
    competency_model_version_id: UUID,
    criterion_id: UUID,
    answers: tuple[LocalDemoAnswer, ...],
    now: datetime,
) -> None:
    """Write why each seeded question was asked, and the submitted material behind it.

    A reviewer reading a question on the review screen has to be able to see what in the
    applicant's own submission prompted it; without these rows the console can only show
    the question, which reads as if the AI made it up.
    """
    asked_at = now - timedelta(hours=2)
    for index, (answer, (target_type, objective, question_type, source_keys)) in enumerate(
        zip(answers, _DEMO_RATIONALES, strict=True), start=1
    ):
        references = tuple(
            QuestionSourceReference(
                # Keyed by the material, not the question, so the same submitted excerpt
                # cited twice stays one row per question with a stable id on re-runs.
                source_reference_id=uuid5(
                    NAMESPACE_URL, f"{session_id}:source-reference:{index}:{key}"
                ),
                company_id=company_id,
                interview_session_id=session_id,
                question_turn_id=answer.question_turn_id,
                source_id=uuid5(NAMESPACE_URL, f"local-interview-demo-source:{key}"),
                source_type=_DEMO_QUESTION_SOURCES[key][0],
                locator=_DEMO_QUESTION_SOURCES[key][1],
                excerpt=_DEMO_QUESTION_SOURCES[key][2],
                relevance_score=_DEMO_QUESTION_SOURCES[key][3],
                ownership_confidence=(
                    0.9 if _DEMO_QUESTION_SOURCES[key][0] == "candidate_code_unit" else 0.5
                ),
                retrieval_config_version="local-demo",
                model_config_version="local-demo",
                created_at=asked_at,
            )
            for key in source_keys
        )
        repository.save_question_source_references(context, references)
        repository.save_question_rationale(
            context,
            QuestionRationale(
                question_rationale_id=uuid5(NAMESPACE_URL, f"{session_id}:rationale:{index}"),
                company_id=company_id,
                interview_session_id=session_id,
                question_turn_id=answer.question_turn_id,
                applicant_id=applicant_id,
                competency_model_version_id=competency_model_version_id,
                criterion_id=criterion_id,
                verification_target_id=uuid5(
                    NAMESPACE_URL, f"{session_id}:verification-target:{index}"
                ),
                verification_target_type=target_type,
                objective=objective,
                question_type=question_type,
                retrieval_version="local-demo",
                generation_version="local-demo",
                policy_result="accepted",
                source_reference_ids=tuple(
                    reference.source_reference_id for reference in references
                ),
                created_at=asked_at,
            ),
        )
