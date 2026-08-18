from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from interview_evidence.reporting.domain.timeline import (
    RecordingAsset,
    RecordingStatus,
)
from interview_evidence.reporting.repositories.postgres import ReportingRepository
from interview_evidence.shared.ids import new_uuid7
from interview_evidence.shared.tenant import TenantContext, require_tenant_context


@dataclass(frozen=True, slots=True)
class RecordingChunkObject:
    sequence: int
    object_key: str


def assembled_recording_key(*, company_id: UUID, session_id: UUID) -> str:
    """Where the single playable recording of one session lives.

    Beside the chunks it is built from, under the layout the upload path already uses.
    Derived from the session rather than the attempt, so a retried media event overwrites
    its own output instead of orphaning it. Exposed as a function because the local seed
    writes the same object without running the worker, and a second copy of this f-string
    is how the review screen ended up asking the bucket for a key nothing had written.
    """
    return f"tenants/{company_id}/sessions/{session_id}/recording/recording.webm"


class MediaObjectStore(Protocol):
    def read_object(self, context: TenantContext, object_key: str) -> bytes: ...

    def write_object(
        self,
        context: TenantContext,
        *,
        object_key: str,
        body: bytes,
        content_type: str,
    ) -> None: ...


class RecordingAssembler:
    """Turns the verified chunks of one session into a single playable object.

    The applicant's recorder emits `MediaRecorder` output in timeslices, so the chunks
    concatenated in sequence order are the original stream. No transcode is involved,
    which is why this runs in the worker rather than through a managed media service.
    """

    def __init__(self, objects: MediaObjectStore) -> None:
        self._objects = objects

    def assemble(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        chunks: tuple[RecordingChunkObject, ...],
    ) -> str:
        tenant = require_tenant_context(context)
        if not chunks:
            raise ValueError("recording assembly requires at least one verified chunk")
        sequences = [chunk.sequence for chunk in chunks]
        if len(set(sequences)) != len(sequences):
            raise ValueError("recording chunks must have distinct sequence numbers")
        prefix = f"tenants/{tenant.company_id}/"
        # Chunks arrive under either prefix the bucket uses, matching the storage
        # adapter's own scope check; the assembled object always goes under `tenants/`.
        allowed_prefixes = (prefix, f"companies/{tenant.company_id}/")
        for chunk in chunks:
            if not chunk.object_key.startswith(allowed_prefixes):
                raise PermissionError("recording chunk is outside the tenant scope")
        ordered = sorted(chunks, key=lambda chunk: chunk.sequence)
        # Held in memory because the manifest already hashes every chunk to decide the
        # asset status, so the whole recording is read in this job either way.
        body = b"".join(self._objects.read_object(context, chunk.object_key) for chunk in ordered)
        object_key = assembled_recording_key(
            company_id=tenant.company_id,
            session_id=session_id,
        )
        self._objects.write_object(
            context,
            object_key=object_key,
            body=body,
            content_type="video/webm",
        )
        return object_key


class MediaPostProcessor:
    def __init__(self, repository: ReportingRepository) -> None:
        self._repository = repository

    def build_manifest(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        chunks: tuple[tuple[int, int, str], ...],
        output_object_key: str,
        occurred_at: datetime,
    ) -> RecordingAsset:
        if not chunks:
            raise ValueError("recording manifest requires verified chunks")
        ordered = tuple(sorted(chunks, key=lambda item: item[0]))
        missing_ranges: list[tuple[int, int]] = []
        previous_end = ordered[0][0]
        for start_ms, end_ms, content_hash in ordered:
            if start_ms < previous_end or end_ms <= start_ms:
                raise ValueError("recording chunks must be ordered and non-overlapping")
            if len(content_hash) != 64:
                raise ValueError("recording chunk hash must be SHA-256")
            if start_ms > previous_end:
                missing_ranges.append((previous_end, start_ms))
            previous_end = end_ms
        digest = hashlib.sha256(
            "".join(chunk_hash for _, _, chunk_hash in ordered).encode()
        ).hexdigest()
        asset = RecordingAsset(
            recording_asset_id=new_uuid7(occurred_at),
            company_id=context.company_id,
            interview_session_id=session_id,
            asset_type="final_video",
            object_key=output_object_key,
            content_hash=digest,
            duration_ms=ordered[-1][1],
            status=(RecordingStatus.PARTIAL if missing_ranges else RecordingStatus.READY),
            missing_ranges=tuple(missing_ranges),
            created_at=occurred_at,
        )
        return self._repository.save_recording_asset(context, asset)
