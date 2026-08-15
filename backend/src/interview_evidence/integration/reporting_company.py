from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from interview_evidence.reporting.application.public import ReportingPublic
from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class CompanyReviewProjection:
    invitation_id: UUID
    interview_session_id: UUID
    report_id: UUID | None
    report_status: str
    human_decision_status: str | None


@dataclass(frozen=True, slots=True)
class CompanyDeletionProjection:
    deletion_request_id: UUID
    manifest_id: UUID
    status: str
    expected_targets: int
    verified_targets: int


class ReportingCompanyBoundary:
    """Adapt Lane D's public projections for company-facing read models."""

    def __init__(self, reporting: ReportingPublic) -> None:
        self._reporting = reporting

    def get_invitation_review(
        self,
        context: TenantContext,
        *,
        invitation_id: UUID,
    ) -> CompanyReviewProjection | None:
        projection = self._reporting.get_review_projection(
            context,
            invitation_id=invitation_id,
        )
        if projection is None:
            return None
        return CompanyReviewProjection(
            invitation_id=projection.invitation_id,
            interview_session_id=projection.interview_session_id,
            report_id=projection.report_id,
            report_status=projection.report_status,
            human_decision_status=projection.human_decision_status,
        )

    def get_deletion_progress(
        self,
        context: TenantContext,
        *,
        deletion_request_id: UUID,
    ) -> CompanyDeletionProjection:
        manifest = self._reporting.get_deletion_status(
            context,
            deletion_request_id=deletion_request_id,
        )
        return CompanyDeletionProjection(
            deletion_request_id=manifest.deletion_request_id,
            manifest_id=manifest.manifest_id,
            status=manifest.status.value,
            expected_targets=len(manifest.targets),
            verified_targets=manifest.verified_targets,
        )
