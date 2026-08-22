from __future__ import annotations

import json
from collections.abc import Callable
from threading import Lock
from typing import Protocol
from urllib.request import Request, urlopen
from uuid import UUID

from interview_evidence.shared.operations import MetricRecorder, NullMetricRecorder


class TaskProtection(Protocol):
    def acquire(self, workload_id: UUID) -> bool: ...

    def release(self, workload_id: UUID) -> bool: ...


class NullTaskProtection:
    def acquire(self, workload_id: UUID) -> bool:
        del workload_id
        return False

    def release(self, workload_id: UUID) -> bool:
        del workload_id
        return False


TaskProtectionTransport = Callable[[str, bytes, float], None]


class EcsTaskProtection:
    """Reference-count active work before toggling protection on the local ECS task."""

    def __init__(
        self,
        agent_uri: str,
        *,
        service: str,
        expires_in_minutes: int = 60,
        timeout_seconds: float = 2.0,
        metrics: MetricRecorder | None = None,
        transport: TaskProtectionTransport | None = None,
    ) -> None:
        if not agent_uri.startswith("http"):
            raise ValueError("ECS agent URI must be an HTTP URL")
        if not 1 <= expires_in_minutes <= 2_880:
            raise ValueError("task protection expiry must be between 1 and 2880 minutes")
        self._endpoint = f"{agent_uri.rstrip('/')}/task-protection/v1/state"
        self._service = service
        self._expires_in_minutes = expires_in_minutes
        self._timeout_seconds = timeout_seconds
        self._metrics = metrics or NullMetricRecorder()
        self._transport = transport or _send_task_protection_request
        self._active: set[UUID] = set()
        self._lock = Lock()

    def acquire(self, workload_id: UUID) -> bool:
        with self._lock:
            if workload_id in self._active:
                return True
            if not self._active and not self._set_protection(enabled=True):
                return False
            self._active.add(workload_id)
            return True

    def release(self, workload_id: UUID) -> bool:
        with self._lock:
            if workload_id not in self._active:
                return False
            self._active.remove(workload_id)
            if self._active:
                return True
            return self._set_protection(enabled=False)

    def _set_protection(self, *, enabled: bool) -> bool:
        payload: dict[str, object] = {"ProtectionEnabled": enabled}
        if enabled:
            payload["ExpiresInMinutes"] = self._expires_in_minutes
        try:
            self._transport(
                self._endpoint,
                json.dumps(payload, separators=(",", ":")).encode("utf-8"),
                self._timeout_seconds,
            )
        except (OSError, TimeoutError, ValueError):
            self._record("error")
            return False
        self._record("enabled" if enabled else "disabled")
        return True

    def _record(self, outcome: str) -> None:
        self._metrics.record(
            "ecs_task_protection_change",
            1,
            unit="Count",
            dimensions={"service": self._service, "outcome": outcome},
        )


def create_task_protection(
    *,
    agent_uri: str | None,
    service: str,
    metrics: MetricRecorder | None = None,
) -> TaskProtection:
    if agent_uri is None or not agent_uri.strip():
        return NullTaskProtection()
    return EcsTaskProtection(
        agent_uri.strip(),
        service=service,
        metrics=metrics,
    )


def _send_task_protection_request(endpoint: str, payload: bytes, timeout: float) -> None:
    request = Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed ECS agent URI
        if not 200 <= response.status < 300:
            raise OSError("ECS agent rejected task protection update")
