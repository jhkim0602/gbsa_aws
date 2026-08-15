"""Local worker process entry point for the composed handler registry."""

from __future__ import annotations

import signal
from pathlib import Path
from threading import Event

from interview_evidence.main import create_local_runtime

READY_FILE = Path("/tmp/iep-worker-ready")


def main() -> None:
    runtime = create_local_runtime()
    if not runtime.worker_handlers:
        raise SystemExit("No worker handlers are registered.")

    READY_FILE.write_text(
        "\n".join(sorted(runtime.worker_handlers)),
        encoding="utf-8",
    )
    stopped = Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stopped.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        while not stopped.wait(timeout=1):
            pass
    finally:
        READY_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
