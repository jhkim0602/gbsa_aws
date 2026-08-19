from __future__ import annotations

from typing import Protocol
from uuid import UUID

from interview_evidence.shared.tenant import TenantContext


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
