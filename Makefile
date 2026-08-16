SHELL := /bin/bash
UV_CACHE_DIR ?= .uv-cache
DOCKER_CONTEXT ?= default

# Only commands that npm scripts and a bare pytest invocation cannot express live here.
.PHONY: bootstrap boundaries-check compose-down compose-up contracts-check contracts-generate \
	infra-format-check infra-plan-dev infra-security-check infra-validate migrate migration-check \
	seed-contract-fixtures test-ai-regression test-load-pilot test-local-production-parity \
	verify-foundation

bootstrap:
	npm ci
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv sync --frozen --no-editable

compose-up:
	DOCKER_CONTEXT=$(DOCKER_CONTEXT) docker compose up -d --build --wait

compose-down:
	DOCKER_CONTEXT=$(DOCKER_CONTEXT) docker compose down

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

# The regression and load runners import backend packages directly, so they need PYTHONPATH.
test-ai-regression:
	PYTHONPATH=backend/src:. UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync python tests/regression/run_regression.py --json

test-load-pilot:
	PYTHONPATH=backend/src:. UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync python tests/load/interview_load.py --concurrency 5 --soak-batches 3 --json
	PYTHONPATH=backend/src:. UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync python tests/load/evidence_seek.py --samples 20 --json

test-local-production-parity:
	DOCKER_CONTEXT=$(DOCKER_CONTEXT) ./scripts/verify_local_production_parity.sh

verify-foundation:
	./scripts/verify_foundation.sh

infra-format-check:
	terraform fmt -check -recursive infra

infra-validate:
	@for root in infra/environments/dev/foundation infra/environments/dev/data-ai infra/environments/dev/application infra/environments/stage infra/environments/prod; do \
		terraform -chdir=$$root init -backend=false -input=false >/dev/null && \
		terraform -chdir=$$root validate || exit 1; \
	done

infra-security-check:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync pytest -q infra/tests/test_terraform_contracts.py

infra-plan-dev:
	terraform -chdir=infra/environments/stage test -filter=local-plan.tftest.hcl
