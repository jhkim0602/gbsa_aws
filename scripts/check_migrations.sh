#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

UV_CACHE_DIR="${UV_CACHE_DIR:-.uv-cache}" \
  uv run --no-sync python scripts/check_migrations.py

