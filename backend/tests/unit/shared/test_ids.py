from datetime import UTC, datetime, timedelta
from uuid import UUID

from interview_evidence.shared.ids import CommandMeta, FrozenClock, new_uuid7


def test_uuid7_is_time_ordered_and_uses_rfc_variant() -> None:
    first_time = datetime(2026, 8, 15, 0, 0, tzinfo=UTC)
    second_time = first_time + timedelta(milliseconds=1)

    first = new_uuid7(first_time, random_bits=0)
    second = new_uuid7(second_time, random_bits=0)

    assert isinstance(first, UUID)
    assert first.version == 7
    assert first.variant == "specified in RFC 4122"
    assert first.int < second.int


def test_command_meta_is_immutable_and_uses_server_time() -> None:
    occurred_at = datetime(2026, 8, 15, 0, 0, tzinfo=UTC)
    clock = FrozenClock(occurred_at)

    meta = CommandMeta.create("stable-idempotency-key", clock=clock, expected_version=3)

    assert meta.occurred_at == occurred_at
    assert meta.expected_version == 3
