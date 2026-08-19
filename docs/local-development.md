# Local development

Postgres, DynamoDB and LocalStack run in containers. The API and the worker run on your host,
through the same wiring the deployed environment uses (`create_production_runtime`) — there is no
separate local application runtime to keep in step with production.

Everything the runtime reaches through an endpoint override lands in a container. Everything else
reaches **real AWS on your credentials, and those calls are billed** — see [What is not
local](#what-is-not-local).

## First run

Docker, Node 22, and [uv](https://docs.astral.sh/uv/) are required.

```bash
make dev-install          # npm ci + uv sync (editable)
cp .env.example .env      # then fill in the AWS section
make up                   # containers, then buckets/queues/table, then migrations
```

Then three terminals:

```bash
make api                  # http://localhost:8080
make worker
npm run dev:company       # http://localhost:5173  (or dev:applicant, :5174)
```

Check it came up:

```bash
curl -s localhost:8080/health/ready
# {"status":"ok","dependencies":{...all "ok"...}}
```

`make dev-install`, not `make bootstrap`. Bootstrap installs with `--no-editable`, which copies
`backend/src` into the virtualenv: your edits would not take effect and a new module would import
as though it did not exist. That is correct for CI and for the image, wrong for a workstation.

`make up` is idempotent. Re-run it whenever a container has been reset.

## What is not local

`runtime/aws.py:_client_factory` redirects exactly four services — S3, SQS, SES and Secrets
Manager (via `AWS_ENDPOINT_URL`) — plus DynamoDB, which has its own setting. Anything else ignores
both and goes to the account your credentials name:

| Service | Locally | Consequence |
|---|---|---|
| **Bedrock** | real AWS | Question generation and criterion assessment are billed per call. `BEDROCK_MODEL_ID` must be enabled in `AWS_REGION` or every call fails `AccessDenied`. |
| **Cognito** | real AWS | See [Logging in](#logging-in). |
| Transcribe / Polly | real AWS | Billed. Needed only once an interview produces audio. |
| Textract | real AWS | Billed. Needed only for document submission analysis. |
| MediaConvert | real AWS | The placeholder role ARN fails at job submission; a real ARN is needed to post-process a recording. |
| SES | LocalStack | Accepted and **discarded** — nothing has a mailbox. Read an invitation link from the API response or the database. |

There is no deterministic model substitute. Commit `7d977f7` removed the `local-production`
runtime that provided one (along with the demo seed), and restoring it means ~1,300 lines that no
longer match the current domain — `Invitation.create()` now requires `submission_requirements`,
`ApplicantSessionAdapter` requires `store`. If local Bedrock cost becomes a problem, writing a
small `AIModel` stub is the cheaper path, not reviving that tree.

## Logging in

Cognito has no local substitute, so the console's login needs a real user pool. The `dev`
environment already allows `http://localhost:5173` as a redirect target
(`console_base_urls` in `infra/environments/dev/terraform.tfvars.json`), so point the console at
that pool:

```bash
# apps/company-console/.env.local
VITE_COGNITO_DOMAIN=https://iep-dev-company-868216907365.auth.ap-northeast-2.amazoncognito.com
VITE_COGNITO_CLIENT_ID=<dev pool client id>
VITE_COGNITO_REDIRECT_URI=http://localhost:5173
```

All three or none: `readCompanyAuthConfig` returns null when any is missing, and the console then
falls back to reading a bare `iep_company_token` from `localStorage`, which your local API will
reject. With none of them set you can still work on any screen that does not call the API.

The token is resolved by the API through Cognito `GetUser`, so the user must exist in that pool
and the company must exist in *your local* database — the two are separate stores. A pool user
whose `custom:company_id` names a company your local Postgres has never seen gets a principal
that resolves and then fails on the first query.

## No seed data

A fresh database is empty. There is no demo company, position, or invitation — `make up` creates
infrastructure only. The first company comes from a real signup through the console.

`local_seed.py` used to plant a full demo tenant; it went with `7d977f7` and depends on helper
functions (`ensure_local_demo_recruiting`, `ensure_local_demo_review_projections`, …) that were
removed from every lane's `api/__init__.py` in the same commit.

## Why the frontends proxy `/v1`

The backend installs no CORS middleware. In production each CloudFront distribution routes
`/v1/*` to the ALB beside its own SPA origin, so the browser only ever makes same-origin requests.
Both `vite.config.ts` files proxy `/v1` (with `ws: true`, for the interview transcript) to
reproduce that, which is why neither app needs `VITE_API_BASE_URL` locally. The target is
hardcoded to `http://localhost:8080`; change it in `vite.config.ts` if you move the API.

## Notes

- **`/health/ready` may report `degraded` on the very first request** and `ok` immediately after.
  The probes are synchronous boto3 calls and the first one to each service pays connection setup.
  Only a `degraded` that persists across several requests is real.
- **`DATABASE_URL` must use `psycopg`**, not `asyncpg` — `RequestScopedDatabase` builds a
  synchronous engine, and `asyncpg` is not installed. It fails at connect, not at import.
- **`make migrate` runs Alembic directly**, reading `MIGRATION_DATABASE_URL`. It does not use
  `interview_evidence.migrate`, which resolves the credential from Secrets Manager and only works
  in a deployed environment.
- **`RETRIEVAL_BACKEND=aurora`.** There is no OpenSearch container; `opensearch` would demand
  `OPENSEARCH_ENDPOINT` and fail at startup.
- **Stale containers from the old stack.** If `docker compose` warns about orphans
  (`api-1`, `worker-1`, `mailpit-1`, …) they are left over from when compose ran the whole
  application. Remove them with `docker compose down --remove-orphans`.
