from __future__ import annotations

from uuid import UUID

from interview_evidence.company_management.application.company_service import (
    CompanyManagementPublic,
)
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.workers.analysis.pipeline import AnalysisAxis


class CompanyAnalysisAxisProvider:
    def __init__(self, company: CompanyManagementPublic) -> None:
        self._company = company

    def get_axis(
        self,
        context: TenantContext,
        *,
        invitation_id: UUID,
    ) -> AnalysisAxis:
        invitation = self._company.authorize_invitation(
            context,
            invitation_id,
            required_state="consented",
        )
        if not invitation.authorized:
            raise PermissionError("analysis invitation is not authorized")
        campaign = self._company.get_campaign_snapshot(
            context,
            invitation.campaign_id,
        )
        criterion = self._company.get_criterion_version(
            context,
            campaign.competency_model_version_id,
        )
        return AnalysisAxis(
            competency_model_version_id=criterion.competency_model_version_id,
            criterion_ids=tuple(item.criterion_id for item in criterion.criteria),
        )
