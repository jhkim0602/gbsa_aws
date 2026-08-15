from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from typing import Any
from uuid import UUID

from httpx import ASGITransport, AsyncClient
from interview_evidence.main import LocalRuntime

from tests.e2e.support import COMPANY_TOKEN, run_thin_journey

SEEK_THRESHOLD_SECONDS = 2.0


async def _measure(runtime: LocalRuntime, session_id: UUID, samples: int) -> list[float]:
    durations: list[float] = []
    async with AsyncClient(
        transport=ASGITransport(app=runtime.app),
        base_url="https://testserver",
    ) as client:
        for _ in range(samples):
            started = time.perf_counter()
            response = await client.get(
                f"/v1/interview-sessions/{session_id}/timeline",
                headers={"Authorization": f"Bearer {COMPANY_TOKEN}"},
            )
            durations.append(time.perf_counter() - started)
            if response.status_code != 200:
                raise AssertionError(f"timeline request failed: {response.status_code}")
            payload = response.json()
            if not payload["entries"] or payload["playback"]["status"] != "ready":
                raise AssertionError("Evidence timeline is not seekable")
    return durations


def run_seek_measurement(*, samples: int = 20) -> dict[str, Any]:
    if samples < 1:
        raise ValueError("samples must be positive")
    journey = run_thin_journey()
    durations = asyncio.run(_measure(journey.runtime, journey.session_id, samples))
    ordered = sorted(durations)
    p95_index = max(0, min(len(ordered) - 1, round(len(ordered) * 0.95) - 1))
    p95 = ordered[p95_index]
    return {
        "passed": p95 < SEEK_THRESHOLD_SECONDS,
        "samples": samples,
        "threshold_seconds": SEEK_THRESHOLD_SECONDS,
        "mean_seconds": statistics.fmean(durations),
        "p95_seconds": p95,
        "max_seconds": max(durations),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure local Evidence seek readiness.")
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args()
    report = run_seek_measurement(samples=arguments.samples)
    if arguments.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Evidence seek p95: {report['p95_seconds']:.4f}s")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
