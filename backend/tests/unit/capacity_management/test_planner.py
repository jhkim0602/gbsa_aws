from datetime import UTC, datetime, timedelta
from uuid import UUID

from interview_evidence.capacity_management.domain import (
    CapacityReservation,
    CapacityReservationStatus,
    CapacityServiceRole,
)
from interview_evidence.capacity_management.planner import CapacityPlanner

NOW = datetime(2026, 9, 15, 4, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")


def _reservation(index: int, interview_at: datetime, concurrency: int) -> CapacityReservation:
    return CapacityReservation(
        position_id=UUID(f"00000000-0000-7000-8000-{index:012d}"),
        company_id=COMPANY_ID,
        source_version=1,
        status=CapacityReservationStatus.ACTIVE,
        expected_concurrency=concurrency,
        interview_at=interview_at,
        updated_at=NOW,
    )


def test_100_person_interview_creates_fixed_30_minute_api_and_worker_windows() -> None:
    plan = CapacityPlanner().build(
        (_reservation(1, NOW + timedelta(hours=1), 100),),
        now=NOW,
    )

    assert [(target.service_role, target.min_capacity) for target in plan.current_targets] == [
        (CapacityServiceRole.API, 2),
        (CapacityServiceRole.WORKER, 1),
    ]
    assert [
        (action.service_role, action.effective_at, action.min_capacity)
        for action in plan.scheduled_actions
    ] == [
        (CapacityServiceRole.API, NOW + timedelta(minutes=45), 5),
        (CapacityServiceRole.WORKER, NOW + timedelta(minutes=85), 5),
        (CapacityServiceRole.API, NOW + timedelta(minutes=100), 2),
        (CapacityServiceRole.WORKER, NOW + timedelta(minutes=135), 1),
    ]


def test_overlapping_company_schedules_are_summed_before_task_count_is_derived() -> None:
    plan = CapacityPlanner().build(
        (
            _reservation(1, NOW + timedelta(hours=1), 100),
            _reservation(2, NOW + timedelta(hours=1, minutes=15), 100),
        ),
        now=NOW,
    )

    api_actions = [
        action
        for action in plan.scheduled_actions
        if action.service_role is CapacityServiceRole.API
    ]
    assert [(action.effective_at, action.min_capacity) for action in api_actions] == [
        (NOW + timedelta(minutes=45), 5),
        (NOW + timedelta(minutes=60), 10),
        (NOW + timedelta(minutes=100), 5),
        (NOW + timedelta(minutes=115), 2),
    ]


def test_active_window_is_applied_immediately_and_still_schedules_scale_in() -> None:
    plan = CapacityPlanner().build(
        (_reservation(1, NOW - timedelta(minutes=5), 100),),
        now=NOW,
    )

    targets = {target.service_role: target for target in plan.current_targets}
    assert targets[CapacityServiceRole.API].min_capacity == 5
    assert targets[CapacityServiceRole.WORKER].min_capacity == 1
    assert any(
        action.service_role is CapacityServiceRole.API and action.min_capacity == 2
        for action in plan.scheduled_actions
    )


def test_cancelled_reservation_does_not_change_baseline() -> None:
    reservation = _reservation(1, NOW + timedelta(hours=1), 100).model_copy(
        update={"status": CapacityReservationStatus.CANCELLED}
    )

    plan = CapacityPlanner().build((reservation,), now=NOW)

    assert [target.min_capacity for target in plan.current_targets] == [2, 1]
    assert plan.scheduled_actions == ()
