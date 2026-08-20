from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import UUID

from interview_evidence.company_management.application.company_service import (
    CompanyManagementPublic,
)
from interview_evidence.integration.company_analysis import CompanyAnalysisAxisProvider
from interview_evidence.shared.tenant import ActorType, TenantContext

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
ACTOR_ID = UUID("00000000-0000-7000-8000-000000000002")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000003")
MODEL_VERSION_ID = UUID("00000000-0000-7000-8000-000000000004")


class FakeCompanyManagement:
    def __init__(self, invitation_state: str) -> None:
        self.invitation_state = invitation_state
        self.required_states: frozenset[str] | None = None

    def authorize_invitation(
        self,
        context: TenantContext,
        invitation_id: UUID,
        *,
        required_state: str | frozenset[str],
    ) -> SimpleNamespace:
        context.assert_company(COMPANY_ID)
        assert invitation_id == INVITATION_ID
        required_states = (
            frozenset({required_state}) if isinstance(required_state, str) else required_state
        )
        self.required_states = required_states
        return SimpleNamespace(
            authorized=self.invitation_state in required_states,
            competency_model_version_id=MODEL_VERSION_ID,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )

    def get_criterion_version(
        self,
        context: TenantContext,
        version_id: UUID,
    ) -> SimpleNamespace:
        context.assert_company(COMPANY_ID)
        assert version_id == MODEL_VERSION_ID
        return SimpleNamespace(
            competency_model_version_id=MODEL_VERSION_ID,
            version_number=1,
            criteria=(),
            job_requirements=(),
        )


def test_analysis_axis_allows_invitation_after_analysis_transition() -> None:
    company = FakeCompanyManagement("analyzing")
    provider = CompanyAnalysisAxisProvider(cast(CompanyManagementPublic, company))

    axis = provider.get_axis(_context(), invitation_id=INVITATION_ID)

    assert axis.competency_model_version_id == MODEL_VERSION_ID
    assert company.required_states == frozenset(
        {"consented", "materials_submitted", "analyzing", "ready"}
    )


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=ACTOR_ID,
        request_id=ACTOR_ID,
        trace_id="company-analysis-axis-test",
    )
