from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from interview_evidence.interview_engine.api import create_lane_c_runtime
from interview_evidence.interview_engine.application.authorization import (
    FakeInterviewAuthorization,
    InterviewAuthorization,
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

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000002")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000003")
STRATEGY_ID = UUID("00000000-0000-7000-8000-000000000004")
CRITERIA_VERSION_ID = UUID("00000000-0000-7000-8000-000000000005")


def principal() -> ApplicantPrincipal:
    return ApplicantPrincipal(
        company_id=COMPANY_ID,
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        session_id=UUID("00000000-0000-7000-8000-000000000006"),
    )


@pytest.mark.asyncio
async def test_equipment_session_resume_and_media_intent_contract() -> None:
    audit = InMemoryAuditAppender()
    runtime = create_lane_c_runtime(
        principal_provider=FakePrincipalProvider(
            applicant_principals={"applicant-session": principal()}
        ),
        authorization=FakeInterviewAuthorization(
            InterviewAuthorization(
                company_id=COMPANY_ID,
                invitation_id=INVITATION_ID,
                applicant_id=APPLICANT_ID,
                strategy_id=STRATEGY_ID,
                competency_model_version_id=CRITERIA_VERSION_ID,
                partial_analysis=False,
            )
        ),
        repository=InMemoryInterviewRepository(),
        object_storage=InMemoryObjectStorage(),
        audit=audit,
        clock=FrozenClock(NOW),
    )

    async with AsyncClient(
        transport=ASGITransport(app=runtime.app),
        base_url="https://testserver",
        cookies={"iep_applicant_session": "applicant-session"},
    ) as client:
        equipment = await client.post(
            "/v1/applicant/equipment-checks",
            headers={"Idempotency-Key": "equipment-check-0001"},
            json={
                "camera": {"status": "ready", "sanitized_code": None},
                "microphone": {"status": "ready", "sanitized_code": None},
                "network": {
                    "status": "warning",
                    "sanitized_code": "NETWORK_JITTER",
                },
            },
        )
        assert equipment.status_code == 201
        assert equipment.json()["overall_status"] == "warning"

        created = await client.post(
            "/v1/applicant/interview-sessions",
            headers={"Idempotency-Key": "interview-session-0001"},
            json={
                "equipment_check_id": equipment.json()["equipment_check_id"],
                "strategy_id": str(STRATEGY_ID),
                "acknowledged_partial_analysis": False,
            },
        )
        assert created.status_code == 201
        session_id = created.json()["interview_session_id"]
        assert created.json()["websocket_path"].endswith(f"/{session_id}/stream")
        assert created.json()["protocol_version"] == "1.0"

        resume = await client.get(f"/v1/applicant/interview-sessions/{session_id}/resume")
        assert resume.status_code == 200
        assert resume.json()["server_sequence"] == 0

        media = await client.post(
            f"/v1/applicant/interview-sessions/{session_id}/media-upload-intents",
            headers={"Idempotency-Key": "recording-upload-0001"},
            json={
                "chunk_sequence": 0,
                "byte_size": 1024,
                "sha256": "a" * 64,
                "session_start_ms": 0,
                "session_end_ms": 2000,
            },
        )
        assert media.status_code == 201
        assert media.json()["method"] == "PUT"
        assert "signed" not in str(audit.events).lower()

    assert {event.action for event in audit.events} == {
        "interview.equipment_checked",
        "interview.session_created",
        "interview.recording_upload_intent_created",
    }


@pytest.mark.asyncio
async def test_applicant_cannot_access_another_scoped_session() -> None:
    repository = InMemoryInterviewRepository()
    runtime = create_lane_c_runtime(
        principal_provider=FakePrincipalProvider(
            applicant_principals={"applicant-session": principal()}
        ),
        authorization=FakeInterviewAuthorization(
            InterviewAuthorization(
                company_id=COMPANY_ID,
                invitation_id=INVITATION_ID,
                applicant_id=APPLICANT_ID,
                strategy_id=STRATEGY_ID,
                competency_model_version_id=CRITERIA_VERSION_ID,
                partial_analysis=False,
            )
        ),
        repository=repository,
        object_storage=InMemoryObjectStorage(),
        audit=InMemoryAuditAppender(),
        clock=FrozenClock(NOW),
    )

    async with AsyncClient(
        transport=ASGITransport(app=runtime.app),
        base_url="https://testserver",
        cookies={"iep_applicant_session": "applicant-session"},
    ) as client:
        response = await client.get(
            "/v1/applicant/interview-sessions/00000000-0000-7000-8000-000000000099/resume"
        )

    assert response.status_code == 404
