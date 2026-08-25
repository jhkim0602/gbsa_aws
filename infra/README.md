# Infrastructure Ownership

Lane A owns all Terraform implementation under `infra/`. Terraform manages infrastructure target
state only; application builds, ECS image promotion, Alembic migrations, applicant indexing and
business workflows remain deployment-pipeline or application responsibilities.

## Layout

```text
bootstrap/
  state-backend/
  pipeline-role/
modules/
  network/
  edge/
  compute/
  data/
  async-workflow/
  ai-search/        # Bedrock Guardrail only; retrieval runs in Aurora pgvector
  identity/
  observability/
environments/
  dev/
    foundation/
    data-ai/
    application/
  prod/
```

Each environment uses an independent remote-state key, deployment role, KMS key and durable data
store. The dev roots are separated into `foundation`, `data-ai` and `application` so frequently
deployed compute changes cannot plan replacements for retained data resources.

## Development Environment Lifecycle

The `Manage Dev Infrastructure` GitHub Action owns the complete disposable dev environment. Run it
from `main`, choose `up` or `down`, and choose whether the application source comes from `develop`
or `main`. Destruction requires entering `destroy-dev` in the confirmation field.

`up` applies `foundation`, `data-ai` and `application` in order, builds immutable API and worker
images, runs the database migration, publishes both browser applications and runs the deployed
smoke checks. `down` destroys those roots in reverse order. The Terraform state bucket, GitHub OIDC
role, verified dev sender and `iep-dev/application/config` secret remain in the bootstrap root, so
credentials never pass through GitHub and the sender address does not need verification after every
recreation.

The workflow appears in the Actions tab only after its definition is present on the repository's
default branch. Selecting a different workflow branch is rejected; use the `source_ref` input to
deploy `develop` while the trusted workflow itself continues to run from `main`.

## Runtime Configuration and Secrets

Task configuration is split by whether the value is a credential. Non-secret values are passed as
`task_environment` and appear in the task definition; credentials are passed as `task_secrets`, which
renders a container `secrets` block holding a Secrets Manager reference rather than a value. The
reference is resolved at task start by the **execution** role, not the task role, so the value never
reaches the task definition, a saved plan or a deploy log.

Terraform creates `${name}/application/config` as an empty secret and never writes to it — there is
no `aws_secretsmanager_secret_version` in this tree, deliberately, because a version resource would
put the credential in state. The JSON keys must therefore be populated out of band **before the
first apply of the application root**. A `secrets` entry pointing at a key that does not exist makes
the task fail to start with a `ResourceNotFoundException`, before any application log line exists to
explain it.

| Key                            | Consumer                                 | Consequence if absent                                                                                                                                                                                 |
| ------------------------------ | ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `github_token`                 | analysis worker, public repository fetch | The task will not start. Were the reference removed instead, analysis would fall back to anonymous GitHub — 60 requests an hour, which a single repository analysis can exhaust — and stop mid-fetch. |
| `gcp_project_id`               | Vertex AI and Document AI                | API and worker cannot construct their GCP clients.                                                                                                                                                    |
| `gcp_document_ai_processor_id` | scanned or image-heavy PDF OCR           | The worker cannot construct the hybrid document extractor.                                                                                                                                            |
| `gcp_service_account_json`     | Vertex AI, Speech and Document AI        | GCP clients have no deployed Application Default Credentials and task startup fails.                                                                                                                  |

```sh
SECRET_JSON="$(jq -n \
  --arg github_token "$GITHUB_TOKEN" \
  --arg gcp_project_id "$GCP_PROJECT_ID" \
  --arg gcp_document_ai_processor_id "$GCP_DOCUMENT_AI_PROCESSOR_ID" \
  --arg gcp_service_account_json "$(cat "$GCP_SERVICE_ACCOUNT_FILE")" \
  '$ARGS.named')"
aws secretsmanager put-secret-value \
  --secret-id "$NAME/application/config" \
  --secret-string "$SECRET_JSON"
```

The runtime uses GCP for Gemini generation, streaming speech and Document AI, while embeddings
remain on Amazon Titan. The service-account JSON is injected only into the container process and is
never written to the image or Terraform state. Both deployed applicant bundles expose automated
interview verification and use the same API, retrieval and reporting paths as live interviews.

The Aurora master secret is the one secret the application reads through the SDK
(`AURORA_MASTER_SECRET_ARN`); it is written by RDS, not by hand.

## Verification

`make infra-format-check infra-validate infra-security-check infra-plan-check` needs no AWS
credentials and runs in CI on every pull request. `infra-plan-check` includes a rendered
task-definition probe that decodes `container_definitions` under a mock provider, because the
configuration being well-formed says nothing about what the container is actually told to run —
a worker launched outside the image virtualenv and a credential that reached no container both
passed `validate` and the file-level contracts.

`validate` does not resolve data sources or run provider-side argument validation; only a real
`terraform plan` does. Until a state bucket exists, plan against a throwaway copy of this tree with
the backend block stripped. The `dev/data-ai` and `dev/application` roots read `terraform_remote_state`
and cannot be planned before `dev/foundation` is applied.

## Safety Rules

- Production data stores are private, encrypted and deletion-protected.
- State locking uses the native S3 lockfile mechanism.
- Saved plans are reviewed before apply.
- ECS task-definition image revisions are owned by the deployment pipeline; `command`,
  `environment` and `secrets` stay Terraform-owned, so the pipeline replaces only `.image`.
- A lane task never edits another lane's Terraform or application path.
- Secrets, state files, credentials and generated plans are never committed.

## Known Grant Without a Consumer

`aws_iam_role.media_convert` in `modules/compute` is provisioned and its ARN passed to the task, but
no application code starts a MediaConvert job: the worker remuxes the applicant's `MediaRecorder`
segments with its bundled FFmpeg binary and does not use an AWS-managed transcode. The role is a real
grant with nothing behind it, which is why it is recorded as T311 rather than left unremarked. Removing
it means removing the adapter, the port and the wiring in the same change; it is not this tree's
decision alone.
