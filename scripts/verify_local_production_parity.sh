#!/usr/bin/env bash
set -euo pipefail

DOCKER_CONTEXT="${DOCKER_CONTEXT:-default}"
compose=(docker --context "${DOCKER_CONTEXT}" compose)

"${compose[@]}" up -d --build --wait
"${compose[@]}" exec -T api \
  uv run --no-sync python -m interview_evidence.runtime.parity write

"${compose[@]}" restart api
"${compose[@]}" up -d --wait api
"${compose[@]}" exec -T api \
  uv run --no-sync python -m interview_evidence.runtime.parity read
"${compose[@]}" exec -T api \
  uv run --no-sync python -m interview_evidence.runtime.parity adapters
"${compose[@]}" exec -T api \
  uv run --no-sync python -m interview_evidence.runtime.parity worker-roundtrip

"${compose[@]}" stop opensearch
ready_status="$(
  "${compose[@]}" exec -T api uv run --no-sync python -c \
    "import urllib.error, urllib.request
try:
    urllib.request.urlopen('http://127.0.0.1:8080/health/ready', timeout=5)
    print(200)
except urllib.error.HTTPError as error:
    print(error.code)"
)"
live_status="$(
  "${compose[@]}" exec -T api uv run --no-sync python -c \
    "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health/live', timeout=5).status)"
)"
if [[ "${ready_status}" != "503" || "${live_status}" != "200" ]]; then
  echo "dependency failure isolation failed: ready=${ready_status} live=${live_status}" >&2
  "${compose[@]}" start opensearch
  exit 1
fi

"${compose[@]}" start opensearch
"${compose[@]}" up -d --wait opensearch api worker
"${compose[@]}" exec -T api \
  uv run --no-sync python -c \
  "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8080/health/ready', timeout=10).status == 200"
"${compose[@]}" exec -T worker test -f /tmp/iep-worker-ready

echo "Local production parity verification passed."
