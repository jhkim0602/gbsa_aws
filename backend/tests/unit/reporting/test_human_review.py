from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.reporting.api.company_routes import ReviewArtifactCreate
from interview_evidence.reporting.domain.report import Report, ReportKind, ReportStatus
from interview_evidence.reporting.domain.review import (
    Decision,
    HumanReview,
    ReviewType,
)
from interview_evidence.shared.tenant import ActorType
from pydantic import ValidationError

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")


def test_ai_original_is_immutable_and_human_reviews_are_append_only() -> None:
    report = Report(
        report_id=UUID("00000000-0000-7000-8000-000000000002"),
        company_id=COMPANY_ID,
        interview_session_id=UUID("00000000-0000-7000-8000-000000000003"),
        invitation_id=UUID("00000000-0000-7000-8000-000000000004"),
        version=1,
        kind=ReportKind.AI_ORIGINAL,
        model_version="model-v1",
        prompt_version="prompt-v1",
        config_version="config-v1",
        status=ReportStatus.READY,
        summary="AI 원본 요약",
        created_at=NOW,
    )
    with pytest.raises(AttributeError):
        report.summary = "수정된 요약"  # type: ignore[misc]

    review = HumanReview.assessment_override(
        human_review_id=UUID("00000000-0000-7000-8000-000000000005"),
        company_id=COMPANY_ID,
        report_id=report.report_id,
        company_user_id=UUID("00000000-0000-7000-8000-000000000006"),
        report_item_id=UUID("00000000-0000-7000-8000-000000000007"),
        assessment_state="needs_follow_up",
        reason="답변의 구체성이 부족하다.",
        created_at=NOW,
    )
    assert review.review_type is ReviewType.ASSESSMENT_OVERRIDE
    assert review.reason


def test_only_company_user_can_author_final_decision() -> None:
    with pytest.raises(PermissionError, match="human company user"):
        HumanReview.final_decision(
            human_review_id=UUID("00000000-0000-7000-8000-000000000008"),
            company_id=COMPANY_ID,
            report_id=UUID("00000000-0000-7000-8000-000000000002"),
            company_user_id=UUID("00000000-0000-7000-8000-000000000006"),
            invitation_id=UUID("00000000-0000-7000-8000-000000000004"),
            actor_type=ActorType.SYSTEM,
            decision=Decision.ADVANCE,
            reason="AI가 추천했다.",
            created_at=NOW,
        )


def test_requirement_override_is_a_separate_append_only_review() -> None:
    requirement_assessment_id = UUID("00000000-0000-7000-8000-000000000009")

    review = HumanReview.requirement_override(
        human_review_id=UUID("00000000-0000-7000-8000-000000000010"),
        company_id=COMPANY_ID,
        report_id=UUID("00000000-0000-7000-8000-000000000002"),
        company_user_id=UUID("00000000-0000-7000-8000-000000000006"),
        requirement_assessment_id=requirement_assessment_id,
        requirement_status="partially_met",
        reason="자료에는 관련 경험이 있으나 직접 수행 범위는 추가 확인이 필요합니다.",
        created_at=NOW,
    )

    assert review.review_type is ReviewType.REQUIREMENT_OVERRIDE
    assert review.target_id == requirement_assessment_id
    assert review.value == {"requirement_status": "partially_met"}


def test_new_review_artifacts_only_accept_notes() -> None:
    note = ReviewArtifactCreate(
        review_type="note",
        target_id=UUID("00000000-0000-7000-8000-000000000004"),
        value="채용팀과 공유할 메모",
    )
    assert note.review_type == "note"

    with pytest.raises(ValidationError):
        ReviewArtifactCreate(
            review_type="bookmark",  # type: ignore[arg-type]
            target_id=UUID("00000000-0000-7000-8000-000000000004"),
            value="더 이상 생성할 수 없음",
        )
