from __future__ import annotations

from typing import Protocol
from uuid import UUID

from interview_evidence.shared.tenant import TenantContext
from interview_evidence.submission_analysis.domain.strategy import InterviewStrategy
from interview_evidence.submission_analysis.domain.submission import (
    Submission,
    SubmissionAnalysis,
    SubmissionStatus,
)

SOURCE_CANDIDATE_CLAIM = "source_reference_candidate"


class StrategyFreshnessRepository(Protocol):
    def list_analyses(
        self,
        context: TenantContext,
        submission_ids: frozenset[UUID],
    ) -> tuple[SubmissionAnalysis, ...]: ...


def strategy_matches_latest_analyses(
    repository: StrategyFreshnessRepository,
    context: TenantContext,
    *,
    submissions: tuple[Submission, ...],
    strategy: InterviewStrategy | None,
) -> bool:
    if strategy is None:
        return False
    included_ids = frozenset(
        submission.submission_id
        for submission in submissions
        if submission.status in {SubmissionStatus.READY, SubmissionStatus.PARTIAL}
    )
    if not included_ids:
        return False
    latest: dict[UUID, SubmissionAnalysis] = {}
    for analysis in repository.list_analyses(context, included_ids):
        current = latest.get(analysis.submission_id)
        if current is None or analysis.analysis_version > current.analysis_version:
            latest[analysis.submission_id] = analysis
    current_source_ids = {
        source_id for analysis in latest.values() for source_id in _analysis_source_ids(analysis)
    }
    strategy_source_ids = {
        candidate.source_id for candidate in strategy.source_reference_candidates
    }
    if not current_source_ids:
        return bool(strategy_source_ids)
    if set(latest) != set(included_ids):
        return False
    return strategy_source_ids == current_source_ids


def _analysis_source_ids(analysis: SubmissionAnalysis) -> tuple[UUID, ...]:
    source_ids: list[UUID] = []
    for claim in analysis.claims:
        if claim.get("type") != SOURCE_CANDIDATE_CLAIM:
            continue
        candidate = claim.get("candidate")
        if not isinstance(candidate, dict) or candidate.get("source_id") is None:
            continue
        try:
            source_ids.append(UUID(str(candidate["source_id"])))
        except ValueError:
            continue
    return tuple(source_ids)
