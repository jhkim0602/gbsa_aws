from __future__ import annotations

from interview_evidence.company_management.domain.applicant_access import (
    ApplicantProfile,
    ConsentRecord,
    ProcessingPurpose,
)
from interview_evidence.company_management.domain.hiring import (
    Invitation,
    InvitationStateChange,
)
from interview_evidence.company_management.repositories.postgres import CompanyRepository
from interview_evidence.shared.ids import Clock, new_uuid7
from interview_evidence.shared.messaging.outbox import Outbox, OutboxEvent
from interview_evidence.shared.security.principals import ApplicantPrincipal
from interview_evidence.shared.tenant import TenantContext

REQUIRED_CONSENT_PURPOSES = frozenset(ProcessingPurpose)


class ApplicantAccessService:
    def __init__(
        self,
        repository: CompanyRepository,
        outbox: Outbox,
        clock: Clock,
        *,
        default_retention_days: int = 180,
    ) -> None:
        self._repository = repository
        self._outbox = outbox
        self._clock = clock
        self._default_retention_days = default_retention_days

    def verify_identity(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        *,
        display_name: str,
        verification_value: str,
    ) -> tuple[ApplicantProfile, Invitation]:
        context.assert_company(principal.company_id)
        invitation = self._repository.get_invitation(context, principal.invitation_id)
        if invitation.applicant_id != principal.applicant_id:
            raise PermissionError("applicant session is outside the invitation scope")
        if not verification_value.strip():
            raise PermissionError("identity verification failed")
        if display_name.strip().casefold() != invitation.applicant_display_name.casefold():
            raise PermissionError("identity verification failed")
        profile = ApplicantProfile(
            applicant_id=principal.applicant_id,
            company_id=context.company_id,
            invitation_id=principal.invitation_id,
            display_name=display_name.strip(),
        )
        updated = invitation.transition(
            "identity_verified",
            actor_type="applicant",
            occurred_at=self._clock.now(),
            expected_version=invitation.row_version,
        )
        self._repository.save_applicant_profile(context, profile)
        self._save_transition(context, invitation, updated)
        return profile, updated

    def record_consent(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        *,
        policy_version: str,
        accepted_purposes: tuple[ProcessingPurpose, ...],
        consent_content_digest: str,
    ) -> ConsentRecord:
        purposes = frozenset(accepted_purposes)
        if purposes != REQUIRED_CONSENT_PURPOSES:
            raise ValueError("all required consent purposes must be accepted")
        invitation = self._repository.get_invitation(context, principal.invitation_id)
        consent = ConsentRecord.accept(
            consent_record_id=new_uuid7(self._clock.now()),
            company_id=context.company_id,
            invitation_id=principal.invitation_id,
            policy_version=policy_version,
            purposes=tuple(purposes),
            retention_days=self._default_retention_days,
            accepted_at=self._clock.now(),
            evidence_digest=consent_content_digest,
        )
        updated = invitation.transition(
            "consented",
            actor_type="applicant",
            occurred_at=self._clock.now(),
            expected_version=invitation.row_version,
        )
        self._repository.save_consent(context, consent)
        self._save_transition(context, invitation, updated)
        self._outbox.append(
            OutboxEvent(
                outbox_event_id=new_uuid7(self._clock.now()),
                company_id=context.company_id,
                aggregate_type="invitation",
                aggregate_id=invitation.invitation_id,
                aggregate_version=updated.row_version,
                event_type="invitation.consent_completed",
                event_version=1,
                payload={
                    "invitation_id": str(invitation.invitation_id),
                    "applicant_id": str(principal.applicant_id),
                    "consent_record_id": str(consent.consent_record_id),
                    "purpose_codes": sorted(purpose.value for purpose in purposes),
                    "retention_days": consent.retention_days,
                },
                idempotency_key=f"consent-{consent.consent_record_id}",
                trace_id=context.trace_id,
                occurred_at=self._clock.now(),
            )
        )
        return consent

    def _save_transition(
        self,
        context: TenantContext,
        before: Invitation,
        after: Invitation,
    ) -> None:
        self._repository.save_invitation(context, after)
        self._repository.append_invitation_state_change(
            context,
            InvitationStateChange(
                invitation_state_change_id=new_uuid7(self._clock.now()),
                company_id=context.company_id,
                invitation_id=after.invitation_id,
                from_status=before.status,
                to_status=after.status,
                actor_type="applicant",
                occurred_at=self._clock.now(),
                aggregate_version=after.row_version,
            ),
        )
