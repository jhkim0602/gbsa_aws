from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from interview_evidence.reporting.application.deletion_service import (
    DeletionService,
    DeletionTargetSpec,
)
from interview_evidence.reporting.domain.deletion import DeletionManifest
from interview_evidence.reporting.domain.report import Report
from interview_evidence.reporting.repositories.postgres import ReportingRepository
from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class ReviewProjection:
    company_id: UUID
    invitation_id: UUID
    interview_session_id: UUID
    report_id: UUID | None
    report_status: str
    human_decision_status: str | None


@dataclass(frozen=True, slots=True)
class ReportingDeletionReceipt:
    store: str
    target_type: str
    resource_id: str
    verified_absent: bool


class ReportingPublic:
    """Frozen Lane D boundary for company-management consumers."""

    def __init__(
        self,
        *,
        repository: ReportingRepository,
        deletion_service: DeletionService,
    ) -> None:
        self._repository = repository
        self._deletion_service = deletion_service

    def get_review_projection(
        self,
        context: TenantContext,
        *,
        invitation_id: UUID,
    ) -> ReviewProjection | None:
        report = self._repository.get_report_for_invitation(context, invitation_id)
        if report is None:
            return None
        decisions = [
            review
            for review in self._repository.list_reviews(context, report.report_id)
            if review.review_type.value == "final_decision"
        ]
        return ReviewProjection(
            company_id=report.company_id,
            invitation_id=report.invitation_id,
            interview_session_id=report.interview_session_id,
            report_id=report.report_id,
            report_status=report.status.value,
            human_decision_status=(decisions[-1].value.get("decision") if decisions else None),
        )

    def get_report(
        self,
        context: TenantContext,
        *,
        report_id: UUID,
    ) -> Report:
        return self._repository.get_report(context, report_id)

    def request_deletion(
        self,
        context: TenantContext,
        *,
        scope_type: str,
        scope_id: UUID,
        reason: str,
        policy_snapshot: dict[str, object],
        occurred_at: datetime,
    ) -> DeletionManifest:
        _, manifest = self._deletion_service.request(
            context,
            scope_type=scope_type,
            scope_id=scope_id,
            reason=reason,
            policy_snapshot=policy_snapshot,
            occurred_at=occurred_at,
        )
        return manifest

    def get_deletion_status(
        self,
        context: TenantContext,
        *,
        deletion_request_id: UUID,
    ) -> DeletionManifest:
        return self._repository.get_deletion(context, deletion_request_id)[1]

    def enumerate_reporting_deletion_targets(
        self,
        context: TenantContext,
        *,
        invitation_id: UUID,
    ) -> tuple[DeletionTargetSpec, ...]:
        report = self._repository.get_report_for_invitation(context, invitation_id)
        if report is None:
            return ()
        targets = [
            DeletionTargetSpec(
                owner_lane="D",
                store="aurora",
                target_type="report",
                resource_id=str(report.report_id),
            ),
            *[
                DeletionTargetSpec(
                    owner_lane="D",
                    store="aurora",
                    target_type="transcript_segment",
                    resource_id=str(segment.transcript_segment_id),
                )
                for segment in self._repository.list_transcripts(
                    context,
                    report.interview_session_id,
                )
            ],
        ]
        for asset in self._repository.list_recording_assets(
            context,
            report.interview_session_id,
        ):
            targets.extend(
                (
                    DeletionTargetSpec(
                        owner_lane="D",
                        store="s3",
                        target_type="recording_asset_object",
                        resource_id=asset.object_key,
                    ),
                    DeletionTargetSpec(
                        owner_lane="D",
                        store="aurora",
                        target_type="recording_asset",
                        resource_id=str(asset.recording_asset_id),
                    ),
                )
            )
        targets.extend(
            DeletionTargetSpec(
                owner_lane="D",
                store="aurora",
                target_type="session_event",
                resource_id=str(event.session_event_id),
            )
            for event in self._repository.list_session_events(
                context,
                report.interview_session_id,
            )
        )
        for item in report.items:
            targets.extend(
                DeletionTargetSpec(
                    owner_lane="D",
                    store="aurora",
                    target_type="evidence",
                    resource_id=str(evidence.evidence_id),
                )
                for evidence in item.evidence
            )
            targets.append(
                DeletionTargetSpec(
                    owner_lane="D",
                    store="aurora",
                    target_type="report_item",
                    resource_id=str(item.report_item_id),
                )
            )
        targets.extend(
            DeletionTargetSpec(
                owner_lane="D",
                store="aurora",
                target_type="human_review",
                resource_id=str(review.human_review_id),
            )
            for review in self._repository.list_reviews(context, report.report_id)
        )
        return tuple(targets)

    def delete_reporting_target(
        self,
        context: TenantContext,
        *,
        target: DeletionTargetSpec,
    ) -> ReportingDeletionReceipt:
        delete_and_verify = getattr(self._repository, "delete_and_verify_target", None)
        if delete_and_verify is None:
            raise RuntimeError("reporting deletion adapter is not configured")
        verified_absent = bool(
            delete_and_verify(
                context,
                store=target.store,
                target_type=target.target_type,
                resource_id=target.resource_id,
            )
        )
        return ReportingDeletionReceipt(
            store=target.store,
            target_type=target.target_type,
            resource_id=target.resource_id,
            verified_absent=verified_absent,
        )
