from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from uuid import UUID

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.types import Receive, Scope, Send

from interview_evidence.shared.ids import new_uuid7
from interview_evidence.shared.observability import (
    bind_trace_context,
    configure_structured_logging,
    reset_trace_context,
)
from interview_evidence.shared.operations import ReadinessChecker
from interview_evidence.shared.security.principals import PrincipalProvider


def create_app(
    public_routers: Iterable[APIRouter] = (),
    *,
    readiness: ReadinessChecker | None = None,
) -> FastAPI:
    configure_structured_logging()
    application = FastAPI(
        title="Interview Evidence Platform",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
    )

    @application.middleware("http")
    async def trace_request(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = _request_id(request.headers.get("x-request-id"))
        trace_id = request.headers.get("x-trace-id") or request_id
        tokens = bind_trace_context(request_id=request_id, trace_id=trace_id)
        try:
            response = await call_next(request)
        finally:
            reset_trace_context(tokens)
        response.headers["x-request-id"] = request_id
        response.headers["x-trace-id"] = trace_id
        return response

    @application.get("/health/live", include_in_schema=False)
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/health/ready", include_in_schema=False)
    async def ready() -> Response:
        if readiness is None:
            return JSONResponse({"status": "ok"})
        report = readiness.check()
        return JSONResponse(
            {
                "status": report.status,
                "dependencies": dict(report.dependencies),
            },
            status_code=200 if report.ready else 503,
        )

    for router in public_routers:
        application.include_router(router)
    return application


def _request_id(candidate: str | None) -> str:
    if candidate is not None:
        try:
            return str(UUID(candidate))
        except ValueError:
            pass
    return str(new_uuid7())


@dataclass(frozen=True, slots=True)
class LocalRuntime:
    app: FastAPI
    lanes: Mapping[str, object]
    boundaries: Mapping[str, object]
    worker_handlers: Mapping[str, object]
    resources: Mapping[str, object]


def create_local_runtime(
    *,
    company_principal_provider: PrincipalProvider | None = None,
) -> LocalRuntime:
    from interview_evidence.company_management.adapters.company_auth import CompanyAuthAdapter
    from interview_evidence.company_management.api import create_lane_a_runtime
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
    from interview_evidence.integration.reporting_company import (
        ReportingCompanyBoundary,
    )
    from interview_evidence.integration.submission_interview import (
        SubmissionInterviewBoundary,
    )
    from interview_evidence.interview_engine.api import create_lane_c_runtime
    from interview_evidence.interview_engine.api.applicant_routes import (
        create_applicant_interview_router,
    )
    from interview_evidence.interview_engine.api.websocket import (
        ProtocolStreamHandler,
        create_interview_websocket_router,
    )
    from interview_evidence.interview_engine.application.deletion_targets import (
        InMemoryInterviewTargetDeleter,
        InterviewDeletionTargets,
    )
    from interview_evidence.interview_engine.application.public import InterviewEnginePublic
    from interview_evidence.reporting.adapters.playback import ScopedPlaybackLocator
    from interview_evidence.reporting.api import create_lane_d_runtime
    from interview_evidence.reporting.api.company_routes import (
        create_company_router as create_reporting_router,
    )
    from interview_evidence.reporting.application.deletion_service import DeletionService
    from interview_evidence.reporting.application.evidence_service import EvidenceService
    from interview_evidence.reporting.application.public import ReportingPublic
    from interview_evidence.reporting.application.transcript_service import TranscriptService
    from interview_evidence.shared.audit import InMemoryAuditAppender
    from interview_evidence.shared.aws_clients.ports import InMemoryObjectStorage
    from interview_evidence.shared.ids import SystemClock
    from interview_evidence.shared.security.principals import (
        ApplicantPrincipal,
        CompanyPrincipal,
        FakePrincipalProvider,
    )
    from interview_evidence.shared.tenant import TenantContext
    from interview_evidence.submission_analysis.adapters.search import InMemorySearchIndex
    from interview_evidence.submission_analysis.api import create_lane_b_runtime
    from interview_evidence.submission_analysis.api.applicant_routes import (
        create_applicant_submission_router,
    )
    from interview_evidence.submission_analysis.application.deletion_targets import (
        InMemorySubmissionTargetDeleter,
        SubmissionDeletionTargets,
    )
    from interview_evidence.submission_analysis.application.public import (
        SubmissionAnalysisPublic,
    )
    from interview_evidence.submission_analysis.application.retrieval import (
        HybridRetrievalConfig,
        HybridRetriever,
    )
    from interview_evidence.workers.analysis.handlers import (
        AnalysisJob,
        AnalysisJobHandler,
        AnalysisResult,
        JobStatus,
    )
    from interview_evidence.workers.reporting.media import MediaPostProcessor
    from interview_evidence.workers.reporting.report import ReportGenerator

    clock = SystemClock()
    audit = InMemoryAuditAppender()
    object_storage = InMemoryObjectStorage()
    company_principals = company_principal_provider or FakePrincipalProvider()
    lane_a = create_lane_a_runtime(
        principal_provider=company_principals,
        audit=audit,
        clock=clock,
    )

    class RuntimePrincipalProvider:
        def __init__(self, company_provider: PrincipalProvider) -> None:
            self._company_provider = company_provider

        def get_company_principal(self, credential: str) -> CompanyPrincipal:
            return self._company_provider.get_company_principal(credential)

        def get_applicant_principal(self, credential: str) -> ApplicantPrincipal:
            return lane_a.sessions.get_applicant_principal(credential)

    principals = RuntimePrincipalProvider(company_principals)
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
        object_storage=object_storage,
        audit=audit,
        clock=clock,
    )
    search_index = InMemorySearchIndex()
    submission_public = SubmissionAnalysisPublic(
        repository=lane_b.repository,
        retriever=HybridRetriever(search_index, HybridRetrievalConfig()),
        deletion_targets=SubmissionDeletionTargets(lane_b.repository),
        target_deleter=InMemorySubmissionTargetDeleter(
            repository=lane_b.repository,
            storage=lane_b.storage,
            search_index=search_index,
        ),
    )
    submission_interview = SubmissionInterviewBoundary(submission_public)
    lane_c = create_lane_c_runtime(
        principal_provider=principals,
        authorization=submission_interview,
        object_storage=object_storage,
        audit=audit,
        clock=clock,
    )
    base_lane_d = create_lane_d_runtime(
        principal_provider=principals,
        audit=audit,
        clock=clock,
    )

    interview_public = InterviewEnginePublic(
        repository=lane_c.repository,
        deletion_targets=InterviewDeletionTargets(lane_c.repository),
        target_deleter=InMemoryInterviewTargetDeleter(
            repository=lane_c.repository,
            hot_view=lane_c.hot_view,
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

    class LocalAnalysisProcessor:
        def process(
            self,
            _context: TenantContext,
            job: AnalysisJob,
        ) -> AnalysisResult:
            return AnalysisResult(
                status=JobStatus.READY,
                analysis_id=new_uuid7(),
                impact_code=None,
            )

    root = create_app(
        [
            create_hiring_router(
                auth=CompanyAuthAdapter(company_principals),
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
                handler=ProtocolStreamHandler(session_service=lane_c.service),
            ),
            create_reporting_router(
                principal_provider=principals,
                repository=lane_d.repository,
                audit=audit,
                clock=clock,
                deletion_service=lane_d.deletion_service,
                playback=ScopedPlaybackLocator(),
            ),
        ]
    )
    root.exception_handlers.update(lane_d.app.exception_handlers)
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
            "submission_analysis": AnalysisJobHandler(
                LocalAnalysisProcessor(),
                lane_b.outbox,
                clock,
                max_attempts=3,
            ),
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
            "outbox": lane_b.outbox,
            "company_principals": company_principals,
            "object_storage": object_storage,
            "search_index": search_index,
            "privacy_deletion": privacy_deletion,
        },
    )


class LazyEnvironmentApplication:
    def __init__(self, *, environment: Mapping[str, str] | None = None) -> None:
        self._environment = dict(os.environ if environment is None else environment)
        self._runtime: LocalRuntime | None = None

    @property
    def runtime_mode(self) -> str:
        environment = self._environment.get(
            "APP_ENVIRONMENT",
            self._environment.get("APP_ENV", "local"),
        )
        return "local" if environment == "local" else "production"

    def _application(self) -> FastAPI:
        if self._runtime is None:
            if self.runtime_mode == "local":
                self._runtime = create_local_runtime()
            elif (
                self._environment.get(
                    "APP_ENVIRONMENT",
                    self._environment.get("APP_ENV"),
                )
                == "local-production"
            ):
                from interview_evidence.runtime.local_production import (
                    create_local_production_runtime,
                )

                self._runtime = create_local_production_runtime(self._environment)
            else:
                from interview_evidence.runtime.production import create_production_runtime

                self._runtime = create_production_runtime(self._environment)
        return self._runtime.app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self._application()(scope, receive, send)


LazyLocalApplication = LazyEnvironmentApplication

app = LazyEnvironmentApplication()
