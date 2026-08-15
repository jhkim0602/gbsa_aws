import warnings
from datetime import UTC, datetime
from uuid import UUID

from starlette.exceptions import StarletteDeprecationWarning

with warnings.catch_warnings():
    warnings.simplefilter("ignore", StarletteDeprecationWarning)
    from starlette.testclient import TestClient

from interview_evidence.interview_engine.api import create_lane_c_runtime
from interview_evidence.interview_engine.application.authorization import (
    FakeInterviewAuthorization,
    InterviewAuthorization,
)
from interview_evidence.interview_engine.domain.session import (
    EquipmentCheck,
    EquipmentComponent,
    EquipmentStatus,
)
from interview_evidence.interview_engine.repositories.postgres import (
    InMemoryInterviewRepository,
)
from interview_evidence.shared.audit import InMemoryAuditAppender
from interview_evidence.shared.aws_clients.ports import InMemoryObjectStorage
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.security.principals import (
    ApplicantPrincipal,
    FakePrincipalProvider,
)
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000002")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000003")
STRATEGY_ID = UUID("00000000-0000-7000-8000-000000000004")


def test_websocket_resume_returns_authoritative_snapshot() -> None:
    principal = ApplicantPrincipal(
        company_id=COMPANY_ID,
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        session_id=UUID("00000000-0000-7000-8000-000000000005"),
    )
    repository = InMemoryInterviewRepository()
    runtime = create_lane_c_runtime(
        principal_provider=FakePrincipalProvider(
            applicant_principals={"applicant-session": principal}
        ),
        authorization=FakeInterviewAuthorization(
            InterviewAuthorization(
                company_id=COMPANY_ID,
                invitation_id=INVITATION_ID,
                applicant_id=APPLICANT_ID,
                strategy_id=STRATEGY_ID,
                competency_model_version_id=UUID("00000000-0000-7000-8000-000000000006"),
                partial_analysis=False,
            )
        ),
        repository=repository,
        object_storage=InMemoryObjectStorage(),
        audit=InMemoryAuditAppender(),
        clock=FrozenClock(NOW),
    )
    context = TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.APPLICANT,
        actor_id=APPLICANT_ID,
        request_id=principal.session_id,
        trace_id="trace-websocket",
    )
    check = repository.save_equipment_check(
        context,
        EquipmentCheck(
            equipment_check_id=UUID("00000000-0000-7000-8000-000000000007"),
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            camera=EquipmentComponent(status=EquipmentStatus.READY),
            microphone=EquipmentComponent(status=EquipmentStatus.READY),
            network=EquipmentComponent(status=EquipmentStatus.READY),
            overall_status=EquipmentStatus.READY,
            checked_at=NOW,
        ),
    )
    session = runtime.service.create_session(
        context,
        principal,
        equipment_check_id=check.equipment_check_id,
        strategy_id=STRATEGY_ID,
        acknowledged_partial_analysis=False,
        idempotency_key="websocket-session-0001",
    )

    with TestClient(runtime.app) as client:
        client.cookies.set("iep_applicant_session", "applicant-session")
        with client.websocket_connect(
            f"/v1/applicant/interview-sessions/{session.interview_session_id}/stream"
        ) as websocket:
            websocket.send_json(
                {
                    "protocol_version": "1.0",
                    "message_type": "session.resume",
                    "session_id": str(session.interview_session_id),
                    "sequence": 0,
                    "idempotency_key": "websocket-resume-0001",
                    "correlation_id": "00000000-0000-7000-8000-000000000008",
                    "sent_at": NOW.isoformat(),
                    "payload": {
                        "last_applied_server_sequence": 0,
                        "last_final_turn_id": None,
                        "last_uploaded_recording_chunk_sequence": 0,
                    },
                }
            )
            response = websocket.receive_json()

    assert response["message_type"] == "resume.snapshot"
    assert response["sequence"] == 0
    assert response["payload"]["last_verified_recording_chunk_sequence"] == 0
