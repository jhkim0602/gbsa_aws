from dataclasses import dataclass
from enum import StrEnum
from math import ceil
from typing import Protocol
from uuid import UUID

from interview_evidence.shared.interview_level import (
    DEFAULT_INTERVIEW_LEVEL,
    MAX_FOLLOW_UPS,
    InterviewLevel,
)
from interview_evidence.shared.tenant import TenantContext


class InterviewStage(StrEnum):
    TECHNICAL = "technical"
    PROJECT_DEEP_DIVE = "project_deep_dive"
    BEHAVIORAL = "behavioral"


DEFAULT_INTERVIEW_STAGES = (
    InterviewStage.TECHNICAL,
    InterviewStage.PROJECT_DEEP_DIVE,
    InterviewStage.BEHAVIORAL,
)
INTERVIEW_STAGE_FOCUS = {
    InterviewStage.TECHNICAL: "기술 선택, 구현 원리, 문제 해결 과정과 트레이드오프",
    InterviewStage.PROJECT_DEEP_DIVE: "프로젝트 목표, 본인 역할, 설계와 구현, 결과와 회고",
    InterviewStage.BEHAVIORAL: "협업, 갈등 조정, 의사소통, 피드백과 책임",
}
INTERVIEW_STAGE_WEIGHTS = {
    InterviewStage.TECHNICAL: 3,
    InterviewStage.PROJECT_DEEP_DIVE: 4,
    InterviewStage.BEHAVIORAL: 3,
}
FIXED_INTERVIEW_DURATION_SECONDS = 30 * 60
EXPECTED_QUESTION_SECONDS = 90
DEFAULT_OPENING_MESSAGE = "안녕하세요. 오늘은 기술, 프로젝트, 협업 경험을 중심으로 진행하겠습니다."
DEFAULT_WARM_UP_QUESTION = (
    "먼저 간단한 자기소개와 지원 직무와 관련해 가장 자신 있는 경험을 말씀해 주시겠어요?"
)


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
    #: Seconds this criterion may occupy, from CriterionVerificationGuide. The loop
    #: stops opening new targets once the plan's remaining budget cannot cover one.
    time_budget_seconds: int = 300

    def __post_init__(self) -> None:
        if not self.criterion_text.strip():
            raise ValueError("verification target requires criterion text")
        if not self.objective.strip():
            raise ValueError("verification target requires an objective")
        if not 0 <= self.max_follow_ups <= MAX_FOLLOW_UPS:
            raise ValueError("verification target follow-up budget must be between 0 and 3")
        if self.time_budget_seconds <= 0:
            raise ValueError("verification target requires a positive time budget")


@dataclass(frozen=True, slots=True)
class StageQuestionDecision:
    stage: InterviewStage
    question_type: str
    completes_interview: bool = False


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
    interview_level: InterviewLevel = DEFAULT_INTERVIEW_LEVEL
    stages: tuple[InterviewStage, ...] = DEFAULT_INTERVIEW_STAGES
    opening_message: str = DEFAULT_OPENING_MESSAGE
    warm_up_question: str = DEFAULT_WARM_UP_QUESTION

    def __post_init__(self) -> None:
        if not self.criterion_ids:
            raise ValueError("interview plan requires at least one criterion")
        if not self.initial_question.strip().endswith("?"):
            raise ValueError("initial interview prompt must be one question")
        if not self.fallback_question.strip().endswith("?"):
            raise ValueError("fallback interview prompt must be one question")
        if self.remaining_time_seconds != FIXED_INTERVIEW_DURATION_SECONDS:
            raise ValueError("interview plan requires the fixed 30 minute duration")
        if self.verification_targets:
            target_criteria = {target.criterion_id for target in self.verification_targets}
            if not target_criteria.issubset(set(self.criterion_ids)):
                raise ValueError("verification target criterion is outside the plan")
        if self.stages != DEFAULT_INTERVIEW_STAGES:
            raise ValueError("interview plan requires the fixed interview stage sequence")
        if not self.opening_message.strip():
            raise ValueError("interview plan requires an opening message")
        if not self.warm_up_question.strip().endswith("?"):
            raise ValueError("interview warm-up prompt must be one question")

    @property
    def opening_prompt(self) -> str:
        return f"{self.opening_message.strip()} {self.warm_up_question.strip()}"

    def is_warm_up_question(self, text: str | None) -> bool:
        if text is None:
            return False
        return text.strip() == self.opening_prompt

    def initial_target(self) -> VerificationTargetPlan | None:
        return self.verification_targets[0] if self.verification_targets else None

    @property
    def initial_stage(self) -> InterviewStage:
        return self.stages[0]

    def stage_time_budget_seconds(self, stage: InterviewStage) -> int:
        weight_total = sum(INTERVIEW_STAGE_WEIGHTS.values())
        return max(
            1,
            self.remaining_time_seconds * INTERVIEW_STAGE_WEIGHTS[stage] // weight_total,
        )

    def stage_question_limit(self, stage: InterviewStage) -> int:
        return max(
            1,
            ceil(self.stage_time_budget_seconds(stage) / EXPECTED_QUESTION_SECONDS),
        )

    def next_stage_after(self, stage: InterviewStage) -> InterviewStage | None:
        index = self.stages.index(stage)
        return self.stages[index + 1] if index + 1 < len(self.stages) else None

    def next_stage_question(
        self,
        *,
        current_stage: InterviewStage,
        stage_question_count: int,
        stage_elapsed_seconds: int,
        total_elapsed_seconds: int,
        last_question_was_final: bool,
    ) -> StageQuestionDecision:
        if stage_question_count < 0 or stage_elapsed_seconds < 0 or total_elapsed_seconds < 0:
            raise ValueError("interview stage progress cannot be negative")
        if stage_question_count == 0:
            question_type = (
                "stage_final" if self.stage_question_limit(current_stage) == 1 else "stage_opening"
            )
            return StageQuestionDecision(current_stage, question_type)

        stage_budget = self.stage_time_budget_seconds(current_stage)
        stage_limit = self.stage_question_limit(current_stage)
        stage_exhausted = (
            last_question_was_final
            or stage_elapsed_seconds >= stage_budget
            or stage_question_count >= stage_limit
            or total_elapsed_seconds >= self.remaining_time_seconds
        )
        if stage_exhausted:
            next_stage = self.next_stage_after(current_stage)
            if next_stage is None:
                return StageQuestionDecision(
                    current_stage,
                    "complete",
                    completes_interview=True,
                )
            question_type = (
                "stage_final" if self.stage_question_limit(next_stage) == 1 else "stage_opening"
            )
            return StageQuestionDecision(next_stage, question_type)

        stage_remaining = stage_budget - stage_elapsed_seconds
        total_remaining = self.remaining_time_seconds - total_elapsed_seconds
        final_window = max(30, min(90, stage_budget // 4))
        next_question_is_final = (
            stage_question_count + 1 >= stage_limit
            or stage_remaining <= final_window
            or total_remaining <= final_window
        )
        return StageQuestionDecision(
            current_stage,
            "stage_final" if next_question_is_final else "adaptive",
        )

    def next_target_for_question(
        self,
        *,
        answered_target_id: UUID,
        follow_up_count: int,
        completed_target_ids: frozenset[UUID],
        prefer_new_target: bool,
    ) -> VerificationTargetPlan:
        answered = self.target(answered_target_id)
        if (
            not prefer_new_target
            and answered_target_id not in completed_target_ids
            and follow_up_count < self.follow_up_budget(answered)
        ):
            return answered
        upcoming = next(
            (
                target
                for target in self.verification_targets
                if target.verification_target_id not in completed_target_ids
                and target.verification_target_id != answered_target_id
            ),
            None,
        )
        return upcoming or self.initial_target() or answered

    def target(self, target_id: UUID) -> VerificationTargetPlan:
        for target in self.verification_targets:
            if target.verification_target_id == target_id:
                return target
        raise LookupError("verification target is outside the plan")

    def follow_up_budget(self, target: VerificationTargetPlan) -> int:
        """How many follow-ups this interview allows on one target.

        The recruiter configures the number per criterion; the interview level moves it
        so the same criteria can be reused for a 신입 and a 시니어 posting.
        """
        return self.interview_level.follow_up_budget(target.max_follow_ups)

    def next_target_after_answer(
        self,
        *,
        answered_target_id: UUID,
        follow_up_count: int,
        completed_target_ids: frozenset[UUID],
        elapsed_seconds: int = 0,
    ) -> VerificationTargetPlan | None:
        answered = self.target(answered_target_id)
        remaining_seconds = self.remaining_time_seconds - max(0, elapsed_seconds)
        if remaining_seconds <= 0:
            return None
        if follow_up_count < self.follow_up_budget(answered):
            return answered
        completed = completed_target_ids | {answered_target_id}
        upcoming = next(
            (
                target
                for target in self.verification_targets
                if target.verification_target_id not in completed
            ),
            None,
        )
        # Opening a criterion needs room for the budget its verification guide asks
        # for; starting one the clock cannot finish leaves it half-verified, which is
        # worse evidence than ending the interview here.
        if upcoming is not None and remaining_seconds < upcoming.time_budget_seconds:
            return None
        return upcoming


class InterviewPlanProvider(Protocol):
    def get_interview_plan(
        self,
        context: TenantContext,
        *,
        strategy_id: UUID,
        competency_model_version_id: UUID,
    ) -> InterviewPlan: ...
