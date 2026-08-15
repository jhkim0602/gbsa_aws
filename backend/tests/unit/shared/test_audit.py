from uuid import UUID

import pytest
from interview_evidence.shared.audit import (
    AuditMetadataError,
    InMemoryAuditAppender,
)
from interview_evidence.shared.tenant import ActorType, TenantContext


def context() -> TenantContext:
    return TenantContext(
        company_id=UUID("00000000-0000-7000-8000-000000000001"),
        actor_type=ActorType.COMPANY_USER,
        actor_id=UUID("00000000-0000-7000-8000-000000000002"),
        request_id=UUID("00000000-0000-7000-8000-000000000003"),
        trace_id="trace-audit",
    )


def test_audit_appender_accepts_opaque_metadata() -> None:
    appender = InMemoryAuditAppender()

    audit_id = appender.append(
        context(),
        action="report.viewed",
        resource_type="report",
        resource_id=UUID("00000000-0000-7000-8000-000000000004"),
        result="allowed",
        metadata={"report_version": 1},
    )

    assert audit_id == appender.events[0].audit_event_id


def test_audit_appender_rejects_protected_fields() -> None:
    appender = InMemoryAuditAppender()

    with pytest.raises(AuditMetadataError):
        appender.append(
            context(),
            action="report.viewed",
            resource_type="report",
            resource_id=UUID("00000000-0000-7000-8000-000000000004"),
            result="allowed",
            metadata={"signed_url": "https://example.invalid/private"},
        )
