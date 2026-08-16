from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from interview_evidence.shared.idempotency import (
    InMemoryResourceIdempotencyStore,
    ResourceIdempotencyStore,
)
from interview_evidence.shared.ids import Clock, new_uuid7
from interview_evidence.shared.messaging.outbox import Outbox, OutboxEvent
from interview_evidence.shared.security.principals import ApplicantPrincipal
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.submission_analysis.adapters.object_storage import (
    ScopedSubmissionStorage,
    ScopedUploadIntent,
)
from interview_evidence.submission_analysis.application.submission_validator import (
    SubmissionValidator,
)
from interview_evidence.submission_analysis.domain.submission import (
    SourceType,
    Submission,
    SubmissionStatus,
)
from interview_evidence.submission_analysis.repositories.postgres import (
    SubmissionRepository,
)

MAX_PUBLIC_GIT_PROJECTS = 3


@dataclass(frozen=True, slots=True)
class AnalysisReadiness:
    overall_status: str
    submissions: tuple[Submission, ...]
    interview_ready: bool
    strategy_id: UUID | None = None
    strategy_version: int | None = None
    impact_summary: str | None = None


class SubmissionService:
    def __init__(
        self,
        repository: SubmissionRepository,
        storage: ScopedSubmissionStorage,
        validator: SubmissionValidator,
        outbox: Outbox,
        clock: Clock,
        idempotency: ResourceIdempotencyStore | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._validator = validator
        self._outbox = outbox
        self._clock = clock
        self._idempotency = idempotency or InMemoryResourceIdempotencyStore()

    def create_upload_intent(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        *,
        source_type: SourceType,
        filename: str,
        media_type: str,
        byte_size: int,
        sha256: str,
    ) -> ScopedUploadIntent:
        self._validator.validate_file(
            source_type=source_type,
            filename=filename,
            media_type=media_type,
            byte_size=byte_size,
            content_hash=sha256,
        )
        return self._storage.create_upload_intent(
            context,
            invitation_id=principal.invitation_id,
            applicant_id=principal.applicant_id,
            source_type=source_type.value,
            filename=filename,
            media_type=media_type,
            byte_size=byte_size,
            sha256=sha256,
        )

    def register_file_submission(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        *,
        source_type: SourceType,
        upload_id: UUID,
        idempotency_key: str,
    ) -> Submission:
        existing = self._idempotency.get(
            context,
            operation="submission.register_file",
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            return self._repository.get_submission(context, existing)
        intent = self._storage.resolve(
            context,
            upload_id=upload_id,
            applicant_id=principal.applicant_id,
        )
        if intent.source_type != source_type.value:
            raise ValueError("upload source type mismatch")
        submission = Submission(
            submission_id=new_uuid7(self._clock.now()),
            company_id=context.company_id,
            invitation_id=principal.invitation_id,
            applicant_id=principal.applicant_id,
            source_type=source_type,
            source_uri=intent.object_key,
            original_filename=intent.original_filename,
            content_hash=intent.sha256,
            byte_size=intent.byte_size,
            media_type=intent.media_type,
            created_at=self._clock.now(),
        )
        return self._persist_requested(context, submission, idempotency_key)

    def register_public_submission(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
        *,
        source_type: SourceType,
        public_url: str,
        candidate_identity_inputs: dict[str, object] | None,
        idempotency_key: str,
    ) -> Submission:
        existing = self._idempotency.get(
            context,
            operation="submission.register_public",
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            return self._repository.get_submission(context, existing)
        validated_url = self._validator.validate_public_url(
            source_type=source_type,
            public_url=public_url,
        )
        if source_type is SourceType.PUBLIC_GIT:
            existing_projects = tuple(
                submission
                for submission in self._repository.list_submissions(
                    context,
                    principal.applicant_id,
                )
                if submission.invitation_id == principal.invitation_id
                and submission.source_type is SourceType.PUBLIC_GIT
                and submission.status is not SubmissionStatus.DELETED
            )
            if len(existing_projects) >= MAX_PUBLIC_GIT_PROJECTS:
                raise ValueError("up to 3 public Git project URLs are allowed")
        submission = Submission(
            submission_id=new_uuid7(self._clock.now()),
            company_id=context.company_id,
            invitation_id=principal.invitation_id,
            applicant_id=principal.applicant_id,
            source_type=source_type,
            source_uri=validated_url,
            candidate_identity_inputs=_normalize_candidate_identity_inputs(
                candidate_identity_inputs
            ),
            created_at=self._clock.now(),
        )
        return self._persist_requested(context, submission, idempotency_key)

    def list_submissions(
        self,
        context: TenantContext,
        applicant_id: UUID,
    ) -> tuple[Submission, ...]:
        return self._repository.list_submissions(context, applicant_id)

    def readiness(
        self,
        context: TenantContext,
        principal: ApplicantPrincipal,
    ) -> AnalysisReadiness:
        submissions = self.list_submissions(context, principal.applicant_id)
        strategy = self._repository.latest_strategy(context, principal.invitation_id)
        if not submissions:
            overall = "waiting"
        elif any(item.status is SubmissionStatus.ANALYZING for item in submissions):
            overall = "analyzing"
        elif any(item.status is SubmissionStatus.PARTIAL for item in submissions):
            overall = "partial"
        elif all(item.status is SubmissionStatus.READY for item in submissions):
            overall = "ready"
        elif all(item.status is SubmissionStatus.FAILED for item in submissions):
            overall = "failed"
        else:
            overall = "waiting"
        impacts = [item.impact_summary for item in submissions if item.impact_summary]
        return AnalysisReadiness(
            overall_status=overall,
            submissions=submissions,
            interview_ready=strategy is not None and strategy.status.value in {"ready", "partial"},
            strategy_id=(strategy.interview_strategy_id if strategy is not None else None),
            strategy_version=(strategy.strategy_version if strategy is not None else None),
            impact_summary="; ".join(impacts) or None,
        )

    def _persist_requested(
        self,
        context: TenantContext,
        submission: Submission,
        idempotency_key: str,
    ) -> Submission:
        self._repository.save_submission(context, submission)
        operation = (
            "submission.register_public"
            if submission.source_type is SourceType.PUBLIC_GIT
            else "submission.register_file"
        )
        self._idempotency.put(
            context,
            operation=operation,
            idempotency_key=idempotency_key,
            resource_id=submission.submission_id,
        )
        self._outbox.append(
            OutboxEvent(
                outbox_event_id=new_uuid7(self._clock.now()),
                company_id=context.company_id,
                aggregate_type="submission",
                aggregate_id=submission.submission_id,
                aggregate_version=submission.row_version,
                event_type="submission.analysis_requested",
                event_version=1,
                payload={
                    "submission_id": str(submission.submission_id),
                    "analysis_version": 1,
                    "source_type": submission.source_type.value,
                    "source_object_id": str(submission.submission_id),
                    "limits_config_version": "analysis-limits-v1",
                },
                idempotency_key=f"analysis-request-{submission.submission_id}",
                trace_id=context.trace_id,
                occurred_at=self._clock.now(),
            )
        )
        return submission


def _normalize_candidate_identity_inputs(
    values: dict[str, object] | None,
) -> dict[str, tuple[str, ...]] | None:
    if values is None:
        return None
    normalized: dict[str, tuple[str, ...]] = {}
    for key, raw_values in values.items():
        if not isinstance(raw_values, list) or not all(
            isinstance(value, str) for value in raw_values
        ):
            raise ValueError("candidate identity inputs must be string arrays")
        normalized[key] = tuple(value.strip() for value in raw_values)
    return normalized
