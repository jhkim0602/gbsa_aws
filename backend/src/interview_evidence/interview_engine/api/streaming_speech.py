from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, field
from uuid import UUID

from interview_evidence.interview_engine.api.websocket import (
    AudioChunkMetadata,
    ServerEnvelope,
    WebSocketEnvelope,
)
from interview_evidence.shared.speech.ports import (
    SpeechAudioChunk,
    SpeechProviderError,
    SpeechRecognitionConfig,
    SpeechRecognitionSession,
    StreamingSpeechToText,
    StreamingTextToSpeech,
)
from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class WebSocketSpeechRuntime:
    speech_to_text: StreamingSpeechToText | None = None
    text_to_speech: StreamingTextToSpeech | None = None
    recognition_language_code: str = "ko-KR"
    recognition_model: str = "latest_long"
    final_result_timeout_seconds: float = 8.0


@dataclass(frozen=True, slots=True)
class CompletedTranscript:
    answer_turn_id: UUID
    text: str
    confidence: float
    last_chunk_sequence: int


@dataclass(slots=True)
class _ActiveRecognition:
    answer_turn_id: UUID
    envelope: WebSocketEnvelope
    session: SpeechRecognitionSession
    task: asyncio.Task[None] | None = None
    final_segments: list[str] = field(default_factory=list)
    latest_text: str = ""
    confidence: float = 0.0
    last_chunk_sequence: int = 0
    error: SpeechProviderError | None = None


class StreamingSpeechConnection:
    def __init__(
        self,
        *,
        context: TenantContext,
        runtime: WebSocketSpeechRuntime,
        publish: Callable[[ServerEnvelope | bytes], Awaitable[None]],
    ) -> None:
        self._context = context
        self._runtime = runtime
        self._publish = publish
        self._active: _ActiveRecognition | None = None
        self._speech_task: asyncio.Task[None] | None = None

    @property
    def enabled(self) -> bool:
        return self._runtime.speech_to_text is not None

    @property
    def active(self) -> bool:
        return self._active is not None

    async def start_answer(
        self,
        envelope: WebSocketEnvelope,
        *,
        answer_turn_id: UUID,
        sample_rate_hz: int,
        channel_count: int = 1,
    ) -> None:
        provider = self._runtime.speech_to_text
        if provider is None:
            return
        if self._active is not None:
            if self._active.answer_turn_id == answer_turn_id:
                return
            raise ValueError("another streaming answer is already active")
        session = await provider.open_stream(
            self._context,
            SpeechRecognitionConfig(
                language_code=self._runtime.recognition_language_code,
                sample_rate_hz=sample_rate_hz,
                model=self._runtime.recognition_model,
                channel_count=channel_count,
            ),
        )
        active = _ActiveRecognition(
            answer_turn_id=answer_turn_id,
            envelope=envelope,
            session=session,
        )
        self._active = active
        active.task = asyncio.create_task(self._pump_results(active))

    async def send_audio(self, metadata: AudioChunkMetadata, audio: bytes) -> None:
        active = self._require_active(metadata.answer_turn_id)
        active.last_chunk_sequence = metadata.chunk_sequence
        await active.session.send_audio(audio)

    async def complete_answer(self, answer_turn_id: UUID) -> CompletedTranscript:
        active = self._require_active(answer_turn_id)
        try:
            await active.session.end_input()
            if active.task is not None:
                try:
                    await asyncio.wait_for(
                        asyncio.shield(active.task),
                        timeout=self._runtime.final_result_timeout_seconds,
                    )
                except TimeoutError as error:
                    await active.session.abort()
                    active.task.cancel()
                    with suppress(asyncio.CancelledError):
                        await active.task
                    raise SpeechProviderError(
                        "speech recognition final result timed out"
                    ) from error
            if active.error is not None:
                raise active.error
            text = " ".join(active.final_segments).strip() or active.latest_text.strip()
            if not text:
                raise SpeechProviderError("speech recognition returned no transcript")
            return CompletedTranscript(
                answer_turn_id=active.answer_turn_id,
                text=text,
                confidence=active.confidence,
                last_chunk_sequence=active.last_chunk_sequence,
            )
        finally:
            self._active = None

    def prepare_question_response(self, response: ServerEnvelope) -> ServerEnvelope:
        if self._runtime.text_to_speech is None or response.message_type != "question.ready":
            return response
        text = response.payload.get("text")
        if not isinstance(text, str) or not text.strip():
            return response
        payload = dict(response.payload)
        payload.update(
            {
                "audio_url": None,
                "audio_expires_at": None,
                "speech_marks_url": None,
                "audio_stream": True,
                "text_only": False,
            }
        )
        return response.model_copy(update={"payload": payload})

    async def start_question_audio(self, response: ServerEnvelope) -> None:
        provider = self._runtime.text_to_speech
        if provider is None or response.message_type != "question.ready":
            return
        text = response.payload.get("text")
        if not isinstance(text, str) or not text.strip():
            return
        if self._speech_task is not None:
            self._speech_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._speech_task
        voice_id = response.payload.get("voice_id")
        self._speech_task = asyncio.create_task(
            self._stream_question_audio(
                response,
                text=text,
                voice_id=voice_id if isinstance(voice_id, str) else "default",
            )
        )

    async def wait_for_question_audio(self) -> None:
        if self._speech_task is not None:
            await self._speech_task

    async def abort(self) -> None:
        active = self._active
        self._active = None
        if active is not None:
            await active.session.abort()
            if active.task is not None:
                active.task.cancel()
                with suppress(asyncio.CancelledError):
                    await active.task
        if self._speech_task is not None:
            self._speech_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._speech_task
            self._speech_task = None

    async def _pump_results(self, active: _ActiveRecognition) -> None:
        try:
            async for event in active.session.results():
                if event.is_final:
                    active.final_segments.append(event.text)
                    active.confidence = event.confidence
                    display_text = " ".join(active.final_segments).strip()
                else:
                    prefix = " ".join(active.final_segments).strip()
                    display_text = f"{prefix} {event.text}".strip()
                    if not active.final_segments:
                        active.confidence = event.confidence
                active.latest_text = display_text
                await self._publish(
                    _message(
                        active.envelope,
                        message_type="transcript.partial",
                        payload={
                            "answer_turn_id": str(active.answer_turn_id),
                            "chunk_sequence": active.last_chunk_sequence,
                            "text": display_text,
                            "display_only": True,
                            "stability": event.stability,
                        },
                    )
                )
        except asyncio.CancelledError:
            raise
        except SpeechProviderError as error:
            active.error = error
            await self._publish(_speech_error(active.envelope))

    async def _stream_question_audio(
        self,
        response: ServerEnvelope,
        *,
        text: str,
        voice_id: str,
    ) -> None:
        provider = self._runtime.text_to_speech
        if provider is None:
            return
        question_turn_id = str(response.payload.get("question_turn_id", ""))
        began = False
        sample_rate_hz = 0
        try:
            async for chunk in provider.synthesize_stream(
                self._context,
                text,
                voice_id=voice_id,
            ):
                if not began:
                    sample_rate_hz = chunk.sample_rate_hz
                    await self._publish(
                        _message(
                            response,
                            message_type="question.audio.begin",
                            payload=_audio_payload(question_turn_id, chunk),
                        )
                    )
                    began = True
                await self._publish(chunk.content)
            if not began:
                raise SpeechProviderError("speech synthesis returned no audio")
            await self._publish(
                _message(
                    response,
                    message_type="question.audio.end",
                    payload={
                        "question_turn_id": question_turn_id,
                        "sample_rate_hz": sample_rate_hz,
                    },
                )
            )
        except asyncio.CancelledError:
            raise
        except SpeechProviderError:
            await self._publish(
                _message(
                    response,
                    message_type="question.audio.error",
                    payload={
                        "question_turn_id": question_turn_id,
                        "code": "SPEECH_SYNTHESIS_UNAVAILABLE",
                        "message": "음성 질문을 재생하지 못해 텍스트로 계속 진행합니다.",
                    },
                )
            )

    def _require_active(self, answer_turn_id: UUID) -> _ActiveRecognition:
        if self._active is None or self._active.answer_turn_id != answer_turn_id:
            raise ValueError("streaming answer is not active")
        return self._active


def _message(
    envelope: WebSocketEnvelope | ServerEnvelope,
    *,
    message_type: str,
    payload: dict[str, object],
) -> ServerEnvelope:
    return ServerEnvelope(
        message_type=message_type,
        session_id=envelope.session_id,
        sequence=envelope.sequence,
        idempotency_key=f"server:{envelope.idempotency_key}",
        correlation_id=envelope.correlation_id,
        sent_at=envelope.sent_at,
        payload=payload,
    )


def _speech_error(envelope: WebSocketEnvelope) -> ServerEnvelope:
    return _message(
        envelope,
        message_type="error",
        payload={
            "code": "TRANSCRIPTION_UNAVAILABLE",
            "message": "음성 인식 연결이 끊어졌습니다. 답변을 다시 시도해 주세요.",
            "retryable": True,
            "current_sequence": envelope.sequence,
        },
    )


def _audio_payload(question_turn_id: str, chunk: SpeechAudioChunk) -> dict[str, object]:
    return {
        "question_turn_id": question_turn_id,
        "encoding": chunk.encoding,
        "sample_rate_hz": chunk.sample_rate_hz,
        "channel_count": chunk.channel_count,
    }
