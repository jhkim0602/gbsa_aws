from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InvalidSessionTransition(ValueError):
    pass


class InterviewSessionState(StrEnum):
    PREPARING = "preparing"
    IN_PROGRESS = "in_progress"
    AWAITING_ANSWER = "awaiting_answer"
    PREPARING_QUESTION = "preparing_question"
    PAUSED = "paused"
    COMPLETED = "completed"
    REPORT_GENERATING = "report_generating"
    REVIEWABLE = "reviewable"


SESSION_TRANSITIONS: dict[InterviewSessionState, frozenset[InterviewSessionState]] = {
    InterviewSessionState.PREPARING: frozenset({InterviewSessionState.IN_PROGRESS}),
    InterviewSessionState.IN_PROGRESS: frozenset(
        {
            InterviewSessionState.AWAITING_ANSWER,
            InterviewSessionState.PAUSED,
            InterviewSessionState.COMPLETED,
        }
    ),
    InterviewSessionState.AWAITING_ANSWER: frozenset(
        {
            InterviewSessionState.PREPARING_QUESTION,
            InterviewSessionState.PAUSED,
            InterviewSessionState.COMPLETED,
        }
    ),
    InterviewSessionState.PREPARING_QUESTION: frozenset(
        {InterviewSessionState.IN_PROGRESS, InterviewSessionState.PAUSED}
    ),
    InterviewSessionState.PAUSED: frozenset({InterviewSessionState.IN_PROGRESS}),
    InterviewSessionState.COMPLETED: frozenset({InterviewSessionState.REPORT_GENERATING}),
    InterviewSessionState.REPORT_GENERATING: frozenset({InterviewSessionState.REVIEWABLE}),
    InterviewSessionState.REVIEWABLE: frozenset(),
}


class InterviewSession(BaseModel):
    model_config = ConfigDict(frozen=True)

    interview_session_id: UUID
    company_id: UUID
    invitation_id: UUID
    applicant_id: UUID
    interview_strategy_id: UUID
    competency_model_version_id: UUID
    state: InterviewSessionState = InterviewSessionState.PREPARING
    session_sequence: int = Field(default=0, ge=0)
    row_version: int = Field(default=1, ge=1)
    degraded_modes: tuple[str, ...] = ()
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def timestamps_match_state(self) -> InterviewSession:
        if self.state is InterviewSessionState.COMPLETED and self.completed_at is None:
            raise ValueError("completed session requires completed_at")
        return self

    def transition(
        self,
        target: InterviewSessionState,
        *,
        occurred_at: datetime | None = None,
    ) -> InterviewSession:
        if target not in SESSION_TRANSITIONS[self.state]:
            raise InvalidSessionTransition(
                f"cannot transition interview session from {self.state} to {target}"
            )
        updates: dict[str, object] = {
            "state": target,
            "session_sequence": self.session_sequence + 1,
            "row_version": self.row_version + 1,
        }
        if target is InterviewSessionState.IN_PROGRESS and self.started_at is None:
            updates["started_at"] = occurred_at or self.created_at
        if target is InterviewSessionState.COMPLETED:
            updates["completed_at"] = occurred_at
        return self.model_copy(update=updates)
