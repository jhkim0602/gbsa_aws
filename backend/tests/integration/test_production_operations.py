from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
from interview_evidence.integration.production_deletion import (
    ProductionInterviewTargetDeleter,
    ProductionSubmissionTargetDeleter,
)
from interview_evidence.interview_engine.application.deletion_targets import (
    InterviewDeletionTarget,
)
from interview_evidence.main import create_app
from interview_evidence.shared.ids import CommandMeta, FrozenClock
from interview_evidence.shared.operations import (
    CloudWatchMetricRecorder,
    DependencyReadiness,
    InMemoryMetricRecorder,
)
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.application.deletion_targets import (
    SubmissionDeletionTarget,
)

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
ACTOR_ID = UUID("00000000-0000-7000-8000-000000000002")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000003")
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=ACTOR_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000004"),
        trace_id="production-operations",
    )


class ObjectVerifier:
    def __init__(self, *, verified: bool) -> None:
        self.verified = verified
        self.keys: list[str] = []

    def delete_and_verify_object(self, context: TenantContext, object_key: str) -> bool:
        context.assert_company(COMPANY_ID)
        self.keys.append(object_key)
        return self.verified


class SearchVerifier:
    def __init__(self, *, verified: bool) -> None:
        self.verified = verified
        self.ids: list[str] = []

    def delete_and_verify(self, context: TenantContext, document_id: str) -> bool:
        context.assert_company(COMPANY_ID)
        self.ids.append(document_id)
        return self.verified


class RepositoryVerifier:
    def delete_and_verify_target(
        self,
        context: TenantContext,
        *,
        resource_type: str,
        resource_id: UUID,
    ) -> bool:
        context.assert_company(COMPANY_ID)
        return resource_type == "submission" and resource_id == ACTOR_ID


class HotViewVerifier:
    def __init__(self) -> None:
        self.deleted: list[UUID] = []

    def delete(self, context: TenantContext, session_id: UUID) -> None:
        context.assert_company(COMPANY_ID)
        self.deleted.append(session_id)

    def get(self, context: TenantContext, session_id: UUID) -> None:
        context.assert_company(COMPANY_ID)
        assert session_id in self.deleted
        return None


def test_production_deleters_require_verified_absence_and_record_metrics() -> None:
    metrics = InMemoryMetricRecorder()
    object_store = ObjectVerifier(verified=False)
    search = SearchVerifier(verified=True)
    submission = ProductionSubmissionTargetDeleter(
        repository=RepositoryVerifier(),
        object_storage=object_store,
        search_index=search,
        metrics=metrics,
    )
    s3_receipt = submission.delete_and_verify(
        _context(),
        SubmissionDeletionTarget(
            company_id=COMPANY_ID,
            owner_lane="B",
            store="s3",
            resource_type="submission_original",
            resource_id=f"tenants/{COMPANY_ID}/submission-original/object-1",
        ),
        CommandMeta.create("delete-submission-object-1", clock=FrozenClock(NOW)),
    )
    search_receipt = submission.delete_and_verify(
        _context(),
        SubmissionDeletionTarget(
            company_id=COMPANY_ID,
            owner_lane="B",
            store="opensearch",
            resource_type="submission_chunk_index",
            resource_id="chunk-index-1",
        ),
        CommandMeta.create("delete-submission-index-1", clock=FrozenClock(NOW)),
    )

    interview = ProductionInterviewTargetDeleter(
        repository=RepositoryVerifier(),
        object_storage=ObjectVerifier(verified=True),
        hot_view=HotViewVerifier(),
        metrics=metrics,
    )
    dynamo_receipt = interview.delete_and_verify(
        _context(),
        InterviewDeletionTarget(
            company_id=COMPANY_ID,
            owner_lane="C",
            store="dynamodb",
            resource_type="interview_hot_view",
            resource_id=f"SESSION#{SESSION_ID}",
        ),
        CommandMeta.create("delete-interview-hot-view", clock=FrozenClock(NOW)),
    )

    assert s3_receipt.verified_absent is False
    assert search_receipt.verified_absent is True
    assert dynamo_receipt.verified_absent is True
    assert [(item.name, item.dimensions["outcome"]) for item in metrics.records] == [
        ("privacy_deletion_target", "retrying"),
        ("privacy_deletion_target", "verified_absent"),
        ("privacy_deletion_target", "verified_absent"),
    ]


@dataclass
class Probe:
    healthy: bool

    def check(self) -> None:
        if not self.healthy:
            raise ConnectionError("credential-bearing dependency failure")


@pytest.mark.anyio
async def test_readiness_returns_dependency_status_without_error_details() -> None:
    readiness = DependencyReadiness(
        {
            "database": Probe(healthy=True).check,
            "analysis_queue": Probe(healthy=False).check,
        }
    )
    app = create_app(readiness=readiness)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "dependencies": {
            "analysis_queue": "unavailable",
            "database": "ok",
        },
    }
    assert "credential" not in response.text


def test_operational_metrics_reject_tenant_or_applicant_dimensions() -> None:
    metrics = InMemoryMetricRecorder()
    metrics.record(
        "pipeline_stage_latency_ms",
        12.5,
        unit="Milliseconds",
        dimensions={"stage": "retrieval", "config_version": "retrieval-v1"},
    )
    metrics.record(
        "queue_depth",
        3,
        unit="Count",
        dimensions={"queue": "analysis"},
    )

    with pytest.raises(ValueError, match="metric dimension is not allowed"):
        metrics.record(
            "queue_depth",
            1,
            unit="Count",
            dimensions={"company_id": str(COMPANY_ID)},
        )

    assert [item.name for item in metrics.records] == [
        "pipeline_stage_latency_ms",
        "queue_depth",
    ]


class CloudWatchClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def put_metric_data(self, **kwargs: object) -> Mapping[str, object]:
        self.calls.append(dict(kwargs))
        return {}


def test_cloudwatch_metrics_use_only_safe_low_cardinality_dimensions() -> None:
    client = CloudWatchClient()
    metrics = CloudWatchMetricRecorder(
        client,
        namespace="InterviewEvidencePlatform",
    )

    metrics.record(
        "pipeline_stage_latency_ms",
        42,
        unit="Milliseconds",
        dimensions={
            "stage": "question_generation",
            "config_version": "question-v1",
        },
    )

    assert client.calls == [
        {
            "Namespace": "InterviewEvidencePlatform",
            "MetricData": [
                {
                    "MetricName": "pipeline_stage_latency_ms",
                    "Value": 42.0,
                    "Unit": "Milliseconds",
                    "Dimensions": [
                        {"Name": "config_version", "Value": "question-v1"},
                        {"Name": "stage", "Value": "question_generation"},
                    ],
                }
            ],
        }
    ]
