from __future__ import annotations

from uuid import UUID

from interview_evidence.shared.aws_clients.ports import AIModel
from interview_evidence.shared.ids import Clock, new_uuid7
from interview_evidence.shared.messaging.outbox import Outbox, OutboxEvent
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.submission_analysis.application.strategy_prompt import (
    build_strategy_prompt,
    parse_strategy_response,
)
from interview_evidence.submission_analysis.domain.source import (
    SourceReferenceCandidate,
)
from interview_evidence.submission_analysis.domain.strategy import (
    InterviewStrategy,
    StrategyStatus,
    VerificationPoint,
)
from interview_evidence.submission_analysis.repositories.postgres import (
    SubmissionRepository,
)


class StrategyGenerationError(ValueError):
    """Raised when model output escapes the fixed criterion or source axes."""


MAX_STRATEGY_PROMPT_SOURCES = 24


class StrategyService:
    def __init__(
        self,
        model: AIModel,
        *,
        model_config_version: str,
        repository: SubmissionRepository | None = None,
        outbox: Outbox | None = None,
        clock: Clock | None = None,
    ) -> None:
        if any(value is not None for value in (repository, outbox, clock)) and not all(
            value is not None for value in (repository, outbox, clock)
        ):
            raise ValueError("strategy persistence requires repository, outbox, and clock together")
        self._model = model
        self._model_config_version = model_config_version
        self._repository = repository
        self._outbox = outbox
        self._clock = clock

    def generate(
        self,
        context: TenantContext,
        *,
        invitation_id: UUID,
        applicant_id: UUID,
        competency_model_version_id: UUID,
        criterion_ids: tuple[UUID, ...],
        source_candidates: tuple[SourceReferenceCandidate, ...],
        strategy_version: int,
    ) -> InterviewStrategy:
        prompt_candidates = _select_prompt_candidates(source_candidates)
        try:
            result = parse_strategy_response(
                self._model.generate(
                    context,
                    build_strategy_prompt(
                        invitation_id=invitation_id,
                        competency_model_version_id=competency_model_version_id,
                        criterion_ids=criterion_ids,
                        source_candidates=prompt_candidates,
                        model_config_version=self._model_config_version,
                    ),
                )
            )
        except (TypeError, ValueError) as error:
            raise StrategyGenerationError("invalid structured strategy output") from error
        allowed_criteria = set(criterion_ids)
        allowed_sources = {candidate.source_id for candidate in prompt_candidates}
        try:
            verification_points = tuple(
                VerificationPoint.model_validate(item) for item in result["verification_points"]
            )
            common_topics = tuple(str(item) for item in result["common_topics"])
            follow_up_directions = dict(result["follow_up_directions"])
            time_budget = dict(result["time_budget"])
            required_evidence_plan = dict(result["required_evidence_plan"])
        except (KeyError, TypeError, ValueError) as error:
            raise StrategyGenerationError("invalid structured strategy output") from error
        for point in verification_points:
            if point.criterion_id not in allowed_criteria:
                raise StrategyGenerationError("strategy referenced an unknown criterion")
            if not set(point.source_ids).issubset(allowed_sources):
                raise StrategyGenerationError("strategy referenced an unknown source")
        strategy = InterviewStrategy(
            interview_strategy_id=new_uuid7(),
            company_id=context.company_id,
            invitation_id=invitation_id,
            applicant_id=applicant_id,
            competency_model_version_id=competency_model_version_id,
            strategy_version=strategy_version,
            common_topics=common_topics,
            verification_points=verification_points,
            follow_up_directions={
                str(key): [str(item) for item in value]
                for key, value in follow_up_directions.items()
            },
            time_budget={str(key): int(value) for key, value in time_budget.items()},
            required_evidence_plan={
                str(key): int(value) for key, value in required_evidence_plan.items()
            },
            source_reference_candidates=source_candidates,
            model_config_version=self._model_config_version,
            status=(StrategyStatus.READY if verification_points else StrategyStatus.PARTIAL),
        )
        if self._repository is not None and self._outbox is not None and self._clock is not None:
            self._repository.save_strategy(context, strategy)
            occurred_at = self._clock.now()
            self._outbox.append(
                OutboxEvent(
                    outbox_event_id=new_uuid7(occurred_at),
                    company_id=context.company_id,
                    aggregate_type="interview_strategy",
                    aggregate_id=strategy.interview_strategy_id,
                    aggregate_version=strategy.strategy_version,
                    event_type="strategy.ready",
                    event_version=1,
                    payload={
                        "invitation_id": str(strategy.invitation_id),
                        "strategy_id": str(strategy.interview_strategy_id),
                        "strategy_version": strategy.strategy_version,
                        "criterion_version_id": str(strategy.competency_model_version_id),
                        "status": strategy.status.value,
                    },
                    idempotency_key=(
                        f"strategy-ready-{strategy.invitation_id}-{strategy.strategy_version}"
                    ),
                    trace_id=context.trace_id,
                    occurred_at=occurred_at,
                )
            )
        return strategy


def _select_prompt_candidates(
    candidates: tuple[SourceReferenceCandidate, ...],
) -> tuple[SourceReferenceCandidate, ...]:
    selected: list[SourceReferenceCandidate] = []
    seen_hashes: set[str] = set()
    ordered = sorted(
        candidates,
        key=lambda candidate: (
            -candidate.relevance_score,
            -candidate.ownership_confidence,
            candidate.source_type,
            candidate.content_hash,
            str(candidate.source_id),
        ),
    )
    for candidate in ordered:
        if candidate.content_hash in seen_hashes:
            continue
        selected.append(candidate)
        seen_hashes.add(candidate.content_hash)
        if len(selected) == MAX_STRATEGY_PROMPT_SOURCES:
            break
    return tuple(selected)
