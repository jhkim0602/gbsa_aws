from uuid import UUID

import pytest
from interview_evidence.shared.tenant import (
    ActorType,
    TenantContext,
    TenantScopeError,
    require_tenant_context,
)

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
OTHER_COMPANY_ID = UUID("00000000-0000-7000-8000-000000000002")


def make_context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=UUID("00000000-0000-7000-8000-000000000003"),
        request_id=UUID("00000000-0000-7000-8000-000000000004"),
        trace_id="trace-foundation",
    )


def test_missing_tenant_context_is_rejected() -> None:
    with pytest.raises(TenantScopeError):
        require_tenant_context(None)


def test_cross_tenant_resource_is_rejected() -> None:
    context = make_context()

    with pytest.raises(TenantScopeError):
        context.assert_company(OTHER_COMPANY_ID)
