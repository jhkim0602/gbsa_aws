from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import FastAPI
from sqlalchemy.orm import Session

from interview_evidence.company_management.adapters.applicant_session import (
    ApplicantSessionAdapter,
)
from interview_evidence.company_management.adapters.company_auth import CompanyAuthAdapter
from interview_evidence.company_management.api.applicant_routes import create_applicant_router
from interview_evidence.company_management.api.company_routes import (
    InvitationReviewResolver,
    InvitationSessionResolver,
    create_company_router,
)
from interview_evidence.company_management.application.applicant_access_service import (
    ApplicantAccessService,
)
from interview_evidence.company_management.application.company_service import CompanyService
from interview_evidence.company_management.application.criteria_service import CriteriaService
from interview_evidence.company_management.application.hiring_service import HiringService
from interview_evidence.company_management.application.interviewer_service import (
    InterviewerProfileService,
)
from interview_evidence.company_management.application.invitation_template_service import (
    InvitationTemplateService,
)
from interview_evidence.company_management.domain.company import (
    Company,
    CompanyUser,
    Position,
    PositionStatus,
)
from interview_evidence.company_management.domain.criteria import (
    CompetencyModelStatus,
    CompetencyModelVersion,
    CriterionVerificationGuide,
    EvaluationCriterion,
    JobRequirement,
    RequirementType,
)
from interview_evidence.company_management.domain.hiring import Invitation, InvitationStatus
from interview_evidence.company_management.repositories.postgres import (
    CompanyRepository,
    InMemoryCompanyRepository,
    SqlAlchemyCompanyRepository,
    TenantScopedResourceNotFound,
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
from interview_evidence.shared.tenant import ActorType, TenantContext


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
    interviewer_service: InterviewerProfileService
    hiring_service: HiringService
    applicant_access_service: ApplicantAccessService
    template_service: InvitationTemplateService


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
    logo_base_url: str = "https://console.local",
    interview_sessions: InvitationSessionResolver | None = None,
    invitation_reviews: InvitationReviewResolver | None = None,
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
    interviewer_service = InterviewerProfileService(
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
    template_service = InvitationTemplateService(
        active_repository,
        active_clock,
        logo_base_url=logo_base_url,
    )
    company_router = create_company_router(
        auth=CompanyAuthAdapter(principal_provider),
        company_service=company_service,
        criteria_service=criteria_service,
        interviewer_service=interviewer_service,
        hiring_service=hiring_service,
        template_service=template_service,
        audit=active_audit,
        invitation_email=InvitationEmailHandler(active_email_sender),
        applicant_access_base_url=applicant_access_base_url,
        interview_sessions=interview_sessions,
        invitation_reviews=invitation_reviews,
    )
    applicant_router = create_applicant_router(
        sessions=active_sessions,
        access_service=access_service,
        clock=active_clock,
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
        interviewer_service=interviewer_service,
        hiring_service=hiring_service,
        applicant_access_service=access_service,
        template_service=template_service,
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
    logo_base_url: str = "https://console.local",
    interview_sessions: InvitationSessionResolver | None = None,
    invitation_reviews: InvitationReviewResolver | None = None,
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
        logo_base_url=logo_base_url,
        interview_sessions=interview_sessions,
        invitation_reviews=invitation_reviews,
    ).app


def create_sql_repository(session: Session) -> CompanyRepository:
    return SqlAlchemyCompanyRepository(session)


def ensure_company_principal(
    session: Session,
    *,
    company_id: UUID,
    company_user_id: UUID,
    company_name: str,
    identity_subject: str,
    email_normalized: str,
    now: datetime,
) -> None:
    """Create the local company principal without exposing Lane A persistence details."""
    context = TenantContext(
        company_id=company_id,
        actor_type=ActorType.COMPANY_USER,
        actor_id=company_user_id,
        request_id=uuid5(NAMESPACE_URL, f"local-company-seed:{company_id}"),
        trace_id="local-company-seed",
    )
    repository = SqlAlchemyCompanyRepository(session)
    repository.save_company(
        context,
        Company(
            company_id=company_id,
            name=company_name,
            created_at=now,
            updated_at=now,
        ),
    )
    repository.save_company_user(
        context,
        CompanyUser(
            company_user_id=company_user_id,
            company_id=company_id,
            identity_subject=identity_subject,
            email_normalized=email_normalized,
            created_at=now,
            last_seen_at=now,
        ),
    )


#: Reported on the seeded review screen as well, so the two must not drift apart.
_DEMO_CRITERION_NAME = "운영 문제 해결"


@dataclass(frozen=True, slots=True)
class LocalDemoRecruiting:
    """What the seeded demo workspace exposes to the lanes that build on it."""

    position_id: UUID
    competency_model_version_id: UUID
    criterion_id: UUID
    criterion_name: str
    reviewed_invitation_id: UUID
    reviewed_applicant_id: UUID


def ensure_local_demo_recruiting(
    session: Session,
    *,
    company_id: UUID,
    company_user_id: UUID,
    now: datetime,
) -> LocalDemoRecruiting:
    """Seed one local-only recruiting workspace without resetting existing demo progress."""
    context = TenantContext(
        company_id=company_id,
        actor_type=ActorType.COMPANY_USER,
        actor_id=company_user_id,
        request_id=uuid5(NAMESPACE_URL, f"local-recruiting-demo:{company_id}"),
        trace_id="local-recruiting-demo",
    )
    repository = SqlAlchemyCompanyRepository(session)
    position_id = uuid5(NAMESPACE_URL, f"local-recruiting-demo-position:{company_id}")
    version_id = uuid5(NAMESPACE_URL, f"local-recruiting-demo-version:{company_id}")
    criterion_id = uuid5(NAMESPACE_URL, f"{version_id}:problem-solving")

    try:
        repository.get_position(context, position_id)
    except TenantScopedResourceNotFound:
        repository.save_position(
            context,
            Position(
                position_id=position_id,
                company_id=company_id,
                title="로컬 데모 백엔드 엔지니어",
                description="지원자 초대와 면접 진행 상태를 확인하는 로컬 데모 포지션입니다.",
                role_type="백엔드 개발",
                headcount=3,
                recruitment_start_at=now.date(),
                recruitment_end_at=(now + timedelta(days=45)).date(),
                created_by=company_user_id,
                status=PositionStatus.ACTIVE,
                created_at=now,
            ),
        )

    try:
        repository.get_criterion_version(context, version_id)
    except TenantScopedResourceNotFound:
        criterion = EvaluationCriterion(
            criterion_id=criterion_id,
            code="PROBLEM_SOLVING",
            name=_DEMO_CRITERION_NAME,
            description="서비스 운영 문제를 분석하고 복구하는 역량",
            weight=1,
            verification_guide=CriterionVerificationGuide(
                observable_dimensions=("문제 상황", "본인 행동", "결과"),
                strong_answer_signals=("판단 근거와 직접 수행한 행동이 구체적이다.",),
                weak_answer_signals=("팀의 결과만 설명하고 본인 행동이 불명확하다.",),
                follow_up_directions=("직접 수행한 분석과 복구 작업",),
                max_follow_ups=2,
                time_budget_seconds=300,
            ),
            abstain_guidance="답변 근거가 부족하면 판단을 유보한다.",
            common_questions=("운영 문제를 해결한 경험을 설명해 주세요.",),
            required=True,
        )
        repository.save_criterion_version(
            context,
            CompetencyModelVersion(
                competency_model_version_id=version_id,
                company_id=company_id,
                position_id=position_id,
                version_number=1,
                job_requirements=(
                    JobRequirement(
                        job_requirement_id=uuid5(NAMESPACE_URL, f"{version_id}:requirement"),
                        requirement_type=RequirementType.PREFERRED,
                        statement="클라우드 환경의 장애 분석과 복구 경험",
                        priority=4,
                        criterion_code=criterion.code,
                    ),
                ),
                criteria=(criterion,),
                prohibited_topics=("직무와 무관한 개인정보",),
                interview_duration_minutes=30,
                status=CompetencyModelStatus.PUBLISHED,
                row_version=2,
                published_at=now,
            ),
        )

    # One applicant per recruiter phase, plus a reviewed case, so every dashboard metric has data.
    demo_applicants = (
        ("김하늘", "kim.haneul@example.test", InvitationStatus.INVITED),
        ("정유진", "jung.yujin@example.test", InvitationStatus.ANALYZING),
        ("윤지후", "yoon.jihu@example.test", InvitationStatus.READY),
        ("오세린", "oh.serin@example.test", InvitationStatus.COMPLETED),
        ("강민재", "kang.minjae@example.test", InvitationStatus.REVIEWED),
    )
    for index, (display_name, email, status) in enumerate(demo_applicants, start=1):
        invitation_id = uuid5(NAMESPACE_URL, f"{position_id}:invitation:{index}")
        try:
            repository.get_invitation(context, invitation_id)
            continue
        except TenantScopedResourceNotFound:
            pass
        expires_at = (
            now - timedelta(days=1)
            if status is InvitationStatus.EXPIRED
            else now + timedelta(days=14)
        )
        repository.save_invitation(
            context,
            Invitation(
                invitation_id=invitation_id,
                company_id=company_id,
                position_id=position_id,
                competency_model_version_id=version_id,
                applicant_id=uuid5(NAMESPACE_URL, f"{invitation_id}:applicant"),
                applicant_email_normalized=email,
                applicant_display_name=display_name,
                token_hash=sha256(f"local-demo:{invitation_id}".encode()).hexdigest(),
                expires_at=expires_at,
                status=status,
                identity_verified_at=(
                    None if status in {InvitationStatus.INVITED, InvitationStatus.EXPIRED} else now
                ),
                last_state_actor_type="system",
                row_version=index,
            ),
        )
    # The last applicant is the reviewed one, so it is the row a seeded interview and
    # report attach to. Returned rather than re-derived by the caller: the uuid5 recipe
    # is this lane's, and a caller that guessed it wrong would silently seed an orphan.
    reviewed_invitation_id = uuid5(
        NAMESPACE_URL, f"{position_id}:invitation:{len(demo_applicants)}"
    )
    return LocalDemoRecruiting(
        position_id=position_id,
        competency_model_version_id=version_id,
        criterion_id=criterion_id,
        criterion_name=_DEMO_CRITERION_NAME,
        reviewed_invitation_id=reviewed_invitation_id,
        reviewed_applicant_id=uuid5(NAMESPACE_URL, f"{reviewed_invitation_id}:applicant"),
    )
