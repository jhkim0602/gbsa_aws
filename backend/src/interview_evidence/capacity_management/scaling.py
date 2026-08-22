from __future__ import annotations

from datetime import UTC
from typing import Protocol

from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from interview_evidence.capacity_management.domain import (
    CapacityServiceRole,
    CapacityTarget,
    ScheduledCapacityAction,
)


class ApplicationAutoScalingClient(Protocol):
    def register_scalable_target(self, **kwargs: object) -> object: ...

    def put_scheduled_action(self, **kwargs: object) -> object: ...

    def delete_scheduled_action(self, **kwargs: object) -> object: ...


class ScheduledScaling(Protocol):
    def set_current_minimum(self, target: CapacityTarget) -> None: ...

    def put_scheduled_action(self, action: ScheduledCapacityAction) -> None: ...

    def delete_scheduled_action(self, action: ScheduledCapacityAction) -> None: ...


class AwsEcsScheduledScaling:
    def __init__(
        self,
        client: ApplicationAutoScalingClient,
        *,
        cluster_name: str,
        api_service_name: str,
        worker_service_name: str,
    ) -> None:
        self._client = client
        self._cluster_name = cluster_name
        self._services = {
            CapacityServiceRole.API: api_service_name,
            CapacityServiceRole.WORKER: worker_service_name,
        }

    def set_current_minimum(self, target: CapacityTarget) -> None:
        self._client.register_scalable_target(
            ServiceNamespace="ecs",
            ResourceId=self._resource_id(target.service_role),
            ScalableDimension="ecs:service:DesiredCount",
            MinCapacity=target.min_capacity,
            MaxCapacity=target.max_capacity,
        )

    def put_scheduled_action(self, action: ScheduledCapacityAction) -> None:
        effective_at = action.effective_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")
        self._client.put_scheduled_action(
            ServiceNamespace="ecs",
            ScheduledActionName=action.action_name,
            ResourceId=self._resource_id(action.service_role),
            ScalableDimension="ecs:service:DesiredCount",
            Schedule=f"at({effective_at})",
            ScalableTargetAction={
                "MinCapacity": action.min_capacity,
                "MaxCapacity": action.max_capacity,
            },
        )

    def delete_scheduled_action(self, action: ScheduledCapacityAction) -> None:
        try:
            self._client.delete_scheduled_action(
                ServiceNamespace="ecs",
                ScheduledActionName=action.action_name,
                ResourceId=self._resource_id(action.service_role),
                ScalableDimension="ecs:service:DesiredCount",
            )
        except ClientError as error:
            code = str(error.response.get("Error", {}).get("Code", ""))
            if code != "ObjectNotFoundException":
                raise

    def _resource_id(self, service_role: CapacityServiceRole) -> str:
        return f"service/{self._cluster_name}/{self._services[service_role]}"


class InMemoryScheduledScaling:
    def __init__(self) -> None:
        self.current_targets: dict[CapacityServiceRole, CapacityTarget] = {}
        self.actions: dict[str, ScheduledCapacityAction] = {}
        self.deleted_action_names: list[str] = []

    def set_current_minimum(self, target: CapacityTarget) -> None:
        self.current_targets[target.service_role] = target

    def put_scheduled_action(self, action: ScheduledCapacityAction) -> None:
        self.actions[action.action_name] = action

    def delete_scheduled_action(self, action: ScheduledCapacityAction) -> None:
        self.actions.pop(action.action_name, None)
        self.deleted_action_names.append(action.action_name)
