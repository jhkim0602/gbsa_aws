from interview_evidence.shared.config import Settings


def test_settings_safe_projection_redacts_credentials_and_urls() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://user:secret@localhost/database",
        aws_access_key_id="access-key",
        aws_secret_access_key="secret-key",
    )

    projection = settings.safe_projection()

    assert projection["database_url"] == "[REDACTED]"
    assert projection["aws_access_key_id"] == "[REDACTED]"
    assert projection["aws_secret_access_key"] == "[REDACTED]"
    assert "secret-key" not in str(settings)
