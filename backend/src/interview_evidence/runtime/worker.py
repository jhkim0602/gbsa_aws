from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from interview_evidence.company_management.application.company_service import (
    CompanyManagementPublic,
)
from interview_evidence.integration.company_analysis import CompanyAnalysisAxisProvider
from interview_evidence.integration.interview_reporting import (
    FinalTurnRange,
    InterviewReportingBoundary,
)
from interview_evidence.interview_engine.application.public import InterviewEnginePublic
from interview_evidence.main import create_local_runtime
from interview_evidence.reporting.api import LaneDRuntime
from interview_evidence.reporting.application.deletion_service import DeletionService
from interview_evidence.reporting.application.evidence_service import EvidenceService
from interview_evidence.shared.aws_clients.ports import ConsumableQueue, InMemoryQueue
from interview_evidence.shared.database import RequestScopedDatabase
from interview_evidence.shared.ids import Clock, SystemClock
from interview_evidence.shared.messaging.outbox import Outbox, OutboxEvent
from interview_evidence.shared.messaging.worker import (
    EventHandler,
    InMemoryProcessedMessageStore,
    MessageConsumer,
    OutboxDispatcher,
    ProcessedMessageStore,
)
from interview_evidence.shared.persistence import SQLProcessedMessageStore
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.submission_analysis.api import LaneBRuntime
from interview_evidence.workers.analysis.document_extract import DocumentExtractionAdapter
from interview_evidence.workers.analysis.event_handler import (
    AnalysisRequestedEventHandler,
)
from interview_evidence.workers.analysis.handlers import AnalysisJobHandler
from interview_evidence.workers.analysis.pipeline import SubmissionAnalysisPipeline
from interview_evidence.workers.reporting.report import CriterionInput, ReportGenerator

EVENT_QUEUE_ROUTING = {
    "invitation.consent_completed": "analysis",
    "submission.analysis_requested": "analysis",
    "submission.analysis_completed": "analysis",
    "strategy.ready": "analysis",
    "interview.turn_finalized": "reporting",
    "interview.session_paused": "reporting",
    "interview.completed": "reporting",
    "media.postprocess_requested": "media",
    "report.generation_requested": "reporting",
    "report.ready": "reporting",
    "deletion.requested": "deletion",
    "deletion.target_requested": "deletion",
    "deletion.target_verified": "deletion",
    "retention.expired": "deletion",
}


@dataclass(slots=True)
class WorkerRuntime:
    dispatcher: OutboxDispatcher
    consumers: tuple[MessageConsumer, ...]
    database: RequestScopedDatabase | None = None

    def run_once(self) -> int:
        if self.database is None:
            return self._run_without_transaction()
        token = self.database.begin_scope()
        try:
            completed = self._run_without_transaction()
            self.database.session.commit()
            return completed
        except BaseException:
            self.database.session.rollback()
            raise
        finally:
            self.database.end_scope(token)

    def _run_without_transaction(self) -> int:
        completed = self.dispatcher.dispatch_once()
        for consumer in self.consumers:
            completed += consumer.consume_once(max_messages=10)
        return completed


class MediaRequestedEventHandler:
    def __init__(
        self,
        interview: InterviewEnginePublic,
        reporting: InterviewReportingBoundary,
        clock: Clock,
    ) -> None:
        self._interview = interview
        self._reporting = reporting
        self._clock = clock

    def __call__(self, context: TenantContext, event: OutboxEvent) -> object:
        session_id = UUID(str(event.payload["interview_session_id"]))
        turns = self._interview.list_final_turns(context, session_id=session_id)
        chunks = self._interview.resolve_recording_chunks(context, session_id=session_id)
        if not turns or not chunks:
            raise TimeoutError("completed session projection is not ready")
        ranges = tuple(
            FinalTurnRange(
                turn_id=turn.turn_id,
                session_start_ms=chunks[min(index, len(chunks) - 1)].session_start_ms,
                session_end_ms=chunks[min(index, len(chunks) - 1)].session_end_ms,
                confidence=0.9,
            )
            for index, turn in enumerate(turns)
        )
        return self._reporting.project_completed_session(
            context,
            session_id=session_id,
            turn_ranges=ranges,
            output_object_key=(
                f"companies/{context.company_id}/sessions/{session_id}/"
                "recording/final/v1/manifest.m3u8"
            ),
            occurred_at=self._clock.now(),
        )


class ReportRequestedEventHandler:
    def __init__(
        self,
        *,
        company: CompanyManagementPublic,
        interview: InterviewEnginePublic,
        reporting: LaneDRuntime,
        generator: ReportGenerator,
        clock: Clock,
    ) -> None:
        self._company = company
        self._interview = interview
        self._reporting = reporting
        self._generator = generator
        self._clock = clock

    def __call__(self, context: TenantContext, event: OutboxEvent) -> object:
        session_id = UUID(str(event.payload["interview_session_id"]))
        existing = self._reporting.repository.get_report_for_session(context, session_id)
        if existing is not None:
            return existing
        snapshot = self._interview.get_session_snapshot(context, session_id=session_id)
        criterion = self._company.get_criterion_version(
            context,
            snapshot.competency_model_version_id,
        )
        turns = tuple(
            turn
            for turn in self._interview.list_final_turns(context, session_id=session_id)
            if turn.speaker.value == "applicant"
        )
        transcripts = {
            segment.turn_id: segment
            for segment in self._reporting.repository.list_transcripts(context, session_id)
        }
        recording = next(
            (
                asset
                for asset in reversed(
                    self._reporting.repository.list_recording_assets(context, session_id)
                )
                if asset.asset_type == "final_video"
            ),
            None,
        )
        if recording is None or not turns:
            raise TimeoutError("report inputs are not ready")
        inputs = tuple(
            CriterionInput(
                criterion_id=criterion_item.criterion_id,
                observation="지원자의 최종 답변에서 관찰된 내용",
                answer_turn_id=turn.turn_id,
                transcript=transcripts[turn.turn_id],
                video_start_ms=transcripts[turn.turn_id].session_start_ms,
                video_end_ms=transcripts[turn.turn_id].session_end_ms,
            )
            for criterion_item, turn in zip(criterion.criteria, turns, strict=False)
            if turn.turn_id in transcripts
        )
        if not inputs:
            raise TimeoutError("report transcript inputs are not ready")
        return self._generator.generate(
            context,
            session_id=session_id,
            invitation_id=snapshot.invitation_id,
            competency_model_version_id=snapshot.competency_model_version_id,
            criteria=inputs,
            recording=recording,
            events=self._reporting.repository.list_session_events(context, session_id),
            occurred_at=self._clock.now(),
        )


class DeletionRequestedEventHandler:
    def __init__(self, service: DeletionService, clock: Clock) -> None:
        self._service = service
        self._clock = clock

    def __call__(self, context: TenantContext, event: OutboxEvent) -> object:
        if event.event_type == "retention.expired":
            return self._service.consume_retention_expired(
                context,
                invitation_id=UUID(str(event.payload["invitation_id"])),
                policy_snapshot=dict(event.payload["policy_snapshot"]),
                occurred_at=self._clock.now(),
            )
        return self._service.execute(
            context,
            request_id=UUID(str(event.payload["deletion_request_id"])),
            occurred_at=self._clock.now(),
        )


def create_worker_runtime(
    *,
    outbox: Outbox,
    queues: Mapping[str, ConsumableQueue],
    processed: ProcessedMessageStore,
    handlers: Mapping[str, EventHandler],
    clock: Clock,
    database: RequestScopedDatabase | None = None,
) -> WorkerRuntime:
    consumers = tuple(
        MessageConsumer(
            consumer_name=f"{queue_name}-worker",
            queue=queue,
            processed=processed,
            handlers={
                event_type: handlers[event_type]
                for event_type, routed_queue in EVENT_QUEUE_ROUTING.items()
                if routed_queue == queue_name and event_type in handlers
            },
            clock=clock,
        )
        for queue_name, queue in queues.items()
    )
    return WorkerRuntime(
        dispatcher=OutboxDispatcher(
            outbox=outbox,
            queues=queues,
            routing=EVENT_QUEUE_ROUTING,
        ),
        consumers=consumers,
        database=database,
    )


def create_local_worker_runtime() -> WorkerRuntime:
    runtime = create_local_runtime()
    outbox = cast(Outbox, runtime.resources["outbox"])
    queues = {
        name: InMemoryQueue()
        for name in ("analysis", "media", "reporting", "deletion")
    }
    lane_b = runtime.lanes["submission_analysis"]
    analysis_handler = runtime.worker_handlers["submission_analysis"]
    if not isinstance(lane_b, LaneBRuntime) or not isinstance(
        analysis_handler,
        AnalysisJobHandler,
    ):
        raise TypeError("local analysis worker is not configured")
    return create_worker_runtime(
        outbox=outbox,
        queues=queues,
        processed=InMemoryProcessedMessageStore(),
        handlers={
            "submission.analysis_requested": AnalysisRequestedEventHandler(
                lane_b,
                analysis_handler,
            )
        },
        clock=SystemClock(),
    )


def create_production_worker_runtime(environment: Mapping[str, str]) -> WorkerRuntime:
    from interview_evidence.runtime.aws import create_aws_runtime_dependencies
    from interview_evidence.runtime.production import create_production_runtime

    aws = create_aws_runtime_dependencies(environment)
    database = RequestScopedDatabase(aws.database_url)
    runtime = create_production_runtime(
        environment,
        principal_provider=aws.principal_provider,
        object_storage=aws.object_storage,
        email_sender=aws.email_sender,
        recent_context=aws.recent_context,
        search_index=aws.search_index,
        database=database,
    )
    outbox = cast(Outbox, runtime.resources["outbox"])
    clock = cast(Clock, runtime.resources["clock"])
    lane_b = runtime.lanes["submission_analysis"]
    company = runtime.boundaries["company_management"]
    interview = runtime.boundaries["interview_engine"]
    reporting_boundary = runtime.boundaries["interview_reporting"]
    lane_d = runtime.lanes["reporting"]
    if not isinstance(lane_b, LaneBRuntime):
        raise TypeError("production analysis runtime is invalid")
    if not isinstance(company, CompanyManagementPublic):
        raise TypeError("production company boundary is invalid")
    if not isinstance(interview, InterviewEnginePublic):
        raise TypeError("production interview boundary is invalid")
    if not isinstance(reporting_boundary, InterviewReportingBoundary):
        raise TypeError("production reporting projection is invalid")
    if not isinstance(lane_d, LaneDRuntime):
        raise TypeError("production reporting runtime is invalid")
    deletion_service = lane_d.deletion_service
    analysis_handler = AnalysisJobHandler(
        SubmissionAnalysisPipeline(
            repository=lane_b.repository,
            extractor=DocumentExtractionAdapter(
                aws.textract,
                extractor_version="textract-v1",
            ),
            search_index=aws.search_index,
            strategy_model=aws.model,
            axis_provider=CompanyAnalysisAxisProvider(company),
            outbox=outbox,
            clock=clock,
        ),
        outbox,
        clock,
        max_attempts=3,
    )
    return create_worker_runtime(
        outbox=outbox,
        queues=aws.queues,
        processed=SQLProcessedMessageStore(database.session),
        handlers={
            "submission.analysis_requested": AnalysisRequestedEventHandler(
                lane_b,
                analysis_handler,
            ),
            "media.postprocess_requested": MediaRequestedEventHandler(
                interview,
                reporting_boundary,
                clock,
            ),
            "report.generation_requested": ReportRequestedEventHandler(
                company=company,
                interview=interview,
                reporting=lane_d,
                generator=ReportGenerator(
                    lane_d.repository,
                    EvidenceService(lane_d.repository),
                ),
                clock=clock,
            ),
            "deletion.requested": DeletionRequestedEventHandler(
                deletion_service,
                clock,
            ),
            "retention.expired": DeletionRequestedEventHandler(
                deletion_service,
                clock,
            ),
        },
        clock=clock,
        database=database,
    )


def create_environment_worker_runtime(
    environment: Mapping[str, str] | None = None,
) -> WorkerRuntime:
    active_environment = dict(os.environ if environment is None else environment)
    application_environment = active_environment.get(
        "APP_ENVIRONMENT",
        active_environment.get("APP_ENV", "local"),
    )
    if application_environment == "local":
        return create_local_worker_runtime()
    return create_production_worker_runtime(active_environment)
