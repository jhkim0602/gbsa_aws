SHELL := /bin/bash
UV_CACHE_DIR ?= .uv-cache

.PHONY: bootstrap boundaries-check build compose-down compose-up contracts-check contracts-generate \
	format-check infra-format-check infra-plan-dev infra-security-check infra-validate lint migrate \
	migration-check seed-contract-fixtures test test-foundation test-workspace typecheck verify-foundation

bootstrap:
	npm install
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv sync --no-editable

build:
	npm run build

compose-up:
	docker compose up -d postgres dynamodb localstack opensearch

compose-down:
	docker compose down

contracts-generate:
	npm run contracts:generate

contracts-check:
	npm run contracts:check

boundaries-check:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync python scripts/check_module_boundaries.py

migration-check:
	./scripts/check_migrations.sh

migrate:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync alembic -c backend/alembic.ini upgrade heads

seed-contract-fixtures:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync python -m tests.fixtures.shared.factories

format-check:
	npm run format:check

lint:
	npm run lint

typecheck:
	npm run typecheck

test:
	npm test

test-workspace:
	npm run test:workspace

test-foundation:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync pytest backend/tests/contract backend/tests/unit/shared

verify-foundation:
	./scripts/verify_foundation.sh

infra-format-check:
	terraform fmt -check -recursive infra

infra-validate:
	@echo "Terraform validation becomes active when environment roots are implemented."

infra-security-check:
	@echo "Terraform security scanning becomes active with the first Terraform module."

infra-plan-dev:
	@echo "A reviewed backend configuration is required before planning dev infrastructure."
