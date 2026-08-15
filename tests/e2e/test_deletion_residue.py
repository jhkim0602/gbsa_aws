from typing import cast

import pytest
from interview_evidence.company_management.application.company_service import (
    CompanyManagementPublic,
)
from interview_evidence.company_management.repositories.postgres import (
    TenantScopedResourceNotFound,
)
from interview_evidence.integration.privacy_deletion import PrivacyDeletionBoundary
from interview_evidence.interview_engine.api import LaneCRuntime
from interview_evidence.interview_engine.repositories.postgres import (
    TenantScopedInterviewNotFound,
)
from interview_evidence.reporting.api.company_routes import LaneDRuntime
from interview_evidence.reporting.application.deletion_service import DeletionService
from interview_evidence.reporting.domain.deletion import DeletionTarget
from interview_evidence.reporting.repositories.postgres import TenantScopedReportingNotFound
from interview_evidence.shared.ids import Clock
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.submission_analysis.application.public import (
    SubmissionAnalysisPublic,
)

from tests.e2e.support import run_thin_journey


def test_full_store_deletion_retries_until_every_target_is_verified_absent() -> None:
    result = run_thin_journey()
    lane_d = cast(LaneDRuntime, result.runtime.lanes["reporting"])
    lane_c = cast(LaneCRuntime, result.runtime.lanes["interview_engine"])
    company = cast(
        CompanyManagementPublic,
        result.runtime.boundaries["company_management"],
    )
    submission = cast(
        SubmissionAnalysisPublic,
        result.runtime.boundaries["submission_analysis"],
    )
    privacy = cast(
        PrivacyDeletionBoundary,
        result.runtime.resources["privacy_deletion"],
    )
    clock = cast(Clock, result.runtime.resources["clock"])
    failed_once = False

    def submission_with_timeout(
        context: TenantContext,
        target: DeletionTarget,
    ) -> bool:
        nonlocal failed_once
        if target.store == "opensearch" and not failed_once:
            failed_once = True
            raise TimeoutError
        return privacy.execute_submission(context, target)

    deletion = DeletionService(
        lane_d.repository,
        enumerators=(privacy.enumerate,),
        executors={
            "A": privacy.execute_company,
            "B": submission_with_timeout,
            "C": privacy.execute_interview,
            "D": privacy.execute_reporting,
        },
    )
    request, manifest = deletion.request(
        result.company_context,
        scope_type="invitation",
        scope_id=result.invitation_id,
        reason="지원자 삭제 요청",
        policy_snapshot={"retention_days": 180},
        occurred_at=clock.now(),
    )

    stores = {target.store for target in manifest.targets}
    assert {"aurora", "dynamodb", "s3", "opensearch"} <= stores
    retrying = deletion.execute(
        result.company_context,
        request_id=request.deletion_request_id,
        occurred_at=clock.now(),
    )
    assert retrying.status.value == "retrying"
    assert sum(target.status.value == "retrying" for target in retrying.targets) == 1

    completed = deletion.execute(
        result.company_context,
        request_id=request.deletion_request_id,
        occurred_at=clock.now(),
    )
    assert completed.status.value == "completed"
    assert completed.verified_targets == len(completed.targets)

    with pytest.raises(TenantScopedResourceNotFound):
        company.authorize_invitation(
            result.company_context,
            result.invitation_id,
            required_state="consented",
        )
    assert (
        submission.get_analysis_status(
            result.company_context,
            invitation_id=result.invitation_id,
        ).submissions
        == ()
    )
    assert (
        submission.retrieve_context(
            result.company_context,
            applicant_id=result.applicant_id,
            query="결제 장애",
            query_vector=(1.0, 0.0),
            criterion_id=result.report_id,
            config_version="local-hybrid-v1",
            limit=5,
        )
        == ()
    )
    with pytest.raises(TenantScopedInterviewNotFound):
        lane_c.repository.get_session(result.company_context, result.session_id)
    assert lane_c.hot_view.get(result.company_context, result.session_id) is None
    with pytest.raises(TenantScopedReportingNotFound):
        lane_d.repository.get_report(result.company_context, result.report_id)
