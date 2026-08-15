from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, Integer, String, Uuid, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from interview_evidence.company_management.adapters.applicant_session import (
    ApplicantTokenRecord,
)
from interview_evidence.shared.audit import (
    AuditAppender,
    _assert_safe_metadata,
)
from interview_evidence.shared.ids import new_uuid7
from interview_evidence.shared.messaging.outbox import (
    OutboxEvent,
    ProcessedMessage,
    PublishStatus,
)
from interview_evidence.shared.security.principals import ApplicantPrincipal
from interview_evidence.shared.tenant import TenantContext, require_tenant_context
from interview_evidence.shared.uploads import StoredUploadIntent


class Base(DeclarativeBase):
    pass


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class OutboxEventRow(Base):
    __tablename__ = "outbox_events"

    outbox_event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(100))
    aggregate_id: Mapped[UUID] = mapped_column(Uuid)
    aggregate_version: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(200))
    event_version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    trace_id: Mapped[str] = mapped_column(String(200))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    publish_status: Mapped[str] = mapped_column(String(30), default=PublishStatus.PENDING.value)
    publish_attempts: Mapped[int] = mapped_column(Integer, default=0)


class ProcessedMessageRow(Base):
    __tablename__ = "processed_messages"

    consumer_name: Mapped[str] = mapped_column(String(200), primary_key=True)
    event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    event_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(200))
    first_processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    outcome_digest: Mapped[str] = mapped_column(String(128))


class AuditEventRow(Base):
    __tablename__ = "audit_events"

    audit_event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    actor_type: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[UUID] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(String(200))
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[UUID] = mapped_column(Uuid)
    result: Mapped[str] = mapped_column(String(100))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    request_id: Mapped[UUID] = mapped_column(Uuid)
    trace_id: Mapped[str] = mapped_column(String(200))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON)


class ApplicantTokenRow(Base):
    __tablename__ = "applicant_access_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    invitation_id: Mapped[UUID] = mapped_column(Uuid)
    applicant_id: Mapped[UUID] = mapped_column(Uuid)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApplicantSessionRow(Base):
    __tablename__ = "applicant_access_sessions"

    session_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    invitation_id: Mapped[UUID] = mapped_column(Uuid)
    applicant_id: Mapped[UUID] = mapped_column(Uuid)
    session_id: Mapped[UUID] = mapped_column(Uuid, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UploadIntentRow(Base):
    __tablename__ = "submission_upload_intents"

    company_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    upload_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    invitation_id: Mapped[UUID] = mapped_column(Uuid)
    applicant_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    source_type: Mapped[str] = mapped_column(String(50))
    original_filename: Mapped[str] = mapped_column(String(512))
    media_type: Mapped[str] = mapped_column(String(200))
    byte_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    object_key: Mapped[str] = mapped_column(String(1024))
    method: Mapped[str] = mapped_column(String(20))
    url: Mapped[str] = mapped_column(String(4096))
    required_headers: Mapped[dict[str, str]] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CommandIdempotencyRow(Base):
    __tablename__ = "command_idempotency"

    company_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    operation: Mapped[str] = mapped_column(String(100), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(Uuid)


class SQLOutbox:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, event: OutboxEvent) -> OutboxEvent:
        existing = self._session.scalar(
            select(OutboxEventRow).where(OutboxEventRow.idempotency_key == event.idempotency_key)
        )
        if existing is not None:
            return self._domain(existing)
        self._session.add(
            OutboxEventRow(
                outbox_event_id=event.outbox_event_id,
                company_id=event.company_id,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                aggregate_version=event.aggregate_version,
                event_type=event.event_type,
                event_version=event.event_version,
                payload=event.payload,
                idempotency_key=event.idempotency_key,
                trace_id=event.trace_id,
                occurred_at=event.occurred_at,
                publish_status=event.publish_status.value,
                publish_attempts=event.publish_attempts,
            )
        )
        self._session.flush()
        return event

    def pending(self) -> tuple[OutboxEvent, ...]:
        rows = self._session.scalars(
            select(OutboxEventRow)
            .where(OutboxEventRow.publish_status == PublishStatus.PENDING.value)
            .order_by(OutboxEventRow.occurred_at, OutboxEventRow.outbox_event_id)
        )
        return tuple(self._domain(row) for row in rows)

    def mark_published(self, event_id: UUID) -> None:
        row = self._session.get(OutboxEventRow, event_id)
        if row is None:
            raise LookupError("outbox event not found")
        row.publish_status = PublishStatus.PUBLISHED.value
        row.publish_attempts += 1
        self._session.flush()

    @staticmethod
    def _domain(row: OutboxEventRow) -> OutboxEvent:
        return OutboxEvent(
            outbox_event_id=row.outbox_event_id,
            company_id=row.company_id,
            aggregate_type=row.aggregate_type,
            aggregate_id=row.aggregate_id,
            aggregate_version=row.aggregate_version,
            event_type=row.event_type,
            event_version=row.event_version,
            payload=row.payload,
            idempotency_key=row.idempotency_key,
            trace_id=row.trace_id,
            occurred_at=_utc(row.occurred_at),
            publish_status=PublishStatus(row.publish_status),
            publish_attempts=row.publish_attempts,
        )


class SQLProcessedMessageStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def contains(self, *, consumer_name: str, event_id: UUID, event_version: int) -> bool:
        return (
            self._session.get(
                ProcessedMessageRow,
                {
                    "consumer_name": consumer_name,
                    "event_id": event_id,
                    "event_version": event_version,
                },
            )
            is not None
        )

    def get(
        self,
        *,
        consumer_name: str,
        event_id: UUID,
        event_version: int,
    ) -> ProcessedMessage:
        row = self._session.get(
            ProcessedMessageRow,
            {
                "consumer_name": consumer_name,
                "event_id": event_id,
                "event_version": event_version,
            },
        )
        if row is None:
            raise LookupError("processed message not found")
        return ProcessedMessage(
            consumer_name=row.consumer_name,
            event_id=row.event_id,
            event_version=row.event_version,
            idempotency_key=row.idempotency_key,
            first_processed_at=_utc(row.first_processed_at),
            outcome_digest=row.outcome_digest,
        )

    def record(self, message: ProcessedMessage) -> None:
        if self.contains(
            consumer_name=message.consumer_name,
            event_id=message.event_id,
            event_version=message.event_version,
        ):
            return
        self._session.add(
            ProcessedMessageRow(
                consumer_name=message.consumer_name,
                event_id=message.event_id,
                event_version=message.event_version,
                idempotency_key=message.idempotency_key,
                first_processed_at=message.first_processed_at,
                outcome_digest=message.outcome_digest,
            )
        )
        self._session.flush()


class SQLAuditAppender(AuditAppender):
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(
        self,
        context: TenantContext,
        *,
        action: str,
        resource_type: str,
        resource_id: UUID,
        result: str,
        metadata: dict[str, Any],
    ) -> UUID:
        tenant = require_tenant_context(context)
        _assert_safe_metadata(metadata)
        event_id = new_uuid7()
        self._session.add(
            AuditEventRow(
                audit_event_id=event_id,
                company_id=tenant.company_id,
                actor_type=tenant.actor_type.value,
                actor_id=tenant.actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                result=result,
                occurred_at=datetime.now(UTC),
                request_id=tenant.request_id,
                trace_id=tenant.trace_id,
                metadata_json=metadata,
            )
        )
        self._session.flush()
        return event_id

    def count_for_company(self, company_id: UUID) -> int:
        return len(
            tuple(
                self._session.scalars(
                    select(AuditEventRow).where(AuditEventRow.company_id == company_id)
                )
            )
        )

    def delete_for_resource(
        self,
        context: TenantContext,
        resource_id: UUID,
    ) -> bool:
        tenant = require_tenant_context(context)
        predicate = (
            AuditEventRow.company_id == tenant.company_id,
            AuditEventRow.resource_id == resource_id,
        )
        self._session.execute(delete(AuditEventRow).where(*predicate))
        self._session.flush()
        return self._session.scalar(select(AuditEventRow).where(*predicate)) is None


class SQLApplicantSessionStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_token(
        self,
        *,
        token_hash: str,
        company_id: UUID,
        invitation_id: UUID,
        applicant_id: UUID,
        expires_at: datetime,
    ) -> None:
        self._session.add(
            ApplicantTokenRow(
                token_hash=token_hash,
                company_id=company_id,
                invitation_id=invitation_id,
                applicant_id=applicant_id,
                expires_at=expires_at,
                consumed_at=None,
            )
        )
        self._session.flush()

    def get_token(self, token_hash: str) -> ApplicantTokenRecord | None:
        row = self._session.get(ApplicantTokenRow, token_hash)
        if row is None:
            return None
        return ApplicantTokenRecord(
            token_hash=row.token_hash,
            company_id=row.company_id,
            invitation_id=row.invitation_id,
            applicant_id=row.applicant_id,
            expires_at=_utc(row.expires_at),
            consumed_at=None if row.consumed_at is None else _utc(row.consumed_at),
        )

    def consume_token(self, token_hash: str, *, consumed_at: datetime) -> None:
        row = self._session.get(ApplicantTokenRow, token_hash)
        if row is None:
            raise LookupError("applicant token not found")
        row.consumed_at = consumed_at
        self._session.flush()

    def save_session(
        self,
        *,
        session_hash: str,
        principal: ApplicantPrincipal,
        expires_at: datetime,
    ) -> None:
        self._session.add(
            ApplicantSessionRow(
                session_hash=session_hash,
                company_id=principal.company_id,
                invitation_id=principal.invitation_id,
                applicant_id=principal.applicant_id,
                session_id=principal.session_id,
                expires_at=expires_at,
            )
        )
        self._session.flush()

    def get_session(self, session_hash: str, *, now: datetime) -> ApplicantPrincipal | None:
        row = self._session.get(ApplicantSessionRow, session_hash)
        if row is None or now >= _utc(row.expires_at):
            return None
        return ApplicantPrincipal(
            company_id=row.company_id,
            invitation_id=row.invitation_id,
            applicant_id=row.applicant_id,
            session_id=row.session_id,
        )


class SQLUploadIntentStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, intent: StoredUploadIntent) -> None:
        self._session.add(
            UploadIntentRow(
                upload_id=intent.upload_id,
                company_id=intent.company_id,
                invitation_id=intent.invitation_id,
                applicant_id=intent.applicant_id,
                source_type=intent.source_type,
                original_filename=intent.original_filename,
                media_type=intent.media_type,
                byte_size=intent.byte_size,
                sha256=intent.sha256,
                object_key=intent.object_key,
                method=intent.method,
                url=intent.url,
                required_headers=intent.required_headers,
                expires_at=intent.expires_at,
            )
        )
        self._session.flush()

    def get(
        self,
        context: TenantContext,
        upload_id: UUID,
        applicant_id: UUID,
    ) -> StoredUploadIntent | None:
        tenant = require_tenant_context(context)
        row = self._session.scalar(
            select(UploadIntentRow).where(
                UploadIntentRow.company_id == tenant.company_id,
                UploadIntentRow.upload_id == upload_id,
                UploadIntentRow.applicant_id == applicant_id,
            )
        )
        if row is None:
            return None
        return StoredUploadIntent(
            upload_id=row.upload_id,
            company_id=row.company_id,
            invitation_id=row.invitation_id,
            applicant_id=row.applicant_id,
            source_type=row.source_type,
            original_filename=row.original_filename,
            media_type=row.media_type,
            byte_size=row.byte_size,
            sha256=row.sha256,
            object_key=row.object_key,
            method=row.method,
            url=row.url,
            required_headers=row.required_headers,
            expires_at=_utc(row.expires_at),
        )

    def delete(self, context: TenantContext, object_key: str) -> bool:
        tenant = require_tenant_context(context)
        rows = tuple(
            self._session.scalars(
                select(UploadIntentRow).where(
                    UploadIntentRow.company_id == tenant.company_id,
                    UploadIntentRow.object_key == object_key,
                )
            )
        )
        for row in rows:
            self._session.delete(row)
        self._session.flush()
        return True


class SQLCommandIdempotencyStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(
        self,
        context: TenantContext,
        *,
        operation: str,
        idempotency_key: str,
    ) -> UUID | None:
        tenant = require_tenant_context(context)
        row = self._session.get(
            CommandIdempotencyRow,
            {
                "company_id": tenant.company_id,
                "operation": operation,
                "idempotency_key": idempotency_key,
            },
        )
        return None if row is None else row.resource_id

    def put(
        self,
        context: TenantContext,
        *,
        operation: str,
        idempotency_key: str,
        resource_id: UUID,
    ) -> None:
        tenant = require_tenant_context(context)
        if (
            self.get(
                context,
                operation=operation,
                idempotency_key=idempotency_key,
            )
            is not None
        ):
            return
        self._session.add(
            CommandIdempotencyRow(
                company_id=tenant.company_id,
                operation=operation,
                idempotency_key=idempotency_key,
                resource_id=resource_id,
            )
        )
        self._session.flush()
