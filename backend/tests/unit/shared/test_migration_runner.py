from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config


class FakeSecretsManager:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.requested_secret_id: str | None = None

    def get_secret_value(self, *, SecretId: str) -> dict[str, str]:
        self.requested_secret_id = SecretId
        return {"SecretString": json.dumps(self.payload)}


@pytest.fixture(autouse=True)
def migration_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    config_path = tmp_path / "alembic.ini"
    config_path.write_text("[alembic]\nscript_location = migrations\n", encoding="utf-8")
    monkeypatch.setenv("ALEMBIC_CONFIG", str(config_path))
    monkeypatch.setenv("AURORA_ENDPOINT", "private.cluster.example")
    monkeypatch.setenv("AURORA_DATABASE", "interview_evidence")
    monkeypatch.setenv("AURORA_MASTER_SECRET_ARN", "arn:aws:secretsmanager:region:acct:secret:db")
    yield config_path


def test_migration_runner_fetches_secret_and_upgrades_all_heads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from interview_evidence import migrate

    secrets = FakeSecretsManager(
        {
            "username": "platform_admin",
            "password": "not logged:/?#[]@!",
            "port": 5432,
        }
    )
    observed: dict[str, Any] = {}

    def upgrade(config: Config, revision: str) -> None:
        observed["url"] = config.get_main_option("sqlalchemy.url")
        observed["revision"] = revision

    monkeypatch.setattr(migrate.boto3, "client", lambda service: secrets)
    monkeypatch.setattr(migrate.command, "upgrade", upgrade)

    migrate.main()

    assert secrets.requested_secret_id == "arn:aws:secretsmanager:region:acct:secret:db"
    assert observed["revision"] == "heads"
    assert observed["url"].startswith("postgresql+psycopg://platform_admin:")
    assert "private.cluster.example:5432/interview_evidence" in observed["url"]
    assert "not logged:/?#[]@!" not in observed["url"]
    assert "%3A%2F%3F%23%5B%5D%40%21" in observed["url"]


def test_migration_runner_rejects_incomplete_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from interview_evidence import migrate

    secrets = FakeSecretsManager({"username": "platform_admin"})
    monkeypatch.setattr(migrate.boto3, "client", lambda service: secrets)

    with pytest.raises(RuntimeError, match="required database fields"):
        migrate.main()
