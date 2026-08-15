from __future__ import annotations

from datetime import datetime
from uuid import UUID

from interview_evidence.interview_engine.domain.turn import (
    HotViewSyncStatus,
    SessionCheckpoint,
)
from interview_evidence.interview_engine.repositories.postgres import InterviewRepository
from interview_evidence.shared.ids import new_uuid7
from interview_evidence.shared.messaging.outbox import Outbox, OutboxEvent
from interview_evidence.shared.tenant import TenantContext


class CheckpointService:
    def __init__(
        self,
        repository: InterviewRepository,
        outbox: Outbox | None = None,
    ) -> None:
        self._repository = repository
        self._outbox = outbox

    def create(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        last_final_turn_id: UUID | None,
        last_media_chunk_sequence: int,
        pending_turn_id: UUID | None,
        hot_view_sync_status: HotViewSyncStatus,
        occurred_at: datetime,
    ) -> SessionCheckpoint:
        session = self._repository.get_session(context, session_id)
        checkpoint = SessionCheckpoint(
            checkpoint_id=new_uuid7(occurred_at),
            company_id=session.company_id,
            interview_session_id=session_id,
            session_sequence=session.session_sequence,
            last_final_turn_id=last_final_turn_id,
            last_media_chunk_sequence=last_media_chunk_sequence,
            pending_turn_id=pending_turn_id,
            hot_view_sync_status=hot_view_sync_status,
            created_at=occurred_at,
        )
        saved = self._repository.save_checkpoint(context, checkpoint)
        if self._outbox is not None:
            self._outbox.append(
                OutboxEvent(
                    outbox_event_id=new_uuid7(occurred_at),
                    company_id=session.company_id,
                    aggregate_type="interview_session",
                    aggregate_id=session_id,
                    aggregate_version=session.session_sequence,
                    event_type="interview.checkpoint_changed",
                    event_version=1,
                    payload={
                        "session_id": str(session_id),
                        "checkpoint_id": str(checkpoint.checkpoint_id),
                    },
                    idempotency_key=f"checkpoint-sync-{checkpoint.checkpoint_id}",
                    trace_id=context.trace_id,
                    occurred_at=occurred_at,
                )
            )
        return saved

    def latest(self, context: TenantContext, session_id: UUID) -> SessionCheckpoint | None:
        return self._repository.latest_checkpoint(context, session_id)
