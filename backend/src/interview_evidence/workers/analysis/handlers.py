from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from interview_evidence.shared.ids import Clock, new_uuid7
from interview_evidence.shared.messaging.outbox import InMemoryOutbox, OutboxEvent
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.submission_analysis.domain.submission import SourceType


class RetryableAnalysisError(RuntimeError):
    pass


class NonRetryableAnalysisError(RuntimeError):
    pass


class JobStatus(StrEnum):
    RETRYING = "retrying"
    READY = "ready"
    PARTIAL = "partial"
    FAILED = "failed"
    DLQ = "dlq"


@dataclass(frozen=True, slots=True)
class AnalysisJob:
    submission_id: UUID
    invitation_id: UUID
    applicant_id: UUID
    analysis_version: int
    source_type: SourceType
    source_object_id: UUID
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    status: JobStatus
    analysis_id: UUID | None
    impact_code: str | None = None


@dataclass(frozen=True, slots=True)
class JobOutcome:
    status: JobStatus
    attempts: int
    analysis_id: UUID | None
    failure_code: str | None = None


class AnalysisProcessor(Protocol):
    def process(self, context: TenantContext, job: AnalysisJob) -> AnalysisResult: ...


class AnalysisJobHandler:
    def __init__(
        self,
        processor: AnalysisProcessor,
        outbox: InMemoryOutbox,
        clock: Clock,
        *,
        max_attempts: int,
    ) -> None:
        self._processor = processor
        self._outbox = outbox
        self._clock = clock
        self._max_attempts = max_attempts
        self._attempts: dict[tuple[UUID, str], int] = {}
        self._final: dict[tuple[UUID, str], JobOutcome] = {}

    def handle(
        self,
        context: TenantContext,
        job: AnalysisJob,
    ) -> JobOutcome:
        key = (context.company_id, job.idempotency_key)
        existing = self._final.get(key)
        if existing is not None:
            return existing
        attempts = self._attempts.get(key, 0) + 1
        self._attempts[key] = attempts
        try:
            result = self._processor.process(context, job)
        except RetryableAnalysisError as error:
            code = str(error)
            if attempts < self._max_attempts:
                return JobOutcome(
                    status=JobStatus.RETRYING,
                    attempts=attempts,
                    analysis_id=None,
                    failure_code=code,
                )
            outcome = JobOutcome(
                status=JobStatus.DLQ,
                attempts=attempts,
                analysis_id=None,
                failure_code=code,
            )
            self._final[key] = outcome
            self._emit(context, job, outcome)
            return outcome
        except NonRetryableAnalysisError as error:
            outcome = JobOutcome(
                status=JobStatus.FAILED,
                attempts=attempts,
                analysis_id=None,
                failure_code=str(error),
            )
            self._final[key] = outcome
            self._emit(context, job, outcome)
            return outcome

        outcome = JobOutcome(
            status=result.status,
            attempts=attempts,
            analysis_id=result.analysis_id,
            failure_code=result.impact_code,
        )
        if result.status is not JobStatus.RETRYING:
            self._final[key] = outcome
            self._emit(context, job, outcome)
        return outcome

    def _emit(
        self,
        context: TenantContext,
        job: AnalysisJob,
        outcome: JobOutcome,
    ) -> None:
        self._outbox.append(
            OutboxEvent(
                outbox_event_id=new_uuid7(self._clock.now()),
                company_id=context.company_id,
                aggregate_type="submission",
                aggregate_id=job.submission_id,
                aggregate_version=job.analysis_version,
                event_type="submission.analysis_completed",
                event_version=1,
                payload={
                    "invitation_id": str(job.invitation_id),
                    "submission_id": str(job.submission_id),
                    "analysis_id": (
                        str(outcome.analysis_id) if outcome.analysis_id is not None else None
                    ),
                    "status": outcome.status.value,
                    "impact_code": outcome.failure_code,
                },
                idempotency_key=f"analysis-completed-{job.idempotency_key}",
                trace_id=context.trace_id,
                occurred_at=self._clock.now(),
            )
        )
