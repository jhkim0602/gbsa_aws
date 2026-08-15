from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.interview_engine.adapters.recent_context import (
    DynamoRecentContext,
    RecentContextSnapshot,
)
from interview_evidence.shared.tenant import ActorType, TenantContext

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=UUID("00000000-0000-7000-8000-000000000003"),
        request_id=UUID("00000000-0000-7000-8000-000000000004"),
        trace_id="trace-dynamo-hot-view",
    )


class FakeDynamoClient:
    def __init__(self) -> None:
        self.items: dict[tuple[str, str], dict[str, dict[str, str]]] = {}

    def put_item(
        self,
        *,
        TableName: str,
        Item: dict[str, dict[str, str]],
        ConditionExpression: str | None = None,
    ) -> dict[str, object]:
        del ConditionExpression
        key = (Item["PK"]["S"], Item["SK"]["S"])
        self.items[key] = Item
        return {}

    def get_item(
        self,
        *,
        TableName: str,
        Key: dict[str, dict[str, str]],
        ConsistentRead: bool,
    ) -> dict[str, object]:
        del TableName, ConsistentRead
        item = self.items.get((Key["PK"]["S"], Key["SK"]["S"]))
        return {} if item is None else {"Item": item}

    def delete_item(
        self,
        *,
        TableName: str,
        Key: dict[str, dict[str, str]],
    ) -> dict[str, object]:
        del TableName
        self.items.pop((Key["PK"]["S"], Key["SK"]["S"]), None)
        return {}


def test_dynamo_adapter_round_trips_tenant_scoped_snapshot() -> None:
    client = FakeDynamoClient()
    adapter = DynamoRecentContext(client, table_name="interview-hot-view")
    snapshot = RecentContextSnapshot(
        company_id=COMPANY_ID,
        interview_session_id=SESSION_ID,
        session_sequence=4,
        checkpoint_id=UUID("00000000-0000-7000-8000-000000000005"),
        last_final_turn_id=UUID("00000000-0000-7000-8000-000000000006"),
        pending_turn_id=None,
        last_media_chunk_sequence=2,
        last_reconciled_event_id=UUID("00000000-0000-7000-8000-000000000007"),
        expires_at=datetime(2026, 8, 22, 9, 0, tzinfo=UTC),
    )

    adapter.put(context(), snapshot)
    restored = adapter.get(context(), SESSION_ID)

    assert restored == snapshot
    item = client.items[(f"SESSION#{SESSION_ID}", "META")]
    assert item["company_id"]["S"] == str(COMPANY_ID)
    assert item["schema_version"]["N"] == "1"

    adapter.delete(context(), SESSION_ID)
    assert adapter.get(context(), SESSION_ID) is None
