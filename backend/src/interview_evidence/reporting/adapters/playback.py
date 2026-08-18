from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from interview_evidence.reporting.domain.timeline import RecordingAsset
from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class PlaybackLocator:
    url: str | None
    expires_at: datetime | None
    status: str


class RecordingPresigner(Protocol):
    """Signs a read of one recording object in the media bucket."""

    def create_playback_url(
        self,
        context: TenantContext,
        *,
        object_key: str,
        expires_in_seconds: int,
    ) -> str: ...


class ScopedPlaybackLocator:
    def __init__(self, *, presigner: RecordingPresigner | None = None) -> None:
        self._presigner = presigner

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
        # Before signing, so a cross-tenant caller cannot cause a signature to exist for
        # a recording it is not allowed to read.
        context.assert_company(asset.company_id)
        status = asset.status.value
        if status not in {"ready", "partial"}:
            return PlaybackLocator(url=None, expires_at=None, status=status)
        if self._presigner is None:
            # A composition root that never wired the media bucket cannot produce a
            # playable URL. Reporting "unavailable" is wrong-but-honest; a syntactically
            # valid URL for a host nobody serves is neither, and it fails in the
            # reviewer's browser rather than at startup.
            return PlaybackLocator(url=None, expires_at=None, status="unavailable")
        expires_in_seconds = max(1, int(ttl.total_seconds()))
        url = self._presigner.create_playback_url(
            context,
            object_key=asset.object_key,
            expires_in_seconds=expires_in_seconds,
        )
        return PlaybackLocator(
            url=url,
            # Derived from the number the signature itself uses, so the response cannot
            # promise a lifetime the URL does not have.
            expires_at=now + timedelta(seconds=expires_in_seconds),
            status=status,
        )
