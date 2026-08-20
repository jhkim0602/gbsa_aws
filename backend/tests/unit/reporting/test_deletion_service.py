from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from interview_evidence.reporting.application.deletion_service import (
    DeletionService,
    DeletionTargetSpec,
)
from interview_evidence.reporting.domain.deletion import DeletionManifest, DeletionRequest
from interview_evidence.reporting.repositories.postgres import ReportingRepository
from interview_evidence.shared.messaging.outbox import Outbox, OutboxEvent
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 20, 15, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000002")


class RecordingDeletionRepository:
    def __init__(self) -> None:
        self.saved: tuple[DeletionRequest, DeletionManifest] | None = None

    def save_deletion(
        self,
        context: TenantContext,
        request: DeletionRequest,
        manifest: DeletionManifest,
    ) -> DeletionManifest:
        context.assert_company(request.company_id)
        self.saved = (request, manifest)
        return manifest

    def get_deletion(
        self,
        context: TenantContext,
        request_id: UUID,
    ) -> tuple[DeletionRequest, DeletionManifest]:
        assert self.saved is not None
        context.assert_company(self.saved[0].company_id)
        assert self.saved[0].deletion_request_id == request_id
        return self.saved

    def update_deletion_manifest(
        self,
        context: TenantContext,
        request: DeletionRequest,
        manifest: DeletionManifest,
    ) -> DeletionManifest:
        context.assert_company(request.company_id)
        self.saved = (request, manifest)
        return manifest


class RecordingOutbox:
    def __init__(self) -> None:
        self.events: list[OutboxEvent] = []

    def append(self, event: OutboxEvent) -> OutboxEvent:
        self.events.append(event)
        return event


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.COMPANY_USER,
        actor_id=UUID("00000000-0000-7000-8000-000000000003"),
        request_id=UUID("00000000-0000-7000-8000-000000000004"),
        trace_id="trace-applicant-deletion",
    )


def test_deletion_request_publishes_worker_event() -> None:
    repository = RecordingDeletionRepository()
    outbox = RecordingOutbox()
    service = DeletionService(
        cast(ReportingRepository, repository),
        outbox=cast(Outbox, outbox),
    )

    request, manifest = service.request(
        context(),
        scope_type="invitation",
        scope_id=INVITATION_ID,
        reason="company_user_requested_applicant_deletion",
        policy_snapshot={"retention_days": 180},
        occurred_at=NOW,
    )

    assert repository.saved == (request, manifest)
    event = outbox.events[0]
    assert event.event_type == "deletion.requested"
    assert event.aggregate_id == request.deletion_request_id
    assert event.payload == {"deletion_request_id": str(request.deletion_request_id)}


def test_deletion_executes_child_targets_before_parent_rows() -> None:
    repository = RecordingDeletionRepository()
    executed: list[str] = []

    def execute_target(_context: TenantContext, target: object) -> bool:
        executed.append(cast(DeletionTargetSpec, target).target_type)
        return True

    service = DeletionService(
        cast(ReportingRepository, repository),
        enumerators=(
            lambda _context, _scope_type, _scope_id: (
                DeletionTargetSpec("B", "aurora", "submission", str(INVITATION_ID)),
                DeletionTargetSpec(
                    "B",
                    "aurora",
                    "submission_analysis",
                    str(INVITATION_ID),
                ),
                DeletionTargetSpec(
                    "B",
                    "aurora",
                    "submission_chunk",
                    str(INVITATION_ID),
                ),
            ),
        ),
        executors={"B": execute_target},
    )
    request, _ = service.request(
        context(),
        scope_type="invitation",
        scope_id=INVITATION_ID,
        reason="company_user_requested_applicant_deletion",
        policy_snapshot={"retention_days": 180},
        occurred_at=NOW,
    )

    service.execute(
        context(),
        request_id=request.deletion_request_id,
        occurred_at=NOW,
    )

    assert executed == ["submission_chunk", "submission_analysis", "submission"]
