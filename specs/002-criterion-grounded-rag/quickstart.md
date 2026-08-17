# Quickstart: Criterion-Grounded Interview RAG

## End-to-End Scenario

1. Start PostgreSQL with vector support and apply migrations.
2. Start API, worker and both SPAs.
3. Create a position with required API design and preferred ECS incident response criteria.
4. Confirm no AI interviewer route or control exists.
5. Submit a PDF mentioning ECS deployment but no incident recovery.
6. Confirm the verification map identifies missing incident/recovery dimensions.
7. Start the interview and answer without describing direct ownership.
8. Confirm the next question targets direct ownership under the same criterion.
9. Finish and inspect question rationale and SourceReference.
10. Confirm only final answers/transcript/video are Evidence.
11. Delete the applicant and verify all vector/search/verification rows are absent.

## Verification Commands

```bash
npm run contracts:check
./scripts/check_migrations.sh
UV_CACHE_DIR=.uv-cache uv run --no-sync ruff check backend/src backend/tests infra/tests
UV_CACHE_DIR=.uv-cache uv run --no-sync mypy backend/src
UV_CACHE_DIR=.uv-cache uv run --no-sync pytest -q backend/tests
npm run typecheck
npm run test --workspaces --if-present
npm run test:e2e:company
UV_CACHE_DIR=.uv-cache uv run --no-sync pytest -q infra/tests/test_terraform_contracts.py
terraform -chdir=infra/environments/prod validate
terraform -chdir=infra/environments/dev/foundation validate
terraform -chdir=infra/environments/dev/data-ai validate
terraform -chdir=infra/environments/dev/application validate
```

## Cost Model

The cutover removes the separate OpenSearch Serverless and Bedrock Knowledge Base runtime. It does
not add another database cluster: criterion embeddings, candidate chunks, claims and verification
maps use the existing Aurora PostgreSQL cluster.

| Cost driver | Before | After |
|---|---|---|
| Search compute | OpenSearch OCU baseline plus Aurora | Existing Aurora ACU only |
| Vector storage | OpenSearch collection | Aurora table and HNSW index |
| Keyword search | OpenSearch index | PostgreSQL `tsvector`/GIN index |
| Embeddings | Deterministic non-semantic vectors | Titan Text Embeddings V2 input usage |
| Question generation | Bedrock model usage | Bedrock model usage with bounded excerpts |

The avoided monthly search baseline is:

```text
regional OpenSearch OCU-hour rate x configured minimum OCU x monthly hours
```

The incremental Aurora cost is workload-dependent ACU, storage and I/O for retrieval rows and
indexes. Track these separately using Aurora ACU hours, database storage, read/write I/O, Bedrock
embedding input tokens and question-model input/output tokens. Candidate excerpts are bounded so
question generation does not resend complete portfolios.

Production still intentionally carries a larger availability baseline: API and worker desired count
are four each, Aurora minimum capacity is 2 ACU, and NAT gateways are deployed per Availability
Zone. Those settings, not `pgvector`, dominate low-traffic monthly cost.

## Cutover and Rollback

- `RETRIEVAL_BACKEND=aurora` is the default and requires no OpenSearch endpoint.
- `RETRIEVAL_BACKEND=opensearch` keeps the legacy application adapter as a short-term rollback
  option.
- Because Terraform no longer provisions OpenSearch, infrastructure must be restored from the
  previous module revision before using that rollback option in a removed environment.
- Do not treat vector similarity, a source document or a verification target as Evidence. Only the
  applicant's final answer, transcript segment or video segment can become Evidence.
