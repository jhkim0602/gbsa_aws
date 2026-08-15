from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from interview_evidence.shared.aws_clients.ports import ObjectStorage
from interview_evidence.shared.ids import Clock, SystemClock
from interview_evidence.shared.tenant import TenantContext
from interview_evidence.shared.uploads import (
    InMemoryUploadIntentStore,
    StoredUploadIntent,
    UploadIntentStore,
)


class UploadIntentNotFound(PermissionError):
    """Raised without revealing another applicant's upload intent."""


@dataclass(frozen=True, slots=True)
class ScopedUploadIntent:
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


class ScopedSubmissionStorage:
    def __init__(
        self,
        storage: ObjectStorage,
        *,
        clock: Clock | None = None,
        upload_ttl: timedelta = timedelta(minutes=15),
        intent_store: UploadIntentStore | None = None,
    ) -> None:
        self._storage = storage
        self._clock = clock or SystemClock()
        self._upload_ttl = upload_ttl
        self._intent_store = intent_store or InMemoryUploadIntentStore()

    def create_upload_intent(
        self,
        context: TenantContext,
        *,
        invitation_id: UUID,
        applicant_id: UUID,
        source_type: str,
        filename: str,
        media_type: str,
        byte_size: int,
        sha256: str,
    ) -> ScopedUploadIntent:
        namespace = f"submission-original/{applicant_id}"
        base = self._storage.create_upload_intent(
            context,
            namespace,
            byte_size,
            sha256,
        )
        intent = ScopedUploadIntent(
            upload_id=base.object_id,
            company_id=context.company_id,
            invitation_id=invitation_id,
            applicant_id=applicant_id,
            source_type=source_type,
            original_filename=filename,
            media_type=media_type,
            byte_size=byte_size,
            sha256=sha256,
            object_key=base.object_key,
            method="PUT",
            url=base.url,
            required_headers={
                **base.required_headers,
                "content-type": media_type,
            },
            expires_at=self._clock.now() + self._upload_ttl,
        )
        self._intent_store.save(
            StoredUploadIntent(
                upload_id=intent.upload_id,
                company_id=intent.company_id,
                invitation_id=intent.invitation_id,
                applicant_id=intent.applicant_id,
                source_type=intent.source_type,
                original_filename=intent.original_filename,
                media_type=intent.media_type,
                byte_size=intent.byte_size,
                sha256=intent.sha256,
                object_key=intent.object_key,
                method=intent.method,
                url=intent.url,
                required_headers=intent.required_headers,
                expires_at=intent.expires_at,
            )
        )
        return intent

    def resolve(
        self,
        context: TenantContext,
        *,
        upload_id: UUID,
        applicant_id: UUID,
    ) -> ScopedUploadIntent:
        intent = self._intent_store.get(context, upload_id, applicant_id)
        if intent is None or self._clock.now() >= intent.expires_at:
            raise UploadIntentNotFound("upload intent not found")
        return ScopedUploadIntent(
            upload_id=intent.upload_id,
            company_id=intent.company_id,
            invitation_id=intent.invitation_id,
            applicant_id=intent.applicant_id,
            source_type=intent.source_type,
            original_filename=intent.original_filename,
            media_type=intent.media_type,
            byte_size=intent.byte_size,
            sha256=intent.sha256,
            object_key=intent.object_key,
            method=intent.method,
            url=intent.url,
            required_headers=intent.required_headers,
            expires_at=intent.expires_at,
        )

    def delete_object_key(self, context: TenantContext, object_key: str) -> bool:
        return self._intent_store.delete(context, object_key)
