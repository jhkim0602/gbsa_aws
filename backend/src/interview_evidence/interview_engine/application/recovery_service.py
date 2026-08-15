from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from interview_evidence.interview_engine.application.checkpoints import CheckpointService
from interview_evidence.interview_engine.application.context_reconciliation import (
    ContextReconciler,
)
from interview_evidence.interview_engine.application.idempotency import IdempotencyStore
from interview_evidence.interview_engine.application.state_machine import SessionStateMachine
from interview_evidence.interview_engine.domain.session import InterviewSessionState
from interview_evidence.interview_engine.domain.turn import (
    HotViewSyncStatus,
    InterviewTurn,
    TurnSpeaker,
    TurnStatus,
)
from interview_evidence.interview_engine.repositories.postgres import InterviewRepository
from interview_evidence.shared.tenant import TenantContext


class RecoveryMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    message_type: Literal["answer.accepted", "resume.snapshot"]
    server_sequence: int = Field(ge=0)
    checkpoint_id: UUID | None = None
    last_final_turn_id: UUID | None = None
    last_verified_recording_chunk_sequence: int = Field(default=0, ge=0)
    degraded_modes: tuple[str, ...] = ()


class RecoveryService:
    def __init__(
        self,
        *,
        repository: InterviewRepository,
        idempotency: IdempotencyStore,
        checkpoints: CheckpointService,
        reconciler: ContextReconciler,
    ) -> None:
        self._repository = repository
        self._idempotency = idempotency
        self._checkpoints = checkpoints
        self._reconciler = reconciler
        self._state_machine = SessionStateMachine()

    def finalize_answer(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        expected_sequence: int,
        answer_turn_id: UUID,
        text: str,
        last_recording_chunk_sequence: int,
        idempotency_key: str,
        occurred_at: datetime,
    ) -> RecoveryMessage:
        return self._idempotency.execute(
            context,
            session_id=session_id,
            operation="answer.complete",
            idempotency_key=idempotency_key,
            request_payload={
                "answer_turn_id": str(answer_turn_id),
                "expected_sequence": expected_sequence,
                "last_recording_chunk_sequence": last_recording_chunk_sequence,
                "text_sha256": sha256(text.encode("utf-8")).hexdigest(),
            },
            execute=lambda: self._finalize_or_resume(
                context,
                session_id=session_id,
                expected_sequence=expected_sequence,
                answer_turn_id=answer_turn_id,
                text=text,
                last_recording_chunk_sequence=last_recording_chunk_sequence,
                idempotency_key=idempotency_key,
                occurred_at=occurred_at,
            ),
            occurred_at=occurred_at,
        )

    def _finalize_or_resume(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        expected_sequence: int,
        answer_turn_id: UUID,
        text: str,
        last_recording_chunk_sequence: int,
        idempotency_key: str,
        occurred_at: datetime,
    ) -> RecoveryMessage:
        session = self._repository.get_session(context, session_id)
        if expected_sequence != session.session_sequence:
            return self.resume(
                context,
                session_id=session_id,
                client_sequence=expected_sequence,
            )
        return self._finalize_once(
            context,
            session_id=session_id,
            answer_turn_id=answer_turn_id,
            text=text,
            last_recording_chunk_sequence=last_recording_chunk_sequence,
            idempotency_key=idempotency_key,
            occurred_at=occurred_at,
        )

    def _finalize_once(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        answer_turn_id: UUID,
        text: str,
        last_recording_chunk_sequence: int,
        idempotency_key: str,
        occurred_at: datetime,
    ) -> RecoveryMessage:
        session = self._repository.get_session(context, session_id)
        try:
            existing = self._repository.get_turn(context, answer_turn_id)
        except LookupError:
            existing = None
        if existing is not None and (
            existing.interview_session_id != session_id
            or existing.speaker is not TurnSpeaker.APPLICANT
            or existing.status is TurnStatus.FINAL
        ):
            raise ValueError("answer turn cannot be finalized")
        next_turn_sequence = (
            existing.sequence
            if existing is not None
            else max(
                (turn.sequence for turn in self._repository.list_turns(context, session_id)),
                default=0,
            )
            + 1
        )
        turn = self._repository.save_turn(
            context,
            InterviewTurn(
                turn_id=answer_turn_id,
                company_id=session.company_id,
                interview_session_id=session_id,
                sequence=next_turn_sequence,
                speaker=TurnSpeaker.APPLICANT,
                status=TurnStatus.FINAL,
                text=text,
                idempotency_key=idempotency_key,
                finalized_at=occurred_at,
            ),
        )
        transitioned = self._state_machine.transition(
            session,
            expected_sequence=session.session_sequence,
            target=InterviewSessionState.PREPARING_QUESTION,
        )
        self._repository.save_session(context, transitioned)
        checkpoint = self._checkpoints.create(
            context,
            session_id=session_id,
            last_final_turn_id=turn.turn_id,
            last_media_chunk_sequence=last_recording_chunk_sequence,
            pending_turn_id=None,
            hot_view_sync_status=HotViewSyncStatus.PENDING,
            occurred_at=occurred_at,
        )
        return RecoveryMessage(
            message_type="answer.accepted",
            server_sequence=transitioned.session_sequence,
            checkpoint_id=checkpoint.checkpoint_id,
            last_final_turn_id=turn.turn_id,
            last_verified_recording_chunk_sequence=last_recording_chunk_sequence,
        )

    def resume(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        client_sequence: int,
    ) -> RecoveryMessage:
        del client_sequence
        snapshot = self._reconciler.get_or_rebuild(
            context,
            session_id=session_id,
            last_reconciled_event_id=None,
        )
        return RecoveryMessage(
            message_type="resume.snapshot",
            server_sequence=snapshot.session_sequence,
            checkpoint_id=snapshot.checkpoint_id,
            last_final_turn_id=snapshot.last_final_turn_id,
            last_verified_recording_chunk_sequence=snapshot.last_media_chunk_sequence,
            degraded_modes=snapshot.degraded_modes,
        )
