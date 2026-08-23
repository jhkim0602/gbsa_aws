from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.messaging.outbox import InMemoryOutbox, OutboxEvent
from interview_evidence.shared.submission_materials import SubmissionMaterialType
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.api import LaneBRuntime
from interview_evidence.submission_analysis.domain.submission import (
    SourceType,
    Submission,
    SubmissionStatus,
)
from interview_evidence.workers.analysis.event_handler import AnalysisRequestedEventHandler
from interview_evidence.workers.analysis.handlers import (
    AnalysisJob,
    AnalysisJobHandler,
    JobStatus,
    RetryableAnalysisError,
)

NOW = datetime(2026, 8, 21, 6, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000002")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000003")
SUBMISSION_ID = UUID("00000000-0000-7000-8000-000000000004")


class AlwaysUnavailableProcessor:
    def process(self, _context: TenantContext, _job: AnalysisJob) -> object:
        raise RetryableAnalysisError("embedding_provider_unavailable")


class SubmissionRepositoryStub:
    def __init__(self, submission: Submission) -> None:
        self.submission = submission

    def get_submission(
        self,
        _context: TenantContext,
        submission_id: UUID,
    ) -> Submission:
        assert submission_id == SUBMISSION_ID
        return self.submission

    def list_submissions_for_invitation(
        self,
        _context: TenantContext,
        invitation_id: UUID,
    ) -> tuple[Submission, ...]:
        assert invitation_id == INVITATION_ID
        return (self.submission,)

    def save_submission(
        self,
        _context: TenantContext,
        submission: Submission,
    ) -> Submission:
        self.submission = submission
        return submission


def test_retry_exhaustion_marks_submission_failed_instead_of_leaving_it_waiting() -> None:
    repository = SubmissionRepositoryStub(
        Submission(
            submission_id=SUBMISSION_ID,
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            material_type=SubmissionMaterialType.RESUME,
            source_type=SourceType.RESUME,
            source_uri=f"tenants/{COMPANY_ID}/submissions/{SUBMISSION_ID}",
            original_filename="resume.pdf",
            content_hash="a" * 64,
            byte_size=100,
            media_type="application/pdf",
            created_at=NOW,
        )
    )
    outbox = InMemoryOutbox()
    handler = AnalysisRequestedEventHandler(
        cast(LaneBRuntime, SimpleNamespace(repository=repository)),
        AnalysisJobHandler(
            AlwaysUnavailableProcessor(),
            outbox,
            FrozenClock(NOW),
            max_attempts=1,
        ),
    )

    outcome = handler(_context(), _event())

    assert outcome.status is JobStatus.DLQ
    assert repository.submission.status is SubmissionStatus.FAILED
    assert repository.submission.failure_code == "embedding_provider_unavailable"
    assert "다시 제출" in (repository.submission.impact_summary or "")


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=APPLICANT_ID,
        request_id=SUBMISSION_ID,
        trace_id="analysis-event-handler",
    )


def _event() -> OutboxEvent:
    return OutboxEvent(
        outbox_event_id=UUID("00000000-0000-7000-8000-000000000005"),
        company_id=COMPANY_ID,
        aggregate_type="submission",
        aggregate_id=SUBMISSION_ID,
        aggregate_version=1,
        event_type="submission.analysis_requested",
        event_version=1,
        payload={
            "submission_id": str(SUBMISSION_ID),
            "analysis_version": 1,
            "source_type": SourceType.RESUME.value,
            "source_object_id": str(SUBMISSION_ID),
        },
        idempotency_key=f"analysis-request-{SUBMISSION_ID}",
        trace_id="analysis-event-handler",
        occurred_at=NOW,
    )
