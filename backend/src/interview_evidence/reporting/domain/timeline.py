from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class RecordingStatus(StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    PARTIAL = "partial"
    FAILED = "failed"


def _ordered(start_ms: int, end_ms: int) -> None:
    if start_ms < 0 or end_ms <= start_ms:
        raise ValueError("session clock range must be ordered")


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    transcript_segment_id: UUID
    company_id: UUID
    interview_session_id: UUID
    turn_id: UUID
    speaker: str
    text: str
    confidence: float
    session_start_ms: int
    session_end_ms: int
    source_audio_key: str
    version: int
    corrected_by: UUID | None
    created_at: datetime

    def __post_init__(self) -> None:
        _ordered(self.session_start_ms, self.session_end_ms)
        if not 0 <= self.confidence <= 1:
            raise ValueError("transcript confidence must be between zero and one")
        if self.version < 1:
            raise ValueError("transcript version must be positive")
        if not self.text.strip():
            raise ValueError("transcript text is required")


@dataclass(frozen=True, slots=True)
class RecordingAsset:
    recording_asset_id: UUID
    company_id: UUID
    interview_session_id: UUID
    asset_type: str
    object_key: str
    content_hash: str
    duration_ms: int
    status: RecordingStatus
    missing_ranges: tuple[tuple[int, int], ...]
    created_at: datetime

    def __post_init__(self) -> None:
        if self.duration_ms < 1:
            raise ValueError("recording duration must be positive")
        if len(self.content_hash) != 64:
            raise ValueError("recording content hash must be SHA-256")
        for start_ms, end_ms in self.missing_ranges:
            _ordered(start_ms, end_ms)
            if end_ms > self.duration_ms:
                raise ValueError("missing range exceeds recording duration")


@dataclass(frozen=True, slots=True)
class SessionEvent:
    session_event_id: UUID
    company_id: UUID
    interview_session_id: UUID
    event_type: str
    session_start_ms: int
    session_end_ms: int
    technical_failure: bool
    details: dict[str, object]
    created_at: datetime

    def __post_init__(self) -> None:
        _ordered(self.session_start_ms, self.session_end_ms)
        forbidden = {"competency", "competency_score", "assessment", "score"}
        if any(str(key).lower() in forbidden for key in self.details):
            raise ValueError("session event details must contain objective values only")
