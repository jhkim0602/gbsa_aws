from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.shared.submission_materials import SubmissionMaterialType
from interview_evidence.submission_analysis.domain.submission import (
    SourceType,
    Submission,
    SubmissionStatus,
)
from interview_evidence.workers.analysis.pipeline import SubmissionAnalysisPipeline


def test_failed_document_submission_can_return_to_analysis() -> None:
    failed = Submission(
        submission_id=UUID("00000000-0000-7000-8000-000000000001"),
        company_id=UUID("00000000-0000-7000-8000-000000000002"),
        invitation_id=UUID("00000000-0000-7000-8000-000000000003"),
        applicant_id=UUID("00000000-0000-7000-8000-000000000004"),
        material_type=SubmissionMaterialType.RESUME,
        source_type=SourceType.RESUME,
        source_uri="tenants/company/submission-original/applicant/file",
        original_filename="resume.pdf",
        content_hash="a" * 64,
        byte_size=1024,
        media_type="application/pdf",
        status=SubmissionStatus.FAILED,
        failure_code="document_ocr_unavailable",
        impact_summary="분석 실패",
        created_at=datetime(2026, 8, 20, tzinfo=UTC),
    )

    analyzing = SubmissionAnalysisPipeline._to_analyzing(failed)

    assert analyzing.status is SubmissionStatus.ANALYZING
    assert analyzing.failure_code is None
    assert analyzing.impact_summary is None
    assert analyzing.row_version == failed.row_version + 2
