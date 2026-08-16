from __future__ import annotations

from typing import Protocol
from uuid import UUID

from interview_evidence.interview_engine.application.deletion_targets import (
    InterviewDeletionReceipt,
    InterviewDeletionTarget,
)
from interview_evidence.shared.ids import CommandMeta
from interview_evidence.shared.operations import MetricRecorder, NullMetricRecorder
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.submission_analysis.application.deletion_targets import (
    SubmissionDeletionReceipt,
    SubmissionDeletionTarget,
)


class RelationalTargetVerifier(Protocol):
    def delete_and_verify_target(
        self,
        context: TenantContext,
        *,
        resource_type: str,
        resource_id: UUID,
    ) -> bool: ...


class ObjectTargetVerifier(Protocol):
    def delete_and_verify_object(
        self,
        context: TenantContext,
        object_key: str,
    ) -> bool: ...


class SearchTargetVerifier(Protocol):
    def delete_and_verify(
        self,
        context: TenantContext,
        document_id: str,
    ) -> bool: ...


class HotViewTargetVerifier(Protocol):
    def delete(self, context: TenantContext, session_id: UUID) -> None: ...

    def get(self, context: TenantContext, session_id: UUID) -> object | None: ...


def _record_deletion(
    metrics: MetricRecorder,
    *,
    store: str,
    verified_absent: bool,
) -> None:
    metrics.record(
        "privacy_deletion_target",
        1,
        unit="Count",
        dimensions={
            "store": store,
            "outcome": "verified_absent" if verified_absent else "retrying",
        },
    )


class ProductionSubmissionTargetDeleter:
    def __init__(
        self,
        *,
        repository: RelationalTargetVerifier,
        object_storage: ObjectTargetVerifier,
        search_index: SearchTargetVerifier,
        metrics: MetricRecorder | None = None,
    ) -> None:
        self._repository = repository
        self._object_storage = object_storage
        self._search_index = search_index
        self._metrics = metrics or NullMetricRecorder()

    def delete_and_verify(
        self,
        context: TenantContext,
        target: SubmissionDeletionTarget,
        meta: CommandMeta,
    ) -> SubmissionDeletionReceipt:
        del meta
        context.assert_company(target.company_id)
        if target.owner_lane != "B":
            raise PermissionError("deletion target is not owned by Lane B")
        if target.store == "s3":
            verified = self._object_storage.delete_and_verify_object(
                context,
                target.resource_id,
            )
        elif target.store == "retrieval":
            verified = self._search_index.delete_and_verify(
                context,
                target.resource_id,
            )
        elif target.store == "aurora":
            verified = self._repository.delete_and_verify_target(
                context,
                resource_type=target.resource_type,
                resource_id=UUID(target.resource_id),
            )
        else:
            verified = False
        _record_deletion(self._metrics, store=target.store, verified_absent=verified)
        return SubmissionDeletionReceipt(
            company_id=context.company_id,
            resource_type=target.resource_type,
            resource_id=target.resource_id,
            store=target.store,
            verified_absent=verified,
        )


class ProductionInterviewTargetDeleter:
    def __init__(
        self,
        *,
        repository: RelationalTargetVerifier,
        object_storage: ObjectTargetVerifier,
        hot_view: HotViewTargetVerifier,
        metrics: MetricRecorder | None = None,
    ) -> None:
        self._repository = repository
        self._object_storage = object_storage
        self._hot_view = hot_view
        self._metrics = metrics or NullMetricRecorder()

    def delete_and_verify(
        self,
        context: TenantContext,
        target: InterviewDeletionTarget,
        meta: CommandMeta,
    ) -> InterviewDeletionReceipt:
        del meta
        context.assert_company(target.company_id)
        if target.owner_lane != "C":
            raise PermissionError("deletion target is not owned by Lane C")
        if target.store == "s3":
            verified = self._object_storage.delete_and_verify_object(
                context,
                target.resource_id,
            )
        elif target.store == "dynamodb":
            session_id = UUID(target.resource_id.removeprefix("SESSION#"))
            self._hot_view.delete(context, session_id)
            verified = self._hot_view.get(context, session_id) is None
        elif target.store == "aurora":
            verified = self._repository.delete_and_verify_target(
                context,
                resource_type=target.resource_type,
                resource_id=UUID(target.resource_id),
            )
        else:
            verified = False
        _record_deletion(self._metrics, store=target.store, verified_absent=verified)
        return InterviewDeletionReceipt(
            company_id=context.company_id,
            store=target.store,
            resource_type=target.resource_type,
            resource_id=target.resource_id,
            verified_absent=verified,
        )
