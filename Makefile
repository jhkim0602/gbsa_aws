SHELL := /bin/bash
UV_CACHE_DIR ?= .uv-cache
.PHONY: bootstrap infra-format-check infra-validate migrate

bootstrap:
	npm ci
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv sync --frozen --no-editable

migrate:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync alembic -c backend/alembic.ini upgrade heads

infra-format-check:
	terraform fmt -check -recursive infra

infra-validate:
	@for root in infra/environments/dev/foundation infra/environments/dev/data-ai infra/environments/dev/application infra/environments/prod; do \
		terraform -chdir=$$root init -backend=false -input=false >/dev/null && \
		terraform -chdir=$$root validate || exit 1; \
	done
