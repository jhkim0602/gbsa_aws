from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from interview_evidence.shared.tenant import TenantContext, require_tenant_context


class HotViewUnavailable(RuntimeError):
    pass


class RecentContextSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    company_id: UUID
    interview_session_id: UUID
    session_sequence: int = Field(ge=0)
    checkpoint_id: UUID
    last_final_turn_id: UUID | None = None
    pending_turn_id: UUID | None = None
    last_media_chunk_sequence: int = Field(ge=0)
    schema_version: int = Field(default=1, ge=1)
    last_reconciled_event_id: UUID | None = None
    expires_at: datetime


class RecentContextPort(Protocol):
    def get(self, context: TenantContext, session_id: UUID) -> RecentContextSnapshot | None: ...

    def put(
        self, context: TenantContext, snapshot: RecentContextSnapshot
    ) -> RecentContextSnapshot: ...

    def delete(self, context: TenantContext, session_id: UUID) -> None: ...


class InMemoryRecentContext:
    def __init__(self, *, fail_reads: bool = False, fail_writes: bool = False) -> None:
        self._items: dict[tuple[UUID, UUID], RecentContextSnapshot] = {}
        self.fail_reads = fail_reads
        self.fail_writes = fail_writes

    def get(self, context: TenantContext, session_id: UUID) -> RecentContextSnapshot | None:
        if self.fail_reads:
            raise HotViewUnavailable("recent context read unavailable")
        tenant = require_tenant_context(context)
        return self._items.get((tenant.company_id, session_id))

    def put(self, context: TenantContext, snapshot: RecentContextSnapshot) -> RecentContextSnapshot:
        if self.fail_writes:
            raise HotViewUnavailable("recent context write unavailable")
        tenant = require_tenant_context(context)
        tenant.assert_company(snapshot.company_id)
        self._items[(tenant.company_id, snapshot.interview_session_id)] = snapshot
        return snapshot

    def force_sequence(
        self,
        context: TenantContext,
        session_id: UUID,
        *,
        session_sequence: int,
    ) -> None:
        tenant = require_tenant_context(context)
        key = (tenant.company_id, session_id)
        current = self._items[key]
        self._items[key] = current.model_copy(update={"session_sequence": session_sequence})

    def delete(self, context: TenantContext, session_id: UUID) -> None:
        tenant = require_tenant_context(context)
        self._items.pop((tenant.company_id, session_id), None)

    def healthcheck(self) -> None:
        if self.fail_reads:
            raise HotViewUnavailable("recent context read unavailable")


class DynamoClient(Protocol):
    def put_item(
        self,
        *,
        TableName: str,
        Item: dict[str, dict[str, str]],
        ConditionExpression: str | None = None,
    ) -> dict[str, object]: ...

    def get_item(
        self,
        *,
        TableName: str,
        Key: dict[str, dict[str, str]],
        ConsistentRead: bool,
    ) -> dict[str, object]: ...

    def delete_item(
        self,
        *,
        TableName: str,
        Key: dict[str, dict[str, str]],
    ) -> dict[str, object]: ...

    def describe_table(self, *, TableName: str) -> dict[str, object]: ...


class DynamoRecentContext:
    def __init__(self, client: DynamoClient, *, table_name: str) -> None:
        self._client = client
        self._table_name = table_name

    def get(self, context: TenantContext, session_id: UUID) -> RecentContextSnapshot | None:
        tenant = require_tenant_context(context)
        try:
            response = self._client.get_item(
                TableName=self._table_name,
                Key=self._key(session_id),
                ConsistentRead=True,
            )
        except Exception as error:
            raise HotViewUnavailable("recent context read unavailable") from error
        raw_item = response.get("Item")
        if raw_item is None:
            return None
        item = cast(dict[str, dict[str, str]], raw_item)
        if item["company_id"]["S"] != str(tenant.company_id):
            return None
        return RecentContextSnapshot(
            company_id=UUID(item["company_id"]["S"]),
            interview_session_id=UUID(item["interview_session_id"]["S"]),
            session_sequence=int(item["session_sequence"]["N"]),
            checkpoint_id=UUID(item["checkpoint_id"]["S"]),
            last_final_turn_id=self._optional_uuid(item, "last_final_turn_id"),
            pending_turn_id=self._optional_uuid(item, "pending_turn_id"),
            last_media_chunk_sequence=int(item["last_media_chunk_sequence"]["N"]),
            schema_version=int(item["schema_version"]["N"]),
            last_reconciled_event_id=self._optional_uuid(item, "last_reconciled_event_id"),
            expires_at=datetime.fromtimestamp(int(item["ttl"]["N"]), tz=UTC),
        )

    def put(self, context: TenantContext, snapshot: RecentContextSnapshot) -> RecentContextSnapshot:
        tenant = require_tenant_context(context)
        tenant.assert_company(snapshot.company_id)
        item = {
            **self._key(snapshot.interview_session_id),
            "company_id": {"S": str(snapshot.company_id)},
            "interview_session_id": {"S": str(snapshot.interview_session_id)},
            "session_sequence": {"N": str(snapshot.session_sequence)},
            "checkpoint_id": {"S": str(snapshot.checkpoint_id)},
            "last_media_chunk_sequence": {"N": str(snapshot.last_media_chunk_sequence)},
            "schema_version": {"N": str(snapshot.schema_version)},
            "ttl": {"N": str(int(snapshot.expires_at.timestamp()))},
        }
        if snapshot.last_final_turn_id is not None:
            item["last_final_turn_id"] = {"S": str(snapshot.last_final_turn_id)}
        if snapshot.pending_turn_id is not None:
            item["pending_turn_id"] = {"S": str(snapshot.pending_turn_id)}
        if snapshot.last_reconciled_event_id is not None:
            item["last_reconciled_event_id"] = {"S": str(snapshot.last_reconciled_event_id)}
        try:
            self._client.put_item(TableName=self._table_name, Item=item)
        except Exception as error:
            raise HotViewUnavailable("recent context write unavailable") from error
        return snapshot

    def delete(self, context: TenantContext, session_id: UUID) -> None:
        require_tenant_context(context)
        try:
            self._client.delete_item(
                TableName=self._table_name,
                Key=self._key(session_id),
            )
        except Exception as error:
            raise HotViewUnavailable("recent context delete unavailable") from error

    def healthcheck(self) -> None:
        try:
            response = self._client.describe_table(TableName=self._table_name)
        except Exception as error:
            raise HotViewUnavailable("recent context unavailable") from error
        table = response.get("Table")
        if not isinstance(table, dict):
            raise HotViewUnavailable("recent context status is unavailable")
        status = table.get("TableStatus")
        if status not in {"ACTIVE", "UPDATING"}:
            raise HotViewUnavailable("recent context is not active")

    @staticmethod
    def _key(session_id: UUID) -> dict[str, dict[str, str]]:
        return {
            "PK": {"S": f"SESSION#{session_id}"},
            "SK": {"S": "META"},
        }

    @staticmethod
    def _optional_uuid(
        item: dict[str, dict[str, str]],
        key: str,
    ) -> UUID | None:
        value = item.get(key)
        return None if value is None else UUID(value["S"])
