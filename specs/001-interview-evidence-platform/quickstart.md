# Quickstart Validation: Interview Evidence Platform

**Purpose**: Prove the thin end-to-end pilot and each lane independently.

This guide describes the commands and expected outcomes that implementation tasks must make real.
It contains no production implementation. Run from the repository root.

## Prerequisites

- Git with four-worktree support
- Docker with Compose
- Python 3.12+ and the repository's locked Python environment tool
- Node.js compatible with the committed workspace toolchain and the committed package manager
- Terraform 1.10+ for infrastructure validation
- An approved AWS development profile only for the optional live-AWS scenarios

No local unit or contract test requires permanent AWS credentials.

## 1. Bootstrap the Local Environment

```bash
make bootstrap
make compose-up
make migrate
make seed-contract-fixtures
npm run test:e2e:company
```

Expected:

- both SPAs and the API health endpoints become ready;
- the host Chrome renders the company Overview, loads company/position API data and navigates
  through the position and hiring workspaces without browser or HTTP errors;
- local PostgreSQL, object/queue emulation, DynamoDB emulation and search are healthy;
- four Alembic lane heads plus the current integration merge head are visible;
- the seeded companies and applicants use opaque IDs and no secret appears in console output.

## 2. Verify Contract and Ownership Gates

```bash
make contracts-generate
make contracts-check
make boundaries-check
make migration-check
```

Expected:

- generated Python and TypeScript contracts match canonical schemas;
- every route and event has exactly one owner lane;
- no backend module imports another module's private domain, model or repository path;
- every lane has at most one unmerged migration head;
- the working tree remains clean after generation.

## 3. Run the Foundation Test Set

```bash
uv run --no-sync pytest backend/tests/contract backend/tests/unit/shared
```

Expected:

- missing or wrong `TenantContext` is rejected;
- company and applicant authentication cannot cross invitation or tenant scope;
- error envelopes contain a safe request ID and no protected text;
- outbox duplicate delivery is idempotent;
- shared fakes conform to the same contracts as producers.

## 4. Validate Each Lane Independently

Each lane uses contract fakes for dependencies that have not merged.

### Lane A — Platform and Hiring

```bash
uv run --no-sync pytest backend/tests/unit/company_management backend/tests/integration/company_management
```

Expected journey:

1. authenticate a company fixture;
2. create a position and criterion version;
3. publish the criterion version for the position;
4. create a position-owned invitation and exchange its one-time token;
5. verify identity and record consent;
6. demonstrate that a second company cannot read any created object.

### Lane B — Submission and RAG

```bash
uv run --no-sync pytest backend/tests/unit/submission_analysis backend/tests/integration/submission_analysis
```

Expected journey:

1. use a contract fixture for an authorized, consented invitation;
2. register a Korean PDF and a public test repository;
3. show per-source ready/partial/failed status;
4. retrieve a document chunk and an exact code symbol only inside applicant scope;
5. create a strategy linked to the fixed criterion version and source locations;
6. show that low ownership confidence produces a verification question, not a claim.

### Lane C — Live Interview

```bash
uv run --no-sync pytest backend/tests/unit/interview_engine backend/tests/integration/interview_engine
```

Expected journey:

1. use a contract fixture for a ready strategy;
2. start a server-authoritative session;
3. present one question, stream an answer and finalize it;
4. repeat `answer.complete` with the same idempotency key and observe one Turn;
5. generate one safe next question;
6. disconnect, resume from the checkpoint and complete without duplicate Turns;
7. force retrieval and speech failures and observe safe fallback states.

### Lane D — Evidence and Review

```bash
uv run --no-sync pytest backend/tests/unit/reporting backend/tests/integration/reporting
```

Expected journey:

1. use a completed-session fixture with final Turns, transcript and media ranges;
2. generate a report with confirmed, partial, insufficient and follow-up states;
3. reject a confirmed item with no valid applicant-answer Evidence;
4. seek from Evidence to the linked transcript and video range, following the signed playback URL to
   the assembled recording rather than trusting the asset status — a `ready` asset naming an object
   that was never written reads identically to a playable one until the URL is fetched;
5. append a human override and preserve the AI original;
6. reject a final decision request without a human company principal;
7. run deletion and leave it incomplete until every store verifies absence.

## 5. Run the Merged Thin End-to-End Journey

```bash
uv run --no-sync pytest backend/tests/integration/cross_module tests/e2e/test_thin_journey.py
```

Expected:

```text
company criterion
-> position-owned invitation
-> applicant token exchange, identity and consent
-> PDF/public Git submission and strategy
-> device check and interview start
-> one finalized applicant answer and one follow-up
-> reconnect and completion
-> transcript/media processing
-> report with answer Evidence
-> human review and final decision
```

At the end:

- SourceReference points to the exact submitted source used for the question;
- Evidence points only to a final applicant Turn and valid transcript/video interval;
- the criterion version is identical across invitation, strategy, session and report;
- AI has no route, role or worker path to the final decision;
- another tenant cannot retrieve any object, search result, hot-view item or signed media locator.

## 6. Run Failure, Privacy and Regression Gates

```bash
uv run --no-sync pytest backend/tests/integration/interview_engine/test_idempotency.py \
  backend/tests/integration/interview_engine/test_session_recovery.py \
  tests/e2e/test_tenant_isolation.py tests/e2e/test_deletion_residue.py
make test-ai-regression
make test-load-pilot
```

Expected:

- duplicate commands/jobs create no duplicate durable state;
- interrupted sessions resume from the last final Turn;
- every cross-tenant request and search returns no protected data;
- deletion verifies absence across relational, hot-view, object and search stores;
- forbidden, duplicate, multi-part and unsupported questions are blocked;
- fixed Korean and Korean/English-code fixtures preserve retrieval and Evidence thresholds;
- five concurrent interview journeys do not starve the real-time path.

## 7. Validate Infrastructure Without Applying

```bash
make infra-format-check
make infra-validate
make infra-security-check
make infra-plan-check
```

Expected:

- environment and state keys are separated;
- no public S3 data bucket or public database is planned;
- state encryption, native lockfile use, IAM boundaries and deletion protection are present;
- Terraform does not run builds, database migrations, indexing or business workflows;
- image revisions and auto-scaled desired count do not cause Terraform ownership drift.

An apply is never part of local quickstart. A dev or prod apply requires the reviewed saved plan and
human approval defined by the deployment process.

## 8. Four-Branch Integration Drill

Follow [parallel-workstreams.md](./parallel-workstreams.md), then run after each lane merge:

```bash
make contracts-check
make migration-check
uv run --no-sync pytest backend/tests/unit backend/tests/integration tests/e2e/test_thin_journey.py
```

Expected:

- no manual edit to generated contracts;
- no unresolved same-lane or cross-lane migration head;
- all previously merged lane tests remain green;
- exactly one cross-lane fake is replaced at each planned integration step;
- final merged behavior matches the same contracts used by all lane branches.

## 9. Final Spec Convergence

After implementation and all gates:

```text
$speckit-converge
```

Any difference among spec, plan, tasks and implementation becomes a new task. Do not close a gap by
silently changing behavior or weakening the constitution.

## 10. Validate the UI Reference Baseline

The recruiter operations baseline is verified from the running application rather than retained
reference captures.

```bash
npm run test --workspace apps/company-console -- --run
npm run typecheck --workspace apps/company-console
npm run build --workspace apps/company-console
npm run test:e2e:company
```

Expected:

- the company dashboard, position inspection, recruiting calendar and guided hiring route use real
  API data only;
- accepted desktop and mobile screenshots are written under `tests/browser/artifacts/`;
- the browser moves through `/company`, `/positions` and `/hiring` without console errors or
  unexpected 4xx/5xx responses;
- a stale hashed asset returns 404 instead of the SPA document;
- the 390px company layout uses overlay navigation and keeps the current input and primary action
  visible;
- future applicant and candidate-pipeline alignment remains tracked by T212 and T214-T218 rather
  than being represented by mock screens.

## Requirement and Quality-Gate Evidence

The final validation report MUST include:

- executed commit hash and environment;
- task, FR, SC and QG IDs;
- contract and migration versions;
- pass/fail result with artifact location;
- retry, degraded-mode and deletion residue observations;
- reviewer identity for human-only release gates.
