# Local Quickstart Results

**Executed**: 2026-08-15 (Asia/Seoul)  
**Base commit**: `b803918` plus the Phase 10/11 UI reference acceptance tree
**Environment**: macOS, Node 22.14.0, npm 10.9.2, Python 3.13.7
(project venv Python 3.12.2), uv 0.9.28, Terraform 1.13.3,
Docker Engine 28.1.1, Docker Compose 2.35.1

## Command Results

| Quickstart command | Result | Evidence |
|---|---|---|
| `make bootstrap` | PASS | npm installed 314 packages with 0 vulnerabilities; uv rebuilt and installed the locked non-editable wheel |
| `make compose-up` | PASS | API, worker, company SPA, applicant SPA, PostgreSQL, DynamoDB Local, LocalStack, and OpenSearch all reached `healthy` |
| `make migrate` | PASS | Lane A/B/C/D roots upgraded through `merge_001_lane_heads` to `m_002_runtime_persistence` |
| `make seed-contract-fixtures` | PASS | Opaque company, applicant, criterion, strategy, session, and report fixtures emitted without credentials or source text |
| `make contracts-generate` | PASS | REST fragments and Python/TypeScript types regenerated |
| `make contracts-check` | PASS | Canonical and generated contracts are current; generation left no generated diff |
| `make boundaries-check` | PASS | No private cross-lane import was found |
| `make migration-check` | PASS | Ownership, head, downgrade, and drift rules passed |
| `make test-foundation` | PASS | 35 tests |
| `make test-lane-a` / `make demo-lane-a` | PASS | 15 tests plus the isolated quickstart |
| `make test-lane-b` / `make demo-lane-b` | PASS | 18 tests plus the isolated quickstart |
| `make test-lane-c` / `make demo-lane-c` | PASS | 31 tests plus the isolated quickstart |
| `make test-lane-d` / `make demo-lane-d` | PASS | 12 tests plus the isolated quickstart |
| `make test-integration` | PASS | 13 composition, real-boundary, and Compose contract tests |
| `make test-e2e-thin` | PASS | Full company-to-human-decision journey |
| `make test-recovery` | PASS | 5 duplicate-command and reconnect tests |
| `make test-tenant-isolation` | PASS | Cross-route, search, object, and hot-view isolation |
| `make test-deletion-residue` | PASS | First-pass retry followed by 31 verified-absent targets |
| `make test-ai-regression` | PASS | Retrieval 4/4, question policy 8/8, Evidence policy 7/7 |
| `make test-load-pilot` | PASS | 15/15 sessions; p95 0.418 s. Evidence seek 20/20; p95 0.0015 s |
| `make infra-format-check` | PASS | Recursive Terraform formatting is clean |
| `make infra-validate` | PASS | Dev foundation/data/application, stage, and prod roots are valid |
| `make infra-security-check` | PASS | 8 infrastructure safety contracts |
| `make infra-plan-dev` | PASS | Stage-equivalent mock provider plan completed with 1/1 passing run |
| `make test-prior-lanes` | PASS | Lane A 15, Lane B 18, Lane C 31, Lane D 12 |
| company console unit/type/build | PASS | 18 Vitest tests; TypeScript and Vite production build passed |
| applicant portal unit/type/build | PASS | 22 Vitest tests; TypeScript and Vite production build passed |
| `make test-company-browser` | PASS | Real-Chrome E2E covers the API-backed dashboard, positions, direct applicant invitation, AI interviewer management, mobile layout and stale asset handling |

The full workspace gate also passed with 18 SPA tests and 138 Python tests.
The only skipped test is the live stage smoke request because stage endpoints are not yet
provisioned. Its local mock-transport path passed and the same test activates when
`STAGE_COMPANY_URL`, `STAGE_APPLICANT_URL`, and `STAGE_API_URL` are provided.

## Local Runtime Observations

- All eight Compose services remained healthy after image rebuild.
- Contract generation was idempotent.
- The interview load gate continued to run five journeys concurrently while runtime schema
  construction was serialized to match production process startup.
- Deletion remained incomplete after an injected OpenSearch timeout and completed only after
  all relational, hot-view, object, and search targets verified absence.
- Retrieval, model, and speech degraded paths returned the documented fallback states.
- Terraform mock planning found and fixed plan-time name-length, unknown `count`, and unknown
  certificate-validation key defects before any AWS apply.

## Environment Notes

The managed shell sandbox blocked macOS SystemConfiguration access for uv and DNS access to the
Terraform Registry. The exact commands were rerun outside that sandbox and passed. These were
environment restrictions, not application failures.

No Terraform apply, AWS mutation, or live stage call was performed. Applicant and candidate-pipeline
visual alignment remains assigned to T212 and T214-T218.
