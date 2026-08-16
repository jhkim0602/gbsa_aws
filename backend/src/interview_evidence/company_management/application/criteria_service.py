from __future__ import annotations

from uuid import UUID

from interview_evidence.company_management.domain.criteria import (
    CompetencyModelVersion,
    EvaluationCriterion,
    JobRequirement,
)
from interview_evidence.company_management.repositories.postgres import CompanyRepository
from interview_evidence.shared.idempotency import (
    InMemoryResourceIdempotencyStore,
    ResourceIdempotencyStore,
)
from interview_evidence.shared.ids import Clock, new_uuid7
from interview_evidence.shared.tenant import TenantContext


class CriteriaService:
    def __init__(
        self,
        repository: CompanyRepository,
        clock: Clock,
        idempotency: ResourceIdempotencyStore | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._idempotency = idempotency or InMemoryResourceIdempotencyStore()

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
        persona_definition: dict[str, object] | None = None,
    ) -> CompetencyModelVersion:
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
