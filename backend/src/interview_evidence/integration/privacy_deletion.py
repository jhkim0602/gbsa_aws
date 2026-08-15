from __future__ import annotations

from typing import Protocol, cast
from uuid import UUID

from interview_evidence.company_management.application.company_service import (
    CompanyManagementPublic,
)
from interview_evidence.company_management.application.deletion_targets import (
    CompanyDeletionTarget,
)
from interview_evidence.interview_engine.application.deletion_targets import (
    InterviewDeletionTarget,
)
from interview_evidence.interview_engine.application.public import InterviewEnginePublic
from interview_evidence.reporting.application.deletion_service import DeletionTargetSpec
from interview_evidence.reporting.application.public import ReportingPublic
from interview_evidence.shared.ids import Clock, CommandMeta
from interview_evidence.shared.operations import MetricRecorder, NullMetricRecorder
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.submission_analysis.application.deletion_targets import (
    SubmissionDeletionTarget,
)
from interview_evidence.submission_analysis.application.public import (
    SubmissionAnalysisPublic,
)


class ManifestTarget(Protocol):
    @property
    def owner_lane(self) -> str: ...

    @property
    def store(self) -> str: ...

    @property
    def target_type(self) -> str: ...

    @property
    def resource_id(self) -> str: ...


OwnedTarget = (
    CompanyDeletionTarget | SubmissionDeletionTarget | InterviewDeletionTarget | DeletionTargetSpec
)


class PrivacyDeletionBoundary:
    """Enumerate and execute privacy deletion through lane public interfaces."""

    def __init__(
        self,
        *,
        company: CompanyManagementPublic,
        submission: SubmissionAnalysisPublic,
        interview: InterviewEnginePublic,
        reporting: ReportingPublic,
        clock: Clock,
        object_storage: object | None = None,
        metrics: MetricRecorder | None = None,
    ) -> None:
        self._company = company
        self._submission = submission
        self._interview = interview
        self._reporting = reporting
        self._clock = clock
        self._object_storage = object_storage
        self._metrics = metrics or NullMetricRecorder()
        self._targets: dict[tuple[str, str, str, str], OwnedTarget] = {}

    @staticmethod
    def _key(target: ManifestTarget) -> tuple[str, str, str, str]:
        return (
            target.owner_lane,
            target.store,
            target.target_type,
            target.resource_id,
        )

    def enumerate(
        self,
        context: TenantContext,
        scope_type: str,
        scope_id: UUID,
    ) -> tuple[DeletionTargetSpec, ...]:
        if scope_type != "invitation":
            raise ValueError("local deletion composition currently requires invitation scope")
        invitation = self._company.authorize_invitation(
            context,
            scope_id,
            required_state="consented",
        )
        company_targets = self._company.enumerate_company_deletion_targets(
            context,
            invitation_id=scope_id,
            applicant_id=invitation.applicant_id,
        )
        submission_targets = self._submission.enumerate_submission_deletion_targets(
            context,
            invitation_id=scope_id,
            applicant_id=invitation.applicant_id,
        )
        review = self._reporting.get_review_projection(
            context,
            invitation_id=scope_id,
        )
        interview_targets = (
            self._interview.enumerate_interview_deletion_targets(
                context,
                session_id=review.interview_session_id,
            )
            if review is not None
            else ()
        )
        reporting_targets = self._reporting.enumerate_reporting_deletion_targets(
            context,
            invitation_id=scope_id,
        )
        owned: tuple[OwnedTarget, ...] = (
            *company_targets,
            *submission_targets,
            *interview_targets,
            *reporting_targets,
        )
        specs: list[DeletionTargetSpec] = []
        for target in owned:
            if isinstance(target, CompanyDeletionTarget):
                spec = DeletionTargetSpec(
                    owner_lane=target.owner_lane,
                    store=target.store,
                    target_type=target.resource_type,
                    resource_id=str(target.resource_id),
                )
            elif isinstance(target, SubmissionDeletionTarget | InterviewDeletionTarget):
                spec = DeletionTargetSpec(
                    owner_lane=target.owner_lane,
                    store=target.store,
                    target_type=target.resource_type,
                    resource_id=target.resource_id,
                )
            else:
                spec = target
            self._targets[self._key(spec)] = target
            specs.append(spec)
        return tuple(specs)

    def execute_company(self, context: TenantContext, target: object) -> bool:
        manifest_target = cast(ManifestTarget, target)
        owned = self._targets[self._key(manifest_target)]
        if not isinstance(owned, CompanyDeletionTarget):
            raise PermissionError("manifest target is not owned by Lane A")
        verified = self._company.delete_company_target(
            context,
            target=owned,
        ).verified_absent
        self._record(owned.store, verified)
        return verified

    def execute_submission(self, context: TenantContext, target: object) -> bool:
        manifest_target = cast(ManifestTarget, target)
        owned = self._targets[self._key(manifest_target)]
        if not isinstance(owned, SubmissionDeletionTarget):
            raise PermissionError("manifest target is not owned by Lane B")
        return self._submission.delete_submission_target(
            context,
            target=owned,
            meta=CommandMeta.create(
                f"privacy-delete-{manifest_target.resource_id}",
                clock=self._clock,
            ),
        ).verified_absent

    def execute_interview(self, context: TenantContext, target: object) -> bool:
        manifest_target = cast(ManifestTarget, target)
        owned = self._targets[self._key(manifest_target)]
        if not isinstance(owned, InterviewDeletionTarget):
            raise PermissionError("manifest target is not owned by Lane C")
        return self._interview.delete_interview_target(
            context,
            target=owned,
            meta=CommandMeta.create(
                f"privacy-delete-{manifest_target.resource_id}",
                clock=self._clock,
            ),
        ).verified_absent

    def execute_reporting(self, context: TenantContext, target: object) -> bool:
        manifest_target = cast(ManifestTarget, target)
        owned = self._targets[self._key(manifest_target)]
        if not isinstance(owned, DeletionTargetSpec):
            raise PermissionError("manifest target is not owned by Lane D")
        if owned.store == "s3" and self._object_storage is not None:
            delete_and_verify = getattr(
                self._object_storage,
                "delete_and_verify_object",
                None,
            )
            verified = bool(
                callable(delete_and_verify) and delete_and_verify(context, owned.resource_id)
            )
        else:
            verified = self._reporting.delete_reporting_target(
                context,
                target=owned,
            ).verified_absent
        self._record(owned.store, verified)
        return verified

    def _record(self, store: str, verified_absent: bool) -> None:
        self._metrics.record(
            "privacy_deletion_target",
            1,
            unit="Count",
            dimensions={
                "store": store,
                "outcome": "verified_absent" if verified_absent else "retrying",
            },
        )
