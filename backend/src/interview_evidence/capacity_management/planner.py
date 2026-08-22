from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from interview_evidence.capacity_management.domain import (
    CapacityPlan,
    CapacityReservation,
    CapacityServiceRole,
    CapacityTarget,
    ScheduledCapacityAction,
)


@dataclass(frozen=True, slots=True)
class CapacityPlannerConfig:
    interview_duration_minutes: int = 30
    api_baseline_tasks: int = 2
    api_max_tasks: int = 20
    api_safe_sessions_per_task: int = 25
    api_prewarm_minutes: int = 15
    api_drain_minutes: int = 10
    worker_baseline_tasks: int = 1
    worker_max_tasks: int = 30
    worker_safe_completions_per_task: int = 25
    worker_prewarm_minutes: int = 5
    worker_drain_minutes: int = 45
    headroom_ratio: float = 1.25

    def __post_init__(self) -> None:
        if self.interview_duration_minutes != 30:
            raise ValueError("the production interview contract is fixed at 30 minutes")
        positive = (
            self.api_baseline_tasks,
            self.api_max_tasks,
            self.api_safe_sessions_per_task,
            self.worker_baseline_tasks,
            self.worker_max_tasks,
            self.worker_safe_completions_per_task,
        )
        if any(value < 1 for value in positive) or self.headroom_ratio < 1:
            raise ValueError("capacity planner limits must be positive")
        if self.api_baseline_tasks > self.api_max_tasks:
            raise ValueError("API baseline cannot exceed max capacity")
        if self.worker_baseline_tasks > self.worker_max_tasks:
            raise ValueError("Worker baseline cannot exceed max capacity")


@dataclass(frozen=True, slots=True)
class _Interval:
    starts_at: datetime
    ends_at: datetime
    load: int


class CapacityPlanner:
    """Aggregate overlapping tenant schedules into global ECS service minimums."""

    def __init__(self, config: CapacityPlannerConfig | None = None) -> None:
        self.config = config or CapacityPlannerConfig()

    def build(
        self,
        reservations: tuple[CapacityReservation, ...],
        *,
        now: datetime,
    ) -> CapacityPlan:
        api_intervals: list[_Interval] = []
        worker_intervals: list[_Interval] = []
        duration = timedelta(minutes=self.config.interview_duration_minutes)
        for reservation in reservations:
            if not reservation.is_schedulable:
                continue
            assert reservation.interview_at is not None
            assert reservation.expected_concurrency is not None
            interview_ends_at = reservation.interview_at + duration
            api_intervals.append(
                _Interval(
                    starts_at=reservation.interview_at
                    - timedelta(minutes=self.config.api_prewarm_minutes),
                    ends_at=interview_ends_at + timedelta(minutes=self.config.api_drain_minutes),
                    load=reservation.expected_concurrency,
                )
            )
            worker_intervals.append(
                _Interval(
                    starts_at=interview_ends_at
                    - timedelta(minutes=self.config.worker_prewarm_minutes),
                    ends_at=interview_ends_at + timedelta(minutes=self.config.worker_drain_minutes),
                    load=reservation.expected_concurrency,
                )
            )

        current_targets: list[CapacityTarget] = []
        raw_actions: list[tuple[CapacityServiceRole, datetime, int, int, int, bool]] = []
        saturated: list[CapacityServiceRole] = []
        for service_role, intervals in (
            (CapacityServiceRole.API, api_intervals),
            (CapacityServiceRole.WORKER, worker_intervals),
        ):
            current, future = self._service_plan(service_role, intervals, now=now)
            current_targets.append(current)
            raw_actions.extend(future)
            if current.saturated or any(item[-1] for item in future):
                saturated.append(service_role)

        raw_actions.sort(key=lambda item: (item[1], item[0].value))

        digest_payload = [
            {
                "service": role.value,
                "effective_at": effective_at.isoformat(),
                "min": minimum,
                "max": maximum,
                "load": load,
            }
            for role, effective_at, minimum, maximum, load, _ in raw_actions
        ]
        plan_hash = hashlib.sha256(
            json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        actions = tuple(
            ScheduledCapacityAction(
                action_name=_action_name(role, effective_at, minimum),
                service_role=role,
                effective_at=effective_at,
                min_capacity=minimum,
                max_capacity=maximum,
                expected_load=load,
                plan_hash=plan_hash,
            )
            for role, effective_at, minimum, maximum, load, _ in raw_actions
        )
        return CapacityPlan(
            generated_at=now,
            current_targets=tuple(current_targets),
            scheduled_actions=actions,
            saturated_services=tuple(dict.fromkeys(saturated)),
        )

    def _service_plan(
        self,
        service_role: CapacityServiceRole,
        intervals: list[_Interval],
        *,
        now: datetime,
    ) -> tuple[
        CapacityTarget,
        list[tuple[CapacityServiceRole, datetime, int, int, int, bool]],
    ]:
        baseline, maximum, per_task = self._limits(service_role)
        current_load = sum(
            interval.load for interval in intervals if interval.starts_at <= now < interval.ends_at
        )
        current_required = _required_tasks(
            current_load,
            baseline=baseline,
            per_task=per_task,
            headroom_ratio=self.config.headroom_ratio,
        )
        current = CapacityTarget(
            service_role=service_role,
            min_capacity=min(current_required, maximum),
            max_capacity=maximum,
            expected_load=current_load,
            saturated=current_required > maximum,
        )

        boundaries: dict[datetime, int] = defaultdict(int)
        for interval in intervals:
            if interval.starts_at > now:
                boundaries[interval.starts_at] += interval.load
            if interval.ends_at > now:
                boundaries[interval.ends_at] -= interval.load
        load = current_load
        previous_minimum = current.min_capacity
        actions: list[tuple[CapacityServiceRole, datetime, int, int, int, bool]] = []
        for effective_at in sorted(boundaries):
            load = max(0, load + boundaries[effective_at])
            required = _required_tasks(
                load,
                baseline=baseline,
                per_task=per_task,
                headroom_ratio=self.config.headroom_ratio,
            )
            minimum = min(required, maximum)
            if minimum == previous_minimum:
                continue
            actions.append(
                (
                    service_role,
                    effective_at,
                    minimum,
                    maximum,
                    load,
                    required > maximum,
                )
            )
            previous_minimum = minimum
        return current, actions

    def _limits(self, service_role: CapacityServiceRole) -> tuple[int, int, int]:
        if service_role is CapacityServiceRole.API:
            return (
                self.config.api_baseline_tasks,
                self.config.api_max_tasks,
                self.config.api_safe_sessions_per_task,
            )
        return (
            self.config.worker_baseline_tasks,
            self.config.worker_max_tasks,
            self.config.worker_safe_completions_per_task,
        )


def _required_tasks(
    load: int,
    *,
    baseline: int,
    per_task: int,
    headroom_ratio: float,
) -> int:
    return max(baseline, math.ceil(load * headroom_ratio / per_task))


def _action_name(
    service_role: CapacityServiceRole,
    effective_at: datetime,
    minimum: int,
) -> str:
    timestamp = effective_at.strftime("%Y%m%dT%H%M%SZ")
    return f"iep-{service_role.value}-{timestamp}-min-{minimum}"
