from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.messaging.outbox import InMemoryOutbox
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.domain.submission import SourceType
from interview_evidence.workers.analysis.handlers import (
    AnalysisJob,
    AnalysisJobHandler,
    AnalysisResult,
    JobStatus,
    RetryableAnalysisError,
)

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SUBMISSION_ID = UUID("00000000-0000-7000-8000-000000000002")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000003")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


class SequenceProcessor:
    def __init__(self, outcomes: list[AnalysisResult | Exception]) -> None:
        self.outcomes = outcomes
        self.calls = 0

    def process(
        self,
        context: TenantContext,
        job: AnalysisJob,
    ) -> AnalysisResult:
        del context, job
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=SUBMISSION_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000004"),
        trace_id="partial-analysis",
    )


def job(key: str = "analysis-job-0001") -> AnalysisJob:
    return AnalysisJob(
        submission_id=SUBMISSION_ID,
        invitation_id=INVITATION_ID,
        applicant_id=UUID("00000000-0000-7000-8000-000000000005"),
        analysis_version=1,
        source_type=SourceType.PDF,
        source_object_id=UUID("00000000-0000-7000-8000-000000000006"),
        idempotency_key=key,
    )


def test_retryable_failure_moves_to_dlq_after_bounded_attempts() -> None:
    processor = SequenceProcessor(
        [
            RetryableAnalysisError("textract_throttled"),
            RetryableAnalysisError("textract_throttled"),
        ]
    )
    handler = AnalysisJobHandler(
        processor,
        InMemoryOutbox(),
        FrozenClock(NOW),
        max_attempts=2,
    )

    first = handler.handle(context(), job())
    second = handler.handle(context(), job())

    assert first.status is JobStatus.RETRYING
    assert second.status is JobStatus.DLQ
    assert second.failure_code == "textract_throttled"
    assert processor.calls == 2


def test_partial_result_is_successful_idempotent_and_emits_status_event() -> None:
    processor = SequenceProcessor(
        [
            AnalysisResult(
                status=JobStatus.PARTIAL,
                analysis_id=UUID("00000000-0000-7000-8000-000000000010"),
                impact_code="git_fetch_failed",
            )
        ]
    )
    outbox = InMemoryOutbox()
    handler = AnalysisJobHandler(
        processor,
        outbox,
        FrozenClock(NOW),
        max_attempts=3,
    )

    first = handler.handle(context(), job("analysis-job-partial"))
    duplicate = handler.handle(context(), job("analysis-job-partial"))

    assert first.status is JobStatus.PARTIAL
    assert duplicate == first
    assert processor.calls == 1
    assert outbox.pending()[0].event_type == "submission.analysis_completed"
    assert outbox.pending()[0].payload["status"] == "partial"
