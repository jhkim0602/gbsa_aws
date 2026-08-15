from __future__ import annotations

from interview_evidence.company_management.application.company_service import (
    CompanyManagementPublic,
)
from interview_evidence.shared.security.principals import ApplicantPrincipal
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.submission_analysis.application.authorization import (
    SubmissionAuthorization,
    SubmissionAuthorizationDenied,
)


class CompanySubmissionAuthorization:
    """Adapt Lane A invitation and consent snapshots to Lane B's input port."""

    def __init__(self, company: CompanyManagementPublic) -> None:
        self._company = company

    def authorize(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
    ) -> SubmissionAuthorization:
        context.assert_company(principal.company_id)
        try:
            invitation = self._company.authorize_invitation(
                context,
                principal.invitation_id,
                required_state="consented",
            )
            if (
                not invitation.authorized
                or invitation.company_id != principal.company_id
                or invitation.applicant_id != principal.applicant_id
            ):
                raise SubmissionAuthorizationDenied("invitation is not authorized for submission")

            self._company.get_campaign_snapshot(context, invitation.campaign_id)
            consent = self._company.get_consent_authorization(
                context,
                principal.invitation_id,
                required_purposes=frozenset({"document_analysis"}),
            )
            if (
                not consent.authorized
                or consent.consent_record_id is None
                or consent.policy_version is None
                or consent.retention_days is None
            ):
                raise SubmissionAuthorizationDenied("active document-analysis consent is required")
        except SubmissionAuthorizationDenied:
            raise
        except (KeyError, PermissionError, ValueError) as error:
            raise SubmissionAuthorizationDenied("submission authorization denied") from error

        return SubmissionAuthorization(
            company_id=principal.company_id,
            invitation_id=principal.invitation_id,
            applicant_id=principal.applicant_id,
            policy_version=consent.policy_version,
            retention_days=consent.retention_days,
        )
