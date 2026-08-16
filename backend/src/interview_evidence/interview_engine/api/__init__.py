"""Live interview HTTP and WebSocket protocol routes."""

from dataclasses import dataclass
from typing import cast

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
from interview_evidence.interview_engine.application.recording_service import RecordingService
from interview_evidence.interview_engine.application.recovery_service import RecoveryService
from interview_evidence.interview_engine.application.session_service import (
    SessionApplicationService,
)
from interview_evidence.interview_engine.repositories.postgres import (
    InMemoryInterviewRepository,
    InterviewRepository,
    SqlAlchemyInterviewRepository,
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
        recording=RecordingService(active_storage),
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
