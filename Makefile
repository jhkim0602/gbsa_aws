SHELL := /bin/bash
UV_CACHE_DIR ?= .uv-cache
WORKER_CONCURRENCY ?= 4
.PHONY: bootstrap dev-install up down local-infra api worker assistant-backfill infra-format-check infra-validate migrate

# Every target below that runs application code loads `.env` first. `set -a` exports what the
# file assigns, so `os.environ` carries it -- without that the runtime reads none of it and
# fails on the first required setting. Keep the source tree explicit as well so host commands
# always run the current checkout even if an editable-install path is stale or unavailable.
RUN_WITH_ENV = set -a && source .env && set +a && export PYTHONPATH="$(CURDIR)/backend/src$${PYTHONPATH:+:$${PYTHONPATH}}" &&

# `--no-editable`, matching CI and the image: this installs a copy of `backend/src` into the
# virtualenv. Use `make dev-install` for a working copy where edits take effect.
bootstrap:
	npm ci
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv sync --frozen --no-editable

# Editable, so an edit under `backend/src` is picked up without a re-sync. `bootstrap` copies the
# tree instead, which is right for CI and wrong for a workstation: every change would need a
# `uv sync` before it ran, and a newly added module would import as though it did not exist.
dev-install:
	npm ci
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv sync --frozen

# Postgres, DynamoDB and LocalStack, then the buckets, queues and table inside them, then the
# schema. Idempotent -- safe to re-run whenever a container has been reset.
up:
	docker compose up -d --wait
	$(MAKE) local-infra
	$(MAKE) migrate

down:
	docker compose down

# Creates the two S3 buckets (with the CORS rules the browser upload needs), the four SQS
# queues and the DynamoDB table. Nothing seeds application data: there is no demo company or
# position, so a fresh database starts empty and the first company comes from a real signup.
local-infra:
	$(RUN_WITH_ENV) UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync python -m interview_evidence.runtime.local_infra

api:
	$(RUN_WITH_ENV) UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync uvicorn interview_evidence.main:app --reload --port 8080

worker:
	$(RUN_WITH_ENV) \
	pids=""; \
	cleanup() { \
		trap - EXIT INT TERM; \
		if [ -n "$$pids" ]; then \
			kill $$pids 2>/dev/null || true; \
			wait $$pids 2>/dev/null || true; \
		fi; \
	}; \
	trap cleanup EXIT INT TERM; \
	for ((index = 0; index < $(WORKER_CONCURRENCY); index++)); do \
		UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync python -m interview_evidence.worker & \
		pids="$$pids $$!"; \
	done; \
	wait

# Backfill recruiter-assistant search documents for reports created before the projection existed
# or before the configured embedding provider/version changed. The operation is idempotent.
assistant-backfill:
	$(RUN_WITH_ENV) UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync python -m interview_evidence.runtime.assistant_backfill

# Alembic reads MIGRATION_DATABASE_URL from the environment (`backend/alembic/env.py`), so this
# needs `.env` too. Not `interview_evidence.migrate`: that entry point resolves the credential
# from Secrets Manager, which only exists in a deployed environment.
migrate:
	$(RUN_WITH_ENV) UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync alembic -c backend/alembic.ini upgrade heads

infra-format-check:
	terraform fmt -check -recursive infra

infra-validate:
	@for root in infra/environments/dev/foundation infra/environments/dev/data-ai infra/environments/dev/application infra/environments/prod; do \
		terraform -chdir=$$root init -backend=false -input=false >/dev/null && \
		terraform -chdir=$$root validate || exit 1; \
	done
