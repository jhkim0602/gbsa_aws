from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class InterviewPlan:
    criterion_ids: tuple[UUID, ...]
    initial_question: str
    prohibited_topics: tuple[str, ...]
    fallback_question: str
    remaining_time_seconds: int
    model_config_version: str
    retrieval_config_version: str
    voice_id: str

    def __post_init__(self) -> None:
        if not self.criterion_ids:
            raise ValueError("interview plan requires at least one criterion")
        if not self.initial_question.strip().endswith("?"):
            raise ValueError("initial interview prompt must be one question")
        if not self.fallback_question.strip().endswith("?"):
            raise ValueError("fallback interview prompt must be one question")
        if self.remaining_time_seconds <= 0:
            raise ValueError("interview plan requires a positive time budget")


class InterviewPlanProvider(Protocol):
    def get_interview_plan(
        self,
        context: TenantContext,
        *,
        strategy_id: UUID,
        competency_model_version_id: UUID,
    ) -> InterviewPlan: ...
