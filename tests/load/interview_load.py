from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from tests.e2e.support import run_thin_journey


def _journey_duration() -> float:
    started = time.perf_counter()
    result = run_thin_journey()
    if (
        not result.analysis_ready
        or result.question_source_reference_count < 1
        or result.human_decision != "hold"
    ):
        raise AssertionError("load journey did not reach the expected durable outcome")
    return time.perf_counter() - started


def run_load(
    *,
    concurrency: int = 5,
    soak_batches: int = 3,
) -> dict[str, Any]:
    if concurrency < 1 or soak_batches < 1:
        raise ValueError("load dimensions must be positive")
    durations: list[float] = []
    failures: list[str] = []
    started = time.perf_counter()
    for batch in range(soak_batches):
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(_journey_duration) for _ in range(concurrency)]
            for future in as_completed(futures):
                try:
                    durations.append(future.result())
                except Exception as error:  # noqa: BLE001 - load report must capture every failure
                    failures.append(f"batch-{batch + 1}:{type(error).__name__}")
    elapsed = time.perf_counter() - started
    ordered = sorted(durations)
    p95_index = max(0, min(len(ordered) - 1, round(len(ordered) * 0.95) - 1))
    return {
        "passed": not failures and len(durations) == concurrency * soak_batches,
        "concurrency": concurrency,
        "soak_batches": soak_batches,
        "completed_sessions": len(durations),
        "failed_sessions": len(failures),
        "failures": failures,
        "elapsed_seconds": elapsed,
        "mean_session_seconds": statistics.fmean(durations) if durations else None,
        "p95_session_seconds": ordered[p95_index] if ordered else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local concurrent interview journeys.")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--soak-batches", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args()
    report = run_load(
        concurrency=arguments.concurrency,
        soak_batches=arguments.soak_batches,
    )
    if arguments.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            f"{report['completed_sessions']} sessions completed; "
            f"{report['failed_sessions']} failed."
        )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
