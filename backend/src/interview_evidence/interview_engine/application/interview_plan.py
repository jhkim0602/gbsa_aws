from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class VerificationTargetPlan:
    verification_target_id: UUID
    criterion_id: UUID
    criterion_text: str
    target_type: str
    objective: str
    missing_dimensions: tuple[str, ...]
    follow_up_directions: tuple[str, ...]
    max_follow_ups: int
    common_question: str

    def __post_init__(self) -> None:
        if not self.criterion_text.strip():
            raise ValueError("verification target requires criterion text")
        if not self.objective.strip():
            raise ValueError("verification target requires an objective")
        if not 0 <= self.max_follow_ups <= 3:
            raise ValueError("verification target follow-up budget must be between 0 and 3")


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
    verification_targets: tuple[VerificationTargetPlan, ...] = ()

    def __post_init__(self) -> None:
        if not self.criterion_ids:
            raise ValueError("interview plan requires at least one criterion")
        if not self.initial_question.strip().endswith("?"):
            raise ValueError("initial interview prompt must be one question")
        if not self.fallback_question.strip().endswith("?"):
            raise ValueError("fallback interview prompt must be one question")
        if self.remaining_time_seconds <= 0:
            raise ValueError("interview plan requires a positive time budget")
        if self.verification_targets:
            target_criteria = {target.criterion_id for target in self.verification_targets}
            if not target_criteria.issubset(set(self.criterion_ids)):
                raise ValueError("verification target criterion is outside the plan")

    def initial_target(self) -> VerificationTargetPlan | None:
        return self.verification_targets[0] if self.verification_targets else None

    def target(self, target_id: UUID) -> VerificationTargetPlan:
        for target in self.verification_targets:
            if target.verification_target_id == target_id:
                return target
        raise LookupError("verification target is outside the plan")

    def next_target_after_answer(
        self,
        *,
        answered_target_id: UUID,
        follow_up_count: int,
        completed_target_ids: frozenset[UUID],
    ) -> VerificationTargetPlan | None:
        answered = self.target(answered_target_id)
        if follow_up_count < answered.max_follow_ups:
            return answered
        completed = completed_target_ids | {answered_target_id}
        return next(
            (
                target
                for target in self.verification_targets
                if target.verification_target_id not in completed
            ),
            None,
        )


class InterviewPlanProvider(Protocol):
    def get_interview_plan(
        self,
        context: TenantContext,
        *,
        strategy_id: UUID,
        competency_model_version_id: UUID,
    ) -> InterviewPlan: ...
