from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from interview_evidence.company_management.adapters.applicant_session import (
    ApplicantSessionAdapter,
)
from interview_evidence.company_management.application.applicant_access_service import (
    ApplicantAccessService,
)
from interview_evidence.company_management.application.company_service import (
    CompanyManagementPublic,
    CompanyService,
)
from interview_evidence.company_management.application.criteria_service import CriteriaService
from interview_evidence.company_management.application.hiring_service import (
    ApplicantInvitationInput,
    HiringService,
)
from interview_evidence.company_management.domain.applicant_access import ProcessingPurpose
from interview_evidence.company_management.repositories.postgres import InMemoryCompanyRepository
from interview_evidence.integration.company_submission import CompanySubmissionAuthorization
from interview_evidence.shared.audit import InMemoryAuditAppender
from interview_evidence.shared.aws_clients.ports import InMemoryObjectStorage
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.messaging.outbox import InMemoryOutbox
from interview_evidence.shared.security.principals import (
    ApplicantPrincipal,
    CompanyPrincipal,
    FakePrincipalProvider,
)
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.api import create_lane_b_runtime

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_USER_ID = UUID("00000000-0000-7000-8000-000000000002")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def company_context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.COMPANY_USER,
        actor_id=COMPANY_USER_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000003"),
        trace_id="cross-a-to-b",
    )


def build_consented_invitation() -> tuple[
    InMemoryCompanyRepository,
    CompanyManagementPublic,
    ApplicantPrincipal,
]:
    clock = FrozenClock(NOW)
    repository = InMemoryCompanyRepository()
    sessions = ApplicantSessionAdapter(clock=clock)
    company_service = CompanyService(repository, clock)
    criteria_service = CriteriaService(repository, clock)
    hiring_service = HiringService(repository, sessions, clock)
    access_service = ApplicantAccessService(repository, InMemoryOutbox(), clock)
    context = company_context()
    company_principal = CompanyPrincipal(
        company_id=COMPANY_ID,
        company_user_id=COMPANY_USER_ID,
        identity_subject="oidc|company-user",
    )
    position = company_service.create_position(
        context,
        company_principal,
        title="Backend Engineer",
        description="Build evidence-backed interview systems.",
        idempotency_key="cross-position",
    )
    criterion = criteria_service.create_version(
        context,
        position_id=position.position_id,
        criteria=(
            {
                "code": "PROBLEM_SOLVING",
                "name": "Problem solving",
                "description": "Explains alternatives and tradeoffs.",
                "weight": 1.0,
                "good_evidence": {"signal": "tradeoff"},
                "weak_evidence": {"signal": "unsupported"},
                "abstain_guidance": "Abstain without final-answer evidence.",
                "common_questions": ("Which alternatives did you compare?",),
                "required": True,
            },
        ),
        prohibited_topics=("family",),
        interview_duration_minutes=30,
        persona_definition={"tone": "calm"},
        idempotency_key="cross-criterion",
    )
    published_criterion = criteria_service.publish_version(
        context,
        version_id=criterion.competency_model_version_id,
        expected_version=criterion.row_version,
    )
    campaign = hiring_service.create_campaign(
        context,
        position_id=position.position_id,
        competency_model_version_id=published_criterion.competency_model_version_id,
        name="Backend 2026",
        candidate_instructions="Use a quiet room.",
        idempotency_key="cross-campaign",
    )
    published_campaign = hiring_service.publish_campaign(
        context,
        campaign_id=campaign.campaign_id,
        expected_version=campaign.row_version,
    )
    issuance = hiring_service.issue_invitations(
        context,
        campaign_id=published_campaign.campaign_id,
        applicants=(
            ApplicantInvitationInput(
                email="applicant@example.com",
                display_name="Applicant",
            ),
        ),
        expires_at=NOW + timedelta(days=7),
    )[0]
    applicant_principal = ApplicantPrincipal(
        company_id=COMPANY_ID,
        invitation_id=issuance.invitation.invitation_id,
        applicant_id=issuance.invitation.applicant_id,
        session_id=UUID("00000000-0000-7000-8000-000000000004"),
    )
    applicant_context = context.model_copy(
        update={
            "actor_type": ActorType.APPLICANT,
            "actor_id": applicant_principal.applicant_id,
        }
    )
    access_service.verify_identity(
        applicant_context,
        applicant_principal,
        display_name="Applicant",
        verification_value="verified",
    )
    access_service.record_consent(
        applicant_context,
        applicant_principal,
        policy_version=access_service.get_consent_policy().policy_version,
        accepted_purposes=tuple(ProcessingPurpose),
        consent_content_digest=access_service.get_consent_policy().content_digest,
    )
    return repository, CompanyManagementPublic(repository, clock), applicant_principal


@pytest.mark.asyncio
async def test_lane_b_uses_real_campaign_and_consent_boundary() -> None:
    repository, company_public, principal = build_consented_invitation()
    storage = InMemoryObjectStorage()
    runtime = create_lane_b_runtime(
        principal_provider=FakePrincipalProvider(
            applicant_principals={"applicant-session": principal}
        ),
        authorization=CompanySubmissionAuthorization(company_public),
        object_storage=storage,
        audit=InMemoryAuditAppender(),
        clock=FrozenClock(NOW),
    )

    async with AsyncClient(
        transport=ASGITransport(app=runtime.app),
        base_url="https://testserver",
        cookies={"iep_applicant_session": "applicant-session"},
    ) as client:
        allowed = await client.post(
            "/v1/applicant/submissions/upload-intents",
            headers={"Idempotency-Key": "cross-boundary-allowed"},
            json={
                "source_type": "resume",
                "filename": "resume.pdf",
                "media_type": "application/pdf",
                "byte_size": 1024,
                "sha256": "a" * 64,
            },
        )
        assert allowed.status_code == 201

        consent = repository.get_latest_consent(company_context(), principal.invitation_id)
        assert consent is not None
        repository.save_consent(
            company_context(),
            consent.withdraw(at=NOW + timedelta(minutes=1)),
        )
        denied = await client.post(
            "/v1/applicant/submissions/upload-intents",
            headers={"Idempotency-Key": "cross-boundary-withdrawn"},
            json={
                "source_type": "resume",
                "filename": "later.pdf",
                "media_type": "application/pdf",
                "byte_size": 2048,
                "sha256": "b" * 64,
            },
        )

    assert denied.status_code == 403
    assert len(storage.intents) == 1


@pytest.mark.asyncio
async def test_lane_b_rejects_applicant_outside_real_invitation_scope() -> None:
    _, company_public, principal = build_consented_invitation()
    mismatched_principal = principal.model_copy(
        update={"applicant_id": UUID("00000000-0000-7000-8000-000000000099")}
    )
    storage = InMemoryObjectStorage()
    runtime = create_lane_b_runtime(
        principal_provider=FakePrincipalProvider(
            applicant_principals={"mismatched-session": mismatched_principal}
        ),
        authorization=CompanySubmissionAuthorization(company_public),
        object_storage=storage,
        audit=InMemoryAuditAppender(),
        clock=FrozenClock(NOW),
    )

    async with AsyncClient(
        transport=ASGITransport(app=runtime.app),
        base_url="https://testserver",
        cookies={"iep_applicant_session": "mismatched-session"},
    ) as client:
        response = await client.post(
            "/v1/applicant/submissions/upload-intents",
            headers={"Idempotency-Key": "cross-boundary-wrong-applicant"},
            json={
                "source_type": "resume",
                "filename": "resume.pdf",
                "media_type": "application/pdf",
                "byte_size": 1024,
                "sha256": "c" * 64,
            },
        )

    assert response.status_code == 403
    assert storage.intents == []
