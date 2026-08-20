from __future__ import annotations

from uuid import UUID

from interview_evidence.company_management.application.company_service import (
    CompanyManagementPublic,
)
from interview_evidence.shared.ids import CommandMeta
from interview_evidence.shared.messaging.outbox import OutboxEvent
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.submission_analysis.api import LaneBRuntime
from interview_evidence.submission_analysis.domain.submission import SourceType
from interview_evidence.workers.analysis.handlers import AnalysisJob, AnalysisJobHandler


class AnalysisRequestedEventHandler:
    def __init__(
        self,
        runtime: LaneBRuntime,
        handler: AnalysisJobHandler,
        company: CompanyManagementPublic | None = None,
    ) -> None:
        self._runtime = runtime
        self._handler = handler
        self._company = company

    def __call__(self, context: TenantContext, event: OutboxEvent) -> object:
        submission_id = UUID(str(event.payload["submission_id"]))
        submission = self._runtime.repository.get_submission(context, submission_id)
        if self._company is not None:
            snapshot = self._company.authorize_invitation(
                context,
                submission.invitation_id,
                required_state=frozenset({"materials_submitted", "analyzing", "ready"}),
            )
            if snapshot.state == "materials_submitted":
                self._company.advance_invitation_state(
                    context,
                    submission.invitation_id,
                    from_state="materials_submitted",
                    to_state="analyzing",
                    meta=CommandMeta.create(
                        f"analysis-started-{submission.invitation_id}",
                        expected_version=snapshot.row_version,
                    ),
                )
        outcome = self._handler.handle(
            context,
            AnalysisJob(
                submission_id=submission_id,
                invitation_id=submission.invitation_id,
                applicant_id=submission.applicant_id,
                analysis_version=int(event.payload["analysis_version"]),
                source_type=SourceType(str(event.payload["source_type"])),
                source_object_id=UUID(str(event.payload["source_object_id"])),
                idempotency_key=event.idempotency_key,
            ),
        )
        if self._company is not None:
            self._advance_ready_when_required_analysis_finishes(
                context,
                submission.invitation_id,
            )
        return outcome

    def _advance_ready_when_required_analysis_finishes(
        self,
        context: TenantContext,
        invitation_id: UUID,
    ) -> None:
        assert self._company is not None
        requirements = self._company.get_submission_requirements(
            context,
            invitation_id,
        ).requirements
        required_materials = {
            requirement.material_type
            for requirement in requirements
            if requirement.enabled and requirement.required
        }
        submissions = self._runtime.repository.list_submissions_for_invitation(
            context,
            invitation_id,
        )
        ready_materials = {
            submission.material_type
            for submission in submissions
            if submission.status.value in {"ready", "partial"}
        }
        strategy = self._runtime.repository.latest_strategy(context, invitation_id)
        if (
            not required_materials.issubset(ready_materials)
            or strategy is None
            or strategy.status.value not in {"ready", "partial"}
        ):
            return
        snapshot = self._company.authorize_invitation(
            context,
            invitation_id,
            required_state=frozenset({"analyzing", "ready"}),
        )
        if snapshot.state != "analyzing":
            return
        self._company.advance_invitation_state(
            context,
            invitation_id,
            from_state="analyzing",
            to_state="ready",
            meta=CommandMeta.create(
                f"analysis-ready-{invitation_id}",
                expected_version=snapshot.row_version,
            ),
        )
