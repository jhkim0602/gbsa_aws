from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from interview_evidence.shared.tenant import TenantContext


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
