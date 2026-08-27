from __future__ import annotations

from collections.abc import Mapping, Sequence
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
MIN_GIT_STRATEGY_PROMPT_SOURCES = 4
MIN_REPOSITORY_OVERVIEW_PROMPT_SOURCES = 2
FIXED_INTERVIEW_DURATION_SECONDS = 30 * 60


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
            parsed_verification_points = tuple(
                _verification_point_from_model(
                    item,
                    allowed_criteria=allowed_criteria,
                    fallback_criterion_id=(
                        criterion_ids[index % len(criterion_ids)] if criterion_ids else None
                    ),
                    allowed_sources=allowed_sources,
                    fallback_source_id=(
                        prompt_candidates[0].source_id if prompt_candidates else None
                    ),
                )
                for index, item in enumerate(result["verification_points"])
            )
            common_topics = tuple(str(item) for item in result.get("common_topics", ()))
            follow_up_directions = _normalized_follow_up_directions(
                result.get("follow_up_directions")
            )
            time_budget = _normalized_time_budget(result.get("time_budget"))
            required_evidence_plan = _normalized_required_evidence_plan(
                result.get("required_evidence_plan"),
                criterion_ids=criterion_ids,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise StrategyGenerationError("invalid structured strategy output") from error
        verification_points: list[VerificationPoint] = []
        for point in parsed_verification_points:
            if point.criterion_id not in allowed_criteria:
                raise StrategyGenerationError("strategy referenced an unknown criterion")
            verification_points.append(point)
        strategy = InterviewStrategy(
            interview_strategy_id=new_uuid7(),
            company_id=context.company_id,
            invitation_id=invitation_id,
            applicant_id=applicant_id,
            competency_model_version_id=competency_model_version_id,
            strategy_version=strategy_version,
            common_topics=common_topics,
            verification_points=tuple(verification_points),
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
    git_candidates = tuple(
        candidate for candidate in ordered if candidate.source_type == "candidate_code_unit"
    )[:MIN_GIT_STRATEGY_PROMPT_SOURCES]
    overview_candidates = tuple(
        candidate for candidate in ordered if candidate.source_type == "repository_overview"
    )[:MIN_REPOSITORY_OVERVIEW_PROMPT_SOURCES]
    for candidate in (*overview_candidates, *git_candidates, *ordered):
        if candidate.content_hash in seen_hashes:
            continue
        selected.append(candidate)
        seen_hashes.add(candidate.content_hash)
        if len(selected) == MAX_STRATEGY_PROMPT_SOURCES:
            break
    return tuple(selected)


def _verification_point_from_model(
    value: object,
    *,
    allowed_criteria: set[UUID],
    fallback_criterion_id: UUID | None,
    allowed_sources: set[UUID],
    fallback_source_id: UUID | None,
) -> VerificationPoint:
    if not isinstance(value, Mapping):
        raise TypeError("verification point must be an object")
    try:
        parsed_criterion_id: UUID | None = UUID(str(value["criterion_id"]))
    except (KeyError, TypeError, ValueError):
        parsed_criterion_id = None
    criterion_id = (
        parsed_criterion_id if parsed_criterion_id in allowed_criteria else fallback_criterion_id
    )
    if criterion_id is None:
        raise StrategyGenerationError("strategy has no available criterion")
    raw_source_ids = value.get("source_ids", ())
    if isinstance(raw_source_ids, str):
        source_values: Sequence[object] = (raw_source_ids,)
    elif isinstance(raw_source_ids, Sequence):
        source_values = raw_source_ids
    else:
        source_values = ()
    valid_source_ids: list[UUID] = []
    for raw_source_id in source_values:
        try:
            source_id = UUID(str(raw_source_id))
        except (TypeError, ValueError):
            continue
        if source_id in allowed_sources and source_id not in valid_source_ids:
            valid_source_ids.append(source_id)
    if not valid_source_ids:
        if fallback_source_id is None:
            raise StrategyGenerationError("strategy has no available source")
        valid_source_ids.append(fallback_source_id)
    return VerificationPoint(
        criterion_id=criterion_id,
        prompt=value["prompt"],
        source_ids=tuple(valid_source_ids),
    )


def _normalized_time_budget(value: object) -> dict[str, int]:
    normalized: dict[str, int] = {}
    if isinstance(value, Mapping):
        for key, raw_value in value.items():
            try:
                normalized[str(key)] = int(raw_value)
            except (TypeError, ValueError):
                continue
    normalized["total_seconds"] = FIXED_INTERVIEW_DURATION_SECONDS
    return normalized


def _normalized_follow_up_directions(value: object) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {}
    if not isinstance(value, Mapping):
        return normalized
    for raw_key, raw_directions in value.items():
        if isinstance(raw_directions, str):
            directions: Sequence[object] = (raw_directions,)
        elif isinstance(raw_directions, Sequence):
            directions = raw_directions
        else:
            continue
        normalized[str(raw_key)] = [
            str(direction) for direction in directions if str(direction).strip()
        ]
    return normalized


def _normalized_required_evidence_plan(
    value: object,
    *,
    criterion_ids: tuple[UUID, ...],
) -> dict[str, int]:
    normalized = {str(criterion_id): 1 for criterion_id in criterion_ids}
    if not isinstance(value, Mapping):
        return normalized
    allowed_criteria = set(criterion_ids)
    for raw_key, raw_value in value.items():
        try:
            criterion_id = UUID(str(raw_key))
            evidence_count = int(raw_value)
        except (TypeError, ValueError):
            continue
        if criterion_id in allowed_criteria and evidence_count > 0:
            normalized[str(criterion_id)] = evidence_count
    return normalized
