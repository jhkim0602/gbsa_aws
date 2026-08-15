from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from interview_evidence.reporting.domain.deletion import (
    DeletionManifest,
    DeletionRequest,
    DeletionTarget,
    TargetStatus,
)
from interview_evidence.reporting.repositories.postgres import ReportingRepository
from interview_evidence.shared.ids import new_uuid7
from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class DeletionTargetSpec:
    owner_lane: str
    store: str
    target_type: str
    resource_id: str


TargetEnumerator = Callable[
    [TenantContext, str, UUID],
    tuple[DeletionTarget | DeletionTargetSpec, ...],
]
TargetExecutor = Callable[[TenantContext, DeletionTarget], bool]


class DeletionService:
    def __init__(
        self,
        repository: ReportingRepository,
        *,
        enumerators: tuple[TargetEnumerator, ...] = (),
        executors: dict[str, TargetExecutor] | None = None,
    ) -> None:
        self._repository = repository
        self._enumerators = enumerators
        self._executors = executors or {}

    def request(
        self,
        context: TenantContext,
        *,
        scope_type: str,
        scope_id: UUID,
        reason: str,
        policy_snapshot: dict[str, object],
        occurred_at: datetime,
    ) -> tuple[DeletionRequest, DeletionManifest]:
        request = DeletionRequest(
            deletion_request_id=new_uuid7(occurred_at),
            company_id=context.company_id,
            scope_type=scope_type,
            scope_id=scope_id,
            reason=reason,
            requester_type=context.actor_type.value,
            requester_id=context.actor_id,
            policy_snapshot=policy_snapshot,
            requested_at=occurred_at,
        )
        candidates = tuple(
            candidate
            for enumerator in self._enumerators
            for candidate in enumerator(context, scope_type, scope_id)
        )
        targets = tuple(
            candidate
            if isinstance(candidate, DeletionTarget)
            else DeletionTarget.pending(
                target_id=new_uuid7(occurred_at),
                owner_lane=candidate.owner_lane,
                store=candidate.store,
                target_type=candidate.target_type,
                resource_id=candidate.resource_id,
            )
            for candidate in candidates
        )
        manifest = DeletionManifest(
            manifest_id=new_uuid7(occurred_at),
            deletion_request_id=request.deletion_request_id,
            manifest_version=1,
            targets=targets,
        )
        self._repository.save_deletion(context, request, manifest)
        return request, manifest

    def execute(
        self,
        context: TenantContext,
        *,
        request_id: UUID,
        occurred_at: datetime,
    ) -> DeletionManifest:
        request, manifest = self._repository.get_deletion(context, request_id)
        for target in manifest.targets:
            if target.status is TargetStatus.VERIFIED_ABSENT:
                continue
            executor = self._executors.get(target.owner_lane)
            try:
                verified = executor is not None and executor(context, target)
            except TimeoutError:
                verified = False
            manifest = manifest.record_result(
                target.target_id,
                status=(TargetStatus.VERIFIED_ABSENT if verified else TargetStatus.RETRYING),
                verified_at=occurred_at if verified else None,
                error_code=None if verified else "TARGET_NOT_VERIFIED",
            )
        return self._repository.update_deletion_manifest(context, request, manifest)

    def consume_retention_expired(
        self,
        context: TenantContext,
        *,
        invitation_id: UUID,
        policy_snapshot: dict[str, object],
        occurred_at: datetime,
    ) -> tuple[DeletionRequest, DeletionManifest]:
        return self.request(
            context,
            scope_type="invitation",
            scope_id=invitation_id,
            reason="retention_expired",
            policy_snapshot=policy_snapshot,
            occurred_at=occurred_at,
        )
