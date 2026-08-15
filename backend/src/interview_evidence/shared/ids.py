from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    def __init__(self, current: datetime) -> None:
        if current.tzinfo is None:
            raise ValueError("clock time must be timezone-aware")
        self._current = current

    def now(self) -> datetime:
        return self._current


def new_uuid7(occurred_at: datetime | None = None, *, random_bits: int | None = None) -> UUID:
    timestamp = occurred_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("UUIDv7 timestamp must be timezone-aware")

    timestamp_ms = int(timestamp.timestamp() * 1000)
    if not 0 <= timestamp_ms < 1 << 48:
        raise ValueError("UUIDv7 timestamp is outside the 48-bit range")

    randomness = secrets.randbits(74) if random_bits is None else random_bits
    if not 0 <= randomness < 1 << 74:
        raise ValueError("UUIDv7 randomness must fit in 74 bits")

    rand_a = (randomness >> 62) & 0xFFF
    rand_b = randomness & ((1 << 62) - 1)
    value = (timestamp_ms << 80) | (7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    return UUID(int=value)


class CommandMeta(BaseModel):
    model_config = ConfigDict(frozen=True)

    idempotency_key: str = Field(min_length=8, max_length=200)
    expected_version: int | None = Field(default=None, ge=0)
    occurred_at: datetime

    @classmethod
    def create(
        cls,
        idempotency_key: str,
        *,
        clock: Clock | None = None,
        expected_version: int | None = None,
    ) -> CommandMeta:
        return cls(
            idempotency_key=idempotency_key,
            expected_version=expected_version,
            occurred_at=(clock or SystemClock()).now(),
        )
