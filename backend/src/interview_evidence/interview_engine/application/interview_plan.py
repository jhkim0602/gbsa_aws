from dataclasses import dataclass
from enum import StrEnum
from math import ceil
from typing import Protocol
from uuid import UUID

from interview_evidence.interview_engine.application.question_policy import (
    is_interview_prompt,
)
from interview_evidence.shared.interview_level import (
    DEFAULT_INTERVIEW_LEVEL,
    MAX_FOLLOW_UPS,
    InterviewLevel,
)
from interview_evidence.shared.tenant import TenantContext


class InterviewStage(StrEnum):
    ADAPTIVE = "adaptive"
    TECHNICAL = "technical"
    PROJECT_DEEP_DIVE = "project_deep_dive"
    BEHAVIORAL = "behavioral"


DEFAULT_INTERVIEW_STAGES = (InterviewStage.ADAPTIVE,)
INTERVIEW_STAGE_FOCUS = {
    InterviewStage.ADAPTIVE: (
        "회사가 설정한 필수·우대 자격요건과 반드시 물어볼 질문을 중심으로 확인합니다. "
        "지원자의 제출 자료에서 관련 근거를 찾아 질문에 자연스럽게 연결하고, 직전 답변에 "
        "상황·본인 행동·판단 근거·결과가 부족할 때만 필요한 꼬리질문을 이어갑니다."
    ),
    InterviewStage.TECHNICAL: (
        "기술 선택, 구현 원리, 문제 해결 과정, 대안과 트레이드오프를 확인합니다. "
        "협업 방식 자체를 중심 질문으로 삼지 않습니다."
    ),
    InterviewStage.PROJECT_DEEP_DIVE: (
        "하나의 실제 프로젝트를 기준으로 목표, 주요 구성 요소와 책임 경계, 요청·데이터 흐름, "
        "설계 결정과 트레이드오프, 운영·확장 방식, 본인 기여를 연결해 확인합니다. "
        "특정 함수, 메서드, 클래스 내부 구현이나 코드 문법을 직접 묻지 않습니다."
    ),
    InterviewStage.BEHAVIORAL: (
        "실제 경험에서 함께 일한 사람, 역할 조율, 의견 차이, 의사소통, 피드백과 책임을 "
        "확인합니다. 기술 구현이나 장애 해결만 묻는 질문은 사용하지 않습니다."
    ),
}
INTERVIEW_STAGE_WEIGHTS = {
    InterviewStage.ADAPTIVE: 1,
    InterviewStage.TECHNICAL: 3,
    InterviewStage.PROJECT_DEEP_DIVE: 4,
    InterviewStage.BEHAVIORAL: 3,
}
FIXED_INTERVIEW_DURATION_SECONDS = 30 * 60
EXPECTED_QUESTION_SECONDS = 90
FOLLOW_UP_QUESTION_TYPE = "follow_up"
CORE_QUESTION_TYPES = frozenset(
    {
        "common",
        "personalized",
        "adaptive",
        "core",
        "stage_opening",
        "stage_final",
    }
)
DEFAULT_OPENING_MESSAGE = (
    "안녕하세요. 오늘은 회사가 설정한 자격요건과 제출하신 자료를 바탕으로 진행하겠습니다."
)
DEFAULT_WARM_UP_QUESTION = (
    "먼저 간단한 자기소개와 지원 직무와 관련해 가장 자신 있는 경험을 말씀해 주시겠어요?"
)

_STAGE_CRITERION_TERMS = {
    InterviewStage.TECHNICAL: (
        "기술",
        "구현",
        "개발",
        "시스템",
        "설계",
        "cs 기본기",
        "문제 해결",
    ),
    InterviewStage.PROJECT_DEEP_DIVE: (
        "프로젝트",
        "실행",
        "성과",
        "제품",
        "과제",
        "오너십",
    ),
    InterviewStage.BEHAVIORAL: (
        "협업",
        "행동",
        "인성",
        "소통",
        "조율",
        "피드백",
        "갈등",
        "리더십",
        "팀워크",
    ),
}


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

    @property
    def preferred_stage(self) -> InterviewStage | None:
        return infer_criterion_stage(self.criterion_text)


def infer_criterion_stage(criterion_text: str) -> InterviewStage | None:
    """Map a published criterion to the interview stage that can actually assess it."""
    normalized = criterion_text.casefold()
    name = normalized.splitlines()[0] if normalized else ""
    scores = {
        stage: sum(
            (4 if term.casefold() in name else 0) + (1 if term.casefold() in normalized else 0)
            for term in terms
        )
        for stage, terms in _STAGE_CRITERION_TERMS.items()
    }
    best_score = max(scores.values(), default=0)
    if best_score == 0:
        return None
    return max(scores, key=scores.__getitem__)


@dataclass(frozen=True, slots=True)
class StageQuestionDecision:
    stage: InterviewStage
    question_type: str
    completes_interview: bool = False


def is_follow_up_question_type(question_type: str) -> bool:
    return question_type == FOLLOW_UP_QUESTION_TYPE


def is_core_question_type(question_type: str) -> bool:
    return question_type in CORE_QUESTION_TYPES or not is_follow_up_question_type(question_type)


def stage_verification_objective(
    stage: InterviewStage,
    target: VerificationTargetPlan,
) -> str:
    if stage is InterviewStage.ADAPTIVE:
        return (
            f"{target.objective} 지원자의 제출 자료와 직전 답변을 연결하고, 실제 본인 경험과 "
            "판단 근거 및 결과를 확인합니다."
        )
    if stage is InterviewStage.TECHNICAL:
        return (
            f"{target.objective} 답변에서는 실제 기술 선택, 구현 방식, 판단 근거와 검증 결과를 "
            "확인합니다."
        )
    if stage is InterviewStage.PROJECT_DEEP_DIVE:
        return (
            f"{target.objective} 하나의 프로젝트 안에서 목표, 본인 역할, 설계·구현 범위, 결과와 "
            "회고를 연결해 확인합니다."
        )
    return (
        "앞서 확인한 실제 경험과 연결해 함께 일한 사람, 역할이나 의견을 조율한 행동, "
        "그 결과와 배운 점을 확인합니다. 자료에 협업 사실이 없으면 있다고 전제하지 않습니다."
    )


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
    interviewer_system_prompt: str = ""
    verification_targets: tuple[VerificationTargetPlan, ...] = ()
    interview_level: InterviewLevel = DEFAULT_INTERVIEW_LEVEL
    stages: tuple[InterviewStage, ...] = DEFAULT_INTERVIEW_STAGES
    opening_message: str = DEFAULT_OPENING_MESSAGE
    warm_up_question: str = DEFAULT_WARM_UP_QUESTION

    def __post_init__(self) -> None:
        if not self.criterion_ids:
            raise ValueError("interview plan requires at least one criterion")
        if not is_interview_prompt(self.initial_question):
            raise ValueError("initial interview prompt must be one question")
        if not is_interview_prompt(self.fallback_question):
            raise ValueError("fallback interview prompt must be one question")
        if self.remaining_time_seconds != FIXED_INTERVIEW_DURATION_SECONDS:
            raise ValueError("interview plan requires the fixed 30 minute duration")
        if self.verification_targets:
            target_criteria = {target.criterion_id for target in self.verification_targets}
            if not target_criteria.issubset(set(self.criterion_ids)):
                raise ValueError("verification target criterion is outside the plan")
        if not self.stages or len(set(self.stages)) != len(self.stages):
            raise ValueError("interview plan requires at least one unique interview flow stage")
        if not self.opening_message.strip():
            raise ValueError("interview plan requires an opening message")
        if not is_interview_prompt(self.warm_up_question):
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

    def targets_for_stage(self, stage: InterviewStage) -> tuple[VerificationTargetPlan, ...]:
        matched = tuple(
            target for target in self.verification_targets if target.preferred_stage is stage
        )
        if matched:
            return matched
        unclassified = tuple(
            target for target in self.verification_targets if target.preferred_stage is None
        )
        return unclassified or self.verification_targets

    def initial_target_for_stage(
        self,
        stage: InterviewStage,
    ) -> VerificationTargetPlan | None:
        return next(iter(self.targets_for_stage(stage)), None)

    @property
    def initial_stage(self) -> InterviewStage:
        return self.stages[0]

    def stage_time_budget_seconds(self, stage: InterviewStage) -> int:
        weight_total = sum(INTERVIEW_STAGE_WEIGHTS[item] for item in self.stages)
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
        stage_core_question_count: int,
        consecutive_follow_up_count: int,
        stage_elapsed_seconds: int,
        total_elapsed_seconds: int,
        last_question_was_final: bool,
        answer_needs_follow_up: bool,
        follow_up_limit: int,
    ) -> StageQuestionDecision:
        if (
            stage_core_question_count < 0
            or consecutive_follow_up_count < 0
            or stage_elapsed_seconds < 0
            or total_elapsed_seconds < 0
            or follow_up_limit < 0
        ):
            raise ValueError("interview stage progress cannot be negative")
        if stage_core_question_count == 0:
            question_type = (
                "stage_final" if self.stage_question_limit(current_stage) == 1 else "stage_opening"
            )
            return StageQuestionDecision(current_stage, question_type)

        stage_budget = self.stage_time_budget_seconds(current_stage)
        stage_limit = self.stage_question_limit(current_stage)
        stage_exhausted = (
            last_question_was_final
            or stage_elapsed_seconds >= stage_budget
            or stage_core_question_count >= stage_limit
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
        next_question_is_final = stage_remaining <= final_window or total_remaining <= final_window
        if next_question_is_final:
            return StageQuestionDecision(current_stage, "stage_final")
        if answer_needs_follow_up and consecutive_follow_up_count < follow_up_limit:
            return StageQuestionDecision(current_stage, FOLLOW_UP_QUESTION_TYPE)
        return StageQuestionDecision(
            current_stage,
            "stage_final" if stage_core_question_count + 1 >= stage_limit else "core",
        )

    def next_target_for_question(
        self,
        *,
        answered_target_id: UUID,
        follow_up_count: int,
        completed_target_ids: frozenset[UUID],
        prefer_new_target: bool,
        interview_stage: InterviewStage | None = None,
    ) -> VerificationTargetPlan:
        answered = self.target(answered_target_id)
        eligible_targets = (
            self.targets_for_stage(interview_stage)
            if interview_stage is not None
            else self.verification_targets
        )
        if (
            not prefer_new_target
            and answered in eligible_targets
            and answered_target_id not in completed_target_ids
            and follow_up_count < self.follow_up_budget(answered)
        ):
            return answered
        upcoming = next(
            (
                target
                for target in eligible_targets
                if target.verification_target_id not in completed_target_ids
                and target.verification_target_id != answered_target_id
            ),
            None,
        )
        return upcoming or next(iter(eligible_targets), None) or answered

    def target(self, target_id: UUID) -> VerificationTargetPlan:
        for target in self.verification_targets:
            if target.verification_target_id == target_id:
                return target
        raise LookupError("verification target is outside the plan")

    def follow_up_budget(self, target: VerificationTargetPlan) -> int:
        """How many follow-ups this interview allows on one target.

        The criterion configures the number. Interview level changes question depth,
        not how many follow-ups the target receives.
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

    def has_sufficient_evidence_for_all_targets(
        self,
        *,
        answered_target_id: UUID,
        answer_needs_follow_up: bool,
        follow_up_count: int,
        completed_target_ids: frozenset[UUID],
    ) -> bool:
        """Return whether the adaptive interview can finish before the 30-minute cap.

        A target is complete when the latest answer no longer needs clarification or
        when its configured follow-up budget has been exhausted. The clock remains a
        hard upper bound; collecting enough evidence is the normal earlier stop.
        """
        if follow_up_count < 0:
            raise ValueError("interview target progress cannot be negative")
        answered = self.target(answered_target_id)
        assessed = set(completed_target_ids)
        if not answer_needs_follow_up or follow_up_count >= self.follow_up_budget(answered):
            assessed.add(answered_target_id)
        return bool(self.verification_targets) and all(
            target.verification_target_id in assessed for target in self.verification_targets
        )


class InterviewPlanProvider(Protocol):
    def get_interview_plan(
        self,
        context: TenantContext,
        *,
        strategy_id: UUID,
        competency_model_version_id: UUID,
    ) -> InterviewPlan: ...
