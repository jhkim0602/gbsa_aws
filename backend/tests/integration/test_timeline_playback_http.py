"""The served timeline has to hand the reviewer a URL that names the recording.

``ScopedPlaybackLocator`` takes its presigner as an optional argument, and every
composition root constructed it without one -- so the endpoint answered ``status: ready``
with ``url: null`` while the console showed the placeholder. Before that it answered with a
hardcoded ``https://media.local/playback``, a host that resolves nowhere.

Nothing below the HTTP layer noticed: the locator, the storage adapter and the projection
each pass their own tests. This drives the real app, with the same seed the local stack
runs, so the wiring is pinned where it actually broke.
"""

from pathlib import Path
from uuid import UUID

import httpx
import pytest
from alembic import command
from alembic.config import Config
from interview_evidence.interview_engine.adapters.recent_context import (
    InMemoryRecentContext,
)
from interview_evidence.runtime.local_seed import seed_local_company
from interview_evidence.runtime.production import create_production_runtime
from interview_evidence.shared.aws_clients.ports import (
    DeterministicAIModel,
    DeterministicSpeechToText,
    DeterministicTextToSpeech,
    InMemoryEmailSender,
    InMemoryObjectStorage,
    StaticTextEmbedder,
)
from interview_evidence.shared.security.principals import (
    CompanyPrincipal,
    FakePrincipalProvider,
)
from interview_evidence.submission_analysis.adapters.search import InMemorySearchIndex

COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
COMPANY_USER_ID = UUID("00000000-0000-7000-8000-000000000002")
EBML_MAGIC = b"\x1a\x45\xdf\xa3"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _upgrade(database_url: str) -> None:
    config = Config("backend/alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "heads")


def _runtime(database_url: str, media: InMemoryObjectStorage) -> object:
    return create_production_runtime(
        {
            "APP_ENVIRONMENT": "stage",
            "DATABASE_URL": database_url,
            "APPLICANT_ACCESS_BASE_URL": "https://applicant.stage.example/access",
        },
        principal_provider=FakePrincipalProvider(
            company_principals={
                "company-token": CompanyPrincipal(
                    company_id=COMPANY_ID,
                    company_user_id=COMPANY_USER_ID,
                    identity_subject="cognito|company-user",
                )
            }
        ),
        object_storage=InMemoryObjectStorage(),
        # The bucket the recording was seeded into. Passed explicitly so the presigner the
        # router ends up with is the one that holds the bytes, which is the wiring at issue.
        media_storage=media,
        email_sender=InMemoryEmailSender(),
        recent_context=InMemoryRecentContext(),
        search_index=InMemorySearchIndex(),
        model=DeterministicAIModel({}),
        embedder=StaticTextEmbedder(tuple(1.0 if index == 0 else 0.0 for index in range(1024))),
        speech_to_text=DeterministicSpeechToText({"text": "테스트 답변", "confidence": 0.99}),
        text_to_speech=DeterministicTextToSpeech({}),
    )


@pytest.mark.anyio
async def test_served_timeline_offers_a_url_for_bytes_that_exist(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'playback.db'}"
    _upgrade(database_url)
    media = InMemoryObjectStorage()
    seed_local_company(
        {
            "DATABASE_URL": database_url,
            "LOCAL_COMPANY_ID": str(COMPANY_ID),
            "LOCAL_COMPANY_USER_ID": str(COMPANY_USER_ID),
            "LOCAL_DEMO_DATA_ENABLED": "true",
        },
        media_storage=media,
    )

    runtime = _runtime(database_url, media)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=runtime.app),  # type: ignore[attr-defined]
        base_url="http://test",
    ) as client:
        headers = {"Authorization": "Bearer company-token"}
        positions = await client.get("/v1/positions", headers=headers)
        assert positions.status_code == 200
        position_id = positions.json()["items"][0]["position_id"]
        invitations = await client.get(
            f"/v1/positions/{position_id}/invitations",
            headers=headers,
        )
        assert invitations.status_code == 200
        session_ids = [
            item["interview_session_id"]
            for item in invitations.json()["items"]
            if item.get("interview_session_id")
        ]
        assert session_ids, "the seed leaves one reviewable applicant to open"
        response = await client.get(
            f"/v1/interview-sessions/{session_ids[0]}/timeline",
            headers=headers,
        )

    assert response.status_code == 200
    playback = response.json()["playback"]
    assert playback["status"] == "ready"
    # The defect this pins: ready with no URL, so the console shows the placeholder for a
    # recording that is sitting in the bucket.
    assert playback["url"] is not None
    assert playback["expires_at"] is not None

    # And the URL has to name an object that is actually there. Read out of the same store
    # the runtime signed against rather than fetched over HTTP: an in-memory bucket has no
    # endpoint, and a test that skips without one would leave this unasserted everywhere.
    key = playback["url"].removeprefix("memory://recordings/")
    assert key in media.objects, playback["url"]
    body = media.objects[key]
    # A browser decides whether it can play from the container header, so a placeholder of
    # the right length would still leave `<video>` at readyState 0.
    assert body.startswith(EBML_MAGIC)
    assert len(body) > 1024
