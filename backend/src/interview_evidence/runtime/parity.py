from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Protocol, cast
from uuid import UUID

import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]

from interview_evidence.interview_engine.adapters.recent_context import RecentContextSnapshot
from interview_evidence.runtime.local_production import (
    LOCAL_COMPANY_ID,
    LOCAL_COMPANY_USER_ID,
    create_local_aws_runtime_dependencies,
)
from interview_evidence.shared.aws_clients.ports import ObjectStorage
from interview_evidence.shared.database import RequestScopedDatabase
from interview_evidence.shared.ids import SystemClock, new_uuid7
from interview_evidence.shared.messaging.outbox import OutboxEvent
from interview_evidence.shared.persistence import SQLOutbox, SQLProcessedMessageStore
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.adapters.search import (
    SearchCandidate,
    SearchDocument,
    SearchIndex,
)

PARITY_POSITION_TITLE = "Local Production Parity Position"
PARITY_POSITION_IDEMPOTENCY_KEY = "local-production-parity-position-v1"
PARITY_APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000003")
PARITY_SOURCE_ID = UUID("00000000-0000-7000-8000-000000000004")
PARITY_SESSION_ID = UUID("00000000-0000-7000-8000-000000000005")
PARITY_CHECKPOINT_ID = UUID("00000000-0000-7000-8000-000000000006")


class VerifiableObjectStorage(ObjectStorage, Protocol):
    def delete_and_verify_object(
        self,
        context: TenantContext,
        object_key: str,
    ) -> bool: ...


class VerifiableSearchIndex(SearchIndex, Protocol):
    def delete_and_verify(
        self,
        context: TenantContext,
        document_id: str,
    ) -> bool: ...


def run_api_write(environment: Mapping[str, str]) -> dict[str, object]:
    status, _ = _request(
        "GET",
        "/v1/positions",
        token="invalid-local-token",
    )
    if status != 401:
        raise RuntimeError("invalid company credential was not rejected")
    status, body = _request(
        "POST",
        "/v1/positions",
        token=_required(environment, "LOCAL_COMPANY_TOKEN"),
        headers={"Idempotency-Key": PARITY_POSITION_IDEMPOTENCY_KEY},
        payload={
            "title": PARITY_POSITION_TITLE,
            "description": "PostgreSQL restart recovery verification",
        },
    )
    if status not in {200, 201}:
        raise RuntimeError(f"parity position creation failed with status {status}")
    return {
        "phase": "write",
        "status": "ok",
        "position_id": body["position_id"],
    }


def run_api_read(environment: Mapping[str, str]) -> dict[str, object]:
    status, body = _request(
        "GET",
        "/v1/positions",
        token=_required(environment, "LOCAL_COMPANY_TOKEN"),
    )
    if status != 200:
        raise RuntimeError(f"parity position lookup failed with status {status}")
    items = body.get("items")
    if not isinstance(items, list) or PARITY_POSITION_TITLE not in {
        str(item.get("title")) for item in items if isinstance(item, dict)
    }:
        raise RuntimeError("parity position was not recovered after restart")
    return {
        "phase": "read",
        "status": "ok",
        "position_count": len(items),
    }


def run_aws_adapters(environment: Mapping[str, str]) -> dict[str, object]:
    dependencies = create_local_aws_runtime_dependencies(environment)
    context = TenantContext(
        company_id=LOCAL_COMPANY_ID,
        actor_type=ActorType.COMPANY_USER,
        actor_id=LOCAL_COMPANY_USER_ID,
        request_id=UUID("00000000-0000-7000-8000-000000000007"),
        trace_id="local-production-parity",
    )

    storage = cast(VerifiableObjectStorage, dependencies.object_storage)
    intent = storage.create_upload_intent(
        context,
        "parity",
        6,
        "0" * 64,
    )
    if not intent.url.startswith(_required(environment, "S3_PUBLIC_ENDPOINT_URL")):
        raise RuntimeError("presigned upload URL is not browser reachable")
    s3 = boto3.client(
        "s3",
        region_name=_required(environment, "AWS_REGION"),
        endpoint_url=_required(environment, "AWS_ENDPOINT_URL"),
        config=Config(s3={"addressing_style": "path"}),
    )
    s3.put_object(
        Bucket=_required(environment, "SOURCE_BUCKET"),
        Key=intent.object_key,
        Body=b"parity",
    )
    if not storage.delete_and_verify_object(context, intent.object_key):
        raise RuntimeError("S3 deletion verification failed")

    hot_view = dependencies.recent_context
    snapshot = RecentContextSnapshot(
        company_id=context.company_id,
        interview_session_id=PARITY_SESSION_ID,
        session_sequence=3,
        checkpoint_id=PARITY_CHECKPOINT_ID,
        last_media_chunk_sequence=2,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    hot_view.put(context, snapshot)
    recovered = hot_view.get(context, PARITY_SESSION_ID)
    if recovered is None or recovered.session_sequence != 3:
        raise RuntimeError("DynamoDB hot-view round trip failed")
    hot_view.delete(context, PARITY_SESSION_ID)
    if hot_view.get(context, PARITY_SESSION_ID) is not None:
        raise RuntimeError("DynamoDB hot-view deletion failed")

    search = cast(VerifiableSearchIndex, dependencies.search_index)
    document_id = "local-production-parity-document"
    vector = tuple(1.0 if index == 0 else 0.0 for index in range(1024))
    search.add(
        SearchDocument(
            document_id=document_id,
            company_id=context.company_id,
            applicant_id=PARITY_APPLICANT_ID,
            source_id=PARITY_SOURCE_ID,
            text="local production parity exact symbol",
            vector=vector,
            symbols=("ParitySymbol",),
            locator={"page": 1},
            ownership_confidence=1.0,
        )
    )
    candidates = _wait_for_search_candidates(search, context, vector)
    if not any(candidate.document.document_id == document_id for candidate in candidates):
        raise RuntimeError("OpenSearch tenant-filtered retrieval failed")
    if not search.delete_and_verify(context, document_id):
        raise RuntimeError("OpenSearch deletion verification failed")

    queue_depths: dict[str, int] = {}
    for name, queue in dependencies.queues.items():
        queue.healthcheck()
        queue_depths[name] = queue.approximate_depth()
    return {
        "phase": "adapters",
        "status": "ok",
        "queues": queue_depths,
    }


def run_worker_roundtrip(environment: Mapping[str, str]) -> dict[str, object]:
    database = RequestScopedDatabase(_required(environment, "DATABASE_URL"))
    clock = SystemClock()
    occurred_at = clock.now()
    event_id = new_uuid7(occurred_at)
    probe_id = new_uuid7(occurred_at)
    token = database.begin_scope()
    try:
        SQLOutbox(database.session).append(
            OutboxEvent(
                outbox_event_id=event_id,
                company_id=LOCAL_COMPANY_ID,
                aggregate_type="system_parity",
                aggregate_id=probe_id,
                aggregate_version=1,
                event_type="system.parity_probe",
                event_version=1,
                payload={"probe_id": str(probe_id)},
                idempotency_key=f"local-worker-parity-{event_id}",
                trace_id=f"local-worker-parity-{event_id}",
                occurred_at=occurred_at,
            )
        )
        database.session.commit()
    finally:
        database.end_scope(token)

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        token = database.begin_scope()
        try:
            processed = SQLProcessedMessageStore(database.session).contains(
                consumer_name="analysis-worker",
                event_id=event_id,
                event_version=1,
            )
        finally:
            database.end_scope(token)
        if processed:
            return {
                "phase": "worker-roundtrip",
                "status": "ok",
                "event_id": str(event_id),
                "consumer": "analysis-worker",
            }
        time.sleep(0.25)
    raise TimeoutError("worker parity event was not processed")


def _wait_for_search_candidates(
    search: SearchIndex,
    context: TenantContext,
    vector: tuple[float, ...],
    *,
    attempts: int = 20,
    delay_seconds: float = 0.25,
) -> tuple[SearchCandidate, ...]:
    for attempt in range(attempts):
        candidates = search.candidates(
            context,
            applicant_id=PARITY_APPLICANT_ID,
            query="local production parity",
            query_vector=vector,
            exact_symbol="ParitySymbol",
        )
        if candidates:
            return candidates
        if attempt + 1 < attempts:
            time.sleep(delay_seconds)
    return ()


def _request(
    method: str,
    path: str,
    *,
    token: str,
    headers: Mapping[str, str] | None = None,
    payload: Mapping[str, object] | None = None,
) -> tuple[int, dict[str, object]]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:8080{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            **dict(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, _json_body(response.read())
    except urllib.error.HTTPError as error:
        return error.code, _json_body(error.read())


def _json_body(body: bytes) -> dict[str, object]:
    if not body:
        return {}
    try:
        decoded = json.loads(body)
    except json.JSONDecodeError:
        return {}
    return cast(dict[str, object], decoded) if isinstance(decoded, dict) else {}


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"required parity setting is missing: {name}")
    return value.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "phase",
        choices=("write", "read", "adapters", "worker-roundtrip"),
    )
    args = parser.parse_args()
    environment = dict(os.environ)
    runners = {
        "write": run_api_write,
        "read": run_api_read,
        "adapters": run_aws_adapters,
        "worker-roundtrip": run_worker_roundtrip,
    }
    print(json.dumps(runners[args.phase](environment), sort_keys=True))


if __name__ == "__main__":
    main()
