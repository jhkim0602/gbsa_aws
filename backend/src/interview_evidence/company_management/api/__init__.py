from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI
from sqlalchemy.orm import Session

from interview_evidence.company_management.adapters.applicant_session import (
    ApplicantSessionAdapter,
)
from interview_evidence.company_management.adapters.company_auth import CompanyAuthAdapter
from interview_evidence.company_management.api.applicant_routes import create_applicant_router
from interview_evidence.company_management.api.company_routes import create_company_router
from interview_evidence.company_management.application.applicant_access_service import (
    ApplicantAccessService,
)
from interview_evidence.company_management.application.company_service import CompanyService
from interview_evidence.company_management.application.criteria_service import CriteriaService
from interview_evidence.company_management.application.hiring_service import HiringService
from interview_evidence.company_management.repositories.postgres import (
    CompanyRepository,
    InMemoryCompanyRepository,
    SqlAlchemyCompanyRepository,
)
from interview_evidence.company_management.workers.invitation_email import (
    InvitationEmailHandler,
)
from interview_evidence.main import create_app
from interview_evidence.shared.audit import AuditAppender, InMemoryAuditAppender
from interview_evidence.shared.aws_clients.ports import (
    EmailSender,
    InMemoryEmailSender,
)
from interview_evidence.shared.idempotency import (
    InMemoryResourceIdempotencyStore,
    ResourceIdempotencyStore,
)
from interview_evidence.shared.ids import Clock, SystemClock
from interview_evidence.shared.messaging.outbox import InMemoryOutbox, Outbox
from interview_evidence.shared.security.principals import PrincipalProvider


@dataclass(frozen=True, slots=True)
class LaneARuntime:
    app: FastAPI
    repository: CompanyRepository
    audit: AuditAppender
    sessions: ApplicantSessionAdapter
    outbox: Outbox
    email_sender: EmailSender
    company_service: CompanyService
    criteria_service: CriteriaService
    hiring_service: HiringService
    applicant_access_service: ApplicantAccessService


def create_lane_a_runtime(
    *,
    principal_provider: PrincipalProvider,
    repository: CompanyRepository | None = None,
    audit: AuditAppender | None = None,
    clock: Clock | None = None,
    sessions: ApplicantSessionAdapter | None = None,
    outbox: Outbox | None = None,
    idempotency: ResourceIdempotencyStore | None = None,
    email_sender: EmailSender | None = None,
    applicant_access_base_url: str = "https://applicant.local/access",
) -> LaneARuntime:
    active_repository = repository or InMemoryCompanyRepository()
    active_audit = audit or InMemoryAuditAppender()
    active_clock = clock or SystemClock()
    active_sessions = sessions or ApplicantSessionAdapter(clock=active_clock)
    active_outbox = outbox or InMemoryOutbox()
    active_idempotency = idempotency or InMemoryResourceIdempotencyStore()
    active_email_sender = email_sender or InMemoryEmailSender()

    company_service = CompanyService(
        active_repository,
        active_clock,
        active_idempotency,
    )
    criteria_service = CriteriaService(
        active_repository,
        active_clock,
        active_idempotency,
    )
    hiring_service = HiringService(
        active_repository,
        active_sessions,
        active_clock,
        active_idempotency,
    )
    access_service = ApplicantAccessService(
        active_repository,
        active_outbox,
        active_clock,
    )
    company_router = create_company_router(
        auth=CompanyAuthAdapter(principal_provider),
        company_service=company_service,
        criteria_service=criteria_service,
        hiring_service=hiring_service,
        audit=active_audit,
        invitation_email=InvitationEmailHandler(active_email_sender),
        applicant_access_base_url=applicant_access_base_url,
    )
    applicant_router = create_applicant_router(
        sessions=active_sessions,
        access_service=access_service,
    )
    return LaneARuntime(
        app=create_app([company_router, applicant_router]),
        repository=active_repository,
        audit=active_audit,
        sessions=active_sessions,
        outbox=active_outbox,
        email_sender=active_email_sender,
        company_service=company_service,
        criteria_service=criteria_service,
        hiring_service=hiring_service,
        applicant_access_service=access_service,
    )


def create_lane_a_app(
    *,
    principal_provider: PrincipalProvider,
    repository: CompanyRepository | None = None,
    audit: AuditAppender | None = None,
    clock: Clock | None = None,
    sessions: ApplicantSessionAdapter | None = None,
    outbox: Outbox | None = None,
    idempotency: ResourceIdempotencyStore | None = None,
    email_sender: EmailSender | None = None,
    applicant_access_base_url: str = "https://applicant.local/access",
) -> FastAPI:
    return create_lane_a_runtime(
        principal_provider=principal_provider,
        repository=repository,
        audit=audit,
        clock=clock,
        sessions=sessions,
        outbox=outbox,
        idempotency=idempotency,
        email_sender=email_sender,
        applicant_access_base_url=applicant_access_base_url,
    ).app


def create_sql_repository(session: Session) -> CompanyRepository:
    return SqlAlchemyCompanyRepository(session)
