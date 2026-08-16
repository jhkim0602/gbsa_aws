#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

npm run format:check
npm run lint
npm run typecheck
UV_CACHE_DIR="${UV_CACHE_DIR:-.uv-cache}" uv run --no-sync pytest backend/tests/contract backend/tests/unit/shared
make contracts-check
make boundaries-check
make migration-check
npm run build

if [[ "${REQUIRE_FOUNDATION_TAG:-0}" == "1" ]]; then
  tag="$(git describe --tags --exact-match HEAD 2>/dev/null || true)"
  if [[ "$tag" != "foundation-v1" ]]; then
    echo "HEAD must be tagged foundation-v1; found '${tag:-no tag}'." >&2
    exit 1
  fi
fi

echo "Foundation verification passed."

