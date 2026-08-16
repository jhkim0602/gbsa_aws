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
and end-to-end test in one pass. It is exactly what CI runs.

The browser journeys require the local Compose services and Chrome. They verify the rendered
company console, real API responses and primary route navigation.

The complete thin journey is defined in
`specs/001-interview-evidence-platform/quickstart.md`.
