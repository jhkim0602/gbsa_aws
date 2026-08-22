from datetime import UTC, datetime, timedelta
from uuid import UUID

from interview_evidence.capacity_management.event_handler import (
    PositionCapacityChangedHandler,
)
from interview_evidence.capacity_management.planner import CapacityPlanner
from interview_evidence.capacity_management.repository import InMemoryCapacityRepository
from interview_evidence.capacity_management.scaling import InMemoryScheduledScaling
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.messaging.outbox import OutboxEvent
from interview_evidence.shared.operations import InMemoryMetricRecorder
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 9, 15, 4, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
POSITION_ID = UUID("00000000-0000-7000-8000-000000000002")


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=UUID("00000000-0000-7000-8000-000000000003"),
        request_id=UUID("00000000-0000-7000-8000-000000000004"),
        trace_id="capacity-test",
    )


def _event(*, version: int, interview_at: datetime | None, capacity: int | None) -> OutboxEvent:
    return OutboxEvent(
        outbox_event_id=UUID(f"00000000-0000-7000-8000-{version + 10:012d}"),
        company_id=COMPANY_ID,
        aggregate_type="position",
        aggregate_id=POSITION_ID,
        aggregate_version=version,
        event_type="position.capacity_changed",
        event_version=1,
        payload={
            "position_id": str(POSITION_ID),
            "position_status": "active",
            "interview_at": interview_at.isoformat() if interview_at else None,
            "expected_concurrency": capacity,
            "interview_duration_minutes": 30,
        },
        idempotency_key=f"capacity-event-version-{version}",
        trace_id="capacity-test",
        occurred_at=NOW,
    )


def _reconcile_event() -> OutboxEvent:
    return OutboxEvent(
        outbox_event_id=UUID("00000000-0000-7000-8000-000000000099"),
        company_id=COMPANY_ID,
        aggregate_type="capacity_plan",
        aggregate_id=UUID("00000000-0000-7000-8000-000000000000"),
        aggregate_version=1,
        event_type="capacity.reconcile_requested",
        event_version=1,
        payload={},
        idempotency_key="scheduled-capacity-reconcile-test",
        trace_id="capacity-test",
        occurred_at=NOW,
    )


def test_cancellation_deletes_previous_scheduled_actions_and_restores_baselines() -> None:
    repository = InMemoryCapacityRepository()
    scaling = InMemoryScheduledScaling()
    metrics = InMemoryMetricRecorder()
    handler = PositionCapacityChangedHandler(
        repository,
        CapacityPlanner(),
        scaling,
        FrozenClock(NOW),
        metrics,
    )
    scheduled = _event(
        version=1,
        interview_at=NOW + timedelta(hours=1),
        capacity=100,
    )

    first = handler(_context(), scheduled)
    old_action_names = set(repository.actions)
    cancelled = handler(
        _context(),
        _event(version=2, interview_at=None, capacity=100),
    )

    assert first.scheduled_action_count == 4
    assert cancelled.reservation_status == "cancelled"
    assert cancelled.current_api_tasks == 2
    assert cancelled.current_worker_tasks == 1
    assert set(scaling.deleted_action_names) == old_action_names
    assert repository.actions == {}
    assert any(record.name == "scheduled_capacity_action_count" for record in metrics.records)


def test_older_delivery_cannot_restore_a_cancelled_reservation() -> None:
    repository = InMemoryCapacityRepository()
    scaling = InMemoryScheduledScaling()
    handler = PositionCapacityChangedHandler(
        repository,
        CapacityPlanner(),
        scaling,
        FrozenClock(NOW),
    )
    handler(_context(), _event(version=2, interview_at=None, capacity=100))

    result = handler(
        _context(),
        _event(
            version=1,
            interview_at=NOW + timedelta(hours=1),
            capacity=100,
        ),
    )

    assert result.reservation_status == "cancelled"
    assert repository.actions == {}


def test_periodic_reconciliation_repairs_an_aws_action_removed_outside_the_app() -> None:
    repository = InMemoryCapacityRepository()
    scaling = InMemoryScheduledScaling()
    handler = PositionCapacityChangedHandler(
        repository,
        CapacityPlanner(),
        scaling,
        FrozenClock(NOW),
    )
    handler(
        _context(),
        _event(
            version=1,
            interview_at=NOW + timedelta(hours=1),
            capacity=100,
        ),
    )
    expected_action_names = set(repository.actions)
    scaling.actions.clear()

    result = handler(_context(), _reconcile_event())

    assert result.reservation_status == "reconciled"
    assert set(scaling.actions) == expected_action_names
