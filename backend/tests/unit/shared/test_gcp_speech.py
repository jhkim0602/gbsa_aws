from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, cast
from uuid import UUID

import pytest
from google.cloud import speech_v1, texttospeech_v1
from interview_evidence.shared.gcp_clients.speech import (
    GcpStreamingSpeechToText,
    GcpStreamingTextToSpeech,
)
from interview_evidence.shared.speech.ports import SpeechRecognitionConfig
from interview_evidence.shared.tenant import ActorType, TenantContext


def _context() -> TenantContext:
    return TenantContext(
        company_id=UUID("11111111-1111-1111-1111-111111111111"),
        actor_type=ActorType.APPLICANT,
        actor_id=UUID("22222222-2222-2222-2222-222222222222"),
        request_id=UUID("33333333-3333-3333-3333-333333333333"),
        trace_id="trace-gcp-speech",
    )


class FakeSpeechClient:
    def __init__(self) -> None:
        self.requests: list[speech_v1.StreamingRecognizeRequest] = []

    async def streaming_recognize(
        self,
        *,
        requests: AsyncIterator[speech_v1.StreamingRecognizeRequest],
    ) -> AsyncIterator[speech_v1.StreamingRecognizeResponse]:
        self.requests = [request async for request in requests]

        async def responses() -> AsyncIterator[speech_v1.StreamingRecognizeResponse]:
            yield speech_v1.StreamingRecognizeResponse(
                results=[
                    speech_v1.StreamingRecognitionResult(
                        alternatives=[
                            speech_v1.SpeechRecognitionAlternative(
                                transcript=" 안녕하세요 ", confidence=0.91
                            )
                        ],
                        is_final=False,
                        stability=0.8,
                    )
                ]
            )
            yield speech_v1.StreamingRecognizeResponse(
                results=[
                    speech_v1.StreamingRecognitionResult(
                        alternatives=[
                            speech_v1.SpeechRecognitionAlternative(
                                transcript="안녕하세요 반갑습니다", confidence=0.97
                            )
                        ],
                        is_final=True,
                        stability=1.0,
                    )
                ]
            )

        return responses()


@pytest.mark.asyncio
async def test_streaming_stt_sends_config_once_and_maps_results() -> None:
    fake = FakeSpeechClient()
    adapter = GcpStreamingSpeechToText(cast(speech_v1.SpeechAsyncClient, fake))
    session = await adapter.open_stream(
        _context(),
        SpeechRecognitionConfig(
            language_code="ko-KR",
            sample_rate_hz=16000,
            model="latest_long",
        ),
    )

    await session.send_audio(b"first")
    await session.send_audio(b"second")
    await session.end_input()
    events = [event async for event in session.results()]

    assert [event.text for event in events] == ["안녕하세요", "안녕하세요 반갑습니다"]
    assert [event.is_final for event in events] == [False, True]
    assert fake.requests[0].streaming_config.config.language_code == "ko-KR"
    assert fake.requests[0].streaming_config.config.sample_rate_hertz == 16000
    assert [request.audio_content for request in fake.requests[1:]] == [b"first", b"second"]


@pytest.mark.asyncio
async def test_streaming_stt_abort_does_not_block_when_queue_is_full() -> None:
    fake = FakeSpeechClient()
    adapter = GcpStreamingSpeechToText(cast(speech_v1.SpeechAsyncClient, fake))
    session = await adapter.open_stream(
        _context(),
        SpeechRecognitionConfig(
            language_code="ko-KR",
            sample_rate_hz=16000,
            model="latest_long",
            queue_max_chunks=1,
        ),
    )
    await session.send_audio(b"full")

    await asyncio.wait_for(session.abort(), timeout=0.1)


class FakeTextToSpeechClient:
    def __init__(self, *, streaming_error: Exception | None = None) -> None:
        self.streaming_error = streaming_error
        self.streaming_requests: list[texttospeech_v1.StreamingSynthesizeRequest] = []
        self.unary_request: texttospeech_v1.SynthesizeSpeechRequest | None = None

    async def streaming_synthesize(
        self,
        *,
        requests: AsyncIterator[texttospeech_v1.StreamingSynthesizeRequest],
    ) -> AsyncIterator[texttospeech_v1.StreamingSynthesizeResponse]:
        self.streaming_requests = [request async for request in requests]
        if self.streaming_error is not None:
            raise self.streaming_error

        async def responses() -> AsyncIterator[texttospeech_v1.StreamingSynthesizeResponse]:
            yield texttospeech_v1.StreamingSynthesizeResponse(audio_content=b"pcm-one")
            yield texttospeech_v1.StreamingSynthesizeResponse(audio_content=b"pcm-two")

        return responses()

    async def synthesize_speech(
        self,
        *,
        request: texttospeech_v1.SynthesizeSpeechRequest,
    ) -> Any:
        self.unary_request = request
        return texttospeech_v1.SynthesizeSpeechResponse(audio_content=b"pcm-fallback")


@pytest.mark.asyncio
async def test_streaming_tts_emits_headerless_pcm_and_maps_voice_alias() -> None:
    fake = FakeTextToSpeechClient()
    adapter = GcpStreamingTextToSpeech(
        cast(texttospeech_v1.TextToSpeechAsyncClient, fake),
        language_code="ko-KR",
        default_voice_name="ko-KR-Chirp3-HD-Achernar",
        voice_aliases={"Seoyeon": "ko-KR-Chirp3-HD-Aoede"},
    )

    chunks = [
        chunk
        async for chunk in adapter.synthesize_stream(
            _context(), "다음 질문입니다.", voice_id="Seoyeon"
        )
    ]

    assert [chunk.content for chunk in chunks] == [b"pcm-one", b"pcm-two"]
    assert all(chunk.encoding == "pcm_s16le" for chunk in chunks)
    config = fake.streaming_requests[0].streaming_config
    assert config.voice.name == "ko-KR-Chirp3-HD-Aoede"
    assert config.streaming_audio_config.audio_encoding == texttospeech_v1.AudioEncoding.PCM
    assert fake.streaming_requests[1].input.text == "다음 질문입니다."


@pytest.mark.asyncio
async def test_streaming_tts_falls_back_to_unary_before_emitting_audio() -> None:
    fake = FakeTextToSpeechClient(streaming_error=RuntimeError("stream unavailable"))
    adapter = GcpStreamingTextToSpeech(
        cast(texttospeech_v1.TextToSpeechAsyncClient, fake),
        language_code="ko-KR",
        default_voice_name="ko-KR-Chirp3-HD-Achernar",
    )

    chunks = [
        chunk
        async for chunk in adapter.synthesize_stream(_context(), "질문", voice_id="interviewer")
    ]

    assert [chunk.content for chunk in chunks] == [b"pcm-fallback"]
    assert fake.unary_request is not None
    assert fake.unary_request.audio_config.audio_encoding == texttospeech_v1.AudioEncoding.PCM
