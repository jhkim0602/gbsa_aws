from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from interview_evidence.interview_engine.adapters.recent_context import (
    HotViewUnavailable,
    RecentContextPort,
    RecentContextSnapshot,
)
from interview_evidence.interview_engine.repositories.postgres import InterviewRepository
from interview_evidence.shared.messaging.outbox import OutboxEvent
from interview_evidence.shared.tenant import TenantContext


class ReconciledContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    company_id: UUID
    interview_session_id: UUID
    session_sequence: int = Field(ge=0)
    checkpoint_id: UUID
    last_final_turn_id: UUID | None = None
    pending_turn_id: UUID | None = None
    last_media_chunk_sequence: int = Field(ge=0)
    source: str
    degraded_modes: tuple[str, ...] = ()


class MissingDurableCheckpoint(LookupError):
    pass


class ContextReconciler:
    def __init__(
        self,
        repository: InterviewRepository,
        hot_view: RecentContextPort,
    ) -> None:
        self._repository = repository
        self._hot_view = hot_view

    def get_or_rebuild(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        last_reconciled_event_id: UUID | None,
    ) -> ReconciledContext:
        session = self._repository.get_session(context, session_id)
        try:
            current = self._hot_view.get(context, session_id)
        except HotViewUnavailable:
            current = None
        if current is not None and current.session_sequence == session.session_sequence:
            return self._to_result(current, source="hot_view")

        checkpoint = self._repository.latest_checkpoint(context, session_id)
        if checkpoint is None:
            raise MissingDurableCheckpoint("durable checkpoint is required for recovery")
        snapshot = RecentContextSnapshot(
            company_id=session.company_id,
            interview_session_id=session_id,
            session_sequence=session.session_sequence,
            checkpoint_id=checkpoint.checkpoint_id,
            last_final_turn_id=checkpoint.last_final_turn_id,
            pending_turn_id=checkpoint.pending_turn_id,
            last_media_chunk_sequence=checkpoint.last_media_chunk_sequence,
            last_reconciled_event_id=last_reconciled_event_id,
            expires_at=checkpoint.created_at + timedelta(days=7),
        )
        try:
            self._hot_view.put(context, snapshot)
        except HotViewUnavailable:
            return self._to_result(
                snapshot,
                source="aurora_fallback",
                degraded_modes=("context_hot_view",),
            )
        return self._to_result(snapshot, source="aurora_rebuild")

    def reconcile_event(
        self,
        context: TenantContext,
        event: OutboxEvent,
    ) -> ReconciledContext:
        context.assert_company(event.company_id)
        if (
            event.event_type != "interview.checkpoint_changed"
            or event.aggregate_type != "interview_session"
        ):
            raise ValueError("unsupported hot-view reconciliation event")
        session_id = UUID(str(event.payload.get("session_id", "")))
        if session_id != event.aggregate_id:
            raise ValueError("reconciliation event aggregate mismatch")
        checkpoint = self._repository.latest_checkpoint(context, session_id)
        if checkpoint is None:
            raise MissingDurableCheckpoint("durable checkpoint is required for recovery")
        if str(checkpoint.checkpoint_id) != str(event.payload.get("checkpoint_id")):
            raise ValueError("reconciliation event checkpoint is stale")
        return self.get_or_rebuild(
            context,
            session_id=session_id,
            last_reconciled_event_id=event.outbox_event_id,
        )

    @staticmethod
    def _to_result(
        snapshot: RecentContextSnapshot,
        *,
        source: str,
        degraded_modes: tuple[str, ...] = (),
    ) -> ReconciledContext:
        return ReconciledContext(
            company_id=snapshot.company_id,
            interview_session_id=snapshot.interview_session_id,
            session_sequence=snapshot.session_sequence,
            checkpoint_id=snapshot.checkpoint_id,
            last_final_turn_id=snapshot.last_final_turn_id,
            pending_turn_id=snapshot.pending_turn_id,
            last_media_chunk_sequence=snapshot.last_media_chunk_sequence,
            source=source,
            degraded_modes=degraded_modes,
        )
