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
  ai-search/
  identity/
  observability/
environments/
  dev/
    foundation/
    data-ai/
    application/
  stage/
  prod/
```

Each environment uses an independent remote-state key, deployment role, KMS key and durable data
store. The dev roots are separated into `foundation`, `data-ai` and `application` so frequently
deployed compute changes cannot plan replacements for retained data resources.

## Safety Rules

- Production data stores are private, encrypted and deletion-protected.
- State locking uses the native S3 lockfile mechanism.
- Saved plans are reviewed before apply.
- ECS task-definition image revisions are owned by the deployment pipeline.
- A lane task never edits another lane's Terraform or application path.
- Secrets, state files, credentials and generated plans are never committed.
