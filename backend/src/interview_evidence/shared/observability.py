from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from contextvars import ContextVar, Token
from typing import Any

import structlog

REDACTED = "[REDACTED]"
PROHIBITED_FIELD_NAMES = frozenset(
    {
        "access_token",
        "answer",
        "answer_text",
        "applicant_source_text",
        "authorization",
        "credential",
        "document_text",
        "password",
        "raw_token",
        "secret",
        "signed_url",
        "source_text",
        "token",
    }
)
request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
trace_id_context: ContextVar[str | None] = ContextVar("trace_id", default=None)


def normalize_field_name(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def is_prohibited_field(value: str) -> bool:
    normalized = normalize_field_name(value)
    return normalized in PROHIBITED_FIELD_NAMES or normalized.endswith(("_token", "_secret"))


def sanitize_log_event(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): REDACTED if is_prohibited_field(str(key)) else sanitize_log_event(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [sanitize_log_event(item) for item in value]
    return value


def _sanitize_processor(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> dict[str, Any]:
    sanitized = sanitize_log_event(event_dict)
    if not isinstance(sanitized, dict):
        raise TypeError("structured log event must remain a mapping")
    request_id = request_id_context.get()
    trace_id = trace_id_context.get()
    if request_id is not None:
        sanitized["request_id"] = request_id
    if trace_id is not None:
        sanitized["trace_id"] = trace_id
    return sanitized


def configure_structured_logging() -> None:
    structlog.configure(
        processors=[
            _sanitize_processor,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),
        cache_logger_on_first_use=True,
    )


def bind_trace_context(
    *,
    request_id: str,
    trace_id: str,
) -> tuple[Token[str | None], Token[str | None]]:
    return request_id_context.set(request_id), trace_id_context.set(trace_id)


def reset_trace_context(tokens: tuple[Token[str | None], Token[str | None]]) -> None:
    request_id_context.reset(tokens[0])
    trace_id_context.reset(tokens[1])
