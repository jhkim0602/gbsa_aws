from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class TargetStatus(StrEnum):
    PENDING = "pending"
    DELETING = "deleting"
    RETRYING = "retrying"
    FAILED = "failed"
    VERIFIED_ABSENT = "verified_absent"


class DeletionStatus(StrEnum):
    REQUESTED = "requested"
    ENUMERATING = "enumerating"
    DELETING = "deleting"
    VERIFYING = "verifying"
    RETRYING = "retrying"
    PARTIALLY_COMPLETED = "partially_completed"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class DeletionRequest:
    deletion_request_id: UUID
    company_id: UUID
    scope_type: str
    scope_id: UUID
    reason: str
    requester_type: str
    requester_id: UUID
    policy_snapshot: dict[str, object]
    requested_at: datetime

    def __post_init__(self) -> None:
        if self.scope_type not in {"invitation", "applicant"}:
            raise ValueError("unsupported deletion scope")
        if not self.reason.strip():
            raise ValueError("deletion reason is required")


@dataclass(frozen=True, slots=True)
class DeletionTarget:
    target_id: UUID
    owner_lane: str
    store: str
    target_type: str
    resource_id: str
    status: TargetStatus
    attempts: int = 0
    error_code: str | None = None
    verified_at: datetime | None = None

    @classmethod
    def pending(
        cls,
        *,
        target_id: UUID,
        owner_lane: str,
        store: str,
        target_type: str,
        resource_id: str,
    ) -> DeletionTarget:
        if owner_lane not in {"A", "B", "C", "D"}:
            raise ValueError("deletion target owner lane is invalid")
        if store not in {"aurora", "dynamodb", "s3", "retrieval"}:
            raise ValueError("deletion target store is invalid")
        return cls(
            target_id=target_id,
            owner_lane=owner_lane,
            store=store,
            target_type=target_type,
            resource_id=resource_id,
            status=TargetStatus.PENDING,
        )


@dataclass(frozen=True, slots=True)
class DeletionManifest:
    manifest_id: UUID
    deletion_request_id: UUID
    manifest_version: int
    targets: tuple[DeletionTarget, ...]

    @property
    def status(self) -> DeletionStatus:
        if self.targets and all(
            target.status is TargetStatus.VERIFIED_ABSENT for target in self.targets
        ):
            return DeletionStatus.COMPLETED
        if any(target.status is TargetStatus.RETRYING for target in self.targets):
            return DeletionStatus.RETRYING
        if any(target.status is TargetStatus.FAILED for target in self.targets):
            return DeletionStatus.PARTIALLY_COMPLETED
        if any(target.status is TargetStatus.VERIFIED_ABSENT for target in self.targets):
            return DeletionStatus.VERIFYING
        return DeletionStatus.DELETING

    @property
    def is_settled(self) -> bool:
        """Whether this deletion needs no further attempt.

        The worker turns `False` into a raise so the queue redelivers the message. A terminal
        state that will never reach `COMPLETED` on its own therefore has to be admitted here
        too, or that message is retried forever -- which is why the judgement lives beside
        `status` rather than in the worker, where adding a state would not touch it.
        """
        return self.status is DeletionStatus.COMPLETED

    @property
    def verified_targets(self) -> int:
        return sum(target.status is TargetStatus.VERIFIED_ABSENT for target in self.targets)

    def record_result(
        self,
        target_id: UUID,
        *,
        status: TargetStatus,
        verified_at: datetime | None = None,
        error_code: str | None = None,
    ) -> DeletionManifest:
        found = False
        updated: list[DeletionTarget] = []
        for target in self.targets:
            if target.target_id != target_id:
                updated.append(target)
                continue
            found = True
            if status is TargetStatus.VERIFIED_ABSENT and verified_at is None:
                raise ValueError("verified target requires verification time")
            updated.append(
                replace(
                    target,
                    status=status,
                    attempts=target.attempts + 1,
                    error_code=error_code,
                    verified_at=verified_at,
                )
            )
        if not found:
            raise LookupError("deletion target not found")
        return replace(self, targets=tuple(updated))
