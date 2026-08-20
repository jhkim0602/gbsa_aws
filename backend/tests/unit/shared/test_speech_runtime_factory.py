from __future__ import annotations

from typing import cast

import pytest
from google.api_core.client_options import ClientOptions
from google.cloud import speech_v1, texttospeech_v1
from interview_evidence.runtime.speech import create_speech_runtime_dependencies


def test_speech_runtime_keeps_legacy_providers_outside_gcp_factory() -> None:
    dependencies = create_speech_runtime_dependencies({})

    assert dependencies.streaming_speech_to_text is None
    assert dependencies.streaming_text_to_speech is None
    assert dependencies.stt_provider == "aws_legacy"
    assert dependencies.tts_provider == "aws_legacy"


def test_speech_runtime_builds_selected_gcp_streaming_clients() -> None:
    options: list[ClientOptions] = []

    def speech_factory(client_options: ClientOptions) -> speech_v1.SpeechAsyncClient:
        options.append(client_options)
        return cast(speech_v1.SpeechAsyncClient, object())

    def tts_factory(client_options: ClientOptions) -> texttospeech_v1.TextToSpeechAsyncClient:
        options.append(client_options)
        return cast(texttospeech_v1.TextToSpeechAsyncClient, object())

    dependencies = create_speech_runtime_dependencies(
        {
            "STT_PROVIDER": "gcp_streaming",
            "TTS_PROVIDER": "gcp_streaming",
            "GCP_TTS_VOICE_NAME": "ko-KR-Chirp3-HD-Achernar",
            "GCP_TTS_VOICE_ALIASES_JSON": '{"Seoyeon":"ko-KR-Chirp3-HD-Aoede"}',
            "GCP_STT_API_ENDPOINT": "speech.example.test",
            "GCP_TTS_API_ENDPOINT": "texttospeech.example.test",
        },
        speech_client_factory=speech_factory,
        text_to_speech_client_factory=tts_factory,
    )

    assert dependencies.streaming_speech_to_text is not None
    assert dependencies.streaming_text_to_speech is not None
    assert [option.api_endpoint for option in options] == [
        "speech.example.test",
        "texttospeech.example.test",
    ]


@pytest.mark.parametrize(
    ("name", "value"),
    [("STT_PROVIDER", "other"), ("TTS_PROVIDER", "other")],
)
def test_speech_runtime_rejects_unknown_provider(name: str, value: str) -> None:
    with pytest.raises(RuntimeError, match=name):
        create_speech_runtime_dependencies({name: value})


def test_speech_runtime_requires_voice_for_gcp_tts() -> None:
    with pytest.raises(RuntimeError, match="GCP_TTS_VOICE_NAME is required"):
        create_speech_runtime_dependencies(
            {"TTS_PROVIDER": "gcp_streaming"},
            text_to_speech_client_factory=lambda _: cast(
                texttospeech_v1.TextToSpeechAsyncClient, object()
            ),
        )


def test_speech_runtime_rejects_invalid_voice_aliases() -> None:
    with pytest.raises(RuntimeError, match="must be a string map"):
        create_speech_runtime_dependencies(
            {
                "TTS_PROVIDER": "gcp_unary",
                "GCP_TTS_VOICE_NAME": "ko-KR-Chirp3-HD-Achernar",
                "GCP_TTS_VOICE_ALIASES_JSON": '{"Seoyeon":7}',
            },
            text_to_speech_client_factory=lambda _: cast(
                texttospeech_v1.TextToSpeechAsyncClient, object()
            ),
        )
