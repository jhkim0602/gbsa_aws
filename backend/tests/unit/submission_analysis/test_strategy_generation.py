from uuid import UUID

import pytest
from interview_evidence.shared.aws_clients.ports import DeterministicAIModel
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.application.strategy_prompt import (
    strategy_task_payload_of,
)
from interview_evidence.submission_analysis.application.strategy_service import (
    MAX_STRATEGY_PROMPT_SOURCES,
    MIN_GIT_STRATEGY_PROMPT_SOURCES,
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


def test_strategy_rejects_unknown_criterion() -> None:
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


def test_strategy_repairs_unknown_source_references() -> None:
    unknown_source_id = UUID("00000000-0000-7000-8000-000000000099")
    model = DeterministicAIModel(
        {
            "common_topics": ["문제 해결"],
            "verification_points": [
                {
                    "criterion_id": str(CRITERION_ID),
                    "prompt": "문제 해결 과정에서 직접 수행한 내용을 확인한다.",
                    "source_ids": [str(unknown_source_id)],
                }
            ],
            "follow_up_directions": {},
            "time_budget": {"total_seconds": 1800},
            "required_evidence_plan": {str(CRITERION_ID): 1},
        }
    )

    strategy = StrategyService(model, model_config_version="strategy-v1").generate(
        context(),
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        competency_model_version_id=CRITERION_VERSION_ID,
        criterion_ids=(CRITERION_ID,),
        source_candidates=(source_reference(),),
        strategy_version=1,
    )

    assert strategy.verification_points[0].source_ids == (source_reference().source_id,)


def test_strategy_limits_and_deduplicates_prompt_sources_but_keeps_full_provenance() -> None:
    model = DeterministicAIModel(
        {
            "common_topics": [],
            "verification_points": [],
            "follow_up_directions": {},
            "time_budget": {"total_seconds": 1800},
            "required_evidence_plan": {},
        }
    )
    candidates = tuple(
        SourceReferenceCandidate(
            source_id=UUID(int=100 + index),
            source_type="submission_chunk",
            locator={"page_number": index + 1},
            content_hash=f"{index:064x}",
            relevance_score=1,
            ownership_confidence=1,
        )
        for index in range(MAX_STRATEGY_PROMPT_SOURCES + 6)
    )
    duplicate = candidates[0].model_copy(update={"source_id": UUID(int=999)})

    strategy = StrategyService(model, model_config_version="strategy-v1").generate(
        context(),
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        competency_model_version_id=CRITERION_VERSION_ID,
        criterion_ids=(CRITERION_ID,),
        source_candidates=(*candidates, duplicate),
        strategy_version=1,
    )

    prompt_payload = strategy_task_payload_of(model.calls[0][1])
    assert prompt_payload is not None
    assert len(prompt_payload["provided_source_candidates"]) == MAX_STRATEGY_PROMPT_SOURCES
    assert len(strategy.source_reference_candidates) == len(candidates) + 1


def test_strategy_prompt_reserves_sources_for_github_code() -> None:
    model = DeterministicAIModel(
        {
            "common_topics": [],
            "verification_points": [],
            "follow_up_directions": {},
            "time_budget": {"total_seconds": 1800},
            "required_evidence_plan": {},
        }
    )
    documents = tuple(
        SourceReferenceCandidate(
            source_id=UUID(int=200 + index),
            source_type="submission_chunk",
            locator={"page_number": index + 1},
            content_hash=f"{index + 100:064x}",
            relevance_score=1,
            ownership_confidence=1,
        )
        for index in range(MAX_STRATEGY_PROMPT_SOURCES + 10)
    )
    github_sources = tuple(
        SourceReferenceCandidate(
            source_id=UUID(int=400 + index),
            source_type="candidate_code_unit",
            locator={"path": f"src/service_{index}.py", "symbol": f"service_{index}"},
            content_hash=f"{index + 500:064x}",
            relevance_score=1,
            ownership_confidence=0.7,
        )
        for index in range(MIN_GIT_STRATEGY_PROMPT_SOURCES + 2)
    )

    StrategyService(model, model_config_version="strategy-v1").generate(
        context(),
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        competency_model_version_id=CRITERION_VERSION_ID,
        criterion_ids=(CRITERION_ID,),
        source_candidates=(*documents, *github_sources),
        strategy_version=1,
    )

    prompt_payload = strategy_task_payload_of(model.calls[0][1])
    assert prompt_payload is not None
    selected = prompt_payload["provided_source_candidates"]
    assert len(selected) == MAX_STRATEGY_PROMPT_SOURCES
    assert (
        sum(candidate["source_type"] == "candidate_code_unit" for candidate in selected)
        == MIN_GIT_STRATEGY_PROMPT_SOURCES
    )
