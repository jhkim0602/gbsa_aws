from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from interview_evidence.shared.tracing import (
    _EXCLUDED_URLS,
    _strip_query_string,
    current_trace_id,
    tracing_enabled,
)
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def test_tracing_stays_off_without_a_collector_endpoint() -> None:
    # The endpoint is set by the task definition only when the ADOT sidecar exists. Enabled
    # without one, every span export fails and the log fills with connection errors that read
    # as a networking fault.
    assert tracing_enabled({}) is False
    assert tracing_enabled({"OTEL_EXPORTER_OTLP_ENDPOINT": "   "}) is False
    assert tracing_enabled({"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317"}) is True


def test_no_active_span_yields_no_trace_id() -> None:
    assert current_trace_id() is None


def _instrumented_client(exporter: InMemorySpanExporter) -> TestClient:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    application = FastAPI()

    @application.get("/v1/sessions/{session_id}/timeline")
    def timeline(session_id: str, cursor: str | None = None) -> dict[str, str]:
        return {"session_id": session_id}

    @application.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    FastAPIInstrumentor.instrument_app(
        application,
        tracer_provider=provider,
        server_request_hook=_strip_query_string,
        excluded_urls=_EXCLUDED_URLS,
    )
    return TestClient(application)


def _server_spans(exporter: InMemorySpanExporter) -> list[Any]:
    return [span for span in exporter.get_finished_spans() if span.kind is trace.SpanKind.SERVER]


def test_a_span_never_carries_the_query_string() -> None:
    # FastAPI's instrumentation records `http.url` and `http.target` with the query string
    # attached, and a span goes to X-Ray, which is a log by another name. The timeline endpoint
    # deliberately takes no free-text parameter for this reason, but the safety of the default
    # depends on which parameters the API happens to accept, so the hook strips it regardless.
    exporter = InMemorySpanExporter()
    client = _instrumented_client(exporter)

    client.get("/v1/sessions/abc/timeline?cursor=an-applicant-answer")

    spans = _server_spans(exporter)
    assert len(spans) == 1
    attributes = spans[0].attributes or {}
    assert attributes["http.target"] == "/v1/sessions/abc/timeline"
    assert attributes["http.url"] == "http://testserver/v1/sessions/abc/timeline"
    assert "an-applicant-answer" not in repr(dict(attributes))
    # The route template survives, because that is what a latency question is asked about.
    assert attributes["http.route"] == "/v1/sessions/{session_id}/timeline"


def test_health_checks_do_not_consume_the_sampling_reservoir() -> None:
    # The load balancer polls these every few seconds, so by count they would be almost every
    # span and would bury real requests in the console.
    exporter = InMemorySpanExporter()
    client = _instrumented_client(exporter)

    client.get("/health/live")

    assert _server_spans(exporter) == []


def test_recorded_trace_id_is_the_form_the_xray_console_searches_by() -> None:
    # X-Ray searches by `1-<8 hex>-<24 hex>`; the raw 32 hex digits find nothing, so a log line
    # carrying the raw id could not be joined to its trace.
    provider = TracerProvider()
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("probe") as span:
        identifier = current_trace_id()
        assert identifier is not None
        raw = format(span.get_span_context().trace_id, "032x")

    assert identifier == f"1-{raw[:8]}-{raw[8:]}"
