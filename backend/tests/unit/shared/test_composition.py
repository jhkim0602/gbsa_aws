import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient
from interview_evidence.main import create_app


@pytest.mark.asyncio
async def test_composition_root_exposes_health_and_accepts_public_routers() -> None:
    router = APIRouter()

    @router.get("/foundation-probe")
    def foundation_probe() -> dict[str, str]:
        return {"status": "composed"}

    transport = ASGITransport(app=create_app([router]))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/health/live", headers={"x-trace-id": "trace-foundation"})
        probe = await client.get("/foundation-probe")

    assert health.json() == {"status": "ok"}
    assert health.headers["x-trace-id"] == "trace-foundation"
    assert health.headers["x-request-id"]
    assert probe.json() == {"status": "composed"}
