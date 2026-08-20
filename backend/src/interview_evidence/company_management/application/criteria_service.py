from __future__ import annotations

from uuid import UUID

from interview_evidence.company_management.domain.criteria import (
    CompetencyModelVersion,
    EvaluationCriterion,
    JobRequirement,
)
from interview_evidence.company_management.repositories.postgres import CompanyRepository
from interview_evidence.shared.idempotency import ResourceIdempotencyStore
from interview_evidence.shared.ids import Clock, new_uuid7
from interview_evidence.shared.interview_level import (
    DEFAULT_INTERVIEW_LEVEL,
    InterviewLevel,
)
from interview_evidence.shared.tenant import TenantContext


class CriteriaService:
    def __init__(
        self,
        repository: CompanyRepository,
        clock: Clock,
        idempotency: ResourceIdempotencyStore,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._idempotency = idempotency

    def create_version(
        self,
        context: TenantContext,
        *,
        position_id: UUID,
        job_requirements: tuple[dict[str, object], ...] = (),
        criteria: tuple[dict[str, object], ...],
        prohibited_topics: tuple[str, ...],
        interview_duration_minutes: int,
        idempotency_key: str,
        interview_level: InterviewLevel = DEFAULT_INTERVIEW_LEVEL,
        axis_weights: dict[str, float] | None = None,
        persona_definition: dict[str, object] | None = None,
    ) -> CompetencyModelVersion:
        # The weight total used to be checked here. It moved to
        # `CompetencyModelVersion.criterion_weights_total_100` so that the criterion weights and
        # the axis weights are governed by one rule in one place, and so that a version built
        # anywhere -- not only through this service -- cannot carry a total that scoring would
        # then have to guess at. `EvaluationCriterion.weight` is already `float` with `ge=0`, so
        # pydantic rejects a non-numeric or negative weight before the total is summed.
        existing_id = self._idempotency.get(
            context,
            operation="criterion_version.create",
            idempotency_key=idempotency_key,
        )
        if existing_id is not None:
            return self._repository.get_criterion_version(context, existing_id)
        self._repository.get_position(context, position_id)
        existing_versions = self._repository.list_criterion_versions(context, position_id)
        domain_criteria = tuple(
            EvaluationCriterion(
                criterion_id=new_uuid7(self._clock.now()),
                **item,
            )
            for item in criteria
        )
        domain_requirements = tuple(
            JobRequirement(
                job_requirement_id=new_uuid7(self._clock.now()),
                **item,
            )
            for item in job_requirements
        )
        version = CompetencyModelVersion.create(
            competency_model_version_id=new_uuid7(self._clock.now()),
            company_id=context.company_id,
            position_id=position_id,
            version_number=len(existing_versions) + 1,
            job_requirements=domain_requirements,
            criteria=domain_criteria,
            prohibited_topics=prohibited_topics,
            interview_duration_minutes=interview_duration_minutes,
            interview_level=interview_level,
            axis_weights=axis_weights,
            persona_definition=persona_definition,
        )
        self._repository.save_criterion_version(context, version)
        self._idempotency.put(
            context,
            operation="criterion_version.create",
            idempotency_key=idempotency_key,
            resource_id=version.competency_model_version_id,
        )
        return version

    def publish_version(
        self,
        context: TenantContext,
        *,
        version_id: UUID,
        expected_version: int,
    ) -> CompetencyModelVersion:
        current = self._repository.get_criterion_version(context, version_id)
        published = current.publish(
            expected_version=expected_version,
            published_at=self._clock.now(),
        )
        return self._repository.save_criterion_version(context, published)

    def get_criterion_version(
        self,
        context: TenantContext,
        version_id: UUID,
    ) -> CompetencyModelVersion:
        return self._repository.get_criterion_version(context, version_id)

    def list_versions(
        self,
        context: TenantContext,
        position_id: UUID,
    ) -> tuple[CompetencyModelVersion, ...]:
        self._repository.get_position(context, position_id)
        return tuple(
            sorted(
                self._repository.list_criterion_versions(context, position_id),
                key=lambda version: version.version_number,
                reverse=True,
            )
        )
