from tests.load.evidence_seek import run_seek_measurement
from tests.load.interview_load import run_load


def test_concurrent_interview_load_completes_without_starvation() -> None:
    report = run_load(concurrency=5, soak_batches=1)

    assert report["passed"] is True
    assert report["completed_sessions"] == 5
    assert report["failed_sessions"] == 0


def test_evidence_seek_api_is_ready_within_two_seconds() -> None:
    report = run_seek_measurement(samples=5)

    assert report["passed"] is True
    assert report["p95_seconds"] < 2
