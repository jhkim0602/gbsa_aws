from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, TypedDict, cast

import boto3  # type: ignore[import-untyped]
from alembic import command
from alembic.config import Config
from sqlalchemy import URL


class SecretsManagerClient(Protocol):
    def get_secret_value(self, *, SecretId: str) -> Mapping[str, object]: ...


class DatabaseSecret(TypedDict):
    username: str
    password: str
    port: int


def main() -> None:
    endpoint = _required_environment("AURORA_ENDPOINT")
    database = _required_environment("AURORA_DATABASE")
    secret_arn = _required_environment("AURORA_MASTER_SECRET_ARN")
    config_path = Path(os.getenv("ALEMBIC_CONFIG", "backend/alembic.ini"))
    if not config_path.is_file():
        raise RuntimeError("Alembic configuration is unavailable")

    client = cast(SecretsManagerClient, boto3.client("secretsmanager"))
    secret = _database_secret(client.get_secret_value(SecretId=secret_arn))
    url = URL.create(
        drivername="postgresql+psycopg",
        username=secret["username"],
        password=secret["password"],
        host=endpoint,
        port=secret["port"],
        database=database,
    ).render_as_string(hide_password=False)

    config = Config(str(config_path))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "heads")


def _required_environment(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Required migration setting is missing: {name}")
    return value.strip()


def _database_secret(response: Mapping[str, object]) -> DatabaseSecret:
    secret_string = response.get("SecretString")
    if not isinstance(secret_string, str):
        raise RuntimeError("Database secret string is unavailable")

    decoded = json.loads(secret_string)
    if not isinstance(decoded, dict):
        raise RuntimeError("Database secret has an invalid shape")

    username = decoded.get("username")
    password = decoded.get("password")
    port = decoded.get("port", 5432)
    if not isinstance(username, str) or not isinstance(password, str):
        raise RuntimeError("Database secret is missing required database fields")
    if not isinstance(port, int | str):
        raise RuntimeError("Database secret port is invalid")

    try:
        parsed_port = int(port)
    except ValueError as exc:
        raise RuntimeError("Database secret port is invalid") from exc
    return {"username": username, "password": password, "port": parsed_port}


if __name__ == "__main__":
    main()
