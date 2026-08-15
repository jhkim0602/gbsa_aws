from uuid import UUID

import pytest
from interview_evidence.shared.aws_clients.ports import DeterministicAIModel
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.application.strategy_service import (
    StrategyGenerationError,
    StrategyService,
)
from interview_evidence.submission_analysis.domain.source import SourceReferenceCandidate

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000002")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000003")
CRITERION_VERSION_ID = UUID("00000000-0000-7000-8000-000000000004")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000005")


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=APPLICANT_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000006"),
        trace_id="strategy-generation",
    )


def source_reference() -> SourceReferenceCandidate:
    return SourceReferenceCandidate(
        source_id=UUID("00000000-0000-7000-8000-000000000010"),
        source_type="submission_chunk",
        locator={"page": 2, "section": "성과"},
        content_hash="a" * 64,
        relevance_score=0.9,
        ownership_confidence=1,
    )


def test_strategy_keeps_fixed_criterion_axis_and_source_provenance() -> None:
    model = DeterministicAIModel(
        {
            "common_topics": ["문제 해결"],
            "verification_points": [
                {
                    "criterion_id": str(CRITERION_ID),
                    "prompt": "장애율 30% 감소 수치를 검증한다.",
                    "source_ids": [str(source_reference().source_id)],
                }
            ],
            "follow_up_directions": {"PROBLEM_SOLVING": ["대안을 비교한다"]},
            "time_budget": {"total_seconds": 1800},
            "required_evidence_plan": {str(CRITERION_ID): 1},
        }
    )
    service = StrategyService(model, model_config_version="strategy-v1")

    strategy = service.generate(
        context(),
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        competency_model_version_id=CRITERION_VERSION_ID,
        criterion_ids=(CRITERION_ID,),
        source_candidates=(source_reference(),),
        strategy_version=1,
    )

    assert strategy.competency_model_version_id == CRITERION_VERSION_ID
    assert strategy.source_reference_candidates[0].source_id == source_reference().source_id
    assert strategy.status == "ready"


def test_strategy_rejects_unknown_criterion_or_source() -> None:
    model = DeterministicAIModel(
        {
            "common_topics": [],
            "verification_points": [
                {
                    "criterion_id": str(UUID("00000000-0000-7000-8000-000000000099")),
                    "prompt": "잘못된 기준",
                    "source_ids": [str(UUID("00000000-0000-7000-8000-000000000098"))],
                }
            ],
            "follow_up_directions": {},
            "time_budget": {"total_seconds": 1800},
            "required_evidence_plan": {},
        }
    )
    service = StrategyService(model, model_config_version="strategy-v1")

    with pytest.raises(StrategyGenerationError):
        service.generate(
            context(),
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            competency_model_version_id=CRITERION_VERSION_ID,
            criterion_ids=(CRITERION_ID,),
            source_candidates=(source_reference(),),
            strategy_version=1,
        )
