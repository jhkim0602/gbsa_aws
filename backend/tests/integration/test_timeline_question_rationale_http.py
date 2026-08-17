"""The served timeline has to carry why each question was asked.

The rationale provider is optional on the reporting router, and the composed application
builds its own router rather than mounting ``lane_d.app`` -- so a provider wired only into
the lane runtime leaves the deployed endpoint answering with ``question_rationale: null``
for every question. Nothing below the HTTP layer notices: the service, the repository and
the projection all pass their own tests. This drives the real app so the wiring is pinned
where it actually broke.
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


def _upgrade(database_url: str) -> None:
    config = Config("backend/alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "heads")


def _runtime(database_url: str):
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
        email_sender=InMemoryEmailSender(),
        recent_context=InMemoryRecentContext(),
        search_index=InMemorySearchIndex(),
        model=DeterministicAIModel({}),
        embedder=StaticTextEmbedder(tuple(1.0 if index == 0 else 0.0 for index in range(1024))),
        speech_to_text=DeterministicSpeechToText({"text": "테스트 답변", "confidence": 0.99}),
        text_to_speech=DeterministicTextToSpeech({}),
    )


@pytest.mark.anyio
async def test_served_timeline_explains_each_question(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'timeline.db'}"
    _upgrade(database_url)
    seed_local_company(
        {
            "DATABASE_URL": database_url,
            "LOCAL_COMPANY_ID": str(COMPANY_ID),
            "LOCAL_COMPANY_USER_ID": str(COMPANY_USER_ID),
            "LOCAL_DEMO_DATA_ENABLED": "true",
        }
    )

    runtime = _runtime(database_url)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=runtime.app),
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
    entries = response.json()["entries"]
    questions = [entry for entry in entries if entry["entry_type"] == "question"]
    assert questions, "the seeded interview asked questions"
    for question in questions:
        rationale = question["question_rationale"]
        # A question with no rationale reads as if the AI invented it, which is the one
        # thing a reviewer cannot check.
        assert rationale is not None, question["text"]
        assert rationale["objective"]
        assert rationale["policy_result"] == "accepted"
        assert rationale["source_references"], "a personalized question cites its material"
        for source in rationale["source_references"]:
            assert source["excerpt"]
            assert source["locator"]

    # Answers stay clean: submitted material is never attached to what the applicant said.
    answers = [entry for entry in entries if entry["entry_type"] == "answer"]
    assert answers
    assert all(entry["question_rationale"] is None for entry in answers)
