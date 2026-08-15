from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from interview_evidence.company_management.repositories.postgres import CompanyRepository
from interview_evidence.shared.audit import InMemoryAuditAppender
from interview_evidence.shared.ids import Clock, new_uuid7
from interview_evidence.shared.messaging.outbox import InMemoryOutbox, OutboxEvent
from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class CompanyDeletionTarget:
    company_id: UUID
    owner_lane: str
    store: str
    resource_type: str
    resource_id: UUID


@dataclass(frozen=True, slots=True)
class CompanyDeletionReceipt:
    store: str
    resource_type: str
    resource_id: UUID
    verified_absent: bool


class InMemoryCompanyTargetDeleter:
    def __init__(
        self,
        repository: CompanyRepository,
        audit: InMemoryAuditAppender,
    ) -> None:
        self._repository = repository
        self._audit = audit

    def delete_and_verify(
        self,
        context: TenantContext,
        target: CompanyDeletionTarget,
    ) -> CompanyDeletionReceipt:
        context.assert_company(target.company_id)
        if target.owner_lane != "A" or target.store != "aurora":
            raise PermissionError("deletion target is not owned by Lane A")
        resource_id = target.resource_id
        if target.resource_type == "audit_event":
            self._audit.events = [
                event
                for event in self._audit.events
                if not (event.company_id == context.company_id and event.resource_id == resource_id)
            ]
            absent = not any(
                event.company_id == context.company_id and event.resource_id == resource_id
                for event in self._audit.events
            )
        else:
            absent = self._repository.delete_and_verify_target(
                context,
                resource_type=target.resource_type,
                resource_id=resource_id,
            )
        return CompanyDeletionReceipt(
            store=target.store,
            resource_type=target.resource_type,
            resource_id=resource_id,
            verified_absent=absent,
        )


class CompanyDeletionTargets:
    def __init__(
        self,
        repository: CompanyRepository,
        outbox: InMemoryOutbox,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._outbox = outbox
        self._clock = clock

    def enumerate_owned_targets(
        self,
        context: TenantContext,
        *,
        invitation_id: UUID,
        applicant_id: UUID,
    ) -> tuple[CompanyDeletionTarget, ...]:
        invitation = self._repository.get_invitation(context, invitation_id)
        if invitation.applicant_id != applicant_id:
            raise PermissionError("applicant is outside the invitation scope")
        targets = [
            CompanyDeletionTarget(
                company_id=context.company_id,
                owner_lane="A",
                store="aurora",
                resource_type="consent_record",
                resource_id=consent.consent_record_id,
            )
            for consent in [self._repository.get_latest_consent(context, invitation_id)]
            if consent is not None
        ]
        targets.extend(
            [
                CompanyDeletionTarget(
                    company_id=context.company_id,
                    owner_lane="A",
                    store="aurora",
                    resource_type="applicant_profile",
                    resource_id=applicant_id,
                ),
                CompanyDeletionTarget(
                    company_id=context.company_id,
                    owner_lane="A",
                    store="aurora",
                    resource_type="invitation",
                    resource_id=invitation_id,
                ),
                CompanyDeletionTarget(
                    company_id=context.company_id,
                    owner_lane="A",
                    store="aurora",
                    resource_type="invitation_state_history",
                    resource_id=invitation_id,
                ),
                CompanyDeletionTarget(
                    company_id=context.company_id,
                    owner_lane="A",
                    store="aurora",
                    resource_type="audit_event",
                    resource_id=invitation_id,
                ),
            ]
        )
        return tuple(targets)

    def publish_retention_expired(
        self,
        context: TenantContext,
        *,
        invitation_id: UUID,
        applicant_id: UUID,
        policy_snapshot_id: UUID,
        expired_at: datetime,
    ) -> OutboxEvent:
        self._repository.get_invitation(context, invitation_id)
        event = OutboxEvent(
            outbox_event_id=new_uuid7(self._clock.now()),
            company_id=context.company_id,
            aggregate_type="invitation",
            aggregate_id=invitation_id,
            aggregate_version=1,
            event_type="retention.expired",
            event_version=1,
            payload={
                "invitation_id": str(invitation_id),
                "applicant_id": str(applicant_id),
                "policy_snapshot_id": str(policy_snapshot_id),
                "expired_at": expired_at.isoformat(),
            },
            idempotency_key=f"retention-expired-{invitation_id}",
            trace_id=context.trace_id,
            occurred_at=self._clock.now(),
        )
        return self._outbox.append(event)
