from typing import cast

import pytest
from httpx import ASGITransport, AsyncClient
from interview_evidence.interview_engine.api import LaneCRuntime
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.adapters.object_storage import (
    UploadIntentNotFound,
)
from interview_evidence.submission_analysis.api import LaneBRuntime
from interview_evidence.submission_analysis.application.public import (
    SubmissionAnalysisPublic,
)
from tests.e2e.support import (
    SECOND_COMPANY_ID,
    SECOND_COMPANY_TOKEN,
    SECOND_COMPANY_USER_ID,
    run_thin_journey_async,
)


@pytest.mark.asyncio
async def test_cross_route_worker_search_object_and_hot_view_isolation() -> None:
    result = await run_thin_journey_async()
    wrong_context = TenantContext(
        company_id=SECOND_COMPANY_ID,
        actor_type=ActorType.COMPANY_USER,
        actor_id=SECOND_COMPANY_USER_ID,
        request_id=SECOND_COMPANY_USER_ID,
        trace_id="e2e-cross-tenant",
    )
    lane_b = cast(LaneBRuntime, result.runtime.lanes["submission_analysis"])
    lane_c = cast(LaneCRuntime, result.runtime.lanes["interview_engine"])
    submission_public = cast(
        SubmissionAnalysisPublic,
        result.runtime.boundaries["submission_analysis"],
    )

    async with AsyncClient(
        transport=ASGITransport(app=result.runtime.app),
        base_url="https://testserver",
    ) as client:
        report = await client.get(
            f"/v1/interview-sessions/{result.session_id}/report",
            headers={"Authorization": f"Bearer {SECOND_COMPANY_TOKEN}"},
        )

    assert report.status_code == 202
    assert report.json() == {
        "status": "queued",
        "retryable": True,
        "message": None,
    }
    assert (
        submission_public.retrieve_context(
            wrong_context,
            applicant_id=result.applicant_id,
            invitation_id=result.invitation_id,
            competency_model_version_id=result.hiring_criterion_version_id,
            query="결제 장애",
            query_vector=(1.0, 0.0),
            criterion_id=SECOND_COMPANY_ID,
            config_version="local-hybrid-v1",
            limit=5,
        )
        == ()
    )
    with pytest.raises(UploadIntentNotFound):
        lane_b.storage.resolve(
            wrong_context,
            upload_id=result.upload_id,
            applicant_id=result.applicant_id,
        )
    assert lane_c.hot_view.get(wrong_context, result.session_id) is None
