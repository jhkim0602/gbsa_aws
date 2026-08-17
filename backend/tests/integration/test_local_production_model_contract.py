"""The local deterministic model must satisfy the same domain contract as Bedrock."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.interview_engine.application.question_generator import (
    QuestionGenerator,
)
from interview_evidence.interview_engine.application.question_policy import QuestionPolicy
from interview_evidence.interview_engine.application.question_prompt import (
    DEFAULT_QUESTION_PROMPT,
    TASK_NEXT_QUESTION,
    task_payload_of,
)
from interview_evidence.runtime.local_production import LocalDeterministicModel
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.messaging.outbox import InMemoryOutbox
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.application.strategy_service import StrategyService
from interview_evidence.submission_analysis.domain.source import SourceReferenceCandidate
from interview_evidence.submission_analysis.domain.strategy import StrategyStatus
from interview_evidence.submission_analysis.repositories.postgres import (
    InMemorySubmissionRepository,
)

NOW = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000301")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000302")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000303")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000304")
CRITERION_ONE = UUID("00000000-0000-7000-8000-000000000305")
CRITERION_TWO = UUID("00000000-0000-7000-8000-000000000306")
CHUNK_ID = UUID("00000000-0000-7000-8000-000000000307")


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=APPLICANT_ID,
        request_id=INVITATION_ID,
        trace_id="local-production-model",
    )


def test_local_strategy_output_persists_without_violating_the_domain() -> None:
    repository = InMemorySubmissionRepository()
    strategy = StrategyService(
        LocalDeterministicModel(),
        model_config_version="strategy-v1",
        repository=repository,
        outbox=InMemoryOutbox(),
        clock=FrozenClock(NOW),
    ).generate(
        _context(),
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        competency_model_version_id=VERSION_ID,
        criterion_ids=(CRITERION_ONE, CRITERION_TWO),
        source_candidates=(
            SourceReferenceCandidate(
                source_id=CHUNK_ID,
                source_type="submission_chunk",
                locator={"page_number": 1},
                content_hash="a" * 64,
                relevance_score=1.0,
                ownership_confidence=1.0,
            ),
        ),
        strategy_version=1,
    )

    assert strategy.status is StrategyStatus.READY
    assert strategy.time_budget["total_seconds"] > 0
    assert {point.criterion_id for point in strategy.verification_points} == {
        CRITERION_ONE,
        CRITERION_TWO,
    }
    assert repository.latest_strategy(_context(), INVITATION_ID) is not None


def test_local_model_receives_the_same_prompt_body_bedrock_would() -> None:
    """The local substitute must read the rendered prompt, not a bare task dict."""
    recorded: list[Mapping[str, object]] = []
    local = LocalDeterministicModel()

    class RecordingLocalModel:
        def generate(
            self,
            context: TenantContext,
            model_input: Mapping[str, object],
        ) -> Mapping[str, object]:
            recorded.append(model_input)
            return local.generate(context, model_input)

    QuestionGenerator(RecordingLocalModel()).generate(
        _context(),
        target_criterion_id=CRITERION_ONE,
        context_payload={"retrieved_sources": [{"source_id": str(CHUNK_ID)}]},
        model_config_version="strategy-v1",
        retrieval_config_version="aurora-hybrid-v1",
    )

    body = recorded[0]
    assert isinstance(body["system"], str) and body["system"].strip()
    assert body["max_tokens"] == DEFAULT_QUESTION_PROMPT.max_tokens
    payload = task_payload_of(body)
    assert payload is not None
    assert payload["task"] == TASK_NEXT_QUESTION


def test_local_follow_up_question_survives_the_question_policy() -> None:
    draft = QuestionGenerator(LocalDeterministicModel()).generate(
        _context(),
        target_criterion_id=CRITERION_ONE,
        context_payload={"retrieved_sources": [{"source_id": str(CHUNK_ID)}]},
        model_config_version="strategy-v1",
        retrieval_config_version="aurora-hybrid-v1",
    )

    result = QuestionPolicy().evaluate(
        draft,
        allowed_criterion_ids=frozenset({CRITERION_ONE, CRITERION_TWO}),
        prohibited_topics=("가족", "종교"),
        previous_questions=("최근 겪은 장애 하나를 설명해 주시겠어요?",),
        fallback_question="그 판단 과정을 구체적으로 설명해 주세요?",
        fallback_criterion_id=CRITERION_ONE,
    )

    # A rejected draft silently replays the fallback, so every turn looks identical.
    assert result.reason_codes == ()
    assert result.accepted
    assert result.question.source_reference_ids == (CHUNK_ID,)
