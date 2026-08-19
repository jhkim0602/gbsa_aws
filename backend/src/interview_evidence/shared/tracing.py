"""Distributed tracing, configured so that a span can never carry applicant text.

The infrastructure side of this already existed and produced nothing: the observability module
defines an X-Ray sampling rule and an error group, and the compute module can run an ADOT
collector sidecar, but without a producer in the process the X-Ray console shows "no data" --
which is indistinguishable from no traffic and hides exactly the latency questions traces are
for.

Two things are deliberate here.

`OTEL_EXPORTER_OTLP_ENDPOINT` is what turns tracing on. It is set by the task definition only
when the sidecar exists, so a process without a collector installs nothing rather than
exporting spans that fail to send on every request and fill the log with connection errors
that read as a networking fault.

Every attribute that could hold free text is removed before a span is exported. FastAPI's
instrumentation records `http.url` and `http.target` including the query string, so an endpoint
that ever takes a free-text parameter would put it in a span, and a span goes to X-Ray, which
is a log by another name. The query string is stripped in a request hook rather than trusted to
stay harmless, because the safety of the default depends on which parameters the API happens to
accept today. What is left is the route template, the status, the duration, and opaque ids.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI

# The paths the load balancer polls. Excluded because a health check every few seconds is the
# overwhelming majority of spans by count and carries no information: it would consume the
# sampling reservoir and bury real requests in the console.
_EXCLUDED_URLS = "health/live,health/ready"

# Recorded by FastAPI's instrumentation with the query string attached.
_URL_ATTRIBUTES = ("http.url", "http.target", "url.full", "url.query")


def tracing_enabled(environment: Mapping[str, str] | None = None) -> bool:
    values = os.environ if environment is None else environment
    endpoint = values.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    return endpoint != ""


def current_trace_id() -> str | None:
    """The active trace id as X-Ray formats it, or None when nothing is tracing.

    Structured log lines carry this so a log and a trace of the same request can be found from
    each other. Returned in X-Ray's own `1-<8 hex>-<24 hex>` form rather than the raw 32 hex
    digits, because that is what the console searches by; the raw id finds nothing.
    """
    try:
        from opentelemetry import trace
    except ModuleNotFoundError:
        return None

    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return None
    identifier = format(context.trace_id, "032x")
    return f"1-{identifier[:8]}-{identifier[8:]}"


def _strip_query_string(span: Any, _scope: Any) -> None:
    """Drop the query string from a server span before anything reads it."""
    if span is None or not span.is_recording():
        return
    attributes = span.attributes or {}
    for name in _URL_ATTRIBUTES:
        value = attributes.get(name)
        if not isinstance(value, str):
            continue
        if name == "url.query":
            span.set_attribute(name, "")
        elif "?" in value:
            span.set_attribute(name, value.split("?", 1)[0])


def _install_provider(service_name: str, values: Mapping[str, str]) -> None:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
    from opentelemetry.propagate import set_global_textmap
    from opentelemetry.propagators.aws import AwsXRayPropagator
    from opentelemetry.sdk.extension.aws.trace import AwsXRayIdGenerator
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # X-Ray rejects the W3C random trace id: its first 32 bits must be the epoch seconds the
    # trace began. With the default generator every segment is dropped at ingestion, and the
    # only symptom is an empty console.
    provider = TracerProvider(
        id_generator=AwsXRayIdGenerator(),
        resource=Resource.create(
            {
                "service.name": values.get("OTEL_SERVICE_NAME", service_name),
                "deployment.environment": values.get("APP_ENVIRONMENT", "local"),
            }
        ),
    )
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    # The collector and X-Ray both speak the `X-Amzn-Trace-Id` header, and the load balancer
    # already adds one. Without this propagator the API starts a new trace per request and the
    # balancer's id never joins up with it.
    set_global_textmap(AwsXRayPropagator())

    # Bedrock, S3, SQS and DynamoDB calls become child spans, which is the whole point: the
    # question a trace answers here is which dependency a slow interview turn was waiting on.
    # Botocore's instrumentation records operation names and request ids, not payloads.
    #
    # `instrument` is untyped upstream, so mypy cannot see the call as safe.
    BotocoreInstrumentor().instrument()  # type: ignore[no-untyped-call]


def configure_tracing(
    application: FastAPI,
    *,
    environment: Mapping[str, str] | None = None,
) -> bool:
    """Install the tracer and instrument the application. Returns whether it was enabled."""
    if not tracing_enabled(environment):
        return False

    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    values = dict(os.environ if environment is None else environment)
    _install_provider("interview-evidence-api", values)
    FastAPIInstrumentor.instrument_app(
        application,
        server_request_hook=_strip_query_string,
        excluded_urls=_EXCLUDED_URLS,
    )
    return True


def configure_worker_tracing(environment: Mapping[str, str] | None = None) -> bool:
    """The same tracer without the HTTP server half, for the worker process.

    The worker runs the same collector sidecar and makes the same Bedrock, S3, SQS and DynamoDB
    calls, so leaving it uninstrumented would show an interview's analysis stage as a gap in the
    trace between the API enqueuing a job and a report appearing. It serves no HTTP, so there is
    no server span and no query string to strip.
    """
    if not tracing_enabled(environment):
        return False

    values = dict(os.environ if environment is None else environment)
    _install_provider("interview-evidence-worker", values)
    return True
