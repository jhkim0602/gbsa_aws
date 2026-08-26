from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from interview_evidence.shared.tenant import TenantContext, require_tenant_context

if TYPE_CHECKING:
    from interview_evidence.interview_engine.repositories.postgres import InterviewRepository


class HotViewUnavailable(RuntimeError):
    pass


class RecentContextSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    company_id: UUID
    interview_session_id: UUID
    session_sequence: int = Field(ge=0)
    checkpoint_id: UUID
    last_final_turn_id: UUID | None = None
    pending_turn_id: UUID | None = None
    last_media_chunk_sequence: int = Field(ge=0)
    schema_version: int = Field(default=1, ge=1)
    last_reconciled_event_id: UUID | None = None
    expires_at: datetime


class RecentContextPort(Protocol):
    def get(self, context: TenantContext, session_id: UUID) -> RecentContextSnapshot | None: ...

    def put(
        self, context: TenantContext, snapshot: RecentContextSnapshot
    ) -> RecentContextSnapshot: ...

    def delete(self, context: TenantContext, session_id: UUID) -> None: ...


class PostgresRecentContext:
    def __init__(self, repository: InterviewRepository) -> None:
        self._repository = repository

    def get(self, context: TenantContext, session_id: UUID) -> RecentContextSnapshot | None:
        require_tenant_context(context)
        try:
            session = self._repository.get_session(context, session_id)
            checkpoint = self._repository.latest_checkpoint(context, session_id)
        except LookupError:
            return None
        if checkpoint is None:
            return None
        return RecentContextSnapshot(
            company_id=session.company_id,
            interview_session_id=session_id,
            session_sequence=checkpoint.session_sequence,
            checkpoint_id=checkpoint.checkpoint_id,
            last_final_turn_id=checkpoint.last_final_turn_id,
            pending_turn_id=checkpoint.pending_turn_id,
            last_media_chunk_sequence=checkpoint.last_media_chunk_sequence,
            expires_at=checkpoint.created_at + timedelta(days=7),
        )

    def put(self, context: TenantContext, snapshot: RecentContextSnapshot) -> RecentContextSnapshot:
        require_tenant_context(context).assert_company(snapshot.company_id)
        checkpoint = self._repository.latest_checkpoint(
            context,
            snapshot.interview_session_id,
        )
        if checkpoint is None or checkpoint.checkpoint_id != snapshot.checkpoint_id:
            raise HotViewUnavailable("durable recent context checkpoint is unavailable")
        return snapshot

    def delete(self, context: TenantContext, session_id: UUID) -> None:
        require_tenant_context(context)
        del session_id

    def healthcheck(self) -> None:
        return None


class InMemoryRecentContext:
    def __init__(self) -> None:
        self._snapshots: dict[tuple[UUID, UUID], RecentContextSnapshot] = {}
        self.fail_reads = False
        self.fail_writes = False

    def get(self, context: TenantContext, session_id: UUID) -> RecentContextSnapshot | None:
        if self.fail_reads:
            raise HotViewUnavailable("recent context read unavailable")
        tenant = require_tenant_context(context)
        return self._snapshots.get((tenant.company_id, session_id))

    def put(self, context: TenantContext, snapshot: RecentContextSnapshot) -> RecentContextSnapshot:
        if self.fail_writes:
            raise HotViewUnavailable("recent context write unavailable")
        tenant = require_tenant_context(context)
        tenant.assert_company(snapshot.company_id)
        self._snapshots[(tenant.company_id, snapshot.interview_session_id)] = snapshot
        return snapshot

    def delete(self, context: TenantContext, session_id: UUID) -> None:
        tenant = require_tenant_context(context)
        self._snapshots.pop((tenant.company_id, session_id), None)

    def healthcheck(self) -> None:
        return None
