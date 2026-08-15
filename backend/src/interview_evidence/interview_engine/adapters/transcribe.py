from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    segment_sequence: int
    text: str
    start_ms: int
    end_ms: int
    confidence: float
    is_final: bool
    display_only: bool = True
    review_required: bool = False


class StreamingTranscriber(Protocol):
    def stream(self, context: TenantContext, audio: bytes) -> tuple[TranscriptionResult, ...]: ...


class StreamingTranscriptionAdapter:
    def __init__(
        self,
        transcriber: StreamingTranscriber,
        *,
        review_threshold: float = 0.75,
    ) -> None:
        self._transcriber = transcriber
        self._review_threshold = review_threshold

    def transcribe(self, context: TenantContext, audio: bytes) -> tuple[TranscriptionResult, ...]:
        return tuple(
            replace(
                result,
                display_only=not result.is_final,
                review_required=(result.is_final and result.confidence < self._review_threshold),
            )
            for result in self._transcriber.stream(context, audio)
        )
