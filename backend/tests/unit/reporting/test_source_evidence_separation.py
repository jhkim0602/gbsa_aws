from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.reporting.domain.report import Evidence, Sufficiency


def test_source_reference_cannot_be_promoted_to_evidence() -> None:
    with pytest.raises(TypeError, match="final applicant answer"):
        Evidence.from_source_reference(
            source_reference_id=UUID("00000000-0000-7000-8000-000000000001"),
            company_id=UUID("00000000-0000-7000-8000-000000000002"),
            report_item_id=UUID("00000000-0000-7000-8000-000000000003"),
            criterion_id=UUID("00000000-0000-7000-8000-000000000004"),
            competency_model_version_id=UUID("00000000-0000-7000-8000-000000000005"),
            observation="이력서에 기술이 적혀 있다.",
            rationale="질문 생성 출처일 뿐 실제 답변은 아니다.",
            sufficiency=Sufficiency.WEAK,
            generation_version="report-v1",
            created_at=datetime(2026, 8, 15, 9, 0, tzinfo=UTC),
        )
