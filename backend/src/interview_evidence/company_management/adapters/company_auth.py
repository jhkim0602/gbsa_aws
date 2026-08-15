from __future__ import annotations

from uuid import UUID

from interview_evidence.shared.ids import new_uuid7
from interview_evidence.shared.security.principals import (
    CompanyPrincipal,
    PrincipalProvider,
)
from interview_evidence.shared.tenant import ActorType, TenantContext


class CompanyAuthAdapter:
    def __init__(self, principal_provider: PrincipalProvider) -> None:
        self._principal_provider = principal_provider

    def authenticate(
        self,
        credential: str,
        *,
        request_id: UUID | None,
        trace_id: str | None,
    ) -> tuple[CompanyPrincipal, TenantContext]:
        principal = self._principal_provider.get_company_principal(credential)
        effective_request_id = request_id or new_uuid7()
        return principal, TenantContext(
            company_id=principal.company_id,
            actor_type=ActorType.COMPANY_USER,
            actor_id=principal.company_user_id,
            request_id=effective_request_id,
            trace_id=trace_id or str(effective_request_id),
        )
