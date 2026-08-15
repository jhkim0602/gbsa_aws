from datetime import UTC, datetime
from uuid import UUID

import pytest
from interview_evidence.integration.reporting_company import ReportingCompanyBoundary
from interview_evidence.reporting.application.deletion_service import DeletionService
from interview_evidence.reporting.application.public import ReportingPublic
from interview_evidence.reporting.application.review_service import ReviewService
from interview_evidence.reporting.domain.deletion import DeletionTarget
from interview_evidence.reporting.domain.report import (
    Report,
    ReportKind,
    ReportStatus,
)
from interview_evidence.reporting.domain.review import Decision
from interview_evidence.reporting.repositories.postgres import InMemoryReportingRepository
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
OTHER_COMPANY_ID = UUID("00000000-0000-7000-8000-000000000002")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000003")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000004")
REPORT_ID = UUID("00000000-0000-7000-8000-000000000005")


def context(company_id: UUID = COMPANY_ID) -> TenantContext:
    return TenantContext(
        company_id=company_id,
        actor_type=ActorType.COMPANY_USER,
        actor_id=UUID("00000000-0000-7000-8000-000000000006"),
        request_id=UUID("00000000-0000-7000-8000-000000000007"),
        trace_id="cross-d-to-a",
    )


def build_boundary() -> tuple[
    ReportingCompanyBoundary,
    DeletionService,
    InMemoryReportingRepository,
]:
    repository = InMemoryReportingRepository()
    repository.save_report(
        context(),
        Report(
            report_id=REPORT_ID,
            company_id=COMPANY_ID,
            interview_session_id=SESSION_ID,
            invitation_id=INVITATION_ID,
            version=1,
            kind=ReportKind.AI_ORIGINAL,
            model_version="model-v1",
            prompt_version="prompt-v1",
            config_version="report-config-v1",
            status=ReportStatus.READY,
            summary="실제 답변 Evidence에 기반한 원본 리포트",
            created_at=NOW,
        ),
    )
    ReviewService(repository).record_final_decision(
        context(),
        report_id=REPORT_ID,
        invitation_id=INVITATION_ID,
        decision=Decision.HOLD,
        reason="사람 면접에서 추가 확인한다.",
        occurred_at=NOW,
    )
    deletion_target = DeletionTarget.pending(
        target_id=UUID("00000000-0000-7000-8000-000000000008"),
        owner_lane="D",
        store="aurora",
        target_type="report",
        resource_id=str(REPORT_ID),
    )
    deletion_service = DeletionService(
        repository,
        enumerators=(lambda _context, _scope, _id: (deletion_target,),),
        executors={"D": lambda _context, _target: True},
    )
    public = ReportingPublic(
        repository=repository,
        deletion_service=deletion_service,
    )
    return ReportingCompanyBoundary(public), deletion_service, repository


def test_lane_a_uses_real_report_and_human_decision_projection() -> None:
    boundary, _, _ = build_boundary()

    projection = boundary.get_invitation_review(
        context(),
        invitation_id=INVITATION_ID,
    )

    assert projection is not None
    assert projection.interview_session_id == SESSION_ID
    assert projection.report_id == REPORT_ID
    assert projection.report_status == "ready"
    assert projection.human_decision_status == "hold"


def test_lane_a_uses_real_deletion_projection_without_cross_tenant_leakage() -> None:
    boundary, deletion_service, _ = build_boundary()
    request, _ = deletion_service.request(
        context(),
        scope_type="invitation",
        scope_id=INVITATION_ID,
        reason="지원자 삭제 요청",
        policy_snapshot={"retention_days": 180},
        occurred_at=NOW,
    )
    deletion_service.execute(
        context(),
        request_id=request.deletion_request_id,
        occurred_at=NOW,
    )

    projection = boundary.get_deletion_progress(
        context(),
        deletion_request_id=request.deletion_request_id,
    )
    assert projection.status == "completed"
    assert projection.expected_targets == 1
    assert projection.verified_targets == 1

    with pytest.raises(LookupError):
        boundary.get_deletion_progress(
            context(OTHER_COMPANY_ID),
            deletion_request_id=request.deletion_request_id,
        )
