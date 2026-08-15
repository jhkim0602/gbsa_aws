from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from interview_evidence.interview_engine.adapters.retrieval_client import RetrievalRecord
from interview_evidence.interview_engine.application.authorization import (
    InterviewAuthorization,
    InterviewAuthorizationDenied,
)
from interview_evidence.shared.security.principals import ApplicantPrincipal
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.submission_analysis.application.public import SubmissionAnalysisPublic


@dataclass(slots=True)
class BoundaryRetrievalRecord:
    source_id: UUID
    score: float
    locator: dict[str, object]
    ownership_confidence: float


class SubmissionInterviewBoundary:
    """Adapt Lane B strategy and retrieval snapshots to Lane C ports."""

    def __init__(self, submission: SubmissionAnalysisPublic) -> None:
        self._submission = submission

    def authorize_start(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        *,
        strategy_id: UUID,
        acknowledged_partial_analysis: bool,
    ) -> InterviewAuthorization:
        context.assert_company(principal.company_id)
        try:
            strategy = self._submission.get_strategy_snapshot(
                context,
                strategy_id=strategy_id,
            )
        except (LookupError, PermissionError, ValueError) as error:
            raise InterviewAuthorizationDenied("interview strategy is unavailable") from error

        partial = strategy.status.value == "partial"
        if (
            strategy.company_id != principal.company_id
            or strategy.invitation_id != principal.invitation_id
            or strategy.applicant_id != principal.applicant_id
            or (partial and not acknowledged_partial_analysis)
        ):
            raise InterviewAuthorizationDenied("interview strategy is outside applicant scope")

        return InterviewAuthorization(
            company_id=strategy.company_id,
            invitation_id=strategy.invitation_id,
            applicant_id=strategy.applicant_id,
            strategy_id=strategy.interview_strategy_id,
            competency_model_version_id=strategy.competency_model_version_id,
            partial_analysis=partial,
        )

    def retrieve_context(
        self,
        context: TenantContext,
        *,
        applicant_id: UUID,
        query: str,
        query_vector: tuple[float, ...],
        criterion_id: UUID,
        config_version: str,
        limit: int,
        exact_symbol: str | None = None,
    ) -> tuple[RetrievalRecord, ...]:
        results = self._submission.retrieve_context(
            context,
            applicant_id=applicant_id,
            query=query,
            query_vector=query_vector,
            criterion_id=criterion_id,
            config_version=config_version,
            limit=limit,
            exact_symbol=exact_symbol,
        )
        return tuple(
            BoundaryRetrievalRecord(
                source_id=result.source_id,
                score=result.score,
                locator=dict(result.locator),
                ownership_confidence=result.ownership_confidence,
            )
            for result in results
        )
