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
from interview_evidence.shared.tracing import configure_tracing, current_trace_id


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
    # No-op unless the task definition set an OTLP endpoint, which it does only when the ADOT
    # sidecar is running. Called before the middleware below so that `current_trace_id` has a
    # span to read from on the first request.
    configure_tracing(application)

    @application.middleware("http")
    async def trace_request(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = _request_id(request.headers.get("x-request-id"))
        # The sampled X-Ray trace id when there is one, so a log line and the trace of the same
        # request can be found from each other. Falls back to the header, then to the request
        # id, which is what the local runtime uses -- there is no collector there.
        trace_id = current_trace_id() or request.headers.get("x-trace-id") or request_id
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
class Runtime:
    app: FastAPI
    lanes: Mapping[str, object]
    boundaries: Mapping[str, object]
    worker_handlers: Mapping[str, object]
    resources: Mapping[str, object]


class LazyEnvironmentApplication:
    def __init__(self, *, environment: Mapping[str, str] | None = None) -> None:
        self._environment = dict(os.environ if environment is None else environment)
        self._runtime: Runtime | None = None

    def _application(self) -> FastAPI:
        if self._runtime is None:
            from interview_evidence.runtime.production import create_production_runtime

            self._runtime = create_production_runtime(self._environment)
        return self._runtime.app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self._application()(scope, receive, send)


app = LazyEnvironmentApplication()
