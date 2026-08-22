import json
from uuid import UUID

from interview_evidence.shared.aws_clients.task_protection import EcsTaskProtection
from interview_evidence.shared.operations import InMemoryMetricRecorder


def test_task_protection_is_enabled_for_first_work_and_disabled_after_last_work() -> None:
    requests: list[tuple[str, dict[str, object], float]] = []
    metrics = InMemoryMetricRecorder()

    def transport(endpoint: str, payload: bytes, timeout: float) -> None:
        requests.append((endpoint, json.loads(payload), timeout))

    protection = EcsTaskProtection(
        "http://169.254.170.2/v3/agent",
        service="api",
        metrics=metrics,
        transport=transport,
    )
    first = UUID("00000000-0000-7000-8000-000000000001")
    second = UUID("00000000-0000-7000-8000-000000000002")

    assert protection.acquire(first)
    assert protection.acquire(second)
    assert protection.release(first)
    assert protection.release(second)

    assert [request[1] for request in requests] == [
        {"ProtectionEnabled": True, "ExpiresInMinutes": 60},
        {"ProtectionEnabled": False},
    ]
    assert requests[0][0].endswith("/task-protection/v1/state")
    assert [record.dimensions["outcome"] for record in metrics.records] == [
        "enabled",
        "disabled",
    ]


def test_failed_enable_does_not_claim_that_workload_is_protected() -> None:
    calls = 0

    def failing_transport(endpoint: str, payload: bytes, timeout: float) -> None:
        nonlocal calls
        del endpoint, payload, timeout
        calls += 1
        raise OSError("agent unavailable")

    protection = EcsTaskProtection(
        "http://169.254.170.2/v3/agent",
        service="worker",
        transport=failing_transport,
    )
    workload = UUID("00000000-0000-7000-8000-000000000001")

    assert protection.acquire(workload) is False
    assert protection.release(workload) is False
    assert protection.acquire(workload) is False
    assert calls == 2
