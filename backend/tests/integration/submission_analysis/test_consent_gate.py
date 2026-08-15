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


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["consent_missing", "invitation_not_consented"])
async def test_submission_work_is_rejected_before_storage_when_not_authorized(
    reason: str,
) -> None:
    principal = ApplicantPrincipal(
        company_id=COMPANY_ID,
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        session_id=UUID("00000000-0000-7000-8000-000000000004"),
    )
    storage = InMemoryObjectStorage()
    app = create_lane_b_app(
        principal_provider=FakePrincipalProvider(
            applicant_principals={"applicant-session": principal}
        ),
        authorization=FakeSubmissionAuthorization.denied(principal, reason=reason),
        repository=InMemorySubmissionRepository(),
        object_storage=storage,
        audit=InMemoryAuditAppender(),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://testserver",
        cookies={"iep_applicant_session": "applicant-session"},
    ) as client:
        response = await client.post(
            "/v1/applicant/submissions/upload-intents",
            headers={"Idempotency-Key": "consent-gate-0001"},
            json={
                "source_type": "resume",
                "filename": "resume.pdf",
                "media_type": "application/pdf",
                "byte_size": 1024,
                "sha256": "a" * 64,
            },
        )

    assert response.status_code == 403
    assert storage.intents == []
