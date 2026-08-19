from uuid import UUID

from interview_evidence.company_management.domain.company import (
    InterviewerProfile,
    InterviewerTone,
)
from interview_evidence.company_management.repositories.postgres import CompanyRepository
from interview_evidence.shared.idempotency import ResourceIdempotencyStore
from interview_evidence.shared.ids import Clock, new_uuid7
from interview_evidence.shared.tenant import TenantContext


class InterviewerProfileService:
    def __init__(
        self,
        repository: CompanyRepository,
        clock: Clock,
        idempotency: ResourceIdempotencyStore,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._idempotency = idempotency

    def create(
        self,
        context: TenantContext,
        *,
        name: str,
        tone: InterviewerTone,
        voice_id: str,
        idempotency_key: str,
    ) -> InterviewerProfile:
        existing_id = self._idempotency.get(
            context,
            operation="interviewer_profile.create",
            idempotency_key=idempotency_key,
        )
        if existing_id is not None:
            return self._repository.get_interviewer_profile(context, existing_id)
        profile = InterviewerProfile(
            interviewer_profile_id=new_uuid7(self._clock.now()),
            company_id=context.company_id,
            name=name,
            tone=tone,
            voice_id=voice_id,
            created_at=self._clock.now(),
        )
        self._repository.save_interviewer_profile(context, profile)
        self._idempotency.put(
            context,
            operation="interviewer_profile.create",
            idempotency_key=idempotency_key,
            resource_id=profile.interviewer_profile_id,
        )
        return profile

    def list(self, context: TenantContext) -> tuple[InterviewerProfile, ...]:
        return self._repository.list_interviewer_profiles(context)

    def get(self, context: TenantContext, profile_id: UUID) -> InterviewerProfile:
        return self._repository.get_interviewer_profile(context, profile_id)
