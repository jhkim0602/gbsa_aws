from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.reporting.application.review_service import ReviewService
from interview_evidence.reporting.domain.report import Report, ReportKind, ReportStatus
from interview_evidence.reporting.domain.review import Decision
from interview_evidence.reporting.repositories.postgres import (
    InMemoryReportingRepository,
)
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
REPORT_ID = UUID("00000000-0000-7000-8000-000000000002")


def context(actor_type: ActorType) -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=actor_type,
        actor_id=UUID("00000000-0000-7000-8000-000000000003"),
        request_id=UUID("00000000-0000-7000-8000-000000000004"),
        trace_id="trace-human-decision",
    )


def test_ai_or_system_role_cannot_record_final_decision() -> None:
    repository = InMemoryReportingRepository()
    repository.save_report(
        context(ActorType.SYSTEM),
        Report(
            report_id=REPORT_ID,
            company_id=COMPANY_ID,
            interview_session_id=UUID("00000000-0000-7000-8000-000000000005"),
            invitation_id=UUID("00000000-0000-7000-8000-000000000006"),
            version=1,
            kind=ReportKind.AI_ORIGINAL,
            model_version="model-v1",
            prompt_version="prompt-v1",
            config_version="config-v1",
            status=ReportStatus.READY,
            summary="원본",
            created_at=NOW,
        ),
    )
    service = ReviewService(repository)
    with pytest.raises(PermissionError, match="human company user"):
        service.record_final_decision(
            context(ActorType.SYSTEM),
            report_id=REPORT_ID,
            invitation_id=UUID("00000000-0000-7000-8000-000000000006"),
            decision=Decision.ADVANCE,
            reason="AI 판단",
            occurred_at=NOW,
        )
