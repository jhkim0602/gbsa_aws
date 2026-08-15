from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from interview_evidence.shared.audit import InMemoryAuditAppender
from interview_evidence.shared.aws_clients.ports import InMemoryObjectStorage
from interview_evidence.shared.security.principals import (
    ApplicantPrincipal,
    FakePrincipalProvider,
)
from interview_evidence.submission_analysis.api import create_lane_b_app
from interview_evidence.submission_analysis.application.authorization import (
    FakeSubmissionAuthorization,
)
from interview_evidence.submission_analysis.repositories.postgres import (
    InMemorySubmissionRepository,
)

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000002")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000003")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000004")


def app():
    principal = ApplicantPrincipal(
        company_id=COMPANY_ID,
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        session_id=SESSION_ID,
    )
    return create_lane_b_app(
        principal_provider=FakePrincipalProvider(
            applicant_principals={"applicant-session": principal}
        ),
        authorization=FakeSubmissionAuthorization.allowed(principal),
        repository=InMemorySubmissionRepository(),
        object_storage=InMemoryObjectStorage(),
        audit=InMemoryAuditAppender(),
    )


def test_lane_b_exposes_the_frozen_submission_operations() -> None:
    operations = {
        operation["operationId"]
        for path in app().openapi()["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    }

    assert operations >= {
        "createSubmissionUploadIntent",
        "listApplicantSubmissions",
        "registerApplicantSubmission",
        "getApplicantAnalysisStatus",
    }


@pytest.mark.asyncio
async def test_upload_intent_contract_rejects_unknown_scope_fields() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app()),
        base_url="https://testserver",
        cookies={"iep_applicant_session": "applicant-session"},
    ) as client:
        invalid = await client.post(
            "/v1/applicant/submissions/upload-intents",
            headers={"Idempotency-Key": "upload-intent-0001"},
            json={
                "source_type": "resume",
                "filename": "resume.pdf",
                "media_type": "application/pdf",
                "byte_size": 1024,
                "sha256": "a" * 64,
                "company_id": str(COMPANY_ID),
            },
        )
        assert invalid.status_code == 422

        created = await client.post(
            "/v1/applicant/submissions/upload-intents",
            headers={"Idempotency-Key": "upload-intent-0002"},
            json={
                "source_type": "resume",
                "filename": "resume.pdf",
                "media_type": "application/pdf",
                "byte_size": 1024,
                "sha256": "a" * 64,
            },
        )
    assert created.status_code == 201
    assert set(created.json()) == {
        "upload_id",
        "method",
        "url",
        "required_headers",
        "expires_at",
    }
