from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any, TypeVar, cast
from uuid import UUID

from sqlalchemy import JSON, DateTime, String, Uuid, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from interview_evidence.interview_engine.repositories.postgres import Base
from interview_evidence.shared.tenant import TenantContext, require_tenant_context

ResultT = TypeVar("ResultT")


class IdempotencyConflict(ValueError):
    pass


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
