from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from google.api_core.client_options import ClientOptions
from google.cloud import speech_v1, texttospeech_v1

from interview_evidence.shared.gcp_clients.speech import (
    GcpStreamingSpeechToText,
    GcpStreamingTextToSpeech,
)
from interview_evidence.shared.speech.ports import (
    StreamingSpeechToText,
    StreamingTextToSpeech,
)

SpeechClientFactory = Callable[[ClientOptions], speech_v1.SpeechAsyncClient]
TextToSpeechClientFactory = Callable[[ClientOptions], texttospeech_v1.TextToSpeechAsyncClient]


@dataclass(frozen=True, slots=True)
class SpeechRuntimeDependencies:
    streaming_speech_to_text: StreamingSpeechToText | None
    streaming_text_to_speech: StreamingTextToSpeech | None


def create_speech_runtime_dependencies(
    environment: Mapping[str, str],
    *,
    speech_client_factory: SpeechClientFactory | None = None,
    text_to_speech_client_factory: TextToSpeechClientFactory | None = None,
) -> SpeechRuntimeDependencies:
    stt_provider = environment.get("STT_PROVIDER", "aws_legacy").strip().casefold()
    tts_provider = environment.get("TTS_PROVIDER", "aws_legacy").strip().casefold()
    if stt_provider not in {"aws_legacy", "gcp_streaming", "disabled"}:
        raise RuntimeError("STT_PROVIDER must be aws_legacy, gcp_streaming or disabled")
    if tts_provider not in {
        "aws_legacy",
        "gcp_streaming",
        "gcp_unary",
        "text_only",
    }:
        raise RuntimeError("TTS_PROVIDER must be aws_legacy, gcp_streaming, gcp_unary or text_only")

    client_options = _client_options(environment)
    streaming_stt: StreamingSpeechToText | None = None
    streaming_tts: StreamingTextToSpeech | None = None
    if stt_provider == "gcp_streaming":
        create_speech_client = speech_client_factory or _create_speech_client
        streaming_stt = GcpStreamingSpeechToText(create_speech_client(client_options))
    if tts_provider in {"gcp_streaming", "gcp_unary"}:
        create_text_to_speech_client = (
            text_to_speech_client_factory or _create_text_to_speech_client
        )
        streaming_tts = GcpStreamingTextToSpeech(
            create_text_to_speech_client(client_options),
            language_code=environment.get("GCP_SPEECH_LANGUAGE_CODE", "ko-KR").strip(),
            default_voice_name=_required(environment, "GCP_TTS_VOICE_NAME"),
            sample_rate_hz=int(environment.get("GCP_TTS_SAMPLE_RATE_HZ", "24000")),
            voice_aliases=_voice_aliases(environment),
            streaming=tts_provider == "gcp_streaming",
            unary_fallback=True,
        )
    return SpeechRuntimeDependencies(
        streaming_speech_to_text=streaming_stt,
        streaming_text_to_speech=streaming_tts,
    )


def _client_options(environment: Mapping[str, str]) -> ClientOptions:
    endpoint = environment.get("GCP_SPEECH_API_ENDPOINT", "").strip()
    return ClientOptions(api_endpoint=endpoint) if endpoint else ClientOptions()


def _create_speech_client(options: ClientOptions) -> speech_v1.SpeechAsyncClient:
    return speech_v1.SpeechAsyncClient(client_options=options)


def _create_text_to_speech_client(
    options: ClientOptions,
) -> texttospeech_v1.TextToSpeechAsyncClient:
    return texttospeech_v1.TextToSpeechAsyncClient(client_options=options)


def _voice_aliases(environment: Mapping[str, str]) -> Mapping[str, str]:
    raw = environment.get("GCP_TTS_VOICE_ALIASES_JSON", "").strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError("GCP_TTS_VOICE_ALIASES_JSON must be valid JSON") from error
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    ):
        raise RuntimeError("GCP_TTS_VOICE_ALIASES_JSON must be a string map")
    return value


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value
