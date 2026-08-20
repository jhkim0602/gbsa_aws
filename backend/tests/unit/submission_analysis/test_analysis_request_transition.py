from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.shared.submission_materials import SubmissionMaterialType
from interview_evidence.submission_analysis.domain.submission import SourceType, Submission
from interview_evidence.workers.analysis.event_handler import _owns_analysis_state_transition

NOW = datetime(2026, 8, 20, 8, 30, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000002")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000003")


def submission(submission_id: UUID, material_type: SubmissionMaterialType) -> Submission:
    return Submission(
        submission_id=submission_id,
        company_id=COMPANY_ID,
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        material_type=material_type,
        source_type=SourceType.PDF,
        source_uri=f"submissions/{submission_id}",
        original_filename=f"{material_type.value}.pdf",
        content_hash="a" * 64,
        byte_size=128,
        media_type="application/pdf",
        created_at=NOW,
    )


def test_only_the_first_submission_owns_the_analysis_state_transition() -> None:
    first = submission(
        UUID("00000000-0000-7000-8000-000000000010"),
        SubmissionMaterialType.RESUME,
    )
    second = submission(
        UUID("00000000-0000-7000-8000-000000000011"),
        SubmissionMaterialType.COVER_LETTER,
    )

    assert _owns_analysis_state_transition(first, (second, first)) is True
    assert _owns_analysis_state_transition(second, (second, first)) is False
