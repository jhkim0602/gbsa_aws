from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from interview_evidence.company_management.application.company_service import (
    CompanyManagementPublic,
    CriterionSnapshot,
)
from interview_evidence.interview_engine.adapters.retrieval_client import RetrievalRecord
from interview_evidence.interview_engine.application.authorization import (
    InterviewAuthorization,
    InterviewAuthorizationDenied,
)
from interview_evidence.interview_engine.application.interview_plan import (
    FIXED_INTERVIEW_DURATION_SECONDS,
    InterviewPlan,
    VerificationTargetPlan,
)
from interview_evidence.interview_engine.application.question_policy import (
    is_interview_prompt,
    normalize_interview_prompt,
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
    excerpt: str
    source_type: str
    material_type: str | None


class SubmissionInterviewBoundary:
    """Adapt Lane B strategy and retrieval snapshots to Lane C ports."""

    def __init__(
        self,
        submission: SubmissionAnalysisPublic,
        company: CompanyManagementPublic | None = None,
    ) -> None:
        self._submission = submission
        self._company = company

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

        analysis = self._submission.get_analysis_status(
            context,
            invitation_id=principal.invitation_id,
        )
        if analysis.submissions and (
            not analysis.strategy_ready or analysis.strategy_id != strategy_id
        ):
            raise InterviewAuthorizationDenied("interview strategy is being refreshed")

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
        invitation_id: UUID,
        competency_model_version_id: UUID,
        query: str,
        query_vector: tuple[float, ...],
        criterion_id: UUID,
        config_version: str,
        limit: int,
        exact_symbol: str | None = None,
        embedding_model: str | None = None,
        embedding_version: str | None = None,
        source_types: frozenset[str] | None = None,
    ) -> tuple[RetrievalRecord, ...]:
        results = self._submission.retrieve_context(
            context,
            applicant_id=applicant_id,
            invitation_id=invitation_id,
            competency_model_version_id=competency_model_version_id,
            query=query,
            query_vector=query_vector,
            criterion_id=criterion_id,
            config_version=config_version,
            limit=limit,
            exact_symbol=exact_symbol,
            embedding_model=embedding_model,
            embedding_version=embedding_version,
            source_types=source_types,
        )
        return tuple(
            BoundaryRetrievalRecord(
                source_id=result.source_id,
                score=result.score,
                locator=dict(result.locator),
                ownership_confidence=result.ownership_confidence,
                excerpt=result.excerpt,
                source_type=result.source_type,
                material_type=result.material_type,
            )
            for result in results
        )

    def get_interview_plan(
        self,
        context: TenantContext,
        *,
        strategy_id: UUID,
        competency_model_version_id: UUID,
    ) -> InterviewPlan:
        if self._company is None:
            raise RuntimeError("company criterion provider is not configured")
        strategy = self._submission.get_strategy_snapshot(context, strategy_id=strategy_id)
        criteria = self._company.get_criterion_version(context, competency_model_version_id)
        if (
            strategy.company_id != context.company_id
            or strategy.competency_model_version_id != competency_model_version_id
            or criteria.company_id != context.company_id
        ):
            raise PermissionError("interview plan is outside tenant scope")
        criterion_ids = tuple(criterion.criterion_id for criterion in criteria.criteria)
        # Job requirements are reporting dimensions, not question prompts. Questions
        # follow stable competency stages plus the company's explicit required questions.
        verification_targets = _interview_targets(criteria.criteria)
        verification_prompt = next(
            (
                point.prompt
                for point in strategy.verification_points
                if point.criterion_id in criterion_ids
            ),
            "",
        )
        mandatory_question = next(
            (
                question
                for criterion in criteria.criteria
                for question in criterion.common_questions
                if question.strip()
            ),
            "",
        )
        initial_question = _as_question(
            (
                verification_targets[0].common_question
                if verification_targets
                else verification_prompt
            )
            or mandatory_question
            or "최근 해결한 기술 문제를 설명해 주세요"
        )
        fallback_question = _as_question("그 판단 과정과 결과를 구체적으로 설명해 주세요")
        persona = criteria.persona_definition
        return InterviewPlan(
            criterion_ids=criterion_ids,
            initial_question=initial_question,
            prohibited_topics=criteria.prohibited_topics,
            fallback_question=fallback_question,
            remaining_time_seconds=FIXED_INTERVIEW_DURATION_SECONDS,
            model_config_version=strategy.model_config_version,
            retrieval_config_version="stage-aware-hybrid-v1",
            voice_id=str(persona.get("voice_id", "Seoyeon")),
            verification_targets=verification_targets,
            interview_level=criteria.interview_level,
        )


def _as_question(value: str) -> str:
    naturalized = normalize_interview_prompt(value)
    if is_interview_prompt(naturalized):
        return naturalized
    text = naturalized.strip().rstrip(".!？? ")
    return f"{text}?"


def _criterion_text(
    criterion: CriterionSnapshot,
) -> str:
    guide = criterion.verification_guide
    dimensions = _string_tuple(guide.get("observable_dimensions"))
    return "\n".join(
        value
        for value in (
            criterion.name,
            criterion.description,
            *dimensions,
        )
        if value.strip()
    )


def _interview_targets(
    criteria: tuple[CriterionSnapshot, ...],
) -> tuple[VerificationTargetPlan, ...]:
    mandatory: list[VerificationTargetPlan] = []
    baseline: list[VerificationTargetPlan] = []
    for criterion in criteria:
        for index, question in enumerate(criterion.common_questions):
            normalized = _as_question(question)
            mandatory.append(
                VerificationTargetPlan(
                    verification_target_id=uuid5(
                        NAMESPACE_URL,
                        f"iep:company-required:{criterion.criterion_id}:{index}:{normalized}",
                    ),
                    criterion_id=criterion.criterion_id,
                    criterion_text=_criterion_text(criterion),
                    target_type="company_required_question",
                    objective=normalized,
                    missing_dimensions=(),
                    follow_up_directions=(),
                    max_follow_ups=0,
                    common_question=normalized,
                    time_budget_seconds=180,
                )
            )
        guide = criterion.verification_guide
        baseline.append(
            VerificationTargetPlan(
                verification_target_id=uuid5(
                    NAMESPACE_URL,
                    f"iep:criterion-baseline:{criterion.criterion_id}",
                ),
                criterion_id=criterion.criterion_id,
                criterion_text=_criterion_text(criterion),
                target_type="criterion_baseline",
                objective=f"{criterion.name}을 일반적인 직무 면접 질문으로 확인합니다.",
                missing_dimensions=_string_tuple(guide.get("observable_dimensions")),
                follow_up_directions=_string_tuple(guide.get("follow_up_directions")),
                max_follow_ups=_max_follow_ups(guide.get("max_follow_ups")),
                common_question=_baseline_question(criterion),
                time_budget_seconds=_time_budget_seconds(criterion),
            )
        )
    return tuple((*mandatory, *baseline))


def _baseline_question(criterion: CriterionSnapshot) -> str:
    if criterion.code == "TECHNICAL_COMPETENCY":
        return "직무와 관련해 직접 사용한 기술과 그 선택 이유를 설명해 주세요."
    if criterion.code == "PROJECT_EXECUTION":
        return "가장 자신 있는 프로젝트에서 맡은 역할과 해결한 문제를 설명해 주세요."
    return "협업 과정에서 역할이나 의견을 조율한 경험을 설명해 주세요."


def _time_budget_seconds(criterion: CriterionSnapshot) -> int:
    """Seconds this criterion may occupy, from its verification guide.

    The guide is stored as JSON, so a legacy row can be missing the key or hold a
    non-numeric value; both fall back to the domain default rather than failing the
    interview, and the value is clamped to the range the domain accepts.
    """
    raw = criterion.verification_guide.get("time_budget_seconds")
    try:
        seconds = int(str(raw))
    except (TypeError, ValueError):
        return 300
    return max(60, min(seconds, 1800))


def _max_follow_ups(value: object) -> int:
    try:
        count = int(str(value))
    except (TypeError, ValueError):
        return 1
    return max(0, min(count, 3))


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(str(item) for item in value)
