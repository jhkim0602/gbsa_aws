from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from interview_evidence.reporting.application.deletion_service import (
    DeletionService,
    DeletionTargetSpec,
)
from interview_evidence.reporting.domain.deletion import (
    DeletionManifest,
    DeletionRequest,
    DeletionStatus,
    DeletionTarget,
    TargetStatus,
)
from interview_evidence.reporting.repositories.postgres import ReportingRepository
from interview_evidence.runtime.worker import DeletionRequestedEventHandler
from interview_evidence.shared.ids import FrozenClock
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


def test_deletion_keeps_invitation_until_lower_priority_targets_verify() -> None:
    repository = RecordingDeletionRepository()
    executed: list[str] = []
    child_verified = False

    def execute_target(_context: TenantContext, target: object) -> bool:
        target_type = cast(DeletionTargetSpec, target).target_type
        executed.append(target_type)
        return child_verified or target_type == "invitation"

    service = DeletionService(
        cast(ReportingRepository, repository),
        enumerators=(
            lambda _context, _scope_type, _scope_id: (
                DeletionTargetSpec(
                    "B",
                    "aurora",
                    "submission_chunk",
                    str(INVITATION_ID),
                ),
                DeletionTargetSpec("A", "aurora", "invitation", str(INVITATION_ID)),
            ),
        ),
        executors={"A": execute_target, "B": execute_target},
    )
    request, _ = service.request(
        context(),
        scope_type="invitation",
        scope_id=INVITATION_ID,
        reason="company_user_requested_applicant_deletion",
        policy_snapshot={"retention_days": 180},
        occurred_at=NOW,
    )

    first = service.execute(
        context(),
        request_id=request.deletion_request_id,
        occurred_at=NOW,
    )

    assert executed == ["submission_chunk"]
    assert first.status is DeletionStatus.RETRYING
    assert (
        next(target for target in first.targets if target.target_type == "invitation").attempts == 0
    )

    child_verified = True
    completed = service.execute(
        context(),
        request_id=request.deletion_request_id,
        occurred_at=NOW,
    )

    assert executed == ["submission_chunk", "submission_chunk", "invitation"]
    assert completed.status is DeletionStatus.COMPLETED


def test_deletion_worker_retries_until_every_target_is_verified() -> None:
    repository = RecordingDeletionRepository()
    outbox = RecordingOutbox()
    verification_ready = False

    def execute_target(_context: TenantContext, _target: object) -> bool:
        return verification_ready

    service = DeletionService(
        cast(ReportingRepository, repository),
        enumerators=(
            lambda _context, _scope_type, _scope_id: (
                DeletionTargetSpec("A", "aurora", "invitation", str(INVITATION_ID)),
            ),
        ),
        executors={"A": execute_target},
        outbox=cast(Outbox, outbox),
    )
    service.request(
        context(),
        scope_type="invitation",
        scope_id=INVITATION_ID,
        reason="company_user_requested_applicant_deletion",
        policy_snapshot={"retention_days": 180},
        occurred_at=NOW,
    )
    handler = DeletionRequestedEventHandler(service, FrozenClock(NOW))

    with pytest.raises(TimeoutError, match="remain unverified"):
        handler(context(), outbox.events[0])

    assert repository.saved is not None
    assert repository.saved[1].status is DeletionStatus.RETRYING

    verification_ready = True
    manifest = handler(context(), outbox.events[0])

    assert isinstance(manifest, DeletionManifest)
    assert manifest.status is DeletionStatus.COMPLETED


def test_only_a_completed_manifest_is_settled() -> None:
    """`is_settled` is what the worker above retries on, so it has to track `status` exactly.

    The worker raises on every `False`, and the queue redelivers. A terminal state added to
    `DeletionStatus` without an answer here would therefore be retried forever -- which is why
    the worker asks the manifest instead of comparing the enum itself.
    """
    target = DeletionTarget.pending(
        target_id=UUID("00000000-0000-7000-8000-000000000003"),
        owner_lane="A",
        store="aurora",
        target_type="invitation",
        resource_id=str(INVITATION_ID),
    )
    deleting = DeletionManifest(
        manifest_id=UUID("00000000-0000-7000-8000-000000000004"),
        deletion_request_id=UUID("00000000-0000-7000-8000-000000000005"),
        manifest_version=1,
        targets=(target,),
    )
    unsettled = (
        deleting,
        deleting.record_result(target.target_id, status=TargetStatus.RETRYING),
        deleting.record_result(target.target_id, status=TargetStatus.FAILED),
    )
    assert {candidate.status for candidate in unsettled} == {
        DeletionStatus.DELETING,
        DeletionStatus.RETRYING,
        DeletionStatus.PARTIALLY_COMPLETED,
    }
    for candidate in unsettled:
        assert not candidate.is_settled

    completed = deleting.record_result(
        target.target_id,
        status=TargetStatus.VERIFIED_ABSENT,
        verified_at=NOW,
    )
    assert completed.status is DeletionStatus.COMPLETED
    assert completed.is_settled
