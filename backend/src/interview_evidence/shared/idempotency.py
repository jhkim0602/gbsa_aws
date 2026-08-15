from __future__ import annotations

from typing import Protocol
from uuid import UUID

from interview_evidence.shared.tenant import TenantContext, require_tenant_context


class ResourceIdempotencyStore(Protocol):
    def get(
        self,
        context: TenantContext,
        *,
        operation: str,
        idempotency_key: str,
    ) -> UUID | None: ...

    def put(
        self,
        context: TenantContext,
        *,
        operation: str,
        idempotency_key: str,
        resource_id: UUID,
    ) -> None: ...


class InMemoryResourceIdempotencyStore:
    def __init__(self) -> None:
        self._values: dict[tuple[UUID, str, str], UUID] = {}

    def get(
        self,
        context: TenantContext,
        *,
        operation: str,
        idempotency_key: str,
    ) -> UUID | None:
        tenant = require_tenant_context(context)
        return self._values.get((tenant.company_id, operation, idempotency_key))

    def put(
        self,
        context: TenantContext,
        *,
        operation: str,
        idempotency_key: str,
        resource_id: UUID,
    ) -> None:
        tenant = require_tenant_context(context)
        self._values.setdefault(
            (tenant.company_id, operation, idempotency_key),
            resource_id,
        )
