from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import quote

from interview_evidence.reporting.domain.timeline import RecordingAsset
from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class PlaybackLocator:
    url: str | None
    expires_at: datetime | None
    status: str


class ScopedPlaybackLocator:
    def __init__(self, *, base_url: str = "https://media.local/playback") -> None:
        self._base_url = base_url.rstrip("/")

    def create(
        self,
        context: TenantContext,
        *,
        asset: RecordingAsset | None,
        now: datetime,
        ttl: timedelta = timedelta(minutes=5),
    ) -> PlaybackLocator:
        if asset is None:
            return PlaybackLocator(url=None, expires_at=None, status="unavailable")
        context.assert_company(asset.company_id)
        status = asset.status.value
        if status not in {"ready", "partial"}:
            return PlaybackLocator(url=None, expires_at=None, status=status)
        expires_at = now + ttl
        opaque = quote(str(asset.recording_asset_id), safe="")
        return PlaybackLocator(
            url=f"{self._base_url}/{opaque}",
            expires_at=expires_at,
            status=status,
        )
