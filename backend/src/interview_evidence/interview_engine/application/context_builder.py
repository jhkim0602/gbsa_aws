from __future__ import annotations

from math import ceil
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContextTurn(BaseModel):
    model_config = ConfigDict(frozen=True)

    turn_id: UUID
    speaker: str
    text: str


class BuiltInterviewContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    recent_turns: tuple[ContextTurn, ...]
    older_summary: str
    remaining_criterion_ids: tuple[UUID, ...]
    remaining_time_seconds: int = Field(ge=0)
    retrieved_source_ids: tuple[UUID, ...]
    estimated_tokens: int = Field(ge=0)

    def model_payload(self) -> dict[str, object]:
        return {
            "recent_turns": [
                {
                    "turn_id": str(turn.turn_id),
                    "speaker": turn.speaker,
                    "text": turn.text,
                }
                for turn in self.recent_turns
            ],
            "older_summary": self.older_summary,
            "remaining_criterion_ids": [
                str(criterion_id) for criterion_id in self.remaining_criterion_ids
            ],
            "remaining_time_seconds": self.remaining_time_seconds,
            "retrieved_source_ids": [str(source_id) for source_id in self.retrieved_source_ids],
        }


def _estimate_tokens(text: str) -> int:
    return max(1, ceil(len(text) / 4))


class ContextBuilder:
    def __init__(self, *, token_budget: int) -> None:
        if token_budget < 64:
            raise ValueError("context token budget must be at least 64")
        self._token_budget = token_budget

    def build(
        self,
        *,
        recent_turns: tuple[ContextTurn, ...],
        older_summary: str,
        remaining_criterion_ids: tuple[UUID, ...],
        remaining_time_seconds: int,
        retrieved_source_ids: tuple[UUID, ...],
    ) -> BuiltInterviewContext:
        base_text = " ".join(
            (
                older_summary,
                str(remaining_time_seconds),
                *(str(value) for value in remaining_criterion_ids),
                *(str(value) for value in retrieved_source_ids),
            )
        )
        estimated = _estimate_tokens(base_text)
        selected_reversed: list[ContextTurn] = []
        for turn in reversed(recent_turns):
            turn_tokens = _estimate_tokens(f"{turn.speaker} {turn.text}")
            if estimated + turn_tokens > self._token_budget and selected_reversed:
                continue
            if estimated + turn_tokens > self._token_budget:
                available_chars = max(4, (self._token_budget - estimated) * 4)
                turn = turn.model_copy(update={"text": turn.text[-available_chars:]})
                turn_tokens = _estimate_tokens(f"{turn.speaker} {turn.text}")
            selected_reversed.append(turn)
            estimated += turn_tokens
            if estimated >= self._token_budget:
                break

        return BuiltInterviewContext(
            recent_turns=tuple(reversed(selected_reversed)),
            older_summary=older_summary,
            remaining_criterion_ids=remaining_criterion_ids,
            remaining_time_seconds=remaining_time_seconds,
            retrieved_source_ids=retrieved_source_ids,
            estimated_tokens=min(estimated, self._token_budget),
        )
