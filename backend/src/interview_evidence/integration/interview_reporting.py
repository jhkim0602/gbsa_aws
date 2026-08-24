from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from interview_evidence.interview_engine.application.public import (
    InterviewEnginePublic,
    RecordingCheckpointSnapshot,
)
from interview_evidence.reporting.application.transcript_service import TranscriptService
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.workers.reporting.media import (
    MediaPostProcessor,
    RecordingAssembler,
    RecordingChunkObject,
    RecordingSourceSegment,
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


class _FinalTurnLike(Protocol):
    @property
    def turn_id(self) -> UUID: ...

    @property
    def speaker(self) -> object: ...


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
        occurred_at: datetime,
        turn_ranges: tuple[FinalTurnRange, ...] | None = None,
    ) -> CompletedSessionProjection:
        snapshot = self._interview.get_session_snapshot(context, session_id=session_id)
        if snapshot.state not in {"completed", "report_generating", "reviewable"}:
            raise ValueError("only a completed interview session can be projected")

        final_turns = {
            turn.turn_id: turn
            for turn in self._interview.list_final_turns(context, session_id=session_id)
        }
        chunks = self._interview.resolve_recording_chunks(context, session_id=session_id)
        if not chunks:
            raise ValueError("completed session has no verified recording chunks")

        assembled = self._assembler.assemble_with_segments(
            context,
            session_id=session_id,
            chunks=tuple(
                RecordingChunkObject(
                    sequence=chunk.sequence,
                    object_key=chunk.object_key,
                    session_start_ms=chunk.session_start_ms,
                    session_end_ms=chunk.session_end_ms,
                )
                for chunk in chunks
            ),
        )
        checkpoints = self._interview.list_recording_checkpoints(
            context,
            session_id=session_id,
        )
        resolved_ranges = turn_ranges or _ranges_from_recording_segments(
            tuple(final_turns.values()),
            assembled.source_segments,
            checkpoints=checkpoints,
        )
        ranges = {item.turn_id: item for item in resolved_ranges}
        if len(ranges) != len(resolved_ranges) or set(ranges) != set(final_turns):
            raise ValueError("every final Turn requires exactly one transcript range")
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
            output_object_key=assembled.object_key,
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


def _ranges_from_recording_segments(
    turns: tuple[_FinalTurnLike, ...],
    segments: tuple[RecordingSourceSegment, ...],
    *,
    checkpoints: tuple[RecordingCheckpointSnapshot, ...] = (),
) -> tuple[FinalTurnRange, ...]:
    applicant_turns = [turn for turn in turns if _speaker_of(turn) == "applicant"]
    applicant_segments = _applicant_recording_segments(
        applicant_turns,
        segments,
        checkpoints=checkpoints,
    )
    ranges: list[FinalTurnRange] = []
    applicant_index = 0
    for turn in turns:
        if _speaker_of(turn) == "applicant":
            segment = applicant_segments[applicant_index]
            applicant_index += 1
            start_ms = segment.session_start_ms
            end_ms = segment.session_end_ms
        else:
            segment = (
                applicant_segments[applicant_index]
                if applicant_index < len(applicant_segments)
                else applicant_segments[-1]
            )
            start_ms = segment.session_start_ms
            end_ms = min(segment.session_end_ms, start_ms + 1)
            if end_ms <= start_ms:
                start_ms = max(0, segment.session_end_ms - 1)
                end_ms = segment.session_end_ms
        ranges.append(
            FinalTurnRange(
                turn_id=turn.turn_id,
                session_start_ms=start_ms,
                session_end_ms=end_ms,
                confidence=0.9,
            )
        )
    return tuple(ranges)


def _applicant_recording_segments(
    applicant_turns: list[_FinalTurnLike],
    segments: tuple[RecordingSourceSegment, ...],
    *,
    checkpoints: tuple[RecordingCheckpointSnapshot, ...],
) -> tuple[RecordingSourceSegment, ...]:
    media_sequence_by_turn = {
        checkpoint.last_final_turn_id: checkpoint.last_media_chunk_sequence
        for checkpoint in checkpoints
        if checkpoint.last_final_turn_id is not None
    }
    if all(turn.turn_id in media_sequence_by_turn for turn in applicant_turns):
        matched: list[RecordingSourceSegment] = []
        previous_sequence = -1
        for turn in applicant_turns:
            media_sequence = media_sequence_by_turn[turn.turn_id]
            candidates = [
                segment
                for segment in segments
                if previous_sequence < segment.last_sequence <= media_sequence
            ]
            if not candidates:
                raise ValueError("applicant final Turn has no matching MediaRecorder segment")
            matched.append(max(candidates, key=lambda segment: segment.last_sequence))
            previous_sequence = media_sequence
        return tuple(matched)
    if len(applicant_turns) != len(segments):
        raise ValueError(
            "applicant final Turns and MediaRecorder segments must have the same count"
        )
    return segments


def _speaker_of(turn: _FinalTurnLike) -> str:
    speaker = getattr(turn, "speaker", "")
    return str(getattr(speaker, "value", speaker)).split(".")[-1].lower()
