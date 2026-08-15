SHELL := /bin/bash
UV_CACHE_DIR ?= .uv-cache
DOCKER_CONTEXT ?= default

.PHONY: bootstrap boundaries-check build compose-down compose-up contracts-check contracts-generate \
	demo-lane-a demo-lane-b demo-lane-c demo-lane-d format-check infra-format-check \
	infra-plan-dev infra-security-check infra-validate lint migrate migration-check \
	seed-contract-fixtures test test-ai-regression test-deletion-residue test-e2e-thin \
	test-foundation test-integration test-lane-a test-lane-b test-lane-c test-lane-d \
	test-load-pilot test-local-production-parity test-prior-lanes test-recovery \
	test-tenant-isolation test-workspace typecheck verify-foundation

bootstrap:
	npm ci
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv sync --frozen --no-editable

build:
	npm run build

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

test-lane-a:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync pytest backend/tests/unit/company_management backend/tests/integration/company_management

demo-lane-a:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync pytest -q backend/tests/integration/company_management/test_lane_a_quickstart.py

test-lane-b:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync pytest backend/tests/unit/submission_analysis backend/tests/integration/submission_analysis

demo-lane-b:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync pytest -q backend/tests/integration/submission_analysis/test_lane_b_quickstart.py

test-lane-c:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync pytest backend/tests/unit/interview_engine backend/tests/integration/interview_engine

demo-lane-c:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync pytest -q backend/tests/integration/interview_engine/test_lane_c_quickstart.py

test-lane-d:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync pytest backend/tests/unit/reporting backend/tests/integration/reporting

demo-lane-d:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync pytest -q backend/tests/integration/reporting/test_lane_d_quickstart.py

test-integration:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync pytest backend/tests/integration/cross_module backend/tests/integration/test_main_composition.py backend/tests/integration/test_compose_contract.py

test-e2e-thin:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync pytest -q tests/e2e/test_thin_journey.py

test-recovery:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync pytest backend/tests/integration/interview_engine/test_idempotency.py backend/tests/integration/interview_engine/test_session_recovery.py

test-tenant-isolation:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync pytest -q tests/e2e/test_tenant_isolation.py

test-deletion-residue:
	UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync pytest -q tests/e2e/test_deletion_residue.py

test-ai-regression:
	PYTHONPATH=backend/src:. UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync python tests/regression/run_regression.py --json

test-load-pilot:
	PYTHONPATH=backend/src:. UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync python tests/load/interview_load.py --concurrency 5 --soak-batches 3 --json
	PYTHONPATH=backend/src:. UV_CACHE_DIR=$(UV_CACHE_DIR) uv run --no-sync python tests/load/evidence_seek.py --samples 20 --json

test-local-production-parity:
	DOCKER_CONTEXT=$(DOCKER_CONTEXT) ./scripts/verify_local_production_parity.sh

test-prior-lanes: test-lane-a test-lane-b test-lane-c test-lane-d

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
