"""The playback locator has to hand the browser a URL that actually plays.

Every earlier test asserted only tenant scope and status mapping, which a hardcoded
placeholder host satisfies. The reviewer's `<video src>` gets this string verbatim, so
"a URL was produced" is not the contract -- "the recorded object is fetchable" is.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from interview_evidence.reporting.adapters.playback import ScopedPlaybackLocator
from interview_evidence.reporting.domain.timeline import RecordingAsset, RecordingStatus
from interview_evidence.shared.tenant import ActorType, TenantContext, TenantScopeError

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
OTHER_COMPANY_ID = UUID("00000000-0000-7000-8000-0000000000ff")
SESSION_ID = UUID("00000000-0000-7000-8000-000000000002")
ASSET_ID = UUID("00000000-0000-7000-8000-000000000003")
NOW = datetime(2026, 8, 18, 9, 0, tzinfo=UTC)
OBJECT_KEY = f"tenants/{COMPANY_ID}/interviews/{SESSION_ID}/recording.webm"


class RecordingPresigner:
    """Stands in for the media bucket's presign client, recording what it was asked."""

    def __init__(self, *, url: str = "https://media.example/signed?sig=abc") -> None:
        self.url = url
        self.calls: list[dict[str, Any]] = []

    def create_playback_url(
        self,
        context: TenantContext,
        *,
        object_key: str,
        expires_in_seconds: int,
    ) -> str:
        self.calls.append(
            {
                "company_id": context.company_id,
                "object_key": object_key,
                "expires_in_seconds": expires_in_seconds,
            }
        )
        return self.url


def context(company_id: UUID = COMPANY_ID) -> TenantContext:
    return TenantContext(
        company_id=company_id,
        actor_type=ActorType.COMPANY_USER,
        actor_id=UUID("00000000-0000-7000-8000-000000000004"),
        request_id=UUID("00000000-0000-7000-8000-000000000005"),
        trace_id="trace-playback",
    )


def asset(
    *,
    status: RecordingStatus = RecordingStatus.READY,
    object_key: str = OBJECT_KEY,
) -> RecordingAsset:
    return RecordingAsset(
        recording_asset_id=ASSET_ID,
        company_id=COMPANY_ID,
        interview_session_id=SESSION_ID,
        asset_type="final_video",
        object_key=object_key,
        content_hash="a" * 64,
        duration_ms=160_000,
        status=status,
        missing_ranges=(),
        created_at=NOW,
    )


def test_playback_url_addresses_the_recorded_object_not_a_placeholder_host() -> None:
    presigner = RecordingPresigner()

    locator = ScopedPlaybackLocator(presigner=presigner).create(
        context(),
        asset=asset(),
        now=NOW,
    )

    assert locator.url == presigner.url
    # The object key is what makes the URL resolve to this session's recording. Signing
    # the asset id instead produced a well-formed URL for a path nothing serves.
    assert presigner.calls == [
        {
            "company_id": COMPANY_ID,
            "object_key": OBJECT_KEY,
            "expires_in_seconds": 300,
        }
    ]


def test_playback_url_expiry_matches_the_signature_lifetime() -> None:
    """A stated `expires_at` the signature outlives is a URL that keeps working after
    the response said it stopped, and one it undercuts is a player that dies mid-scrub."""
    presigner = RecordingPresigner()

    locator = ScopedPlaybackLocator(presigner=presigner).create(
        context(),
        asset=asset(),
        now=NOW,
        ttl=timedelta(minutes=7),
    )

    assert locator.expires_at == NOW + timedelta(minutes=7)
    assert presigner.calls[0]["expires_in_seconds"] == 420


def test_partial_recording_is_still_playable() -> None:
    presigner = RecordingPresigner()

    locator = ScopedPlaybackLocator(presigner=presigner).create(
        context(),
        asset=asset(status=RecordingStatus.PARTIAL),
        now=NOW,
    )

    assert locator.status == "partial"
    assert locator.url == presigner.url


@pytest.mark.parametrize("status", [RecordingStatus.PROCESSING, RecordingStatus.FAILED])
def test_unfinished_recording_is_never_signed(status: RecordingStatus) -> None:
    presigner = RecordingPresigner()

    locator = ScopedPlaybackLocator(presigner=presigner).create(
        context(),
        asset=asset(status=status),
        now=NOW,
    )

    assert locator.url is None
    assert locator.status == status.value
    assert presigner.calls == []


def test_missing_asset_reports_unavailable_without_signing() -> None:
    presigner = RecordingPresigner()

    locator = ScopedPlaybackLocator(presigner=presigner).create(
        context(),
        asset=None,
        now=NOW,
    )

    assert locator == type(locator)(url=None, expires_at=None, status="unavailable")
    assert presigner.calls == []


def test_another_company_cannot_have_a_url_signed_for_this_recording() -> None:
    presigner = RecordingPresigner()

    with pytest.raises(TenantScopeError):
        ScopedPlaybackLocator(presigner=presigner).create(
            context(OTHER_COMPANY_ID),
            asset=asset(),
            now=NOW,
        )

    # The scope check has to run before signing, or the signature exists regardless of
    # whether the caller ever sees the exception.
    assert presigner.calls == []


def test_locator_without_a_presigner_refuses_rather_than_inventing_a_url() -> None:
    """Composition is the only place that knows the media bucket. A runtime that forgets
    to pass the presigner previously got a placeholder URL that failed in the browser
    instead of at startup."""
    locator = ScopedPlaybackLocator(presigner=None).create(
        context(),
        asset=asset(),
        now=NOW,
    )

    assert locator.url is None
    assert locator.status == "unavailable"
