"""Live interview HTTP and WebSocket protocol routes."""

from dataclasses import dataclass

from fastapi import FastAPI

from interview_evidence.interview_engine.adapters.recent_context import InMemoryRecentContext
from interview_evidence.interview_engine.api.applicant_routes import (
    create_applicant_interview_router,
)
from interview_evidence.interview_engine.api.websocket import (
    ProtocolStreamHandler,
    create_interview_websocket_router,
)
from interview_evidence.interview_engine.application.authorization import (
    InterviewAuthorizationPort,
)
from interview_evidence.interview_engine.application.checkpoints import CheckpointService
from interview_evidence.interview_engine.application.context_reconciliation import (
    ContextReconciler,
)
from interview_evidence.interview_engine.application.idempotency import InMemoryIdempotencyStore
from interview_evidence.interview_engine.application.recording_service import RecordingService
from interview_evidence.interview_engine.application.session_service import (
    SessionApplicationService,
)
from interview_evidence.interview_engine.repositories.postgres import (
    InMemoryInterviewRepository,
    InterviewRepository,
)
from interview_evidence.main import create_app
from interview_evidence.shared.audit import AuditAppender, InMemoryAuditAppender
from interview_evidence.shared.aws_clients.ports import InMemoryObjectStorage, ObjectStorage
from interview_evidence.shared.ids import Clock, SystemClock
from interview_evidence.shared.messaging.outbox import InMemoryOutbox
from interview_evidence.shared.security.principals import PrincipalProvider


@dataclass(frozen=True, slots=True)
class LaneCRuntime:
    app: FastAPI
    repository: InterviewRepository
    service: SessionApplicationService
    idempotency: InMemoryIdempotencyStore
    hot_view: InMemoryRecentContext
    audit: AuditAppender
    outbox: InMemoryOutbox


def create_lane_c_runtime(
    *,
    principal_provider: PrincipalProvider,
    authorization: InterviewAuthorizationPort,
    repository: InterviewRepository | None = None,
    object_storage: ObjectStorage | None = None,
    audit: AuditAppender | None = None,
    clock: Clock | None = None,
) -> LaneCRuntime:
    active_repository = repository or InMemoryInterviewRepository()
    active_storage = object_storage or InMemoryObjectStorage()
    active_audit = audit or InMemoryAuditAppender()
    active_clock = clock or SystemClock()
    idempotency = InMemoryIdempotencyStore()
    hot_view = InMemoryRecentContext()
    outbox = InMemoryOutbox()
    checkpoints = CheckpointService(active_repository, outbox)
    reconciler = ContextReconciler(active_repository, hot_view)
    service = SessionApplicationService(
        repository=active_repository,
        authorization=authorization,
        idempotency=idempotency,
        checkpoints=checkpoints,
        reconciler=reconciler,
        recording=RecordingService(active_storage),
        clock=active_clock,
    )
    router = create_applicant_interview_router(
        principal_provider=principal_provider,
        service=service,
        audit=active_audit,
    )
    websocket_router = create_interview_websocket_router(
        principal_provider=principal_provider,
        handler=ProtocolStreamHandler(session_service=service),
    )
    return LaneCRuntime(
        app=create_app([router, websocket_router]),
        repository=active_repository,
        service=service,
        idempotency=idempotency,
        hot_view=hot_view,
        audit=active_audit,
        outbox=outbox,
    )


def create_lane_c_app(
    *,
    principal_provider: PrincipalProvider,
    authorization: InterviewAuthorizationPort,
    repository: InterviewRepository | None = None,
    object_storage: ObjectStorage | None = None,
    audit: AuditAppender | None = None,
    clock: Clock | None = None,
) -> FastAPI:
    return create_lane_c_runtime(
        principal_provider=principal_provider,
        authorization=authorization,
        repository=repository,
        object_storage=object_storage,
        audit=audit,
        clock=clock,
    ).app
