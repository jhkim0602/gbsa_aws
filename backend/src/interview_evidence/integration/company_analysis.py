from __future__ import annotations

from uuid import UUID

from interview_evidence.company_management.application.company_service import (
    CompanyManagementPublic,
)
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.workers.analysis.pipeline import (
    AnalysisAxis,
    AnalysisCriterion,
    AnalysisRequirement,
)


class CompanyAnalysisAxisProvider:
    def __init__(self, company: CompanyManagementPublic) -> None:
        self._company = company

    def get_axis(
        self,
        context: TenantContext,
        *,
        invitation_id: UUID,
    ) -> AnalysisAxis:
        invitation = self._company.authorize_invitation(
            context,
            invitation_id,
            required_state="consented",
        )
        if not invitation.authorized:
            raise PermissionError("analysis invitation is not authorized")
        criterion = self._company.get_criterion_version(
            context,
            invitation.competency_model_version_id,
        )
        return AnalysisAxis(
            competency_model_version_id=criterion.competency_model_version_id,
            criterion_ids=tuple(item.criterion_id for item in criterion.criteria),
            version_number=criterion.version_number,
            criteria=tuple(
                AnalysisCriterion(
                    criterion_id=item.criterion_id,
                    code=item.code,
                    name=item.name,
                    description=item.description,
                    required=item.required,
                    weight=item.weight,
                    observable_dimensions=_string_tuple(
                        item.verification_guide.get("observable_dimensions")
                    ),
                    follow_up_directions=_string_tuple(
                        item.verification_guide.get("follow_up_directions")
                    ),
                    max_follow_ups=_integer(
                        item.verification_guide.get("max_follow_ups"),
                        default=1,
                    ),
                    time_budget_seconds=_integer(
                        item.verification_guide.get("time_budget_seconds"),
                        default=300,
                    ),
                )
                for item in criterion.criteria
            ),
            requirements=tuple(
                AnalysisRequirement(
                    job_requirement_id=item.job_requirement_id,
                    statement=item.statement,
                    criterion_code=item.criterion_code,
                    required=item.requirement_type == "required",
                    priority=item.priority,
                )
                for item in criterion.job_requirements
            ),
        )


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(str(item) for item in value)


def _integer(value: object, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return default
