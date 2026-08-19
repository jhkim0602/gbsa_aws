from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, cast
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
from interview_evidence.reporting.api import LaneDRuntime
from interview_evidence.reporting.application.assessment_service import CriterionAssessor
from interview_evidence.reporting.application.deletion_service import DeletionService
from interview_evidence.reporting.application.evidence_service import EvidenceService
from interview_evidence.shared.aws_clients.ports import ConsumableQueue
from interview_evidence.shared.database import RequestScopedDatabase
from interview_evidence.shared.ids import Clock, new_uuid7
from interview_evidence.shared.messaging.outbox import Outbox, OutboxEvent
from interview_evidence.shared.messaging.worker import (
    EventHandler,
    MessageConsumer,
    OutboxDispatcher,
    ProcessedMessageStore,
)
from interview_evidence.shared.operations import MetricRecorder, NullMetricRecorder
from interview_evidence.shared.persistence import SQLProcessedMessageStore
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.shared.tracing import configure_worker_tracing
from interview_evidence.submission_analysis.adapters.search import SearchIndex
from interview_evidence.submission_analysis.api import LaneBRuntime
from interview_evidence.workers.analysis.document_extract import DocumentExtractionAdapter
from interview_evidence.workers.analysis.event_handler import (
    AnalysisRequestedEventHandler,
)
from interview_evidence.workers.analysis.git_fetch import (
    BoundedGitFetcher,
    GitFetchLimits,
    GitHubPublicTransport,
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
        outbox: Outbox,
        clock: Clock,
    ) -> None:
        self._interview = interview
        self._reporting = reporting
        self._outbox = outbox
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
        projection = self._reporting.project_completed_session(
            context,
            session_id=session_id,
            turn_ranges=ranges,
            occurred_at=self._clock.now(),
        )
        occurred_at = self._clock.now()
        self._outbox.append(
            OutboxEvent(
                outbox_event_id=new_uuid7(occurred_at),
                company_id=context.company_id,
                aggregate_type="interview_session",
                aggregate_id=session_id,
                aggregate_version=event.aggregate_version,
                event_type="report.generation_requested",
                event_version=1,
                payload={
                    "interview_session_id": str(session_id),
                    "report_version": "report-v1",
                    "competency_model_version_id": str(projection.competency_model_version_id),
                },
                idempotency_key=f"report-generation-{session_id}",
                trace_id=context.trace_id,
                occurred_at=occurred_at,
            )
        )
        return projection


class InterviewCompletedEventHandler:
    def __init__(self, outbox: Outbox, clock: Clock) -> None:
        self._outbox = outbox
        self._clock = clock

    def __call__(self, context: TenantContext, event: OutboxEvent) -> object:
        session_id = UUID(str(event.payload["interview_session_id"]))
        occurred_at = self._clock.now()
        requested = OutboxEvent(
            outbox_event_id=new_uuid7(occurred_at),
            company_id=context.company_id,
            aggregate_type="interview_session",
            aggregate_id=session_id,
            aggregate_version=event.aggregate_version,
            event_type="media.postprocess_requested",
            event_version=1,
            payload={
                "interview_session_id": str(session_id),
                "ordered_chunk_set_id": f"session-{session_id}-verified",
                "output_profile_version": "hls-v1",
            },
            idempotency_key=f"media-postprocess-{session_id}",
            trace_id=context.trace_id,
            occurred_at=occurred_at,
        )
        self._outbox.append(requested)
        return requested


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
        final_turns = self._interview.list_final_turns(context, session_id=session_id)
        turns = tuple(turn for turn in final_turns if turn.speaker.value == "applicant")
        questions = _questions_by_answer(final_turns)
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
                criterion_name=criterion_item.name,
                criterion_text=criterion_item.description,
                question=questions.get(turn.turn_id, ""),
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
            interview_level=criterion.interview_level,
        )


class _TurnLike(Protocol):
    """The three fields pairing needs, so this helper is testable without a live Lane C."""

    @property
    def turn_id(self) -> UUID: ...

    @property
    def speaker(self) -> _SpeakerLike: ...

    @property
    def text(self) -> str | None: ...


class _SpeakerLike(Protocol):
    @property
    def value(self) -> str: ...


def _questions_by_answer(turns: Sequence[_TurnLike]) -> dict[UUID, str]:
    """Pair each applicant answer with the question it followed.

    Turns arrive in session order, so the interviewer turn most recently before an answer
    is the one it answers. The scorer needs this: the same answer is strong for one
    question and evasive for another, and judging it without the question asked would
    penalise a candidate for being exactly as brief as we asked them to be.
    """
    paired: dict[UUID, str] = {}
    asked = ""
    for turn in turns:
        if turn.speaker.value == "interviewer":
            asked = turn.text or asked
        elif turn.speaker.value == "applicant":
            paired[turn.turn_id] = asked
    return paired


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
    metrics: MetricRecorder | None = None,
) -> WorkerRuntime:
    active_metrics = metrics or NullMetricRecorder()
    consumers = tuple(
        MessageConsumer(
            consumer_name=f"{queue_name}-worker",
            queue_name=queue_name,
            queue=queue,
            processed=processed,
            handlers={
                event_type: handlers[event_type]
                for event_type, routed_queue in EVENT_QUEUE_ROUTING.items()
                if routed_queue == queue_name and event_type in handlers
            },
            clock=clock,
            metrics=active_metrics,
        )
        for queue_name, queue in queues.items()
    )
    return WorkerRuntime(
        dispatcher=OutboxDispatcher(
            outbox=outbox,
            queues=queues,
            routing=EVENT_QUEUE_ROUTING,
            metrics=active_metrics,
        ),
        consumers=consumers,
        database=database,
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
        media_storage=aws.media_storage,
        email_sender=aws.email_sender,
        recent_context=aws.recent_context,
        search_index=aws.search_index,
        database=database,
        metrics=aws.metrics,
        queues=aws.queues,
        model=aws.model,
        speech_to_text=aws.speech_to_text,
        text_to_speech=aws.text_to_speech,
    )
    search_index = cast(SearchIndex, runtime.resources["search_index"])
    outbox = cast(Outbox, runtime.resources["outbox"])
    clock = cast(Clock, runtime.resources["clock"])
    metrics = cast(MetricRecorder, runtime.resources["metrics"])
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
            search_index=search_index,
            text_embedder=aws.embedder,
            strategy_model=aws.model,
            axis_provider=CompanyAnalysisAxisProvider(company),
            outbox=outbox,
            clock=clock,
            git_fetcher=BoundedGitFetcher(
                GitHubPublicTransport(token=environment.get("GITHUB_TOKEN")),
                GitFetchLimits(),
            ),
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
            "interview.completed": InterviewCompletedEventHandler(
                outbox,
                clock,
            ),
            "media.postprocess_requested": MediaRequestedEventHandler(
                interview,
                reporting_boundary,
                outbox,
                clock,
            ),
            "report.generation_requested": ReportRequestedEventHandler(
                company=company,
                interview=interview,
                reporting=lane_d,
                generator=ReportGenerator(
                    lane_d.repository,
                    EvidenceService(lane_d.repository),
                    CriterionAssessor(aws.model),
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
        metrics=metrics,
    )


def create_environment_worker_runtime(
    environment: Mapping[str, str] | None = None,
) -> WorkerRuntime:
    active_environment = dict(os.environ if environment is None else environment)
    # A no-op unless the task definition set an OTLP endpoint, which it does only when the ADOT
    # sidecar is running. Installed here rather than in `worker.main` so that every entry point
    # into a worker runtime gets it.
    configure_worker_tracing(active_environment)
    return create_production_worker_runtime(active_environment)
