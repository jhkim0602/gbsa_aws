"""Environment-selected worker process entry point."""

from __future__ import annotations

import logging
import signal
from pathlib import Path
from threading import Event

from interview_evidence.runtime.worker import create_environment_worker_runtime

READY_FILE = Path("/tmp/iep-worker-ready")
LOGGER = logging.getLogger(__name__)


def main() -> None:
    runtime = create_environment_worker_runtime()
    READY_FILE.write_text("worker-ready\n", encoding="utf-8")
    stopped = Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stopped.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        while not stopped.is_set():
            try:
                runtime.run_once()
            except Exception:
                LOGGER.exception("worker cycle failed; delivery remains available for retry")
            stopped.wait(timeout=1)
    finally:
        READY_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
