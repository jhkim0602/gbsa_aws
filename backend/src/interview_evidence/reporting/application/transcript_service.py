from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Protocol
from uuid import UUID

from interview_evidence.reporting.domain.timeline import TranscriptSegment
from interview_evidence.reporting.repositories.postgres import ReportingRepository
from interview_evidence.shared.ids import new_uuid7
from interview_evidence.shared.tenant import TenantContext


class FinalTurnSnapshot(Protocol):
    turn_id: UUID
    company_id: UUID
    interview_session_id: UUID
    speaker: object
    status: object
    text: str | None


class TranscriptService:
    def __init__(self, repository: ReportingRepository) -> None:
        self._repository = repository

    def ingest_final_turn(
        self,
        context: TenantContext,
        *,
        turn: FinalTurnSnapshot,
        session_start_ms: int,
        session_end_ms: int,
        source_audio_key: str,
        confidence: float,
        occurred_at: datetime,
    ) -> TranscriptSegment:
        context.assert_company(turn.company_id)
        if str(turn.status) not in {"final", "TurnStatus.FINAL"} or turn.text is None:
            raise ValueError("only final Turns can become transcript segments")
        segment = TranscriptSegment(
            transcript_segment_id=new_uuid7(occurred_at),
            company_id=context.company_id,
            interview_session_id=turn.interview_session_id,
            turn_id=turn.turn_id,
            speaker=str(turn.speaker).split(".")[-1].lower(),
            text=turn.text,
            confidence=confidence,
            session_start_ms=session_start_ms,
            session_end_ms=session_end_ms,
            source_audio_key=source_audio_key,
            version=1,
            corrected_by=None,
            created_at=occurred_at,
        )
        return self._repository.save_transcript(context, segment)

    def correct(
        self,
        context: TenantContext,
        *,
        original: TranscriptSegment,
        corrected_text: str,
        company_user_id: UUID,
        occurred_at: datetime,
    ) -> TranscriptSegment:
        context.assert_company(original.company_id)
        if not corrected_text.strip():
            raise ValueError("corrected transcript text is required")
        corrected = replace(
            original,
            transcript_segment_id=new_uuid7(occurred_at),
            text=corrected_text,
            version=original.version + 1,
            corrected_by=company_user_id,
            created_at=occurred_at,
        )
        return self._repository.save_transcript(context, corrected)
