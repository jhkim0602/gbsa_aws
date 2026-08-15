from __future__ import annotations

from dataclasses import dataclass

from interview_evidence.shared.aws_clients.ports import TextToSpeech
from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class SpeechOutput:
    audio_url: str | None
    audio_expires_at: str | None
    speech_marks_url: str | None
    text_only: bool
    degraded_mode: str | None = None


class SpeechSynthesisAdapter:
    def __init__(self, synthesizer: TextToSpeech) -> None:
        self._synthesizer = synthesizer

    def synthesize(
        self,
        context: TenantContext,
        *,
        text: str,
        voice_id: str,
    ) -> SpeechOutput:
        try:
            response = self._synthesizer.synthesize(
                context,
                text,
                voice_id=voice_id,
            )
        except Exception:
            return SpeechOutput(
                audio_url=None,
                audio_expires_at=None,
                speech_marks_url=None,
                text_only=True,
                degraded_mode="text_only",
            )
        audio_url = response.get("audio_url")
        return SpeechOutput(
            audio_url=str(audio_url) if audio_url is not None else None,
            audio_expires_at=(
                str(response["audio_expires_at"])
                if response.get("audio_expires_at") is not None
                else None
            ),
            speech_marks_url=(
                str(response["speech_marks_url"])
                if response.get("speech_marks_url") is not None
                else None
            ),
            text_only=audio_url is None,
            degraded_mode=None if audio_url is not None else "text_only",
        )
