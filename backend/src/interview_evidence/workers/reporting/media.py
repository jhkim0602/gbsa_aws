from __future__ import annotations

import hashlib
from datetime import datetime
from uuid import UUID

from interview_evidence.reporting.domain.timeline import (
    RecordingAsset,
    RecordingStatus,
)
from interview_evidence.reporting.repositories.postgres import ReportingRepository
from interview_evidence.shared.ids import new_uuid7
from interview_evidence.shared.tenant import TenantContext


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
