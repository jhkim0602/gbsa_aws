from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from interview_evidence.company_management.adapters.applicant_session import (
    ApplicantSessionAdapter,
)
from interview_evidence.company_management.adapters.company_auth import CompanyAuthAdapter
from interview_evidence.company_management.api import (
    create_lane_a_runtime,
)
from interview_evidence.company_management.api import (
    create_sql_repository as create_company_repository,
)
from interview_evidence.company_management.api.applicant_routes import (
    create_applicant_router as create_company_applicant_router,
)
from interview_evidence.company_management.api.company_routes import (
    create_company_router as create_hiring_router,
)
from interview_evidence.company_management.application.company_service import (
    CompanyManagementPublic,
)
from interview_evidence.company_management.application.deletion_targets import (
    CompanyDeletionTargets,
    InMemoryCompanyTargetDeleter,
)
from interview_evidence.company_management.workers.invitation_email import (
    InvitationEmailHandler,
)
from interview_evidence.integration.company_submission import (
    CompanySubmissionAuthorization,
)
from interview_evidence.integration.interview_reporting import (
    InterviewReportingBoundary,
)
from interview_evidence.integration.privacy_deletion import PrivacyDeletionBoundary
from interview_evidence.integration.production_deletion import (
    HotViewTargetVerifier,
    ObjectTargetVerifier,
    ProductionInterviewTargetDeleter,
    ProductionSubmissionTargetDeleter,
    RelationalTargetVerifier,
    SearchTargetVerifier,
)
from interview_evidence.integration.reporting_company import ReportingCompanyBoundary
from interview_evidence.integration.submission_interview import (
    SubmissionInterviewBoundary,
)
from interview_evidence.interview_engine.adapters.recent_context import RecentContextPort
from interview_evidence.interview_engine.api import (
    create_lane_c_runtime,
)
from interview_evidence.interview_engine.api import (
    create_sql_repository as create_interview_repository,
)
from interview_evidence.interview_engine.api.applicant_routes import (
    create_applicant_interview_router,
)
from interview_evidence.interview_engine.api.websocket import (
    create_interview_websocket_router,
)
from interview_evidence.interview_engine.application.deletion_targets import (
    InterviewDeletionTargets,
)
from interview_evidence.interview_engine.application.idempotency import (
    SqlAlchemyIdempotencyStore,
)
from interview_evidence.interview_engine.application.public import InterviewEnginePublic
from interview_evidence.main import LocalRuntime, create_app
from interview_evidence.reporting.adapters.playback import ScopedPlaybackLocator
from interview_evidence.reporting.api import (
    create_lane_d_runtime,
)
from interview_evidence.reporting.api import (
    create_sql_repository as create_reporting_repository,
)
from interview_evidence.reporting.api.company_routes import (
    create_company_router as create_reporting_router,
)
from interview_evidence.reporting.application.deletion_service import DeletionService
from interview_evidence.reporting.application.evidence_service import EvidenceService
from interview_evidence.reporting.application.public import ReportingPublic
from interview_evidence.reporting.application.transcript_service import TranscriptService
from interview_evidence.shared.aws_clients.ports import (
    AIModel,
    ConsumableQueue,
    EmailSender,
    ObjectStorage,
    SpeechToText,
    TextToSpeech,
)
from interview_evidence.shared.database import RequestScopedDatabase
from interview_evidence.shared.ids import SystemClock
from interview_evidence.shared.operations import (
    DependencyReadiness,
    MetricRecorder,
    NullMetricRecorder,
    ReadinessChecker,
)
from interview_evidence.shared.persistence import (
    SQLApplicantSessionStore,
    SQLAuditAppender,
    SQLCommandIdempotencyStore,
    SQLOutbox,
    SQLUploadIntentStore,
)
from interview_evidence.shared.security.principals import (
    ApplicantPrincipal,
    CompanyPrincipal,
    PrincipalProvider,
)
from interview_evidence.submission_analysis.adapters.search import SearchIndex
from interview_evidence.submission_analysis.api import (
    create_lane_b_runtime,
)
from interview_evidence.submission_analysis.api import (
    create_sql_repository as create_submission_repository,
)
from interview_evidence.submission_analysis.api.applicant_routes import (
    create_applicant_submission_router,
)
from interview_evidence.submission_analysis.application.deletion_targets import (
    SubmissionDeletionTargets,
)
from interview_evidence.submission_analysis.application.public import (
    SubmissionAnalysisPublic,
)
from interview_evidence.submission_analysis.application.retrieval import (
    HybridRetrievalConfig,
    HybridRetriever,
)
from interview_evidence.workers.reporting.media import MediaPostProcessor
from interview_evidence.workers.reporting.report import ReportGenerator


def create_production_runtime(
    environment: Mapping[str, str],
    *,
    principal_provider: PrincipalProvider | None = None,
    object_storage: ObjectStorage | None = None,
    media_storage: ObjectStorage | None = None,
    email_sender: EmailSender | None = None,
    recent_context: RecentContextPort | None = None,
    search_index: SearchIndex | None = None,
    database: RequestScopedDatabase | None = None,
    metrics: MetricRecorder | None = None,
    readiness: ReadinessChecker | None = None,
    queues: Mapping[str, ConsumableQueue] | None = None,
    model: AIModel | None = None,
    speech_to_text: SpeechToText | None = None,
    text_to_speech: TextToSpeech | None = None,
) -> LocalRuntime:
    aws = None
    if (
        principal_provider is None
        or object_storage is None
        or email_sender is None
        or recent_context is None
        or search_index is None
        or model is None
        or speech_to_text is None
        or text_to_speech is None
    ):
        from interview_evidence.runtime.aws import create_aws_runtime_dependencies

        aws = create_aws_runtime_dependencies(environment)
        principal_provider = principal_provider or aws.principal_provider
        object_storage = object_storage or aws.object_storage
        media_storage = media_storage or aws.media_storage
        email_sender = email_sender or aws.email_sender
        recent_context = recent_context or aws.recent_context
        search_index = search_index or aws.search_index
        model = model or aws.model
        speech_to_text = speech_to_text or aws.speech_to_text
        text_to_speech = text_to_speech or aws.text_to_speech
        database_url = aws.database_url
    else:
        database_url = environment.get("DATABASE_URL", "").strip()
    media_storage = media_storage or object_storage
    if database is None:
        if not database_url:
            raise RuntimeError("production DATABASE_URL is required")
        database = RequestScopedDatabase(database_url)
    active_principal_provider = principal_provider
    active_metrics = metrics or (aws.metrics if aws is not None else NullMetricRecorder())

    clock = SystemClock()
    session = database.session
    audit = SQLAuditAppender(session)
    outbox = SQLOutbox(session)
    resource_idempotency = SQLCommandIdempotencyStore(session)
    interview_idempotency = SqlAlchemyIdempotencyStore(session)
    applicant_sessions = ApplicantSessionAdapter(
        clock=clock,
        store=SQLApplicantSessionStore(session),
    )

    lane_a = create_lane_a_runtime(
        principal_provider=active_principal_provider,
        repository=create_company_repository(session),
        audit=audit,
        clock=clock,
        sessions=applicant_sessions,
        outbox=outbox,
        idempotency=resource_idempotency,
        email_sender=email_sender,
    )

    class RuntimePrincipalProvider:
        def get_company_principal(self, credential: str) -> CompanyPrincipal:
            return active_principal_provider.get_company_principal(credential)

        def get_applicant_principal(self, credential: str) -> ApplicantPrincipal:
            return applicant_sessions.get_applicant_principal(credential)

    principals = RuntimePrincipalProvider()
    company_public = CompanyManagementPublic(
        lane_a.repository,
        clock,
        deletion_targets=CompanyDeletionTargets(
            lane_a.repository,
            lane_a.outbox,
            clock,
        ),
        target_deleter=InMemoryCompanyTargetDeleter(
            lane_a.repository,
            audit,
        ),
    )
    company_submission = CompanySubmissionAuthorization(company_public)
    lane_b = create_lane_b_runtime(
        principal_provider=principals,
        authorization=company_submission,
        repository=create_submission_repository(session),
        object_storage=object_storage,
        audit=audit,
        clock=clock,
        outbox=outbox,
        idempotency=resource_idempotency,
        upload_intents=SQLUploadIntentStore(session),
    )
    submission_public = SubmissionAnalysisPublic(
        repository=lane_b.repository,
        retriever=HybridRetriever(search_index, HybridRetrievalConfig()),
        deletion_targets=SubmissionDeletionTargets(lane_b.repository),
        target_deleter=ProductionSubmissionTargetDeleter(
            repository=cast(RelationalTargetVerifier, lane_b.repository),
            object_storage=cast(ObjectTargetVerifier, object_storage),
            search_index=cast(SearchTargetVerifier, search_index),
            metrics=active_metrics,
        ),
    )
    submission_interview = SubmissionInterviewBoundary(submission_public, company_public)
    lane_c = create_lane_c_runtime(
        principal_provider=principals,
        authorization=submission_interview,
        repository=create_interview_repository(session),
        object_storage=media_storage,
        audit=audit,
        clock=clock,
        hot_view=recent_context,
        outbox=outbox,
        idempotency=interview_idempotency,
        plan_provider=submission_interview,
        retrieval_provider=submission_interview,
        model=model,
        speech_to_text=speech_to_text,
        text_to_speech=text_to_speech,
    )
    base_lane_d = create_lane_d_runtime(
        principal_provider=principals,
        repository=create_reporting_repository(session),
        audit=audit,
        clock=clock,
    )
    interview_public = InterviewEnginePublic(
        repository=lane_c.repository,
        deletion_targets=InterviewDeletionTargets(lane_c.repository),
        target_deleter=ProductionInterviewTargetDeleter(
            repository=cast(RelationalTargetVerifier, lane_c.repository),
            object_storage=cast(ObjectTargetVerifier, media_storage),
            hot_view=cast(HotViewTargetVerifier, recent_context),
            metrics=active_metrics,
        ),
    )
    base_reporting_public = ReportingPublic(
        repository=base_lane_d.repository,
        deletion_service=base_lane_d.deletion_service,
    )
    privacy_deletion = PrivacyDeletionBoundary(
        company=company_public,
        submission=submission_public,
        interview=interview_public,
        reporting=base_reporting_public,
        clock=clock,
        object_storage=media_storage,
        metrics=active_metrics,
    )
    deletion_service = DeletionService(
        base_lane_d.repository,
        enumerators=(privacy_deletion.enumerate,),
        executors={
            "A": privacy_deletion.execute_company,
            "B": privacy_deletion.execute_submission,
            "C": privacy_deletion.execute_interview,
            "D": privacy_deletion.execute_reporting,
        },
    )
    lane_d = create_lane_d_runtime(
        principal_provider=principals,
        repository=base_lane_d.repository,
        audit=audit,
        clock=clock,
        deletion_service=deletion_service,
    )
    media_processor = MediaPostProcessor(lane_d.repository)
    interview_reporting = InterviewReportingBoundary(
        interview=interview_public,
        transcript_service=TranscriptService(lane_d.repository),
        media_processor=media_processor,
    )
    reporting_public = ReportingPublic(
        repository=lane_d.repository,
        deletion_service=lane_d.deletion_service,
    )
    reporting_company = ReportingCompanyBoundary(reporting_public)

    if readiness is None:
        probes = {"database": database.healthcheck}
        for name, dependency in {
            "object_storage": object_storage,
            "media_storage": media_storage,
            "recent_context": recent_context,
            "search": search_index,
        }.items():
            probe = getattr(dependency, "healthcheck", None)
            if callable(probe):
                probes[name] = probe
        active_queues = queues or (aws.queues if aws is not None else {})
        if active_queues:
            for queue_name, queue in active_queues.items():
                probes[f"{queue_name}_queue"] = queue.healthcheck
        readiness = DependencyReadiness(probes)
    active_queues = queues or (aws.queues if aws is not None else {})

    root = create_app(
        [
            create_hiring_router(
                auth=CompanyAuthAdapter(active_principal_provider),
                company_service=lane_a.company_service,
                criteria_service=lane_a.criteria_service,
                hiring_service=lane_a.hiring_service,
                audit=audit,
                invitation_email=InvitationEmailHandler(lane_a.email_sender),
            ),
            create_company_applicant_router(
                sessions=lane_a.sessions,
                access_service=lane_a.applicant_access_service,
            ),
            create_applicant_submission_router(
                principal_provider=principals,
                authorization=company_submission,
                service=lane_b.service,
                audit=audit,
            ),
            create_applicant_interview_router(
                principal_provider=principals,
                service=lane_c.service,
                audit=audit,
            ),
            create_interview_websocket_router(
                principal_provider=principals,
                handler=lane_c.stream_handler,
                database=database,
            ),
            create_reporting_router(
                principal_provider=principals,
                repository=lane_d.repository,
                audit=audit,
                clock=clock,
                deletion_service=lane_d.deletion_service,
                playback=ScopedPlaybackLocator(),
            ),
        ],
        readiness=readiness,
    )
    root.exception_handlers.update(lane_d.app.exception_handlers)
    database.install_http_transaction_middleware(root)
    return LocalRuntime(
        app=root,
        lanes={
            "company_management": lane_a,
            "submission_analysis": lane_b,
            "interview_engine": lane_c,
            "reporting": lane_d,
        },
        boundaries={
            "company_management": company_public,
            "submission_analysis": submission_public,
            "interview_engine": interview_public,
            "reporting": reporting_public,
            "company_submission": company_submission,
            "submission_interview": submission_interview,
            "interview_reporting": interview_reporting,
            "reporting_company": reporting_company,
        },
        worker_handlers={
            "invitation_email": InvitationEmailHandler(lane_a.email_sender),
            "media_postprocess": media_processor,
            "report_generation": ReportGenerator(
                lane_d.repository,
                EvidenceService(lane_d.repository),
            ),
            "privacy_deletion": lane_d.deletion_service,
        },
        resources={
            "audit": audit,
            "clock": clock,
            "database": database,
            "outbox": outbox,
            "object_storage": object_storage,
            "search_index": search_index,
            "privacy_deletion": privacy_deletion,
            "metrics": active_metrics,
            "readiness": readiness,
            "queues": active_queues,
        },
    )
