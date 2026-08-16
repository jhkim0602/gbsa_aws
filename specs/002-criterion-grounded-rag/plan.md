# Implementation Plan: Criterion-Grounded Interview RAG

**Branch**: `002-criterion-grounded-rag` | **Date**: 2026-08-15 |
**Spec**: [spec.md](./spec.md)

## Summary

Replace recruiter-facing AI interviewer configuration with guided multi-criterion hiring setup.
Publish immutable job requirements and verification guides, embed those guides and candidate
materials with one semantic model, and perform tenant-scoped hybrid retrieval in Aurora PostgreSQL
using pgvector plus native full-text search. Candidate materials remain SourceReference; final
applicant answers remain the sole competency Evidence.

## Technical Context

**Language/Version**: Python 3.12+; TypeScript 5+; Terraform 1.10+

**Primary Dependencies**: FastAPI, Pydantic, SQLAlchemy 2, Alembic, psycopg, pgvector, boto3;
React 18, Vite, React Router, Vitest, Playwright

**Storage**: Aurora PostgreSQL Serverless v2 with `vector` and full-text search; S3 for objects;
DynamoDB for rebuildable recent context

**Testing**: pytest unit/contract/integration/migration/tenant/deletion tests; Vitest; Playwright;
fixed retrieval and question regression cases

**Target Platform**: Modern browsers; Linux ECS Fargate; AWS `ap-northeast-2`

**Project Type**: Web SaaS monorepo with two SPAs, modular-monolith API, workers and Terraform

**Performance Goals**: p95 hybrid retrieval below 1 second at pilot scale; five criteria published
within 30 minutes; bounded question context; no OpenSearch OCU baseline

**Constraints**: Immutable criterion versions; mandatory tenant/applicant scope; vectors are
retrieval signals only; source materials are never Evidence; no automated hiring/fraud decision

**Scale/Scope**: 1-5 pilot companies, hundreds of applicants, tens of thousands of chunks,
1-5 simultaneous interviews

## Constitution Check

| Principle | Plan evidence | Status |
|---|---|---|
| Criterion-grounded Evidence | Immutable criterion snapshot, VerificationTarget and answer-only Evidence | PASS |
| Tenant isolation/privacy | Scoped retrieval rows and complete deletion targets | PASS |
| Contract-first ownership | Shared contracts merge before consumers | PASS |
| Test-first traceability | Tasks start with contract/domain/regression tests | PASS |
| Recoverable state | VerificationProgress follows existing checkpoints | PASS |
| Fixed technology | Aurora pgvector/FTS and approved Bedrock models | PASS |
| Four-lane workflow | Exclusive paths and integration-owned composition | PASS |

**Post-design re-check**: PASS. No waiver is required.

## Architecture

```text
Company criteria UI
  -> immutable JobRequirement + CriterionVerificationGuide
  -> criterion RetrievalDocument + embedding
                                      |
Candidate PDF/Git -> chunks ----------+-> Aurora hybrid retrieval
                                      +-> CandidateClaim
                                      +-> VerificationTarget
                                      +-> CandidateVerificationMap
                                                |
Final answer -> focused retrieval -> criterion + bounded excerpts
                                                |
                                  question policy + Bedrock
                                                |
                              QuestionRationale + SourceReference
                                                |
Final answer/transcript/video -----------------> Evidence
```

## Rollout

1. Add contracts and schema without changing reads.
2. Write real embeddings and Aurora retrieval rows.
3. Compare Aurora retrieval against fixed regression cases.
4. Switch the Lane B search adapter.
5. Enable verification maps and excerpt-rich question context.
6. Validate deletion, isolation, latency and end-to-end behavior.
7. Remove OpenSearch/Knowledge Base Terraform and environment variables.

Rollback before step 7 switches the adapter back. After step 7, rollback restores the previous
infrastructure revision and reindexes from durable source rows.

## Project Structure

```text
apps/company-console/src/features/hiring/       # Lane A UI
backend/src/interview_evidence/company_management/
backend/src/interview_evidence/submission_analysis/
backend/src/interview_evidence/interview_engine/
backend/src/interview_evidence/reporting/
backend/src/interview_evidence/shared/aws_clients/
backend/src/interview_evidence/runtime/
backend/alembic/versions/{company,submission,interview,reporting,merge}/
infra/modules/{data,ai-search,compute}/
```

**Structure Decision**: Preserve the modular monolith and four Lane boundaries. Lane A owns
criterion authoring, Lane B retrieval and verification maps, Lane C live progress and questions,
and Lane D review/deletion.

## Complexity Tracking

No constitutional violations. The temporary dual retrieval path has an explicit removal task.
