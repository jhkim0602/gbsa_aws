from __future__ import annotations

from typing import Protocol
from uuid import UUID

from interview_evidence.company_management.application.company_service import (
    CompanyManagementPublic,
)
from interview_evidence.shared.ids import CommandMeta
from interview_evidence.shared.messaging.outbox import OutboxEvent
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.submission_analysis.api import LaneBRuntime
from interview_evidence.submission_analysis.domain.submission import (
    SourceType,
    Submission,
    SubmissionStatus,
)
from interview_evidence.workers.analysis.handlers import AnalysisJob, AnalysisJobHandler


class InvitationAnalysisFinalizer(Protocol):
    def finalize_invitation(
        self,
        context: TenantContext,
        *,
        invitation_id: UUID,
        applicant_id: UUID,
        submission_ids: frozenset[UUID],
    ) -> bool: ...


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
        if self._company is not None and _owns_analysis_state_transition(
            submission,
            self._runtime.repository.list_submissions_for_invitation(
                context,
                submission.invitation_id,
            ),
        ):
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
        return self._handler.handle(
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


def _owns_analysis_state_transition(
    submission: Submission,
    submissions: tuple[Submission, ...],
) -> bool:
    return submission.submission_id == min(item.submission_id for item in submissions)


class AnalysisCompletedEventHandler:
    def __init__(
        self,
        runtime: LaneBRuntime,
        finalizer: InvitationAnalysisFinalizer,
        company: CompanyManagementPublic,
    ) -> None:
        self._runtime = runtime
        self._finalizer = finalizer
        self._company = company

    def __call__(self, context: TenantContext, event: OutboxEvent) -> object:
        invitation_id = UUID(str(event.payload["invitation_id"]))
        submissions = self._runtime.repository.list_submissions_for_invitation(
            context,
            invitation_id,
        )
        if not submissions or any(
            submission.status
            in {
                SubmissionStatus.RECEIVED,
                SubmissionStatus.VALIDATING,
                SubmissionStatus.ANALYZING,
            }
            for submission in submissions
        ):
            return {"status": "waiting_for_submissions"}
        requirements = self._company.get_submission_requirements(
            context,
            invitation_id,
        ).requirements
        required_materials = {
            requirement.material_type
            for requirement in requirements
            if requirement.enabled and requirement.required
        }
        ready_materials = {
            submission.material_type
            for submission in submissions
            if submission.status in {SubmissionStatus.READY, SubmissionStatus.PARTIAL}
        }
        if not required_materials.issubset(ready_materials):
            return {"status": "required_submission_failed"}
        included = tuple(
            submission
            for submission in submissions
            if submission.status in {SubmissionStatus.READY, SubmissionStatus.PARTIAL}
        )
        if not included or not self._finalizer.finalize_invitation(
            context,
            invitation_id=invitation_id,
            applicant_id=included[0].applicant_id,
            submission_ids=frozenset(submission.submission_id for submission in included),
        ):
            return {"status": "strategy_not_ready"}
        snapshot = self._company.authorize_invitation(
            context,
            invitation_id,
            required_state=frozenset({"analyzing", "ready"}),
        )
        if snapshot.state != "analyzing":
            return {"status": snapshot.state}
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
        return {"status": "ready"}
