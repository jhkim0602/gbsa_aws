from __future__ import annotations

from typing import Any

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    environment: str = "local"
    database_url: SecretStr
    aws_region: str = "ap-northeast-2"
    aws_access_key_id: SecretStr
    aws_secret_access_key: SecretStr

    def safe_projection(self) -> dict[str, Any]:
        return {
            "environment": self.environment,
            "database_url": "[REDACTED]",
            "aws_region": self.aws_region,
            "aws_access_key_id": "[REDACTED]",
            "aws_secret_access_key": "[REDACTED]",
        }
