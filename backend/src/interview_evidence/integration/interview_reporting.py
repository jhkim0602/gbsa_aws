from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from interview_evidence.interview_engine.application.public import InterviewEnginePublic
from interview_evidence.reporting.application.transcript_service import TranscriptService
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.workers.reporting.media import (
    MediaPostProcessor,
    RecordingAssembler,
    RecordingChunkObject,
)


@dataclass(frozen=True, slots=True)
class FinalTurnRange:
    turn_id: UUID
    session_start_ms: int
    session_end_ms: int
    confidence: float

    def __post_init__(self) -> None:
        if self.session_start_ms < 0 or self.session_end_ms <= self.session_start_ms:
            raise ValueError("final Turn range must be ordered")
        if not 0 <= self.confidence <= 1:
            raise ValueError("transcript confidence must be between zero and one")


@dataclass(frozen=True, slots=True)
class TranscriptProjection:
    transcript_segment_id: UUID
    turn_id: UUID


@dataclass(frozen=True, slots=True)
class RecordingProjection:
    recording_asset_id: UUID
    status: str
    missing_ranges: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class CompletedSessionProjection:
    interview_session_id: UUID
    competency_model_version_id: UUID
    transcripts: tuple[TranscriptProjection, ...]
    recording: RecordingProjection


@dataclass(slots=True)
class _ReportingTurnSnapshot:
    turn_id: UUID
    company_id: UUID
    interview_session_id: UUID
    speaker: object
    status: object
    text: str | None


class InterviewReportingBoundary:
    """Project Lane C's public completed-session data into Lane D services."""

    def __init__(
        self,
        *,
        interview: InterviewEnginePublic,
        transcript_service: TranscriptService,
        media_processor: MediaPostProcessor,
        assembler: RecordingAssembler,
    ) -> None:
        self._interview = interview
        self._transcript_service = transcript_service
        self._media_processor = media_processor
        self._assembler = assembler

    def project_completed_session(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        turn_ranges: tuple[FinalTurnRange, ...],
        occurred_at: datetime,
    ) -> CompletedSessionProjection:
        snapshot = self._interview.get_session_snapshot(context, session_id=session_id)
        if snapshot.state not in {"completed", "report_generating", "reviewable"}:
            raise ValueError("only a completed interview session can be projected")

        final_turns = {
            turn.turn_id: turn
            for turn in self._interview.list_final_turns(context, session_id=session_id)
        }
        ranges = {item.turn_id: item for item in turn_ranges}
        if len(ranges) != len(turn_ranges) or set(ranges) != set(final_turns):
            raise ValueError("every final Turn requires exactly one transcript range")

        chunks = self._interview.resolve_recording_chunks(context, session_id=session_id)
        if not chunks:
            raise ValueError("completed session has no verified recording chunks")

        # The asset must describe an object that exists, so the key comes from the write
        # rather than from the caller. Only verified chunks contribute bytes.
        output_object_key = self._assembler.assemble(
            context,
            session_id=session_id,
            chunks=tuple(
                RecordingChunkObject(sequence=chunk.sequence, object_key=chunk.object_key)
                for chunk in chunks
            ),
        )
        recording = self._media_processor.build_manifest(
            context,
            session_id=session_id,
            chunks=tuple(
                (
                    chunk.session_start_ms,
                    chunk.session_end_ms,
                    chunk.content_hash,
                )
                for chunk in chunks
            ),
            output_object_key=output_object_key,
            occurred_at=occurred_at,
        )
        transcripts: list[TranscriptProjection] = []
        for turn_id, turn in final_turns.items():
            turn_range = ranges[turn_id]
            source_chunk = next(
                (
                    chunk
                    for chunk in chunks
                    if chunk.session_start_ms < turn_range.session_end_ms
                    and chunk.session_end_ms > turn_range.session_start_ms
                ),
                None,
            )
            if source_chunk is None:
                raise ValueError("final Turn has no verified recording coverage")
            segment = self._transcript_service.ingest_final_turn(
                context,
                turn=_ReportingTurnSnapshot(
                    turn_id=turn.turn_id,
                    company_id=turn.company_id,
                    interview_session_id=turn.interview_session_id,
                    speaker=turn.speaker.value,
                    status=turn.status.value,
                    text=turn.text,
                ),
                session_start_ms=turn_range.session_start_ms,
                session_end_ms=turn_range.session_end_ms,
                source_audio_key=source_chunk.object_key,
                confidence=turn_range.confidence,
                occurred_at=occurred_at,
            )
            transcripts.append(
                TranscriptProjection(
                    transcript_segment_id=segment.transcript_segment_id,
                    turn_id=segment.turn_id,
                )
            )

        return CompletedSessionProjection(
            interview_session_id=session_id,
            competency_model_version_id=snapshot.competency_model_version_id,
            transcripts=tuple(transcripts),
            recording=RecordingProjection(
                recording_asset_id=recording.recording_asset_id,
                status=recording.status.value,
                missing_ranges=recording.missing_ranges,
            ),
        )
