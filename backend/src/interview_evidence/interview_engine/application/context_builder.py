from __future__ import annotations

from math import ceil
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContextTurn(BaseModel):
    model_config = ConfigDict(frozen=True)

    turn_id: UUID
    speaker: str
    text: str


class RetrievedSourceContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_id: UUID
    source_type: str
    locator: dict[str, object]
    excerpt: str
    score: float
    material_type: str | None = None


class BuiltInterviewContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    recent_turns: tuple[ContextTurn, ...]
    older_summary: str
    remaining_criterion_ids: tuple[UUID, ...]
    remaining_time_seconds: int = Field(ge=0)
    interview_stage: str = ""
    interview_stage_focus: str = ""
    next_question_type: str = "adaptive"
    required_assessment_axis: str | None = None
    retrieved_source_ids: tuple[UUID, ...]
    retrieved_sources: tuple[RetrievedSourceContext, ...] = ()
    criterion_text: str = ""
    verification_objective: str = ""
    missing_dimensions: tuple[str, ...] = ()
    follow_up_directions: tuple[str, ...] = ()
    answer_evidence_gaps: tuple[str, ...] = ()
    stage_evidence_available: bool = True
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
            "interview_stage": self.interview_stage,
            "interview_stage_focus": self.interview_stage_focus,
            "next_question_type": self.next_question_type,
            "required_assessment_axis": self.required_assessment_axis,
            "retrieved_source_ids": [str(source_id) for source_id in self.retrieved_source_ids],
            "criterion_text": self.criterion_text,
            "verification_objective": self.verification_objective,
            "missing_dimensions": list(self.missing_dimensions),
            "follow_up_directions": list(self.follow_up_directions),
            "answer_evidence_gaps": list(self.answer_evidence_gaps),
            "stage_evidence_available": self.stage_evidence_available,
            "retrieved_sources": [
                {
                    "source_id": str(source.source_id),
                    "source_type": source.source_type,
                    "locator": source.locator,
                    "excerpt": source.excerpt,
                    "score": source.score,
                    "material_type": source.material_type,
                }
                for source in self.retrieved_sources
            ],
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
        interview_stage: str = "",
        interview_stage_focus: str = "",
        next_question_type: str = "adaptive",
        required_assessment_axis: str | None = None,
        retrieved_sources: tuple[RetrievedSourceContext, ...] = (),
        criterion_text: str = "",
        verification_objective: str = "",
        missing_dimensions: tuple[str, ...] = (),
        follow_up_directions: tuple[str, ...] = (),
        answer_evidence_gaps: tuple[str, ...] = (),
        stage_evidence_available: bool = True,
    ) -> BuiltInterviewContext:
        base_text = " ".join(
            (
                older_summary,
                str(remaining_time_seconds),
                interview_stage,
                interview_stage_focus,
                next_question_type,
                required_assessment_axis or "",
                *(str(value) for value in remaining_criterion_ids),
                *(str(value) for value in retrieved_source_ids),
                criterion_text,
                verification_objective,
                *missing_dimensions,
                *follow_up_directions,
                *answer_evidence_gaps,
                str(stage_evidence_available),
                *(source.excerpt for source in retrieved_sources),
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
            interview_stage=interview_stage,
            interview_stage_focus=interview_stage_focus,
            next_question_type=next_question_type,
            required_assessment_axis=required_assessment_axis,
            retrieved_source_ids=retrieved_source_ids,
            retrieved_sources=retrieved_sources,
            criterion_text=criterion_text,
            verification_objective=verification_objective,
            missing_dimensions=missing_dimensions,
            follow_up_directions=follow_up_directions,
            answer_evidence_gaps=answer_evidence_gaps,
            stage_evidence_available=stage_evidence_available,
            estimated_tokens=min(estimated, self._token_budget),
        )
