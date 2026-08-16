import pytest
from httpx import ASGITransport, AsyncClient
from interview_evidence.main import create_local_runtime

EXPECTED_OPERATION_IDS = {
    "getCurrentCompanyUser",
    "listPositions",
    "createPosition",
    "createCompetencyModelVersion",
    "publishCompetencyModelVersion",
    "listInvitations",
    "createInvitations",
    "exchangeApplicantInvitationToken",
    "verifyApplicantIdentity",
    "recordApplicantConsent",
    "createSubmissionUploadIntent",
    "listApplicantSubmissions",
    "registerApplicantSubmission",
    "getApplicantAnalysisStatus",
    "recordEquipmentCheck",
    "createInterviewSession",
    "getInterviewResumeSnapshot",
    "createRecordingUploadIntent",
    "getInterviewReport",
    "getInterviewTimeline",
    "createHumanAssessmentReview",
    "createReviewArtifact",
    "recordHumanFinalDecision",
    "createDeletionRequest",
    "getDeletionRequest",
}


def test_main_composes_all_lane_routers_boundaries_and_workers() -> None:
    runtime = create_local_runtime()
    schema = runtime.app.openapi()
    operation_ids = [
        operation["operationId"]
        for methods in schema["paths"].values()
        for operation in methods.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]

    assert set(operation_ids) >= EXPECTED_OPERATION_IDS
    assert all(operation_ids.count(operation_id) == 1 for operation_id in EXPECTED_OPERATION_IDS)
    assert str(
        runtime.app.url_path_for(
            "interview_stream",
            session_id="00000000-0000-7000-8000-000000000001",
        )
    ) == ("/v1/applicant/interview-sessions/00000000-0000-7000-8000-000000000001/stream")
    assert set(runtime.boundaries) == {
        "company_management",
        "submission_analysis",
        "interview_engine",
        "reporting",
        "company_submission",
        "submission_interview",
        "interview_reporting",
        "reporting_company",
    }
    assert set(runtime.worker_handlers) == {
        "invitation_email",
        "submission_analysis",
        "media_postprocess",
        "report_generation",
        "privacy_deletion",
    }


@pytest.mark.asyncio
async def test_composed_application_exposes_single_health_surface() -> None:
    runtime = create_local_runtime()
    async with AsyncClient(
        transport=ASGITransport(app=runtime.app),
        base_url="https://testserver",
    ) as client:
        live = await client.get("/health/live")
        ready = await client.get("/health/ready")

    assert live.json() == {"status": "ok"}
    assert ready.json() == {"status": "ok"}
