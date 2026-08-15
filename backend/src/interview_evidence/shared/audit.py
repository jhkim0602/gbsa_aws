from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from interview_evidence.shared.ids import new_uuid7
from interview_evidence.shared.observability import is_prohibited_field
from interview_evidence.shared.tenant import TenantContext, require_tenant_context


class AuditMetadataError(ValueError):
    """Raised when an audit record includes protected content."""


def _assert_safe_metadata(value: Any, path: str = "metadata") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if is_prohibited_field(key_text):
                raise AuditMetadataError(f"{path}.{key_text} is prohibited")
            _assert_safe_metadata(item, f"{path}.{key_text}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _assert_safe_metadata(item, f"{path}[{index}]")


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    audit_event_id: UUID
    company_id: UUID
    actor_type: str
    actor_id: UUID
    action: str = Field(min_length=1, max_length=200)
    resource_type: str = Field(min_length=1, max_length=100)
    resource_id: UUID
    result: str = Field(min_length=1, max_length=100)
    occurred_at: datetime
    request_id: UUID
    trace_id: str
    metadata: dict[str, Any]


class AuditAppender(Protocol):
    def append(
        self,
        context: TenantContext,
        *,
        action: str,
        resource_type: str,
        resource_id: UUID,
        result: str,
        metadata: dict[str, Any],
    ) -> UUID: ...

    def delete_for_resource(
        self,
        context: TenantContext,
        resource_id: UUID,
    ) -> bool: ...


class InMemoryAuditAppender:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def append(
        self,
        context: TenantContext,
        *,
        action: str,
        resource_type: str,
        resource_id: UUID,
        result: str,
        metadata: dict[str, Any],
    ) -> UUID:
        tenant = require_tenant_context(context)
        _assert_safe_metadata(metadata)
        occurred_at = datetime.now(UTC)
        event = AuditEvent(
            audit_event_id=new_uuid7(occurred_at),
            company_id=tenant.company_id,
            actor_type=tenant.actor_type,
            actor_id=tenant.actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            occurred_at=occurred_at,
            request_id=tenant.request_id,
            trace_id=tenant.trace_id,
            metadata=metadata,
        )
        self.events.append(event)
        return event.audit_event_id

    def delete_for_resource(
        self,
        context: TenantContext,
        resource_id: UUID,
    ) -> bool:
        tenant = require_tenant_context(context)
        self.events = [
            event
            for event in self.events
            if not (event.company_id == tenant.company_id and event.resource_id == resource_id)
        ]
        return not any(
            event.company_id == tenant.company_id and event.resource_id == resource_id
            for event in self.events
        )
