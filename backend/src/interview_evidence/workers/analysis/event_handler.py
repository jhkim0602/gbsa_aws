from __future__ import annotations

from uuid import UUID

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
    ) -> None:
        self._runtime = runtime
        self._handler = handler

    def __call__(self, context: TenantContext, event: OutboxEvent) -> object:
        submission_id = UUID(str(event.payload["submission_id"]))
        submission = self._runtime.repository.get_submission(context, submission_id)
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
