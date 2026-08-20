from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from interview_evidence.shared.tenant import TenantContext


class SpeechProviderError(RuntimeError):
    """Raised when a speech provider stream cannot continue."""


@dataclass(frozen=True, slots=True)
class SpeechRecognitionConfig:
    language_code: str
    sample_rate_hz: int
    model: str
    channel_count: int = 1
    queue_max_chunks: int = 100


@dataclass(frozen=True, slots=True)
class TranscriptEvent:
    text: str
    is_final: bool
    confidence: float
    stability: float


@dataclass(frozen=True, slots=True)
class SpeechAudioChunk:
    content: bytes
    sample_rate_hz: int
    encoding: str = "pcm_s16le"
    channel_count: int = 1


class SpeechRecognitionSession(Protocol):
    async def send_audio(self, chunk: bytes) -> None: ...

    def results(self) -> AsyncIterator[TranscriptEvent]: ...

    async def end_input(self) -> None: ...

    async def abort(self) -> None: ...


class StreamingSpeechToText(Protocol):
    async def open_stream(
        self,
        context: TenantContext,
        config: SpeechRecognitionConfig,
    ) -> SpeechRecognitionSession: ...


class StreamingTextToSpeech(Protocol):
    def synthesize_stream(
        self,
        context: TenantContext,
        text: str,
        *,
        voice_id: str,
    ) -> AsyncIterator[SpeechAudioChunk]: ...
