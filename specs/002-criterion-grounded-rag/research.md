# Research: Criterion-Grounded Interview RAG

**Date**: 2026-08-15

## R-001 — Structured criteria

**Decision**: Separate `JobRequirement` from `EvaluationCriterion`; connect requirements to criteria
and give each criterion a structured verification guide.

**Rationale**: Requirements describe hiring context while criteria define the stable evaluation axis.

## R-002 — Human publication

**Decision**: Only explicit human publication activates a criterion version. Remove recruiter-facing
interviewer persona configuration and use a system presentation default.

## R-003 — Aurora hybrid retrieval

**Decision**: Store protected text, generated `tsvector`, 1024-dimension vectors and structured
metadata in Aurora. Rank semantic, lexical, exact-symbol and bounded ownership signals.

**Rationale**: Pilot volume fits Aurora and transactional deletion/tenant enforcement.

## R-004 — One embedding space

**Decision**: Use Titan Text Embeddings V2 at 1024 dimensions for criterion guides, candidate chunks
and answer queries. Persist model/version.

## R-005 — Verification map before interview

**Decision**: Precompute claims, conflicts and verification targets. Live interview updates only
progress and performs focused retrieval.

## R-006 — Excerpts in model context

**Decision**: Lane B returns bounded protected excerpts with locators and scores. Lane C supplies
criterion text, target, recent final turns and excerpts to the question model.

## R-007 — Neutral gap classes

**Decision**: Use `not_mentioned`, `claim_found`, `detail_missing`, `source_conflict` and
`ownership_uncertain`. None is an assessment state.

## R-008 — Staged removal

**Decision**: Keep the SearchIndex interface, add Aurora behind it, compare regression results, then
remove OpenSearch infrastructure.
