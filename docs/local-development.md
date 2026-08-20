# Local development

Postgres, DynamoDB and LocalStack run in containers. The API and the worker run on your host,
through the same wiring the deployed environment uses (`create_production_runtime`) — there is no
separate local application runtime to keep in step with production.

Everything the runtime reaches through an endpoint override lands in a container. Everything else
reaches **real AWS or GCP on your credentials, and those calls are billed** — see [What is not
local](#what-is-not-local).

## First run

Docker, Node 22, and [uv](https://docs.astral.sh/uv/) are required.

```bash
make dev-install          # npm ci + uv sync (editable)
cp .env.example .env      # then fill in the AWS and GCP sections
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
| **Cognito** | real AWS | Production uses it; local company-console auth uses the fixed local identity below. |
| Speech-to-Text / Text-to-Speech | real GCP | Billed. One streaming STT connection is opened per answer; question PCM is streamed back over the interview WebSocket. |
| Textract | real AWS | Billed. Needed only for document submission analysis. |
| MediaConvert | real AWS | The placeholder role ARN fails at job submission; a real ARN is needed to post-process a recording. |
| SES | LocalStack | Accepted and **discarded** — nothing has a mailbox. Read an invitation link from the API response or the database. |

There is no deterministic model substitute. Commit `7d977f7` removed the `local-production`
runtime that provided one (along with the demo seed), and restoring it means ~1,300 lines that no
longer match the current domain — `Invitation.create()` now requires `submission_requirements`,
`ApplicantSessionAdapter` requires `store`. If local Bedrock cost becomes a problem, writing a
small `AIModel` stub is the cheaper path, not reviving that tree.

## Logging in

When `APP_ENVIRONMENT=local`, the API accepts the fixed local company identity configured in the
root `.env`. The checked-in example contains the ids used by the local recruiting data:

```bash
# .env
LOCAL_COMPANY_ACCESS_TOKEN=local-company-access-token
LOCAL_COMPANY_ID=00000000-0000-7000-8000-000000000001
LOCAL_COMPANY_USER_ID=00000000-0000-7000-8000-000000000002
LOCAL_COMPANY_IDENTITY_SUBJECT=local-production-company-user
LOCAL_COMPANY_EMAIL=local-company@example.test
```

Give Vite the same token in its ignored local settings file:

```bash
# apps/company-console/.env.local
VITE_LOCAL_COMPANY_TOKEN=local-company-access-token
```

This provider cannot activate in staging or production: any `APP_ENVIRONMENT` other than `local`
continues to use Cognito. The ids still need to name a company user in your local Postgres; the
provider authenticates the request but does not seed application data.

## GCP speech locally

Enable Speech-to-Text and Text-to-Speech in the personal GCP project, then store the service
account JSON outside the repository. Point the ignored root `.env` at that file:

```bash
GOOGLE_APPLICATION_CREDENTIALS=$HOME/.config/whyyou/gcp-service-account.json
STT_PROVIDER=gcp_streaming
TTS_PROVIDER=gcp_streaming
GCP_TTS_VOICE_NAME=ko-KR-Chirp3-HD-Achernar
```

The browser sends 16 kHz mono PCM in roughly 40 ms packets. The API keeps one GCP recognition
stream open until `answer.complete`, persists the combined final transcript once, and sends GCP
TTS PCM back through the same WebSocket. Set both providers to `aws_legacy` to use the previous
AWS path without reverting code.

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
reproduce that, which is why neither app needs `VITE_API_BASE_URL` locally. The development
servers and proxy target use explicit `127.0.0.1` addresses so stale Docker listeners on IPv6
localhost cannot silently receive browser or API traffic.

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
