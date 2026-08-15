from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WebSocketEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_version: Literal["1.0"]
    message_type: str = Field(pattern=r"^[a-z]+(?:\.[a-z_]+)+$")
    session_id: UUID
    sequence: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=200)
    correlation_id: UUID
    sent_at: datetime
    payload: dict[str, object]
