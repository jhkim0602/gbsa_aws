from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import pytest


@dataclass(frozen=True, slots=True)
class StageSmokeSettings:
    company_url: str
    applicant_url: str
    api_url: str

    def __post_init__(self) -> None:
        for value in (self.company_url, self.applicant_url, self.api_url):
            parsed = urlparse(value)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError("stage smoke endpoints must be absolute HTTPS URLs")

    @classmethod
    def from_environment(cls) -> StageSmokeSettings | None:
        values = (
            os.getenv("STAGE_COMPANY_URL"),
            os.getenv("STAGE_APPLICANT_URL"),
            os.getenv("STAGE_API_URL"),
        )
        if not all(values):
            return None
        return cls(*(str(value).rstrip("/") for value in values))


async def run_stage_smoke(
    settings: StageSmokeSettings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, object]:
    async with httpx.AsyncClient(
        transport=transport,
        follow_redirects=True,
        timeout=15,
    ) as client:
        company = await client.get(f"{settings.company_url}/hiring")
        applicant = await client.get(f"{settings.applicant_url}/access")
        health = await client.get(f"{settings.api_url}/health/ready")
        protected_api = await client.get(f"{settings.api_url}/v1/positions")
    if company.status_code != 200 or applicant.status_code != 200:
        raise AssertionError("stage SPA deep-link fallback is unavailable")
    if health.status_code != 200 or health.json() != {"status": "ok"}:
        raise AssertionError("stage API readiness failed")
    if protected_api.status_code != 401:
        raise AssertionError("stage protected API did not enforce authentication")
    return {
        "company_cache": company.headers.get("x-cache"),
        "applicant_cache": applicant.headers.get("x-cache"),
        "api_request_id": protected_api.headers.get("x-request-id"),
        "passed": True,
    }


@pytest.mark.asyncio
async def test_stage_smoke_client_covers_cloudfront_spas_and_protected_api() -> None:
    settings = StageSmokeSettings(
        company_url="https://company.stage.example.com",
        applicant_url="https://applicant.stage.example.com",
        api_url="https://api.stage.example.com",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path in {"/hiring", "/access"}:
            return httpx.Response(
                200,
                text="<html>Interview Evidence Platform</html>",
                headers={"x-cache": "Hit from cloudfront"},
            )
        if request.url.path == "/health/ready":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/v1/positions":
            return httpx.Response(
                401,
                json={"detail": "Unauthorized"},
                headers={"x-request-id": "00000000-0000-7000-8000-000000000001"},
            )
        return httpx.Response(404)

    result = await run_stage_smoke(
        settings,
        transport=httpx.MockTransport(handler),
    )

    assert result["passed"] is True
    assert result["company_cache"] == "Hit from cloudfront"
    assert result["applicant_cache"] == "Hit from cloudfront"
    assert result["api_request_id"] is not None


@pytest.mark.asyncio
async def test_live_stage_cloudfront_to_api_smoke() -> None:
    settings = StageSmokeSettings.from_environment()
    if settings is None:
        pytest.skip("stage endpoints are not provisioned; local smoke client is covered separately")

    result = await run_stage_smoke(settings)

    assert result["passed"] is True
