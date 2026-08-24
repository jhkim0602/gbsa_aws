from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from google.auth.credentials import Credentials
from google.oauth2 import service_account

_CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


def resolve_gcp_credentials(environment: Mapping[str, str]) -> Credentials | None:
    raw = environment.get("GCP_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        return None
    try:
        payload: Any = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError("GCP_SERVICE_ACCOUNT_JSON must be valid JSON") from error
    if not isinstance(payload, dict):
        raise RuntimeError("GCP_SERVICE_ACCOUNT_JSON must contain a JSON object")
    try:
        return service_account.Credentials.from_service_account_info(
            payload,
            scopes=[_CLOUD_PLATFORM_SCOPE],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("GCP_SERVICE_ACCOUNT_JSON is not a valid service account") from error
