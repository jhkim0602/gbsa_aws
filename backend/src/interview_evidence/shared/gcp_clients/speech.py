from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import suppress

from google.cloud import speech_v1, texttospeech_v1

from interview_evidence.shared.speech.ports import (
    SpeechAudioChunk,
    SpeechProviderError,
    SpeechRecognitionConfig,
    SpeechRecognitionSession,
    StreamingSpeechToText,
    StreamingTextToSpeech,
    TranscriptEvent,
)
from interview_evidence.shared.tenant import TenantContext, require_tenant_context

_END_OF_AUDIO = object()


class GcpStreamingSpeechToText(StreamingSpeechToText):
    def __init__(self, client: speech_v1.SpeechAsyncClient) -> None:
        self._client = client

    async def open_stream(
        self,
        context: TenantContext,
        config: SpeechRecognitionConfig,
    ) -> SpeechRecognitionSession:
        require_tenant_context(context)
        return _GcpSpeechRecognitionSession(self._client, config)


class _GcpSpeechRecognitionSession(SpeechRecognitionSession):
    def __init__(
        self,
        client: speech_v1.SpeechAsyncClient,
        config: SpeechRecognitionConfig,
    ) -> None:
        self._client = client
        self._config = config
        self._audio: asyncio.Queue[bytes | object] = asyncio.Queue(maxsize=config.queue_max_chunks)
        self._ended = False
        self._aborted = False

    async def send_audio(self, chunk: bytes) -> None:
        if self._ended:
            raise SpeechProviderError("speech recognition input is closed")
        if not chunk:
            return
        await self._audio.put(chunk)

    async def end_input(self) -> None:
        if self._ended:
            return
        self._ended = True
        await self._audio.put(_END_OF_AUDIO)

    async def abort(self) -> None:
        self._aborted = True
        if self._ended:
            return
        self._ended = True
        with suppress(asyncio.QueueEmpty):
            self._audio.get_nowait()
        self._audio.put_nowait(_END_OF_AUDIO)

    async def _requests(self) -> AsyncIterator[speech_v1.StreamingRecognizeRequest]:
        recognition = speech_v1.RecognitionConfig(
            encoding=speech_v1.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=self._config.sample_rate_hz,
            language_code=self._config.language_code,
            audio_channel_count=self._config.channel_count,
            enable_automatic_punctuation=True,
            model=self._config.model,
        )
        yield speech_v1.StreamingRecognizeRequest(
            streaming_config=speech_v1.StreamingRecognitionConfig(
                config=recognition,
                interim_results=True,
                single_utterance=False,
            )
        )
        while True:
            item = await self._audio.get()
            if item is _END_OF_AUDIO:
                return
            yield speech_v1.StreamingRecognizeRequest(audio_content=item)

    async def results(self) -> AsyncIterator[TranscriptEvent]:
        if self._aborted:
            return
        try:
            responses = await self._client.streaming_recognize(requests=self._requests())
            async for response in responses:
                for result in response.results:
                    if not result.alternatives:
                        continue
                    alternative = result.alternatives[0]
                    text = alternative.transcript.strip()
                    if not text:
                        continue
                    yield TranscriptEvent(
                        text=text,
                        is_final=bool(result.is_final),
                        confidence=float(alternative.confidence or 0.0),
                        stability=float(result.stability or 0.0),
                    )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            raise SpeechProviderError("GCP speech recognition unavailable") from error


class GcpStreamingTextToSpeech(StreamingTextToSpeech):
    def __init__(
        self,
        client: texttospeech_v1.TextToSpeechAsyncClient,
        *,
        language_code: str,
        default_voice_name: str,
        sample_rate_hz: int = 24000,
        voice_aliases: Mapping[str, str] | None = None,
        streaming: bool = True,
        unary_fallback: bool = True,
    ) -> None:
        self._client = client
        self._language_code = language_code
        self._default_voice_name = default_voice_name
        self._sample_rate_hz = sample_rate_hz
        self._voice_aliases = dict(voice_aliases or {})
        self._streaming = streaming
        self._unary_fallback = unary_fallback

    def synthesize_stream(
        self,
        context: TenantContext,
        text: str,
        *,
        voice_id: str,
    ) -> AsyncIterator[SpeechAudioChunk]:
        require_tenant_context(context)
        return self._synthesize(text, voice_id=voice_id)

    async def _synthesize(
        self,
        text: str,
        *,
        voice_id: str,
    ) -> AsyncIterator[SpeechAudioChunk]:
        emitted = False
        if self._streaming:
            try:
                async for chunk in self._streaming_synthesis(text, voice_id=voice_id):
                    emitted = True
                    yield chunk
                return
            except asyncio.CancelledError:
                raise
            except Exception as error:
                if emitted or not self._unary_fallback:
                    raise SpeechProviderError("GCP streaming synthesis unavailable") from error
        if not self._unary_fallback:
            raise SpeechProviderError("GCP streaming synthesis unavailable")
        async for chunk in self._unary_synthesis(text, voice_id=voice_id):
            yield chunk

    async def _streaming_synthesis(
        self,
        text: str,
        *,
        voice_id: str,
    ) -> AsyncIterator[SpeechAudioChunk]:
        async def requests() -> AsyncIterator[texttospeech_v1.StreamingSynthesizeRequest]:
            yield texttospeech_v1.StreamingSynthesizeRequest(
                streaming_config=texttospeech_v1.StreamingSynthesizeConfig(
                    voice=self._voice(voice_id),
                    streaming_audio_config=texttospeech_v1.StreamingAudioConfig(
                        audio_encoding=texttospeech_v1.AudioEncoding.PCM,
                        sample_rate_hertz=self._sample_rate_hz,
                    ),
                )
            )
            yield texttospeech_v1.StreamingSynthesizeRequest(
                input=texttospeech_v1.StreamingSynthesisInput(text=text)
            )

        responses = await self._client.streaming_synthesize(requests=requests())
        async for response in responses:
            content = bytes(response.audio_content)
            if content:
                yield self._chunk(content)

    async def _unary_synthesis(
        self,
        text: str,
        *,
        voice_id: str,
    ) -> AsyncIterator[SpeechAudioChunk]:
        try:
            response = await self._client.synthesize_speech(
                request=texttospeech_v1.SynthesizeSpeechRequest(
                    input=texttospeech_v1.SynthesisInput(text=text),
                    voice=self._voice(voice_id),
                    audio_config=texttospeech_v1.AudioConfig(
                        audio_encoding=texttospeech_v1.AudioEncoding.PCM,
                        sample_rate_hertz=self._sample_rate_hz,
                    ),
                )
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            raise SpeechProviderError("GCP speech synthesis unavailable") from error
        content = bytes(response.audio_content)
        if content:
            yield self._chunk(content)

    def _voice(self, voice_id: str) -> texttospeech_v1.VoiceSelectionParams:
        voice_name = self._voice_aliases.get(voice_id, self._default_voice_name)
        return texttospeech_v1.VoiceSelectionParams(
            language_code=self._language_code,
            name=voice_name,
        )

    def _chunk(self, content: bytes) -> SpeechAudioChunk:
        return SpeechAudioChunk(
            content=content,
            sample_rate_hz=self._sample_rate_hz,
        )
