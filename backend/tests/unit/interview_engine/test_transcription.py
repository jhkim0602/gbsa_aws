from uuid import UUID

from interview_evidence.interview_engine.adapters.transcribe import (
    StreamingTranscriptionAdapter,
    TranscriptionResult,
)
from interview_evidence.shared.tenant import ActorType, TenantContext


class StaticTranscriber:
    def stream(self, context: TenantContext, audio: bytes) -> tuple[TranscriptionResult, ...]:
        del context, audio
        return (
            TranscriptionResult(
                segment_sequence=1,
                text="중간 결과",
                start_ms=0,
                end_ms=500,
                confidence=0.7,
                is_final=False,
            ),
            TranscriptionResult(
                segment_sequence=1,
                text="최종 답변",
                start_ms=0,
                end_ms=900,
                confidence=0.92,
                is_final=True,
            ),
        )


def test_only_final_transcription_is_evidence_eligible() -> None:
    context = TenantContext(
        company_id=UUID("00000000-0000-7000-8000-000000000001"),
        actor_type=ActorType.APPLICANT,
        actor_id=UUID("00000000-0000-7000-8000-000000000002"),
        request_id=UUID("00000000-0000-7000-8000-000000000003"),
        trace_id="transcription",
    )
    results = StreamingTranscriptionAdapter(StaticTranscriber()).transcribe(context, b"audio")
    assert results[0].display_only is True
    assert results[1].display_only is False
    assert results[1].review_required is False
