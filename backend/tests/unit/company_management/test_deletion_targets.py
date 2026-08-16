from datetime import UTC, datetime, timedelta
from uuid import UUID

from interview_evidence.company_management.application.deletion_targets import (
    CompanyDeletionTargets,
)
from interview_evidence.company_management.domain.applicant_access import (
    ConsentRecord,
    ProcessingPurpose,
)
from interview_evidence.company_management.domain.company import Position
from interview_evidence.company_management.domain.criteria import (
    CompetencyModelVersion,
    EvaluationCriterion,
)
from interview_evidence.company_management.domain.hiring import Invitation
from interview_evidence.company_management.repositories.postgres import (
    InMemoryCompanyRepository,
)
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.messaging.outbox import InMemoryOutbox
from interview_evidence.shared.tenant import ActorType, TenantContext

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
USER_ID = UUID("00000000-0000-7000-8000-000000000002")
POSITION_ID = UUID("00000000-0000-7000-8000-000000000003")
VERSION_ID = UUID("00000000-0000-7000-8000-000000000004")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000006")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000007")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def test_owned_targets_and_retention_event_are_tenant_scoped() -> None:
    context = TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=USER_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000008"),
        trace_id="deletion-targets",
    )
    repository = InMemoryCompanyRepository()
    position = Position(
        position_id=POSITION_ID,
        company_id=COMPANY_ID,
        title="백엔드 개발자",
        description="서비스 개발",
        created_by=USER_ID,
        created_at=NOW,
    )
    repository.save_position(context, position)
    criterion = EvaluationCriterion(
        criterion_id=UUID("00000000-0000-7000-8000-000000000009"),
        code="PROBLEM_SOLVING",
        name="문제 해결",
        description="대안을 비교한다.",
        weight=1,
        good_evidence={},
        weak_evidence={},
        abstain_guidance="근거가 없으면 보류한다.",
        required=True,
    )
    version = CompetencyModelVersion.create(
        competency_model_version_id=VERSION_ID,
        company_id=COMPANY_ID,
        position_id=POSITION_ID,
        version_number=1,
        criteria=(criterion,),
        prohibited_topics=(),
        interview_duration_minutes=30,
        persona_definition={"name": "면접관"},
    ).publish(expected_version=1, published_at=NOW)
    repository.save_criterion_version(context, version)
    invitation = Invitation.create(
        invitation_id=INVITATION_ID,
        company_id=COMPANY_ID,
        position_id=POSITION_ID,
        competency_model_version_id=VERSION_ID,
        applicant_id=APPLICANT_ID,
        applicant_email="applicant@example.com",
        applicant_display_name="홍길동",
        token_hash="a" * 64,
        expires_at=NOW + timedelta(days=7),
    )
    repository.save_invitation(context, invitation)
    repository.save_consent(
        context,
        ConsentRecord.accept(
            consent_record_id=UUID("00000000-0000-7000-8000-000000000010"),
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            policy_version="2026-08-v1",
            purposes=tuple(ProcessingPurpose),
            retention_days=180,
            accepted_at=NOW,
            evidence_digest="b" * 64,
        ),
    )
    outbox = InMemoryOutbox()
    targets = CompanyDeletionTargets(repository, outbox, FrozenClock(NOW))

    owned = targets.enumerate_owned_targets(
        context,
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
    )
    assert {target.resource_type for target in owned} == {
        "consent_record",
        "applicant_profile",
        "invitation",
        "invitation_state_history",
        "audit_event",
    }
    assert all(target.company_id == COMPANY_ID for target in owned)

    event = targets.publish_retention_expired(
        context,
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        policy_snapshot_id=UUID("00000000-0000-7000-8000-000000000011"),
        expired_at=NOW + timedelta(days=180),
    )
    assert event.event_type == "retention.expired"
    assert event.payload["invitation_id"] == str(INVITATION_ID)
