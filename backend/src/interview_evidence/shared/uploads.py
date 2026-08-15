from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from interview_evidence.shared.tenant import TenantContext, require_tenant_context


@dataclass(frozen=True, slots=True)
class StoredUploadIntent:
    upload_id: UUID
    company_id: UUID
    invitation_id: UUID
    applicant_id: UUID
    source_type: str
    original_filename: str
    media_type: str
    byte_size: int
    sha256: str
    object_key: str
    method: str
    url: str
    required_headers: dict[str, str]
    expires_at: datetime


class UploadIntentStore(Protocol):
    def save(self, intent: StoredUploadIntent) -> None: ...

    def get(
        self,
        context: TenantContext,
        upload_id: UUID,
        applicant_id: UUID,
    ) -> StoredUploadIntent | None: ...

    def delete(self, context: TenantContext, object_key: str) -> bool: ...


class InMemoryUploadIntentStore:
    def __init__(self) -> None:
        self._intents: dict[UUID, StoredUploadIntent] = {}

    def save(self, intent: StoredUploadIntent) -> None:
        self._intents[intent.upload_id] = intent

    def get(
        self,
        context: TenantContext,
        upload_id: UUID,
        applicant_id: UUID,
    ) -> StoredUploadIntent | None:
        tenant = require_tenant_context(context)
        intent = self._intents.get(upload_id)
        if (
            intent is None
            or intent.company_id != tenant.company_id
            or intent.applicant_id != applicant_id
        ):
            return None
        return intent

    def delete(self, context: TenantContext, object_key: str) -> bool:
        tenant = require_tenant_context(context)
        matches = [
            upload_id
            for upload_id, intent in self._intents.items()
            if intent.company_id == tenant.company_id and intent.object_key == object_key
        ]
        for upload_id in matches:
            self._intents.pop(upload_id, None)
        return not any(
            intent.company_id == tenant.company_id and intent.object_key == object_key
            for intent in self._intents.values()
        )
