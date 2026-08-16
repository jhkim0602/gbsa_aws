# Tasks: Criterion-Grounded Interview RAG

**Input**: Design documents from `/specs/002-criterion-grounded-rag/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`

**Tests**: Contract, tenant-isolation, deletion, regression, UI and end-to-end tests are required by
FR-030 and the repository constitution. Each implementation phase starts with a failing governing
test.

**Ownership**: Integration owns shared contracts, composition, migration merge heads and end-to-end
validation. Lane A owns company configuration, Lane B retrieval and verification maps, Lane C live
questioning, and Lane D review/deletion projections.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it edits different files and has no incomplete dependency.
- **[Story]**: Maps the task to a user story in `spec.md`.
- Every task includes the exact implementation path.

## Phase 1: Setup and Shared Contracts

**Purpose**: Establish contract-first compatibility and local pgvector support.

- [X] T001 [Integration] Add criterion-version request/response fields and question-rationale review fields to `packages/contracts/openapi/root.yaml`, `packages/contracts/openapi/paths/company/paths.yaml`, and `packages/contracts/openapi/paths/reporting/paths.yaml`; regenerate `packages/contracts/generated/`
- [X] T002 [P] [Integration] Add `pgvector` Python dependency and vector-enabled local PostgreSQL configuration in `pyproject.toml`, `uv.lock`, and `compose.yaml`
- [X] T003 [P] [Integration] Add shared Bedrock embedding port and production Titan V2 adapter in `backend/src/interview_evidence/shared/aws_clients/ports.py` and `backend/src/interview_evidence/shared/aws_clients/production.py`
- [X] T004 [Integration] Update runtime composition and environment validation for embedding and Aurora retrieval adapters in `backend/src/interview_evidence/runtime/production.py`, `backend/src/interview_evidence/runtime/local_production.py`, and `backend/src/interview_evidence/runtime/parity.py`

---

## Phase 2: Foundational Schema and Safety

**Purpose**: Add immutable criterion configuration and tenant-scoped retrieval storage before user
stories consume it.

- [X] T005 [P] [US1] Write failing criterion contract, versioning and tenant tests in `backend/tests/contract/company_management/test_http_contract.py`, `backend/tests/unit/company_management/test_criterion_versioning.py`, and `backend/tests/integration/company_management/test_tenant_isolation.py`
- [X] T006 [P] [US2] Write failing pgvector schema, retrieval isolation and deletion tests in `backend/tests/integration/migrations/test_lane_merge.py`, `backend/tests/integration/submission_analysis/test_retrieval_isolation.py`, and `backend/tests/integration/submission_analysis/test_deletion_targets.py`
- [X] T007 [Lane A] Add immutable job-requirement and criterion-verification-guide schema in `backend/alembic/versions/company/a_004_criterion_grounding.py` and merge it in `backend/alembic/versions/merge/m_002_criterion_grounded_rag.py`
- [X] T008 [Lane B] Add `vector` extension plus retrieval document, claim, conflict, verification target and verification map schema in `backend/alembic/versions/submission/b_002_pgvector_verification.py` and update `backend/alembic/versions/merge/m_002_criterion_grounded_rag.py`
- [X] T009 [Lane C] Add verification-progress and question-rationale schema in `backend/alembic/versions/interview/c_002_verification_progress.py` and update `backend/alembic/versions/merge/m_002_criterion_grounded_rag.py`
- [X] T010 [Integration] Verify all new rows require company, applicant/invitation and criterion-version scope and migrate cleanly through `backend/tests/integration/migrations/test_lane_merge.py`

**Checkpoint**: Shared contracts and additive schema are available without changing existing reads.

---

## Phase 3: User Story 1 - Publish Recruiter-Friendly Hiring Criteria (Priority: P1)

**Goal**: Replace AI-interviewer configuration with guided multi-criterion, requirement and
verification-guide authoring.

**Independent Test**: A recruiter creates required/preferred requirements and at least five
criteria, publishes them, and reads the same immutable version without any interviewer persona or
voice controls.

### Tests

- [X] T011 [P] [US1] Write failing company-console journey tests for multiple criteria, required/preferred requirements, validation and absence of interviewer controls in `apps/company-console/src/features/hiring/__tests__/hiringJourney.test.tsx` and `apps/company-console/src/app/__tests__/featureRoutes.test.tsx`
- [X] T012 [P] [US1] Write failing Lane A service tests for requirement links, guide bounds, prohibited content and immutable publication in `backend/tests/unit/company_management/test_criterion_versioning.py` and `backend/tests/integration/company_management/test_lane_a_quickstart.py`

### Implementation

- [X] T013 [P] [US1] Add `JobRequirement` and `CriterionVerificationGuide` domain types and validation in `backend/src/interview_evidence/company_management/domain/criteria.py`
- [X] T014 [US1] Persist and retrieve requirements and verification guides in `backend/src/interview_evidence/company_management/repositories/postgres.py`
- [X] T015 [US1] Extend criterion publication services and public HTTP schemas in `backend/src/interview_evidence/company_management/application/criteria_service.py`, `backend/src/interview_evidence/company_management/application/public.py`, and `backend/src/interview_evidence/company_management/api/company_routes.py`
- [X] T016 [P] [US1] Replace the single hard-coded criterion form with requirement and multi-criterion editors in `apps/company-console/src/features/hiring/types.ts`, `apps/company-console/src/features/hiring/steps/HiringSteps.tsx`, and `apps/company-console/src/features/hiring/HiringWorkspace.tsx`
- [X] T017 [P] [US1] Remove recruiter-facing interviewer-profile navigation, route, picker and obsolete tests in `apps/company-console/src/app/layouts/CompanyShell.tsx`, `apps/company-console/src/app/featureRoutes.ts`, `apps/company-console/src/app/routeAdapters.tsx`, `apps/company-console/src/features/hiring/components/InterviewerProfilePicker.tsx`, and `apps/company-console/src/features/company/__tests__/interviewerProfiles.test.tsx`
- [X] T018 [US1] Add accessible validation, weight summary and publication preview styling in `apps/company-console/src/features/hiring/hiring.css` and verify the journey at desktop and mobile widths

**Checkpoint**: Company criteria can be published independently and existing invitations retain
their original criterion version.

---

## Phase 4: User Story 2 - Build the Candidate Verification Map (Priority: P1)

**Goal**: Embed company criteria and candidate materials in the same semantic space, perform
tenant-scoped Aurora hybrid retrieval, and create neutral verification targets.

**Independent Test**: The ECS regression fixture distinguishes deployment evidence from unverified
incident analysis, recovery ownership and prevention details while preserving source locators.

### Tests

- [X] T019 [P] [US2] Write failing unit tests for Titan embedding validation, hybrid rank fusion and exact-symbol boosts in `backend/tests/unit/submission_analysis/test_hybrid_retriever.py` and `backend/tests/unit/submission_analysis/test_pgvector_adapter.py`
- [X] T020 [P] [US2] Add fixed claim, missing-detail, neutral-conflict and ownership-uncertainty fixtures and tests in `backend/tests/integration/submission_analysis/test_verification_map.py`
- [X] T021 [P] [US2] Add regression tests proving SHA-256 vectors are rejected as semantic embeddings in `backend/tests/integration/submission_analysis/test_analysis_pipeline.py`

### Implementation

- [X] T022 [P] [US2] Add retrieval-document, claim, conflict, target and verification-map domain models in `backend/src/interview_evidence/submission_analysis/domain/retrieval.py` and export them from `backend/src/interview_evidence/submission_analysis/domain/__init__.py`
- [X] T023 [US2] Implement tenant-scoped pgvector, PostgreSQL full-text and exact-symbol persistence/query logic in `backend/src/interview_evidence/submission_analysis/repositories/postgres.py` and `backend/src/interview_evidence/submission_analysis/adapters/postgres_hybrid.py`
- [X] T024 [US2] Replace deterministic SHA embeddings with the approved embedding port and index criterion guides plus candidate chunks in `backend/src/interview_evidence/workers/analysis/pipeline.py` and `backend/src/interview_evidence/submission_analysis/application/retrieval.py`
- [X] T025 [US2] Implement neutral claim extraction and immutable verification-map construction in `backend/src/interview_evidence/submission_analysis/application/verification_map.py`
- [X] T026 [US2] Expose `index_criterion_version`, `build_verification_map`, `get_verification_map`, excerpt-rich `retrieve_context` and locator resolution through `backend/src/interview_evidence/submission_analysis/application/public.py`
- [X] T027 [US2] Include all retrieval rows, vectors, claims, conflicts and maps in deletion and absence verification in `backend/src/interview_evidence/submission_analysis/application/deletion_targets.py`

**Checkpoint**: Aurora retrieval and verification maps pass fixed regressions without OpenSearch
being required for the tested path.

---

## Phase 5: User Story 3 - Ask Criterion-Grounded Questions and Follow-Ups (Priority: P1)

**Goal**: Select one verification target at a time, send bounded criterion/source excerpts to the
model, and advance only from final applicant answers.

**Independent Test**: A missing direct-ownership answer produces one ownership follow-up under the
same criterion, then moves to the next unresolved criterion after it is addressed.

### Tests

- [X] T028 [P] [US3] Write failing context-builder and question-policy tests for criterion text, source excerpts, one target per question and neutral wording in `backend/tests/unit/interview_engine/test_context_builder.py` and `backend/tests/unit/interview_engine/test_question_policy.py`
- [X] T029 [P] [US3] Write failing live orchestration tests for target priority, bounded follow-ups, final-answer-only progress and degraded common questions in `backend/tests/integration/interview_engine/test_interview_orchestration.py` and `backend/tests/integration/interview_engine/test_degraded_modes.py`

### Implementation

- [X] T030 [US3] Extend Lane B retrieval client types to carry target metadata, bounded excerpts and versions in `backend/src/interview_evidence/interview_engine/adapters/retrieval_client.py`
- [X] T031 [US3] Build criterion-grounded prompt context without source IDs as stand-ins for content in `backend/src/interview_evidence/interview_engine/application/context_builder.py` and `backend/src/interview_evidence/interview_engine/application/question_generator.py`
- [X] T032 [US3] Implement verification-target selection, progress transitions and follow-up budgets in `backend/src/interview_evidence/interview_engine/application/interview_plan.py` and `backend/src/interview_evidence/interview_engine/application/interview_service.py`
- [X] T033 [US3] Persist `QuestionRationale` and progress checkpoints from live handlers in `backend/src/interview_evidence/interview_engine/repositories/postgres.py` and `backend/src/interview_evidence/interview_engine/api/live_handlers.py`
- [X] T034 [US3] Include verification progress and rationale rows in recovery and deletion paths in `backend/src/interview_evidence/interview_engine/application/recovery_service.py` and `backend/src/interview_evidence/interview_engine/application/deletion_targets.py`

**Checkpoint**: A complete live interview runs on immutable company criteria and candidate
verification targets, with safe degraded behavior.

---

## Phase 6: User Story 4 - Review Question Rationale and Evidence Separately (Priority: P2)

**Goal**: Show why a question was asked while preserving the distinction between source material
and answer-derived Evidence.

**Independent Test**: A reviewer opens a question and sees criterion, neutral verification
objective, protected source excerpt/locator and actual answer Evidence in separate sections.

### Tests

- [X] T035 [P] [US4] Write failing reporting contract and Evidence-separation tests for question rationale in `backend/tests/contract/reporting/test_http_contract.py` and `backend/tests/unit/reporting/test_source_evidence_separation.py`
- [X] T036 [P] [US4] Write failing company-console review journey tests in `apps/company-console/src/features/review/__tests__/reviewJourney.test.tsx`

### Implementation

- [X] T037 [US4] Project rationale and protected SourceReference fields through `backend/src/interview_evidence/reporting/domain/timeline.py`, `backend/src/interview_evidence/reporting/application/timeline_service.py`, and `backend/src/interview_evidence/reporting/application/public.py`
- [X] T038 [US4] Extend the reporting HTTP route and repository query in `backend/src/interview_evidence/reporting/api/company_routes.py` and `backend/src/interview_evidence/reporting/repositories/postgres.py`
- [X] T039 [US4] Render criterion, objective and source excerpts separately from Evidence in `apps/company-console/src/features/review/types.ts`, `apps/company-console/src/features/review/TimelineView.tsx`, and `apps/company-console/src/features/review/review.css`
- [X] T040 [US4] Extend the deletion manifest to verify rationale and all retrieval derivatives are absent in `backend/src/interview_evidence/reporting/application/deletion_service.py` and `backend/tests/integration/reporting/test_deletion_manifest.py`

---

## Phase 7: Cutover, Cost Reduction and End-to-End Validation

**Purpose**: Prove the replacement path, remove the OpenSearch baseline and validate the complete
workflow.

- [X] T041 [P] [Integration] Add Aurora retrieval latency, relevance, tenant-isolation and cost-comparison regression coverage in `backend/tests/integration/submission_analysis/test_lane_b_quickstart.py` and `docs/aws-ai-rag-flow.json`
- [X] T042 [Integration] Switch production composition to Aurora hybrid retrieval, retain an explicit rollback flag, and remove unused OpenSearch environment dependencies in `backend/src/interview_evidence/runtime/production.py` and `infra/modules/compute/main.tf`
- [X] T043 [Integration] After T041-T042 pass, remove OpenSearch Serverless and Bedrock Knowledge Base resources from `infra/modules/ai-search/main.tf` and update root Terraform wiring
- [X] T044 [P] [Integration] Update AWS architecture and cost documentation in `docs/aws-architecture.svg`, `docs/aws-ai-rag-flow.svg`, and `specs/002-criterion-grounded-rag/quickstart.md`
- [X] T045 [Integration] Run backend contract/unit/integration/migration/deletion suites, company-console typecheck/Vitest, Playwright hiring-review journeys and Terraform validation from `specs/002-criterion-grounded-rag/quickstart.md`
- [X] T046 [Integration] Run `$speckit-analyze`, resolve cross-artifact inconsistencies, run `$speckit-converge`, and mark only verified tasks complete in `specs/002-criterion-grounded-rag/tasks.md`

## Phase 8: Applicant Project References

- [X] T047 [Lane B] Allow an applicant to register up to three public Git project URLs, enforce the same limit in the submission service, and cover the applicant journey and server boundary with regression tests.
- [X] T048 [Integration] Use the injected application clock when calculating applicant-session cookie lifetime so frozen-clock tests and runtime session expiry remain consistent.

## Dependencies and Execution Order

### Phase Dependencies

- Phase 1 precedes all consumers of shared contracts and embeddings.
- Phase 2 depends on Phase 1 and blocks all user stories.
- User Story 1 and User Story 2 can proceed after Phase 2; criterion indexing consumes published
  versions from User Story 1.
- User Story 3 depends on the public verification-map and retrieval contracts from User Story 2.
- User Story 4 depends on persisted rationale from User Story 3.
- Cutover and OpenSearch removal require every story checkpoint and fixed regression suite to pass.

### Safety Gates

- Generated contracts are changed only through the repository generation command.
- No candidate source text, answer, embedding input or signed URL may enter logs or events.
- A retrieval row is never accepted as Evidence.
- OpenSearch resources are not removed before Aurora parity, tenant isolation, deletion and rollback
  tests pass.
- Published criterion versions remain immutable and existing invitations keep their version.

## Implementation Strategy

1. Deliver User Story 1 as the recruiter-facing MVP.
2. Dual-write semantic embeddings and validate Aurora retrieval using fixed fixtures.
3. Enable verification maps and criterion-grounded questioning behind a runtime flag.
4. Add rationale review, deletion verification and end-to-end coverage.
5. Cut over production and remove the unused OpenSearch baseline only after all gates pass.
