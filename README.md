# Interview Evidence Platform

Korean-language structured interview SaaS built as two React SPAs, a FastAPI modular monolith,
asynchronous workers and Terraform-managed AWS infrastructure.

## Local Setup

```bash
cp .env.example .env
make bootstrap
make compose-up
```

The bootstrap installs the Python project as a wheel so local commands match the container runtime.
The default local configuration contains only emulator credentials. Never place applicant source
text, answer text, production credentials, raw invitation tokens or signed URLs in configuration or
logs.

### Resetting the local demo data

The seed is idempotent by returning early once a session exists, and the report projections it writes
are immutable by design, so a database seeded by an older revision is not repaired by booting again —
its rows keep pointing at whatever the previous seed wrote. Recreate the volume instead:

```bash
docker compose down -v
make compose-up
```

The symptom to watch for is a review screen whose video will not play while the object is present in
the bucket: that is a stale asset row naming the old key, not a broken player.

### Public repository analysis

Set `GITHUB_TOKEN` in `.env` to analyse public Git submissions at full speed. An anonymous caller
gets 60 GitHub API requests an hour and one repository analysis can spend all of them, so without a
token the analysis is rate limited after a handful of submissions. A read-only token needs no scopes
for public repositories and raises the ceiling to 5000 requests an hour. The token is sent only as a
request header and never reaches a snapshot, an error code or a log line. Leave it empty to stay
anonymous.

## Workspace

```text
apps/company-console/       Company SPA shell and Lane A/D features
apps/applicant-interview/   Applicant SPA shell and Lane A/B/C features
backend/                    FastAPI modular monolith and workers
packages/contracts/         Canonical and generated public contracts
infra/                      Lane A Terraform roots and modules
tests/                      Integration-owned end-to-end, fixture, regression and load tests
```

## Ownership

| Owner       | Paths                                                                                                 |
| ----------- | ----------------------------------------------------------------------------------------------------- |
| Integration | root tools, app shells, backend composition, shared primitives, generated contracts, CI, shared tests |
| Lane A      | company management, applicant access, hiring UI, company migrations, infrastructure                   |
| Lane B      | submissions, document/Git analysis, retrieval, strategy, analysis workers                             |
| Lane C      | interview room, media, session state, recovery, interview workers                                     |
| Lane D      | timeline, Evidence, report, human review, deletion, reporting workers                                 |

Cross-lane calls use only generated contracts, public application interfaces or versioned events.

## Validation

```bash
npm run test:workspace
make contracts-check
make boundaries-check
make migration-check
npm run test:e2e:company
```

`npm run test:workspace` runs formatting, lint, typecheck and every unit, contract, integration
and end-to-end test in one pass. Together with the three `make` targets above it is what the CI
`workspace` job runs.

The browser journeys require the local Compose services and Chrome. They verify the rendered
company console, real API responses and primary route navigation.

Infrastructure is gated separately, because none of it needs AWS credentials and none of it is
reachable from the application suites:

```bash
make infra-format-check infra-validate infra-security-check infra-plan-check
```

CI runs these as a second `infrastructure` job. See `infra/README.md` for the deploy prerequisite
that Terraform cannot own: the `${name}/application/config` secret is created empty and its
`github_token` key must be populated before the application root is first applied.

The complete thin journey is defined in
`specs/001-interview-evidence-platform/quickstart.md`.
