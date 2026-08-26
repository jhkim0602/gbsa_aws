"""The level a recruiter publishes has to survive the trip to the question prompt.

The toggle crosses three modules: Lane A stores it on the published competency version,
the integration boundary copies it onto the interview plan, and Lane C turns it into a
prompt template. A level that is stored but dropped at any hop
looks configured in the console while every interview stays identical, which is the
failure this test exists to catch.

The per-criterion ``time_budget_seconds`` takes the same trip, so it is asserted here
too -- before T273 the guide stored it and nothing read it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.company_management.application.company_service import (
    CompanyManagementPublic,
    CompanyService,
)
from interview_evidence.company_management.application.criteria_service import CriteriaService
from interview_evidence.company_management.repositories.postgres import InMemoryCompanyRepository
from interview_evidence.integration.submission_interview import SubmissionInterviewBoundary
from interview_evidence.interview_engine.application.question_prompt import question_prompt_for
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.interview_level import InterviewLevel
from interview_evidence.shared.security.principals import CompanyPrincipal
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.adapters.search import InMemorySearchIndex
from interview_evidence.submission_analysis.application.deletion_targets import (
    InMemorySubmissionTargetDeleter,
    SubmissionDeletionTargets,
)
from interview_evidence.submission_analysis.application.public import SubmissionAnalysisPublic
from interview_evidence.submission_analysis.application.retrieval import (
    HybridRetrievalConfig,
    HybridRetriever,
)
from interview_evidence.submission_analysis.domain.retrieval import (
    CandidateVerificationMap,
    VerificationTarget,
)
from interview_evidence.submission_analysis.domain.strategy import (
    InterviewStrategy,
    StrategyStatus,
)
from interview_evidence.submission_analysis.repositories.postgres import (
    InMemorySubmissionRepository,
)

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_USER_ID = UUID("00000000-0000-7000-8000-000000000002")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000003")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000004")
STRATEGY_ID = UUID("00000000-0000-7000-8000-000000000005")
VERIFICATION_MAP_ID = UUID("00000000-0000-7000-8000-000000000006")
FIRST_TARGET_ID = UUID("00000000-0000-7000-8000-000000000007")
SECOND_TARGET_ID = UUID("00000000-0000-7000-8000-000000000009")
NOW = datetime(2026, 8, 16, 9, 0, tzinfo=UTC)

#: Long enough that only one criterion fits in the 30 minute slot below, which is what
#: makes the plan's stop condition observable: two criteria are planned and the clock
#: can only pay for one.
CRITERION_TIME_BUDGET_SECONDS = 1500


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.COMPANY_USER,
        actor_id=COMPANY_USER_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000008"),
        trace_id="interview-level-roundtrip",
    )


def _criterion_input(code: str, name: str) -> dict[str, object]:
    return {
        "code": code,
        "name": name,
        "description": "장애 원인을 분석하고 복구를 주도한다.",
        "weight": 50.0,
        "verification_guide": {
            "observable_dimensions": ("상황", "원인 분석", "복구"),
            "strong_answer_signals": ("본인 판단 근거가 구체적이다.",),
            "weak_answer_signals": ("팀 활동만 언급한다.",),
            "follow_up_directions": ("직접 수행한 복구 작업",),
            "max_follow_ups": 2,
            "time_budget_seconds": CRITERION_TIME_BUDGET_SECONDS,
        },
        "abstain_guidance": "근거가 없으면 판단을 보류한다.",
        "common_questions": (f"{name} 경험을 설명해 주세요?",),
        "required": True,
    }


def _publish_criteria(level: InterviewLevel) -> tuple[CompanyManagementPublic, UUID]:
    """Publish a real competency version at ``level`` through Lane A's services."""
    clock = FrozenClock(NOW)
    repository = InMemoryCompanyRepository()
    context = _context()
    position = CompanyService(repository, clock).create_position(
        context,
        CompanyPrincipal(
            company_id=COMPANY_ID,
            company_user_id=COMPANY_USER_ID,
            identity_subject="oidc|company-user",
        ),
        title="백엔드 플랫폼 엔지니어",
        description="ECS 기반 서비스의 안정성과 운영 품질을 개선합니다.",
        idempotency_key="level-position",
    )
    criteria_service = CriteriaService(repository, clock)
    version = criteria_service.create_version(
        context,
        position_id=position.position_id,
        criteria=(
            _criterion_input("PROBLEM_SOLVING", "운영 문제 해결"),
            _criterion_input("OWNERSHIP", "주도적 실행"),
        ),
        prohibited_topics=("가족관계",),
        interview_duration_minutes=30,
        interview_level=level,
        persona_definition={"voice_id": "Seoyeon"},
        idempotency_key="level-criterion",
    )
    published = criteria_service.publish_version(
        context,
        version_id=version.competency_model_version_id,
        expected_version=version.row_version,
    )
    return (
        CompanyManagementPublic(repository, clock),
        published.competency_model_version_id,
    )


def _boundary(
    company: CompanyManagementPublic,
    version_id: UUID,
    *,
    criterion_ids: tuple[UUID, ...],
) -> SubmissionInterviewBoundary:
    repository = InMemorySubmissionRepository()
    context = _context()
    repository.save_strategy(
        context,
        InterviewStrategy(
            interview_strategy_id=STRATEGY_ID,
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            competency_model_version_id=version_id,
            strategy_version=1,
            common_topics=("운영 장애 대응",),
            verification_points=(),
            follow_up_directions={},
            time_budget={"total_seconds": 1800},
            required_evidence_plan={},
            source_reference_candidates=(),
            model_config_version="strategy-v1",
            status=StrategyStatus.READY,
        ),
    )
    target_ids = (FIRST_TARGET_ID, SECOND_TARGET_ID)
    repository.save_verification_targets(
        context,
        tuple(
            VerificationTarget(
                verification_target_id=target_id,
                company_id=COMPANY_ID,
                applicant_id=APPLICANT_ID,
                invitation_id=INVITATION_ID,
                competency_model_version_id=version_id,
                criterion_id=criterion_id,
                target_type="detail_missing",
                objective="원인 분석과 복구 과정에서 본인 역할을 확인합니다.",
                missing_dimensions=("원인 분석",),
                priority=priority,
                max_follow_ups=2,
            )
            for priority, (target_id, criterion_id) in enumerate(
                zip(target_ids, criterion_ids, strict=True),
                start=1,
            )
        ),
    )
    repository.save_verification_map(
        context,
        CandidateVerificationMap(
            candidate_verification_map_id=VERIFICATION_MAP_ID,
            company_id=COMPANY_ID,
            applicant_id=APPLICANT_ID,
            invitation_id=INVITATION_ID,
            competency_model_version_id=version_id,
            criterion_version=1,
            material_version="material-v1",
            retrieval_version="aurora-hybrid-v1",
            embedding_model="titan-embed",
            embedding_version="v1",
            generation_version="strategy-v1",
            ordered_target_ids=target_ids,
            time_budget_seconds=1800,
            readiness_state="ready",
            created_at=NOW,
        ),
    )
    submission = SubmissionAnalysisPublic(
        repository=repository,
        retriever=HybridRetriever(InMemorySearchIndex(), HybridRetrievalConfig()),
        deletion_targets=SubmissionDeletionTargets(repository),
        target_deleter=InMemorySubmissionTargetDeleter(),
    )
    return SubmissionInterviewBoundary(submission, company)


def _plan(level: InterviewLevel):
    company, version_id = _publish_criteria(level)
    criteria = company.get_criterion_version(_context(), version_id)
    boundary = _boundary(
        company,
        version_id,
        criterion_ids=tuple(criterion.criterion_id for criterion in criteria.criteria),
    )
    return boundary.get_interview_plan(
        _context(),
        strategy_id=STRATEGY_ID,
        competency_model_version_id=version_id,
    )


@pytest.mark.parametrize(
    ("level", "expected_follow_ups"),
    [
        (InterviewLevel.ENTRY, 2),
        (InterviewLevel.JUNIOR, 2),
        (InterviewLevel.SENIOR, 2),
    ],
)
def test_published_level_reaches_the_plan_without_moving_the_follow_up_budget(
    level: InterviewLevel,
    expected_follow_ups: int,
) -> None:
    plan = _plan(level)

    assert plan.interview_level is level
    # The criterion is configured with max_follow_ups=2 in every case. The level
    # reaches the prompt but does not alter that budget.
    target = plan.verification_targets[0]
    assert target.max_follow_ups == 2
    assert plan.follow_up_budget(target) == expected_follow_ups
    # And the level selects the prompt the model is actually given.
    assert question_prompt_for(plan.interview_level).interview_level is level


def test_the_criterion_time_budget_reaches_the_plan_and_bounds_the_interview() -> None:
    plan = _plan(InterviewLevel.JUNIOR)
    target = plan.verification_targets[0]

    assert len(plan.verification_targets) == 2
    assert target.time_budget_seconds == CRITERION_TIME_BUDGET_SECONDS
    # 30 minutes published as the slot, so the plan can pay for one 1500 second
    # criterion and not two.
    assert plan.remaining_time_seconds == 1800
    assert (
        plan.next_target_after_answer(
            answered_target_id=target.verification_target_id,
            follow_up_count=2,
            completed_target_ids=frozenset(),
            elapsed_seconds=CRITERION_TIME_BUDGET_SECONDS,
        )
        is None
    )
    # Same call at the start of the slot does open the second criterion, so the stop
    # above is the clock talking and not an empty plan.
    assert (
        plan.next_target_after_answer(
            answered_target_id=target.verification_target_id,
            follow_up_count=2,
            completed_target_ids=frozenset(),
            elapsed_seconds=0,
        ).verification_target_id
        == SECOND_TARGET_ID
    )
