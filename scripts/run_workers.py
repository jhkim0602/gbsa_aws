# Created: 2026-08-21 09:29
"""Run several local worker processes and stop them together."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time


def main() -> None:
    concurrency = int(os.environ.get("WORKER_CONCURRENCY", "4"))
    if concurrency < 1:
        raise SystemExit("WORKER_CONCURRENCY must be at least 1")

    processes = [
        subprocess.Popen([sys.executable, "-m", "interview_evidence.worker"])
        for _ in range(concurrency)
    ]
    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    print(f"Started {concurrency} workers. Press Ctrl+C to stop them.", flush=True)

    try:
        while not stopping:
            failed = next((process for process in processes if process.poll() is not None), None)
            if failed is not None:
                raise SystemExit(f"worker exited unexpectedly with code {failed.returncode}")
            time.sleep(0.5)
    finally:
        if os.name == "nt":
            # The uv-managed Python launcher can leave its real interpreter behind when only
            # the immediate process is terminated. Kill each explicitly scoped worker tree.
            for process in processes:
                if process.poll() is None:
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        check=False,
                        capture_output=True,
                    )
        else:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        print("Workers stopped.", flush=True)


if __name__ == "__main__":
    main()
