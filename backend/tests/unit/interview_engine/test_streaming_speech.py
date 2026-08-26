from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from interview_evidence.interview_engine.api.streaming_speech import (
    StreamingSpeechConnection,
    WebSocketSpeechRuntime,
)
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
    TranscriptEvent,
)
from interview_evidence.shared.tenant import ActorType, TenantContext

SESSION_ID = UUID("00000000-0000-7000-8000-000000000001")
ANSWER_ID = UUID("00000000-0000-7000-8000-000000000002")


def _context() -> TenantContext:
    return TenantContext(
        company_id=UUID("00000000-0000-7000-8000-000000000003"),
        actor_type=ActorType.APPLICANT,
        actor_id=UUID("00000000-0000-7000-8000-000000000004"),
        request_id=UUID("00000000-0000-7000-8000-000000000005"),
        trace_id="trace-streaming-speech",
    )


def _envelope() -> WebSocketEnvelope:
    return WebSocketEnvelope.model_validate(
        {
            "protocol_version": "1.0",
            "message_type": "answer.start",
            "session_id": str(SESSION_ID),
            "sequence": 3,
            "idempotency_key": "answer-start-0001",
            "correlation_id": "00000000-0000-7000-8000-000000000006",
            "sent_at": "2026-08-20T09:00:00+09:00",
            "payload": {"answer_turn_id": str(ANSWER_ID)},
        }
    )


class FakeRecognitionSession(SpeechRecognitionSession):
    def __init__(self) -> None:
        self.audio: list[bytes] = []
        self.events: asyncio.Queue[TranscriptEvent | None] = asyncio.Queue()
        self.aborted = False

    async def send_audio(self, chunk: bytes) -> None:
        self.audio.append(chunk)
        await self.events.put(
            TranscriptEvent(
                text="아",
                is_final=False,
                confidence=0.2,
                stability=0.3,
            )
        )
        await self.events.put(
            TranscriptEvent(
                text="안녕",
                is_final=False,
                confidence=0.4,
                stability=0.7,
            )
        )
        await self.events.put(
            TranscriptEvent(
                text="안녕하세요",
                is_final=True,
                confidence=0.92,
                stability=1.0,
            )
        )

    def results(self) -> AsyncIterator[TranscriptEvent]:
        return self._results()

    async def _results(self) -> AsyncIterator[TranscriptEvent]:
        while True:
            event = await self.events.get()
            if event is None:
                return
            yield event

    async def end_input(self) -> None:
        await self.events.put(
            TranscriptEvent(
                text="반갑습니다",
                is_final=True,
                confidence=0.96,
                stability=1.0,
            )
        )
        await self.events.put(None)

    async def abort(self) -> None:
        self.aborted = True
        await self.events.put(None)


class FakeStreamingSpeechToText:
    def __init__(self, session: SpeechRecognitionSession) -> None:
        self.session = session
        self.config: SpeechRecognitionConfig | None = None

    async def open_stream(
        self,
        context: TenantContext,
        config: SpeechRecognitionConfig,
    ) -> SpeechRecognitionSession:
        assert context == _context()
        self.config = config
        return self.session


@pytest.mark.asyncio
async def test_streaming_connection_accumulates_final_segments() -> None:
    session = FakeRecognitionSession()
    provider = FakeStreamingSpeechToText(session)
    published: list[ServerEnvelope] = []
    connection = StreamingSpeechConnection(
        context=_context(),
        runtime=WebSocketSpeechRuntime(speech_to_text=provider),
        publish=_publisher(published),
    )
    envelope = _envelope()

    await connection.start_answer(
        envelope,
        answer_turn_id=ANSWER_ID,
        sample_rate_hz=16000,
    )
    await connection.send_audio(
        AudioChunkMetadata(
            answer_turn_id=ANSWER_ID,
            chunk_sequence=4,
            codec="pcm_s16le",
            sample_rate_hz=16000,
            channel_count=1,
            byte_length=3,
            sha256="0" * 64,
        ),
        b"pcm",
    )
    transcript = await connection.complete_answer(ANSWER_ID)

    assert transcript.text == "안녕하세요 반갑습니다"
    assert transcript.confidence == pytest.approx(0.96)
    assert transcript.last_chunk_sequence == 4
    assert session.audio == [b"pcm"]
    assert provider.config is not None
    assert provider.config.language_code == "ko-KR"
    assert provider.config.sample_rate_hz == 16000
    assert [message.payload["text"] for message in published] == [
        "아",
        "안녕하세요",
        "안녕하세요 반갑습니다",
    ]
    assert [
        (message.payload["committed_text"], message.payload["interim_text"])
        for message in published
    ] == [
        ("", "아"),
        ("안녕하세요", ""),
        ("안녕하세요 반갑습니다", ""),
    ]


class HangingRecognitionSession(FakeRecognitionSession):
    async def end_input(self) -> None:
        return


@pytest.mark.asyncio
async def test_streaming_connection_aborts_when_final_result_times_out() -> None:
    session = HangingRecognitionSession()
    connection = StreamingSpeechConnection(
        context=_context(),
        runtime=WebSocketSpeechRuntime(
            speech_to_text=FakeStreamingSpeechToText(session),
            final_result_timeout_seconds=0.01,
        ),
        publish=_publisher([]),
    )
    await connection.start_answer(
        _envelope(),
        answer_turn_id=ANSWER_ID,
        sample_rate_hz=16000,
    )

    with pytest.raises(SpeechProviderError, match="timed out"):
        await connection.complete_answer(ANSWER_ID)

    assert session.aborted is True
    assert connection.active is False


class FakeStreamingTextToSpeech:
    def synthesize_stream(
        self,
        context: TenantContext,
        text: str,
        *,
        voice_id: str,
    ) -> AsyncIterator[SpeechAudioChunk]:
        assert context == _context()
        assert text == "다음 질문입니다."
        assert voice_id == "Seoyeon"
        return self._chunks()

    async def _chunks(self) -> AsyncIterator[SpeechAudioChunk]:
        yield SpeechAudioChunk(content=b"one", sample_rate_hz=24000)
        yield SpeechAudioChunk(content=b"two", sample_rate_hz=24000)


@pytest.mark.asyncio
async def test_streaming_connection_sends_question_audio_in_order() -> None:
    published: list[ServerEnvelope | bytes] = []
    connection = StreamingSpeechConnection(
        context=_context(),
        runtime=WebSocketSpeechRuntime(text_to_speech=FakeStreamingTextToSpeech()),
        publish=_publisher(published),
    )
    response = ServerEnvelope(
        message_type="question.ready",
        session_id=SESSION_ID,
        sequence=4,
        idempotency_key="server:question-ready-0001",
        correlation_id=UUID("00000000-0000-7000-8000-000000000007"),
        sent_at=_envelope().sent_at,
        payload={
            "question_turn_id": "00000000-0000-7000-8000-000000000008",
            "text": "다음 질문입니다.",
            "text_only": True,
            "voice_id": "Seoyeon",
        },
    )

    prepared = connection.prepare_question_response(response)
    await connection.start_question_audio(prepared)
    await connection.wait_for_question_audio()

    assert prepared.payload["text_only"] is False
    assert prepared.payload["audio_stream"] is True
    assert [
        item.message_type if isinstance(item, ServerEnvelope) else item for item in published
    ] == ["question.audio.begin", b"one", b"two", "question.audio.end"]
    begin = published[0]
    assert isinstance(begin, ServerEnvelope)
    assert begin.payload["sample_rate_hz"] == 24000


class FakeAutomatedAnswerTextToSpeech:
    def synthesize_stream(
        self,
        context: TenantContext,
        text: str,
        *,
        voice_id: str,
    ) -> AsyncIterator[SpeechAudioChunk]:
        assert context == _context()
        assert text == "제출 자료를 바탕으로 만든 답변입니다."
        assert voice_id == "automated_applicant"
        return self._chunks()

    async def _chunks(self) -> AsyncIterator[SpeechAudioChunk]:
        yield SpeechAudioChunk(content=b"answer-one", sample_rate_hz=24000)
        yield SpeechAudioChunk(content=b"answer-two", sample_rate_hz=24000)


class FakeClosingTextToSpeech:
    def synthesize_stream(
        self,
        context: TenantContext,
        text: str,
        *,
        voice_id: str,
    ) -> AsyncIterator[SpeechAudioChunk]:
        assert context == _context()
        assert text == "답변 감사합니다. 오늘 면접은 여기까지입니다."
        assert voice_id == "Seoyeon"
        return self._chunks()

    async def _chunks(self) -> AsyncIterator[SpeechAudioChunk]:
        yield SpeechAudioChunk(content=b"closing", sample_rate_hz=24000)


@pytest.mark.asyncio
async def test_streaming_connection_sends_closing_audio_before_completion() -> None:
    published: list[ServerEnvelope | bytes] = []
    connection = StreamingSpeechConnection(
        context=_context(),
        runtime=WebSocketSpeechRuntime(text_to_speech=FakeClosingTextToSpeech()),
        publish=_publisher(published),
    )
    completed = ServerEnvelope(
        message_type="session.completed",
        session_id=SESSION_ID,
        sequence=8,
        idempotency_key="server:session-completed-0001",
        correlation_id=UUID("00000000-0000-7000-8000-000000000019"),
        sent_at=_envelope().sent_at,
        payload={
            "closing_message": "답변 감사합니다. 오늘 면접은 여기까지입니다.",
            "voice_id": "Seoyeon",
        },
    )

    closing = connection.prepare_closing_response(completed)
    await connection.start_closing_audio(closing)
    await connection.wait_for_question_audio()

    assert closing.message_type == "session.closing"
    assert closing.payload["audio_stream"] is True
    assert [
        item.message_type if isinstance(item, ServerEnvelope) else item for item in published
    ] == ["question.audio.begin", b"closing", "question.audio.end"]


@pytest.mark.asyncio
async def test_streaming_connection_sends_generated_answer_audio_separately() -> None:
    published: list[ServerEnvelope | bytes] = []
    connection = StreamingSpeechConnection(
        context=_context(),
        runtime=WebSocketSpeechRuntime(text_to_speech=FakeAutomatedAnswerTextToSpeech()),
        publish=_publisher(published),
    )
    response = ServerEnvelope(
        message_type="answer.automated.ready",
        session_id=SESSION_ID,
        sequence=4,
        idempotency_key="server:answer-automated-ready-0001",
        correlation_id=UUID("00000000-0000-7000-8000-000000000009"),
        sent_at=_envelope().sent_at,
        payload={
            "question_turn_id": "00000000-0000-7000-8000-000000000008",
            "text": "제출 자료를 바탕으로 만든 답변입니다.",
            "audio_requested": True,
            "voice_id": "automated_applicant",
        },
    )

    prepared = connection.prepare_automated_answer_response(response)
    await connection.start_automated_answer_audio(prepared)
    await connection.wait_for_question_audio()

    assert prepared.payload["audio_stream"] is True
    assert [
        item.message_type if isinstance(item, ServerEnvelope) else item for item in published
    ] == [
        "answer.automated.audio.begin",
        b"answer-one",
        b"answer-two",
        "answer.automated.audio.end",
    ]


def _publisher(
    messages: list[ServerEnvelope | bytes],
):
    async def publish(message: ServerEnvelope | bytes) -> None:
        messages.append(message)

    return publish
