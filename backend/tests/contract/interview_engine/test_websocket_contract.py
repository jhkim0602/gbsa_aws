from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

import pytest
from interview_evidence.interview_engine.api.websocket import (
    AudioChunkMetadata,
    WebSocketEnvelope,
    validate_audio_frame,
)
from pydantic import ValidationError


def envelope(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "protocol_version": "1.0",
        "message_type": "answer.complete",
        "session_id": str(UUID("00000000-0000-7000-8000-000000000001")),
        "sequence": 4,
        "idempotency_key": "answer-complete-0001",
        "correlation_id": str(UUID("00000000-0000-7000-8000-000000000002")),
        "sent_at": datetime(2026, 8, 15, 9, 0, tzinfo=UTC).isoformat(),
        "payload": {},
    }
    value.update(overrides)
    return value


def test_websocket_envelope_accepts_the_frozen_protocol() -> None:
    parsed = WebSocketEnvelope.model_validate(envelope())
    assert parsed.protocol_version == "1.0"
    assert parsed.sequence == 4


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("protocol_version", "2.0"),
        ("sequence", -1),
        ("idempotency_key", "short"),
        ("message_type", "AnswerComplete"),
    ],
)
def test_websocket_envelope_rejects_incompatible_values(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        WebSocketEnvelope.model_validate(envelope(**{field: value}))


def test_binary_audio_must_match_declared_size_and_digest() -> None:
    audio = b"\x01\x02\x03\x04"
    metadata = AudioChunkMetadata(
        answer_turn_id=UUID("00000000-0000-7000-8000-000000000003"),
        chunk_sequence=1,
        codec="pcm_s16le",
        sample_rate_hz=16000,
        channel_count=1,
        byte_length=len(audio),
        sha256=sha256(audio).hexdigest(),
    )

    validate_audio_frame(metadata, audio)
    with pytest.raises(ValueError):
        validate_audio_frame(metadata, b"\x00")
