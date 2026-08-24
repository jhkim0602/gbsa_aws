from __future__ import annotations

from typing import cast

import pytest
from google.auth.credentials import Credentials
from interview_evidence.runtime import gcp_credentials


def test_gcp_credentials_fall_back_to_application_default_credentials() -> None:
    assert gcp_credentials.resolve_gcp_credentials({}) is None


def test_gcp_credentials_accept_a_secret_manager_json_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    credentials = cast(Credentials, object())

    def from_service_account_info(
        payload: dict[str, str],
        *,
        scopes: list[str],
    ) -> Credentials:
        captured["payload"] = payload
        captured["scopes"] = scopes
        return credentials

    monkeypatch.setattr(
        gcp_credentials.service_account.Credentials,
        "from_service_account_info",
        staticmethod(from_service_account_info),
    )

    resolved = gcp_credentials.resolve_gcp_credentials(
        {"GCP_SERVICE_ACCOUNT_JSON": '{"type":"service_account","project_id":"project"}'}
    )

    assert resolved is credentials
    assert captured["payload"] == {"type": "service_account", "project_id": "project"}
    assert captured["scopes"] == ["https://www.googleapis.com/auth/cloud-platform"]


def test_gcp_credentials_reject_malformed_secret_without_leaking_it() -> None:
    with pytest.raises(RuntimeError, match="must be valid JSON") as error:
        gcp_credentials.resolve_gcp_credentials(
            {"GCP_SERVICE_ACCOUNT_JSON": "private-key-material"}
        )

    assert "private-key-material" not in str(error.value)
