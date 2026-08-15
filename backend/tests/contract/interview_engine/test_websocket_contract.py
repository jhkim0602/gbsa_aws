from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.interview_engine.api.websocket import WebSocketEnvelope
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
