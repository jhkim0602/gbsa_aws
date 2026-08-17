# Data Model: Criterion-Grounded Interview RAG

## Lane A

### JobRequirement

`job_requirement_id`, company/position/version IDs, `requirement_type` (`required|preferred`),
protected statement, priority and `criterion_code`. The code resolves to an EvaluationCriterion in
the same company and criterion version, enforced by `fk_job_requirements_criterion`. Published rows
are immutable.

### CriterionVerificationGuide

Criterion/version IDs, observable dimensions, strong/weak answer signals, follow-up directions,
`max_follow_ups` (0-3) and `time_budget_seconds`.

## Lane B

### RetrievalDocument

| Field | Rule |
|---|---|
| IDs and scope | `retrieval_document_id`, `company_id`, optional `applicant_id`, criterion version |
| Type | requirement, guide, submission chunk or code unit |
| Source | source ID/version, content hash and locator |
| Search | protected text, generated full-text vector, 1024-dimension embedding |
| Provenance | model/version, source type, path, symbol, ownership confidence and metadata |

### CandidateClaim

Neutral extracted claim, source locator, content hash, extraction version and confidence.

### ClaimConflict

Links claims and records a neutral conflict type and verification prompt.

### VerificationTarget

Criterion-scoped target with type (`not_mentioned`, `claim_found`, `detail_missing`,
`source_conflict`, `ownership_uncertain`), objective, missing dimensions, priority, maximum
follow-ups and SourceReference candidates.

### CandidateVerificationMap

Immutable map with criterion/material/retrieval/embedding versions, ordered target IDs, time budget
and readiness state.

## Lane C

### VerificationProgress

Per session/target state: `pending`, `asked`, `partially_addressed`, `addressed`, `skipped_time`,
or `degraded`. Final answer Turn IDs may advance coverage; this is not assessment.

### QuestionRationale

Question Turn, criterion, target, question type, retrieval/generation versions, policy result and
SourceReference IDs.

## Deletion

Deletion includes RetrievalDocuments, vectors, search expressions, claims, conflicts, maps,
progress, rationales and references.
