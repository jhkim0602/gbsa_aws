from pathlib import Path
from uuid import UUID

import httpx
import pytest
from alembic import command
from alembic.config import Config
from interview_evidence.interview_engine.adapters.recent_context import (
    InMemoryRecentContext,
)
from interview_evidence.interview_engine.application.idempotency import (
    SqlAlchemyIdempotencyStore,
)
from interview_evidence.runtime.production import create_production_runtime
from interview_evidence.shared.aws_clients.ports import (
    DeterministicAIModel,
    DeterministicSpeechToText,
    DeterministicTextToSpeech,
    InMemoryEmailSender,
    InMemoryObjectStorage,
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
        speech_to_text=DeterministicSpeechToText(
            {"text": "테스트 답변", "confidence": 0.99}
        ),
        text_to_speech=DeterministicTextToSpeech({}),
    )


@pytest.mark.anyio
async def test_production_runtime_persists_http_state_across_recreation(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'production.db'}"
    _upgrade(database_url)
    headers = {
        "Authorization": "Bearer company-token",
        "Idempotency-Key": "position-production-0001",
    }

    first = _runtime(database_url)
    assert isinstance(
        first.lanes["interview_engine"].idempotency,
        SqlAlchemyIdempotencyStore,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=first.app),
        base_url="http://test",
    ) as client:
        created = await client.post(
            "/v1/positions",
            headers=headers,
            json={"title": "Platform Engineer", "description": "Production runtime"},
        )
    assert created.status_code == 201

    recreated = _runtime(database_url)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=recreated.app),
        base_url="http://test",
    ) as client:
        ready = await client.get("/health/ready")
        positions = await client.get(
            "/v1/positions",
            headers={"Authorization": "Bearer company-token"},
        )
    assert ready.status_code == 200
    assert ready.json() == {
        "status": "ok",
        "dependencies": {
            "database": "ok",
            "media_storage": "ok",
            "object_storage": "ok",
            "recent_context": "ok",
            "search": "ok",
        },
    }
    assert positions.status_code == 200
    assert [item["title"] for item in positions.json()["items"]] == [
        "Platform Engineer",
    ]
