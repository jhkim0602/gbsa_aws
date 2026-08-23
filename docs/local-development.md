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

### Windows PowerShell

Windows does not need Make or WSL. The PowerShell entry point mirrors the Makefile and also starts
the four worker processes needed by the parallel analysis pipeline:

```powershell
Copy-Item .env.example .env   # first run only; then fill in AWS/GCP settings
.\scripts\local.ps1 install
.\scripts\local.ps1 doctor     # validates required values and Google credentials
.\scripts\local.ps1 up
```

Open four PowerShell terminals from the repository root:

```powershell
.\scripts\local.ps1 api        # http://127.0.0.1:8080
.\scripts\local.ps1 worker     # four workers; Ctrl+C stops all four
.\scripts\local.ps1 company    # http://127.0.0.1:5173
.\scripts\local.ps1 applicant  # http://127.0.0.1:5174
```

Use `.\scripts\local.ps1 status` for container/API health, `.\scripts\local.ps1 test` for all
unit tests, `.\scripts\local.ps1 check` for the complete local CI check, and
`.\scripts\local.ps1 down` to stop the containers. If script execution is disabled for only the
current shell, run `Set-ExecutionPolicy -Scope Process Bypass` once in that shell.

## What is not local

`runtime/aws.py:_client_factory` redirects exactly four services — S3, SQS, SES and Secrets
Manager (via `AWS_ENDPOINT_URL`) — plus DynamoDB, which has its own setting. Anything else ignores
both and goes to the account your credentials name:

| Service | Locally | Consequence |
|---|---|---|
| **Vertex AI Gemini** | real GCP by default | Question generation, criterion assessment, and 1024-dimensional embeddings are billed per call. |
| **Bedrock** | optional real AWS fallback | Set `AI_PROVIDER=aws` and `EMBEDDING_PROVIDER=aws` to restore Claude and Titan. `BEDROCK_MODEL_ID` must be enabled in `AWS_REGION`. |
| **Cognito** | real AWS | Production uses it; local company-console auth uses the fixed local identity below. |
| Speech-to-Text / Text-to-Speech | real GCP | Billed. One streaming STT connection is opened per answer; question PCM is streamed back over the interview WebSocket. |
| Document AI | real GCP fallback | Native text PDFs stay local; scanned or image-heavy PDFs use billed Document AI OCR. |
| MediaConvert | real AWS | The placeholder role ARN fails at job submission; a real ARN is needed to post-process a recording. |
| Invitation email | Mailpit SMTP | Delivered to the local mailbox at `http://127.0.0.1:8025`. Production continues to use SES. |

There is no deterministic model substitute. Commit `7d977f7` removed the `local-production`
runtime that provided one (along with the demo seed), and restoring it means ~1,300 lines that no
longer match the current domain — `Invitation.create()` now requires `submission_requirements`,
`ApplicantSessionAdapter` requires `store`. If local model cost becomes a problem, writing a
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
VITE_USE_MOCK_DATA=false
```

The company console uses the real local API by default. Set `VITE_USE_MOCK_DATA=true` only when
you intentionally want the browser-only sample positions; invitations created in that mode do not
reach Mailpit or the local database.

This provider cannot activate in staging or production: any `APP_ENVIRONMENT` other than `local`
continues to use Cognito. The ids still need to name a company user in your local Postgres; the
provider authenticates the request but does not seed application data.

## GCP AI, documents, and speech locally

Enable Vertex AI, Speech-to-Text, Text-to-Speech, and Document AI in the personal GCP project.
Grant the service account Vertex AI User access, store its JSON outside the repository, create a
Document OCR processor, and point the ignored root `.env` at that file and processor:

```bash
GOOGLE_APPLICATION_CREDENTIALS=$HOME/.config/whyyou/gcp-service-account.json
AI_PROVIDER=gcp
EMBEDDING_PROVIDER=gcp
GCP_VERTEX_AI_LOCATION=global
GCP_VERTEX_AI_MODEL_ID=gemini-2.5-flash
GCP_VERTEX_AI_EMBEDDING_MODEL_ID=gemini-embedding-001
STT_PROVIDER=gcp_streaming
TTS_PROVIDER=gcp_streaming
DOCUMENT_OCR_PROVIDER=gcp_document_ai
GCP_DOCUMENT_AI_PROJECT_ID=your-gcp-project-id
GCP_DOCUMENT_AI_LOCATION=us
GCP_DOCUMENT_AI_PROCESSOR_ID=your-document-ocr-processor-id
GCP_TTS_VOICE_NAME=ko-KR-Chirp3-HD-Achernar
```

Vertex AI defaults to `GCP_DOCUMENT_AI_PROJECT_ID`; set `GCP_VERTEX_AI_PROJECT_ID` only when the
generation project differs. Switching embedding providers requires existing materials to be
analyzed again. Retrieval filters by embedding model and version so GCP and Titan vectors are
never compared with each other.

The browser sends 16 kHz mono PCM in roughly 40 ms packets. The API keeps one GCP recognition
stream open until `answer.complete`, persists the combined final transcript once, and sends GCP
TTS PCM back through the same WebSocket. Set both speech providers to `aws_legacy` to use the
previous AWS speech path without reverting code.

## Backfill existing AI-assistant reports

Reports created before the recruiting-assistant projection existed, or before switching the
embedding provider, do not belong to the current vector search space. The UI distinguishes this
state from a position that has no final reports. Backfill only the missing/current-provider
projections with:

```bash
make assistant-backfill
```

The command is idempotent. It skips reports that already have documents for the configured
`EMBEDDING_PROVIDER` model and version, and replaces stale-provider projections using deterministic
document ids.

## Automated interview locally

The applicant interview environment-check screen exposes two development-only actions:

- **빠른 자동 면접 실행** records a synthetic local video and submits generated Korean text
  answers without opening STT. Question generation, GCP TTS, interview progression, media upload,
  worker processing, and report generation still use the normal application path.
- **음성 포함 자동 면접 실행** sends the checked-in Korean WAV fixture as 16 kHz PCM, so the
  real GCP streaming STT path is included as well.

Run the API, worker, applicant app, and company console before starting. The automated run skips
the browser equipment permission prompt, completes each question, then opens
`http://127.0.0.1:5173/review/{session_id}?auto=1`. That page polls until the worker has created the
report and timeline. `VITE_COMPANY_CONSOLE_URL` can override the console origin when needed.

Both entry points are local-only: Vite only renders them in development, and the API accepts the
`answer.automated` WebSocket message only when `APP_ENVIRONMENT=local`.

The analysis worker reads the uploaded PDF from local S3-compatible storage and first attempts
native PDF text extraction inside the worker. Text PDFs continue directly into the existing
chunking and interview-strategy pipeline without a Document AI call. Image-heavy, scanned, mixed,
or unreadable PDFs fall back to the configured Document OCR processor. Only those fallback calls
are billed to the GCP project in `GCP_DOCUMENT_AI_PROJECT_ID`. The same flow runs after deployment;
"native" means inside the deployed worker process, not only on a developer laptop.

## No seed data

A fresh database is empty. There is no demo company, position, or invitation — `make up` creates
infrastructure only. The first company comes from a real signup through the console.

`local_seed.py` used to plant a full demo tenant; it went with `7d977f7` and depends on helper
functions (`ensure_local_demo_recruiting`, `ensure_local_demo_review_projections`, …) that were
removed from every lane's `api/__init__.py` in the same commit.

`scripts/cleanup_test_positions.sql` went with it — the script that dropped every position
except the seeded demo one so a browser run started from a known roster. Its guard test
(`backend/tests/integration/migrations/test_cleanup_script_matches_the_schema.py`) outlived the
script by one commit and was removed on 2026-08-20. **If either is reinstated, restore both**: the
test existed because the script rots silently, and it had already caught two real breakages — a
missing `session_checkpoints` (and friends), and `submission_chunks` ordered after the analyses it
references. Each surfaced as two unrelated-looking browser failures rather than as a cleanup error,
because every foreign key here is `NO ACTION`, so a parent deleted before its children aborts the
whole transaction instead of cascading.

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
