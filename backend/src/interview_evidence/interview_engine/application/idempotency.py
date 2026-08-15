from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from hashlib import sha256
from importlib import import_module
from typing import Any, Protocol, TypeVar, cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import JSON, DateTime, String, Uuid, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from interview_evidence.interview_engine.repositories.postgres import Base
from interview_evidence.shared.tenant import TenantContext, require_tenant_context

ResultT = TypeVar("ResultT")
_ALLOWED_RESULT_MODULE_PREFIX = "interview_evidence.interview_engine."


class IdempotencyConflict(ValueError):
    pass


class IdempotencyStore(Protocol):
    def execute(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        operation: str,
        idempotency_key: str,
        request_payload: Mapping[str, Any],
        execute: Callable[[], ResultT],
        occurred_at: datetime,
    ) -> ResultT: ...


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    company_id: UUID
    session_id: UUID
    operation: str
    idempotency_key: str
    request_digest: str
    result: object
    occurred_at: datetime


def _request_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._records: dict[tuple[UUID, UUID, str, str], IdempotencyRecord] = {}

    def execute(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        operation: str,
        idempotency_key: str,
        request_payload: Mapping[str, Any],
        execute: Callable[[], ResultT],
        occurred_at: datetime,
    ) -> ResultT:
        tenant = require_tenant_context(context)
        if len(idempotency_key) < 8:
            raise ValueError("idempotency key is too short")
        scope = (tenant.company_id, session_id, operation, idempotency_key)
        digest = _request_digest(request_payload)
        existing = self._records.get(scope)
        if existing is not None:
            if existing.request_digest != digest:
                raise IdempotencyConflict("idempotency key was used with a different request")
            return cast(ResultT, deepcopy(existing.result))

        result = execute()
        self._records[scope] = IdempotencyRecord(
            company_id=tenant.company_id,
            session_id=session_id,
            operation=operation,
            idempotency_key=idempotency_key,
            request_digest=digest,
            result=deepcopy(result),
            occurred_at=occurred_at,
        )
        return result


class InterviewCommandResultRow(Base):
    __tablename__ = "interview_command_results"

    company_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    interview_session_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    operation: Mapped[str] = mapped_column(String(100), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    request_digest: Mapped[str] = mapped_column(String(64))
    result_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class JsonMappingIdempotencyStore:
    """Durable store for command handlers whose public result is JSON-shaped."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def execute(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        operation: str,
        idempotency_key: str,
        request_payload: Mapping[str, Any],
        execute: Callable[[], Mapping[str, Any]],
        occurred_at: datetime,
    ) -> dict[str, Any]:
        tenant = require_tenant_context(context)
        digest = _request_digest(request_payload)
        existing = self._session.scalar(
            select(InterviewCommandResultRow).where(
                InterviewCommandResultRow.company_id == tenant.company_id,
                InterviewCommandResultRow.interview_session_id == session_id,
                InterviewCommandResultRow.operation == operation,
                InterviewCommandResultRow.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.request_digest != digest:
                raise IdempotencyConflict("idempotency key was used with a different request")
            return deepcopy(existing.result_payload)

        result = deepcopy(dict(execute()))
        self._session.add(
            InterviewCommandResultRow(
                company_id=tenant.company_id,
                interview_session_id=session_id,
                operation=operation,
                idempotency_key=idempotency_key,
                request_digest=digest,
                result_payload=result,
                occurred_at=occurred_at,
            )
        )
        self._session.flush()
        return result


class SqlAlchemyIdempotencyStore:
    """Durable typed command results without unsafe pickle deserialization."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def execute(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        operation: str,
        idempotency_key: str,
        request_payload: Mapping[str, Any],
        execute: Callable[[], ResultT],
        occurred_at: datetime,
    ) -> ResultT:
        tenant = require_tenant_context(context)
        if len(idempotency_key) < 8:
            raise ValueError("idempotency key is too short")
        digest = _request_digest(request_payload)
        existing = self._session.scalar(
            select(InterviewCommandResultRow).where(
                InterviewCommandResultRow.company_id == tenant.company_id,
                InterviewCommandResultRow.interview_session_id == session_id,
                InterviewCommandResultRow.operation == operation,
                InterviewCommandResultRow.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.request_digest != digest:
                raise IdempotencyConflict("idempotency key was used with a different request")
            return cast(ResultT, _decode_result(existing.result_payload["value"]))

        result = execute()
        self._session.add(
            InterviewCommandResultRow(
                company_id=tenant.company_id,
                interview_session_id=session_id,
                operation=operation,
                idempotency_key=idempotency_key,
                request_digest=digest,
                result_payload={"value": _encode_result(result)},
                occurred_at=occurred_at,
            )
        )
        self._session.flush()
        return result


def _encode_result(value: object) -> object:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, UUID):
        return {"__kind__": "uuid", "value": str(value)}
    if isinstance(value, datetime):
        return {"__kind__": "datetime", "value": value.isoformat()}
    if isinstance(value, BaseModel):
        return {
            "__kind__": "pydantic",
            "module": value.__class__.__module__,
            "name": value.__class__.__qualname__,
            "value": value.model_dump(mode="json"),
        }
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "__kind__": "dataclass",
            "module": value.__class__.__module__,
            "name": value.__class__.__qualname__,
            "value": {
                field.name: _encode_result(getattr(value, field.name))
                for field in fields(value)
            },
        }
    if isinstance(value, tuple):
        return {"__kind__": "tuple", "value": [_encode_result(item) for item in value]}
    if isinstance(value, list):
        return [_encode_result(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _encode_result(item) for key, item in value.items()}
    raise TypeError(f"unsupported interview command result type: {type(value).__name__}")


def _decode_result(value: object) -> object:
    if not isinstance(value, dict):
        if isinstance(value, list):
            return [_decode_result(item) for item in value]
        return value
    kind = value.get("__kind__")
    if kind == "uuid":
        return UUID(str(value["value"]))
    if kind == "datetime":
        return datetime.fromisoformat(str(value["value"]))
    if kind == "tuple":
        items = cast(list[object], value["value"])
        return tuple(_decode_result(item) for item in items)
    if kind in {"pydantic", "dataclass"}:
        result_type = _load_result_type(
            module_name=str(value["module"]),
            qualified_name=str(value["name"]),
        )
        raw_payload = cast(dict[str, object], value["value"])
        if kind == "pydantic":
            if not issubclass(result_type, BaseModel):
                raise TypeError("stored pydantic result type is invalid")
            return result_type.model_validate(raw_payload)
        return result_type(
            **{key: _decode_result(item) for key, item in raw_payload.items()}
        )
    return {str(key): _decode_result(item) for key, item in value.items()}


def _load_result_type(*, module_name: str, qualified_name: str) -> type[Any]:
    if not module_name.startswith(_ALLOWED_RESULT_MODULE_PREFIX):
        raise ValueError("stored interview command result type is not allowed")
    value: object = import_module(module_name)
    for name in qualified_name.split("."):
        value = getattr(value, name)
    if not isinstance(value, type):
        raise TypeError("stored interview command result does not reference a type")
    return value
