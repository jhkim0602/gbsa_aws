from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from fastapi import APIRouter, FastAPI, Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from interview_evidence.shared.ids import new_uuid7
from interview_evidence.shared.observability import (
    bind_trace_context,
    configure_structured_logging,
    reset_trace_context,
)


def create_app(public_routers: Iterable[APIRouter] = ()) -> FastAPI:
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
    async def ready() -> dict[str, str]:
        return {"status": "ok"}

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


app = create_app()
