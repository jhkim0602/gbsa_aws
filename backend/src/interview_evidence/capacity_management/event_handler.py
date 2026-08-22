from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from interview_evidence.capacity_management.domain import (
    CapacityReservation,
    CapacityReservationStatus,
)
from interview_evidence.capacity_management.planner import CapacityPlanner
from interview_evidence.capacity_management.repository import CapacityRepository
from interview_evidence.capacity_management.scaling import ScheduledScaling
from interview_evidence.shared.ids import Clock
from interview_evidence.shared.messaging.outbox import OutboxEvent
from interview_evidence.shared.operations import MetricRecorder, NullMetricRecorder
from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class CapacityReconciliationResult:
    reservation_status: str
    current_api_tasks: int
    current_worker_tasks: int
    scheduled_action_count: int
    deleted_action_count: int
    saturated_services: tuple[str, ...]


class PositionCapacityChangedHandler:
    def __init__(
        self,
        repository: CapacityRepository,
        planner: CapacityPlanner,
        scaling: ScheduledScaling,
        clock: Clock,
        metrics: MetricRecorder | None = None,
    ) -> None:
        self._repository = repository
        self._planner = planner
        self._scaling = scaling
        self._clock = clock
        self._metrics = metrics or NullMetricRecorder()

    def __call__(
        self,
        context: TenantContext,
        event: OutboxEvent,
    ) -> CapacityReconciliationResult:
        context.assert_company(event.company_id)
        if event.event_type == "capacity.reconcile_requested":
            now = self._clock.now()
            self._repository.acquire_plan_lock(now=now)
            return self._apply_plan(
                now=now,
                reservation_status="reconciled",
            )
        if event.event_type != "position.capacity_changed":
            raise ValueError("unsupported capacity event")
        if event.aggregate_type != "position":
            raise ValueError("capacity event aggregate must be a position")
        position_id = UUID(str(event.payload["position_id"]))
        if position_id != event.aggregate_id:
            raise ValueError("capacity event position does not match its aggregate")
        duration = int(event.payload["interview_duration_minutes"])
        if duration != 30:
            raise ValueError("capacity planning only supports the fixed 30-minute interview")
        interview_at_value = event.payload.get("interview_at")
        interview_at = (
            datetime.fromisoformat(str(interview_at_value))
            if interview_at_value is not None
            else None
        )
        concurrency_value = event.payload.get("expected_concurrency")
        expected_concurrency = int(concurrency_value) if concurrency_value is not None else None
        active = (
            event.payload.get("position_status") == "active"
            and interview_at is not None
            and expected_concurrency is not None
        )
        now = self._clock.now()
        reservation = CapacityReservation(
            position_id=position_id,
            company_id=context.company_id,
            source_version=event.aggregate_version,
            status=(
                CapacityReservationStatus.ACTIVE if active else CapacityReservationStatus.CANCELLED
            ),
            expected_concurrency=expected_concurrency,
            interview_at=interview_at,
            interview_duration_minutes=duration,
            updated_at=now,
        )

        self._repository.acquire_plan_lock(now=now)
        stored = self._repository.upsert_reservation(context, reservation)
        return self._apply_plan(
            now=now,
            reservation_status=stored.status.value,
        )

    def _apply_plan(
        self,
        *,
        now: datetime,
        reservation_status: str,
    ) -> CapacityReconciliationResult:
        plan = self._planner.build(self._repository.list_reservations(), now=now)
        existing = {
            action.action_name: action for action in self._repository.list_scheduled_actions()
        }
        desired = {action.action_name: action for action in plan.scheduled_actions}
        stale = [action for name, action in existing.items() if name not in desired]

        for action in stale:
            self._scaling.delete_scheduled_action(action)
        for target in plan.current_targets:
            self._scaling.set_current_minimum(target)
            self._metrics.record(
                "scheduled_capacity_minimum",
                float(target.min_capacity),
                unit="Count",
                dimensions={"service": target.service_role.value},
            )
        # Re-applying every desired action is intentional: the AWS call is idempotent and
        # repairs drift if a scheduled action was removed outside the application.
        for action in plan.scheduled_actions:
            self._scaling.put_scheduled_action(action)
        self._repository.replace_scheduled_actions(
            plan.scheduled_actions,
            applied_at=now,
        )
        for service_role in plan.saturated_services:
            self._metrics.record(
                "scheduled_capacity_saturated",
                1,
                unit="Count",
                dimensions={"service": service_role.value},
            )
        self._metrics.record(
            "scheduled_capacity_action_count",
            float(len(plan.scheduled_actions)),
            unit="Count",
            dimensions={"service": "all"},
        )
        targets = {target.service_role.value: target for target in plan.current_targets}
        return CapacityReconciliationResult(
            reservation_status=reservation_status,
            current_api_tasks=targets["api"].min_capacity,
            current_worker_tasks=targets["worker"].min_capacity,
            scheduled_action_count=len(plan.scheduled_actions),
            deleted_action_count=len(stale),
            saturated_services=tuple(role.value for role in plan.saturated_services),
        )
