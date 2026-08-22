from datetime import UTC, datetime

from botocore.exceptions import ClientError
from interview_evidence.capacity_management.domain import (
    CapacityServiceRole,
    CapacityTarget,
    ScheduledCapacityAction,
)
from interview_evidence.capacity_management.scaling import AwsEcsScheduledScaling


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def register_scalable_target(self, **kwargs: object) -> object:
        self.calls.append(("register", kwargs))
        return {}

    def put_scheduled_action(self, **kwargs: object) -> object:
        self.calls.append(("put", kwargs))
        return {}

    def delete_scheduled_action(self, **kwargs: object) -> object:
        self.calls.append(("delete", kwargs))
        return {}


class AlreadyExpiredActionClient(RecordingClient):
    def delete_scheduled_action(self, **kwargs: object) -> object:
        self.calls.append(("delete", kwargs))
        raise ClientError(
            {
                "Error": {
                    "Code": "ObjectNotFoundException",
                    "Message": "scheduled action already expired",
                }
            },
            "DeleteScheduledAction",
        )


def test_aws_adapter_targets_ecs_service_and_uses_one_time_utc_schedule() -> None:
    client = RecordingClient()
    scaling = AwsEcsScheduledScaling(
        client,
        cluster_name="iep-prod",
        api_service_name="iep-prod-api",
        worker_service_name="iep-prod-worker",
    )
    target = CapacityTarget(
        service_role=CapacityServiceRole.API,
        min_capacity=5,
        max_capacity=20,
        expected_load=100,
    )
    action = ScheduledCapacityAction(
        action_name="iep-api-20260915T044500Z-min-5",
        service_role=CapacityServiceRole.API,
        effective_at=datetime(2026, 9, 15, 4, 45, tzinfo=UTC),
        min_capacity=5,
        max_capacity=20,
        expected_load=100,
        plan_hash="a" * 64,
    )

    scaling.set_current_minimum(target)
    scaling.put_scheduled_action(action)
    scaling.delete_scheduled_action(action)

    assert client.calls[0][1]["ResourceId"] == "service/iep-prod/iep-prod-api"
    assert client.calls[1][1]["Schedule"] == "at(2026-09-15T04:45:00)"
    assert client.calls[1][1]["ScalableTargetAction"] == {
        "MinCapacity": 5,
        "MaxCapacity": 20,
    }
    assert client.calls[2][1]["ScheduledActionName"] == action.action_name


def test_deleting_an_already_expired_action_is_idempotent() -> None:
    client = AlreadyExpiredActionClient()
    scaling = AwsEcsScheduledScaling(
        client,
        cluster_name="iep-prod",
        api_service_name="iep-prod-api",
        worker_service_name="iep-prod-worker",
    )
    action = ScheduledCapacityAction(
        action_name="iep-worker-20260915T061500Z-min-1",
        service_role=CapacityServiceRole.WORKER,
        effective_at=datetime(2026, 9, 15, 6, 15, tzinfo=UTC),
        min_capacity=1,
        max_capacity=30,
        expected_load=0,
        plan_hash="b" * 64,
    )

    scaling.delete_scheduled_action(action)

    assert client.calls[0][0] == "delete"
