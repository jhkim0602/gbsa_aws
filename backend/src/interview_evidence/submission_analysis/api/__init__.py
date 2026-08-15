from dataclasses import dataclass

from fastapi import FastAPI

from interview_evidence.main import create_app
from interview_evidence.shared.audit import AuditAppender, InMemoryAuditAppender
from interview_evidence.shared.aws_clients.ports import (
    InMemoryObjectStorage,
    ObjectStorage,
)
from interview_evidence.shared.ids import Clock, SystemClock
from interview_evidence.shared.messaging.outbox import InMemoryOutbox
from interview_evidence.shared.security.principals import PrincipalProvider
from interview_evidence.submission_analysis.adapters.object_storage import (
    ScopedSubmissionStorage,
)
from interview_evidence.submission_analysis.api.applicant_routes import (
    create_applicant_submission_router,
)
from interview_evidence.submission_analysis.application.authorization import (
    SubmissionAuthorizationPort,
)
from interview_evidence.submission_analysis.application.submission_service import (
    SubmissionService,
)
from interview_evidence.submission_analysis.application.submission_validator import (
    SubmissionValidator,
)
from interview_evidence.submission_analysis.repositories.postgres import (
    InMemorySubmissionRepository,
    SubmissionRepository,
)


@dataclass(frozen=True, slots=True)
class LaneBRuntime:
    app: FastAPI
    repository: SubmissionRepository
    storage: ScopedSubmissionStorage
    service: SubmissionService
    outbox: InMemoryOutbox
    audit: AuditAppender


def create_lane_b_runtime(
    *,
    principal_provider: PrincipalProvider,
    authorization: SubmissionAuthorizationPort,
    repository: SubmissionRepository | None = None,
    object_storage: ObjectStorage | None = None,
    audit: AuditAppender | None = None,
    clock: Clock | None = None,
    outbox: InMemoryOutbox | None = None,
) -> LaneBRuntime:
    active_repository = repository or InMemorySubmissionRepository()
    active_storage_port = object_storage or InMemoryObjectStorage()
    active_audit = audit or InMemoryAuditAppender()
    active_clock = clock or SystemClock()
    active_outbox = outbox or InMemoryOutbox()
    storage = ScopedSubmissionStorage(
        active_storage_port,
        clock=active_clock,
    )
    service = SubmissionService(
        active_repository,
        storage,
        SubmissionValidator(),
        active_outbox,
        active_clock,
    )
    router = create_applicant_submission_router(
        principal_provider=principal_provider,
        authorization=authorization,
        service=service,
        audit=active_audit,
    )
    return LaneBRuntime(
        app=create_app([router]),
        repository=active_repository,
        storage=storage,
        service=service,
        outbox=active_outbox,
        audit=active_audit,
    )


def create_lane_b_app(
    *,
    principal_provider: PrincipalProvider,
    authorization: SubmissionAuthorizationPort,
    repository: SubmissionRepository | None = None,
    object_storage: ObjectStorage | None = None,
    audit: AuditAppender | None = None,
    clock: Clock | None = None,
    outbox: InMemoryOutbox | None = None,
) -> FastAPI:
    return create_lane_b_runtime(
        principal_provider=principal_provider,
        authorization=authorization,
        repository=repository,
        object_storage=object_storage,
        audit=audit,
        clock=clock,
        outbox=outbox,
    ).app
