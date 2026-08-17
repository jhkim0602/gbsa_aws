---
description: "Dependency-ordered, four-lane implementation tasks"
---

# Tasks: Interview Evidence Platform

**Input**: Design documents from `/specs/001-interview-evidence-platform/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/),
[parallel-workstreams.md](./parallel-workstreams.md)

**Tests**: Required by Constitution Principle IV. For each domain rule or contract, commit the test
before or with implementation and observe it fail against the previous state.

**Organization**: Setup and Foundation are integration-owned. After `foundation-v1`, US1/US2/US3/US4
map one-to-one to Lane A/B/C/D and run in four worktrees.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it writes a different owned file and has no incomplete dependency.
- **[Story]**: User story mapping for traceability.
- Every description names the owner, requirement/gate coverage and an exact file path.

## Phase 1: Setup (Integration Owner)

**Purpose**: Create the shared monorepo skeleton without implementing domain behavior.

- [X] T001 Integration — Define JavaScript workspaces and root scripts in `package.json`
- [X] T002 [P] Integration — Define the locked Python workspace, FastAPI and test dependencies in `pyproject.toml`
- [X] T003 [P] Integration — Define local PostgreSQL, DynamoDB, S3/SQS emulation and search services in `compose.yaml`
- [X] T004 Integration — Add the documented bootstrap, generation and test entry points to `Makefile`
- [X] T005 [P] Integration — Document safe local configuration with no credentials in `.env.example`
- [X] T006 [P] Integration — Scaffold the company Vite application and feature slots in `apps/company-console/package.json`
- [X] T007 [P] Integration — Scaffold the applicant Vite application and feature slots in `apps/applicant-interview/package.json`
- [X] T008 [P] Integration — Scaffold the Python package and API/worker entry points in `backend/src/interview_evidence/__init__.py`
- [X] T009 [P] Lane A — Create the approved Terraform directory roots in `infra/README.md` (PD-26, QG-16)
- [X] T010 [P] Integration — Create shared end-to-end, fixture, regression and load test roots in `tests/README.md`
- [X] T011 [P] Integration — Configure editor, Markdown, Python, TypeScript and Terraform formatting in `.editorconfig`
- [X] T012 [P] Integration — Add API and worker container build targets in `backend/Containerfile`
- [X] T013 Integration — Document directory ownership and local setup in `README.md`
- [X] T014 Integration — Add baseline format, type, unit and artifact-drift jobs in `.github/workflows/ci.yml`

**Checkpoint**: All planned paths exist; no domain behavior has been implemented.

---

## Phase 2: Foundation (Blocks All Four Lanes)

**Purpose**: Freeze contracts, shared primitives, fakes, migration rules and CI before branching.

**Critical**: Complete and review `checklists/parallel-readiness.md`, then tag one common
`foundation-v1` commit. No lane branches from an earlier commit.

- [X] T015 Integration — Copy and split the canonical REST contract into lane fragments under `packages/contracts/openapi/root.yaml` (FR-005, QG-04)
- [X] T016 [P] Integration — Encode the WebSocket envelope and message schemas in `packages/contracts/events/websocket/v1/` (FR-032-FR-035, QG-08)
- [X] T017 [P] Integration — Encode the async envelope and domain event schemas in `packages/contracts/events/common/v1/envelope.json` (FR-050)
- [X] T018 Integration — Generate and commit Python/TypeScript contract types from canonical schemas in `packages/contracts/generated/README.md`
- [X] T019 Integration — Add generated-type and canonical-contract drift tests in `backend/tests/contract/test_generated_contract_drift.py`
- [X] T020 [P] Integration — Implement opaque IDs, clocks and CommandMeta primitives in `backend/src/interview_evidence/shared/ids.py`
- [X] T021 [P] Integration — Implement required TenantContext and scope guards in `backend/src/interview_evidence/shared/tenant.py` (FR-005, QG-04)
- [X] T022 [P] Integration — Implement the safe error envelope and error catalog in `backend/src/interview_evidence/shared/errors.py` (FR-049)
- [X] T023 [P] Integration — Implement typed configuration with secret-safe rendering in `backend/src/interview_evidence/shared/config.py` (FR-049)
- [X] T024 [P] Integration — Define company/applicant principal interfaces and deterministic auth fakes in `backend/src/interview_evidence/shared/security/principals.py` (FR-006, FR-013)
- [X] T025 [P] Integration — Define storage, queue, AI, search, speech and email ports plus fakes in `backend/src/interview_evidence/shared/aws_clients/ports.py`
- [X] T026 Integration — Implement OutboxEvent and ProcessedMessage primitives in `backend/src/interview_evidence/shared/messaging/outbox.py` (FR-032, FR-050)
- [X] T027 [P] Integration — Implement the protected audit append interface in `backend/src/interview_evidence/shared/audit.py` (FR-048, FR-049)
- [X] T028 Integration — Configure four Alembic version locations and branch labels in `backend/alembic.ini` (QG-16)
- [X] T029 Integration — Add lane-head, prefix, downgrade and ORM drift validation in `scripts/check_migrations.sh` (QG-16)
- [X] T030 [P] Integration — Add forbidden cross-module import rules in `scripts/check_module_boundaries.py`
- [X] T031 [P] Integration — Create tenant, criterion, invitation, strategy, session and report contract fixtures in `tests/fixtures/shared/factories.py`
- [X] T032 Integration — Create root router composition without domain-private imports in `backend/src/interview_evidence/main.py`
- [X] T033 [P] Integration — Create feature-route registries for both SPAs in `apps/company-console/src/app/featureRoutes.ts` and `apps/applicant-interview/src/app/featureRoutes.ts`
- [X] T034 Integration — Add structured logging, trace propagation and prohibited-field tests in `backend/src/interview_evidence/shared/observability.py` (FR-049, FR-051)
- [X] T035 Integration — Add the complete foundation gate and tag verification in `scripts/verify_foundation.sh`

**Checkpoint**: Contract generation is clean, fakes conform, boundary and migration checks pass, and
all four worktrees can start from the same `foundation-v1` commit.

---

## Phase 3: User Story 1 — Company Criteria and Invitation (Lane A, Priority P1)

**Goal**: A company creates a position with a fixed criterion version, invites an applicant directly, and records
identity and consent with complete tenant isolation.

**Independent Test**: Run `pytest backend/tests/{unit,integration}/company_management` with only shared fakes for B/C/D.

### Tests for User Story 1

- [X] T036 [P] [US1] Lane A — Add HTTP contract tests for company, position, criteria, position invitation and applicant access routes in `backend/tests/contract/company_management/test_http_contract.py` (FR-006-FR-015)
- [X] T037 [P] [US1] Lane A — Add repository and route cross-tenant denial tests in `backend/tests/integration/company_management/test_tenant_isolation.py` (FR-005, SC-014, QG-04)
- [X] T038 [P] [US1] Lane A — Add published criterion immutability and invitation version-pin tests in `backend/tests/unit/company_management/test_criterion_versioning.py` (FR-010)
- [X] T039 [P] [US1] Lane A — Add invitation entropy, hash-only persistence, expiry, reuse and state-transition tests in `backend/tests/unit/company_management/test_invitation_access.py` (FR-011-FR-013)
- [X] T040 [P] [US1] Lane A — Add consent-before-processing and withdrawal authorization tests in `backend/tests/unit/company_management/test_consent_policy.py` (FR-014-FR-015, SC-010, QG-05)
- [X] T041 [P] [US1] Lane A — Add safe audit/log projection tests in `backend/tests/integration/company_management/test_audit_redaction.py` (FR-048-FR-049)
- [X] T042 [P] [US1] Lane A — Add company position/criterion/invitation journey component tests in `apps/company-console/src/features/hiring/__tests__/hiringJourney.test.tsx` (SC-001)
- [X] T043 [P] [US1] Lane A — Add applicant token exchange, identity and consent component tests in `apps/applicant-interview/src/features/access/__tests__/accessJourney.test.tsx` (FR-013-FR-015)

### Implementation for User Story 1

- [X] T044 [US1] Lane A — Create company-domain tables and constraints in `backend/alembic/versions/company/a_001_company_hiring.py` (FR-005-FR-012)
- [X] T045 [P] [US1] Lane A — Implement Company, CompanyUser and Position domain models in `backend/src/interview_evidence/company_management/domain/company.py` (FR-006-FR-007)
- [X] T046 [P] [US1] Lane A — Implement CompetencyModelVersion and EvaluationCriterion invariants in `backend/src/interview_evidence/company_management/domain/criteria.py` (FR-008-FR-010)
- [X] T047 [P] [US1] Lane A — Implement position-owned Invitation and state transitions in `backend/src/interview_evidence/company_management/domain/hiring.py` (FR-011-FR-012)
- [X] T048 [P] [US1] Lane A — Implement ConsentRecord, ApplicantProfile and processing authorization in `backend/src/interview_evidence/company_management/domain/applicant_access.py` (FR-013-FR-015)
- [X] T049 [US1] Lane A — Implement tenant-mandatory company repositories in `backend/src/interview_evidence/company_management/repositories/postgres.py` (FR-005, QG-04)
- [X] T050 [P] [US1] Lane A — Implement company principal validation and auth adapter in `backend/src/interview_evidence/company_management/adapters/company_auth.py` (FR-006)
- [X] T051 [P] [US1] Lane A — Implement raw-token exchange, hash verification and scoped applicant session adapter in `backend/src/interview_evidence/company_management/adapters/applicant_session.py` (FR-011, FR-013)
- [X] T052 [US1] Lane A — Implement company/position application services and public module exports in `backend/src/interview_evidence/company_management/application/company_service.py` (FR-006-FR-007)
- [X] T053 [US1] Lane A — Implement criterion draft/publish/version services in `backend/src/interview_evidence/company_management/application/criteria_service.py` (FR-008-FR-010)
- [X] T054 [US1] Lane A — Implement position invitation issuance and state-history services in `backend/src/interview_evidence/company_management/application/hiring_service.py` (FR-011-FR-012)
- [X] T055 [US1] Lane A — Implement identity and consent services with outbox events in `backend/src/interview_evidence/company_management/application/applicant_access_service.py` (FR-013-FR-015)
- [X] T056 [US1] Lane A — Implement company and hiring API fragment with protected-resource audit events in `backend/src/interview_evidence/company_management/api/company_routes.py` (FR-006-FR-012, FR-048)
- [X] T057 [US1] Lane A — Implement applicant access API fragment in `backend/src/interview_evidence/company_management/api/applicant_routes.py` (FR-013-FR-015)
- [X] T058 [P] [US1] Lane A — Implement Korean company, position, criteria and invitation screens in `apps/company-console/src/features/hiring/index.tsx` (FR-001, FR-007-FR-012, SC-001)
- [X] T059 [P] [US1] Lane A — Implement Korean token exchange, identity and consent screens in `apps/applicant-interview/src/features/access/index.tsx` (FR-001, FR-013-FR-015, SC-010)
- [X] T060 [P] [US1] Lane A — Implement invitation email event handler without exposing raw tokens in logs in `backend/src/interview_evidence/company_management/workers/invitation_email.py` (FR-011, FR-049)
- [X] T061 [P] [US1] Lane A — Implement retention-expiry events and owned relational/audit deletion targets in `backend/src/interview_evidence/company_management/application/deletion_targets.py` (FR-046-FR-047)
- [X] T062 [US1] Lane A — Define dev company/tenant identity and retention inputs in `infra/environments/dev/foundation/variables.tf` (PD-03, PD-26, QG-13-QG-16)
- [X] T063 [US1] Lane A — Complete the isolated Lane A journey in `backend/tests/integration/company_management/test_lane_a_quickstart.py` (US1, QG-04-QG-05)

**Checkpoint**: Lane A works against B/C/D fakes and exports only the frozen module contract.

---

## Phase 4: User Story 2 — Applicant Materials and Strategy (Lane B, Priority P1)

**Goal**: A consented applicant submits documents and a public repository; analysis creates
traceable source chunks and a versioned interview strategy.

**Independent Test**: Run `pytest backend/tests/{unit,integration}/submission_analysis` with Lane A authorization fixtures and
Lane C/D fakes.

### Tests for User Story 2

- [X] T064 [P] [US2] Lane B — Add submission HTTP contract tests in `backend/tests/contract/submission_analysis/test_http_contract.py` (FR-016-FR-022)
- [X] T065 [P] [US2] Lane B — Add consent and invitation authorization rejection tests in `backend/tests/integration/submission_analysis/test_consent_gate.py` (FR-015)
- [X] T066 [P] [US2] Lane B — Add document extraction, chunk locator and content-hash tests in `backend/tests/unit/submission_analysis/test_document_chunking.py` (FR-017-FR-018, QG-09)
- [X] T067 [P] [US2] Lane B — Add tenant/applicant pre-filter and cross-scope retrieval tests in `backend/tests/integration/submission_analysis/test_retrieval_isolation.py` (FR-005, SC-014, QG-10)
- [X] T068 [P] [US2] Lane B — Add candidate commit, AST ownership region and low-confidence behavior tests in `backend/tests/unit/submission_analysis/test_git_ownership.py` (FR-019-FR-020, QG-15)
- [X] T069 [P] [US2] Lane B — Add vector, lexical, exact-symbol and weighting tests in `backend/tests/unit/submission_analysis/test_hybrid_retriever.py` (FR-019, SC-002)
- [X] T070 [P] [US2] Lane B — Add strategy schema, fixed-criterion and source-provenance tests in `backend/tests/unit/submission_analysis/test_strategy_generation.py` (FR-021, QG-09)
- [X] T071 [P] [US2] Lane B — Add partial/failure/retry/DLQ state tests in `backend/tests/integration/submission_analysis/test_partial_analysis.py` (FR-022, FR-050)
- [X] T072 [P] [US2] Lane B — Add submission/readiness UI tests in `apps/applicant-interview/src/features/submissions/__tests__/submissionJourney.test.tsx` (FR-016, FR-022)

### Implementation for User Story 2

- [X] T073 [US2] Lane B — Create submission, Git analysis, chunk and strategy tables in `backend/alembic/versions/submission/b_001_submission_analysis.py` (FR-016-FR-022)
- [X] T074 [P] [US2] Lane B — Implement Submission and SubmissionAnalysis state models in `backend/src/interview_evidence/submission_analysis/domain/submission.py` (FR-016-FR-018, FR-022)
- [X] T075 [P] [US2] Lane B — Implement SubmissionChunk and source locator models in `backend/src/interview_evidence/submission_analysis/domain/source.py` (FR-017, FR-030)
- [X] T076 [P] [US2] Lane B — Implement GitRepositoryAnalysis, GitCommitAnalysis and CandidateCodeUnit in `backend/src/interview_evidence/submission_analysis/domain/git_analysis.py` (FR-019-FR-020)
- [X] T077 [P] [US2] Lane B — Implement InterviewStrategy and fixed-criterion invariants in `backend/src/interview_evidence/submission_analysis/domain/strategy.py` (FR-021)
- [X] T078 [US2] Lane B — Implement tenant-mandatory submission repositories in `backend/src/interview_evidence/submission_analysis/repositories/postgres.py` (FR-005)
- [X] T079 [P] [US2] Lane B — Implement scoped original/derived object storage adapter in `backend/src/interview_evidence/submission_analysis/adapters/object_storage.py` (FR-017, FR-047)
- [X] T080 [P] [US2] Lane B — Implement file, URL, size, media and secret-risk validation in `backend/src/interview_evidence/submission_analysis/application/submission_validator.py` (FR-016, FR-049)
- [X] T081 [P] [US2] Lane B — Implement document/Textract extraction adapter in `backend/src/interview_evidence/workers/analysis/document_extract.py` (FR-018)
- [X] T082 [US2] Lane B — Implement section/page/location-aware chunking in `backend/src/interview_evidence/workers/analysis/document_chunker.py` (FR-017-FR-018)
- [X] T083 [P] [US2] Lane B — Implement bounded, isolated public repository fetch and exclusions in `backend/src/interview_evidence/workers/analysis/git_fetch.py` (FR-019, FR-049)
- [X] T084 [US2] Lane B — Implement per-commit diff and candidate identity matching in `backend/src/interview_evidence/workers/analysis/git_commits.py` (FR-019-FR-020)
- [X] T085 [US2] Lane B — Implement AST symbol expansion, ownership regions and related-test discovery in `backend/src/interview_evidence/workers/analysis/code_units.py` (FR-019-FR-020, QG-15)
- [X] T086 [P] [US2] Lane B — Implement vector and lexical search ports/adapters in `backend/src/interview_evidence/submission_analysis/adapters/search.py` (FR-019, QG-10)
- [X] T087 [US2] Lane B — Implement tenant-first hybrid ranking and exact-symbol boosts in `backend/src/interview_evidence/submission_analysis/application/retrieval.py` (FR-019-FR-020)
- [X] T088 [US2] Lane B — Implement structured strategy generation and validation in `backend/src/interview_evidence/submission_analysis/application/strategy_service.py` (FR-021)
- [X] T089 [US2] Lane B — Implement idempotent analysis job handlers and outbox status events in `backend/src/interview_evidence/workers/analysis/handlers.py` (FR-022, FR-032, FR-050)
- [X] T090 [US2] Lane B — Implement upload, submission and readiness route fragments with protected-resource audit events in `backend/src/interview_evidence/submission_analysis/api/applicant_routes.py` (FR-016-FR-022, FR-048)
- [X] T091 [P] [US2] Lane B — Implement Korean applicant upload, public repository and partial-status UI in `apps/applicant-interview/src/features/submissions/index.tsx` (FR-001, FR-016, FR-022)
- [X] T092 [P] [US2] Lane B — Implement owned object/search/analysis deletion targets in `backend/src/interview_evidence/submission_analysis/application/deletion_targets.py` (FR-047, QG-06)
- [X] T093 [US2] Lane B — Complete the isolated Lane B journey in `backend/tests/integration/submission_analysis/test_lane_b_quickstart.py` (US2, QG-09-QG-10, QG-15)

**Checkpoint**: Lane B creates a strategy against A fixtures, with reproducible SourceReferences and
no cross-tenant search results.

---

## Phase 5: User Story 3 — Recoverable Live Interview (Lane C, Priority P1)

**Goal**: A prepared applicant completes an idempotent, server-authoritative interview that recovers
from connection and dependency failures.

**Independent Test**: Run `pytest backend/tests/{unit,integration}/interview_engine` with a frozen Strategy fixture and
deterministic speech/search/model fakes.

### Tests for User Story 3

- [x] T094 [P] [US3] Lane C — Add WebSocket message/envelope compatibility tests in `backend/tests/contract/interview_engine/test_websocket_contract.py` (FR-032-FR-035)
- [x] T095 [P] [US3] Lane C — Add allowed and rejected session transition tests in `backend/tests/unit/interview_engine/test_session_state_machine.py` (FR-033)
- [x] T096 [P] [US3] Lane C — Add duplicate answer, upload and job idempotency tests in `backend/tests/integration/interview_engine/test_idempotency.py` (FR-026, FR-032, QG-08)
- [x] T097 [P] [US3] Lane C — Add Aurora/outbox/DynamoDB reconciliation and fallback tests in `backend/tests/integration/interview_engine/test_context_reconciliation.py` (FR-034)
- [x] T098 [P] [US3] Lane C — Add reconnect, stale sequence and no-duplicate-Turn tests in `backend/tests/integration/interview_engine/test_session_recovery.py` (FR-034, SC-008, QG-08)
- [x] T099 [P] [US3] Lane C — Add search, model, speech and upload failure-mode tests in `backend/tests/integration/interview_engine/test_degraded_modes.py` (FR-035, FR-050)
- [x] T100 [P] [US3] Lane C — Add media chunk sequence, digest and resume tests in `backend/tests/unit/interview_engine/test_recording_chunks.py` (FR-031-FR-034)
- [x] T101 [P] [US3] Lane C — Add forbidden/duplicate/multi-question/fixed-axis policy tests in `backend/tests/unit/interview_engine/test_question_policy.py` (FR-024-FR-025, FR-029, QG-07)
- [x] T102 [P] [US3] Lane C — Add partial-versus-final speech result tests in `backend/tests/unit/interview_engine/test_transcription.py` (FR-026, FR-031)
- [x] T103 [P] [US3] Lane C — Add applicant session-store recovery tests in `apps/applicant-interview/src/features/interview/__tests__/sessionStore.test.ts` (FR-033-FR-035)
- [x] T104 [P] [US3] Lane C — Add browser device, answer completion, reconnect and text-only tests in `apps/applicant-interview/src/features/interview/__tests__/interviewJourney.spec.ts` (FR-023-FR-036)

### Implementation for User Story 3

- [x] T105 [US3] Lane C — Create session, Turn, checkpoint and recording-chunk tables in `backend/alembic/versions/interview/c_001_interview_session.py` (FR-031-FR-034)
- [x] T106 [P] [US3] Lane C — Implement InterviewSession and state invariants in `backend/src/interview_evidence/interview_engine/domain/session.py` (FR-033)
- [x] T107 [P] [US3] Lane C — Implement Turn, checkpoint and media-chunk invariants in `backend/src/interview_evidence/interview_engine/domain/turn.py` (FR-026, FR-031-FR-034)
- [x] T108 [US3] Lane C — Implement tenant-mandatory session repositories in `backend/src/interview_evidence/interview_engine/repositories/postgres.py` (FR-005)
- [x] T109 [US3] Lane C — Implement compare-and-transition session state machine in `backend/src/interview_evidence/interview_engine/application/state_machine.py` (FR-033)
- [x] T110 [P] [US3] Lane C — Implement scoped command and upload idempotency store in `backend/src/interview_evidence/interview_engine/application/idempotency.py` (FR-032)
- [x] T111 [US3] Lane C — Implement durable checkpoints and recovery snapshots in `backend/src/interview_evidence/interview_engine/application/checkpoints.py` (FR-034)
- [x] T112 [P] [US3] Lane C — Implement DynamoDB recent-context hot-view adapter in `backend/src/interview_evidence/interview_engine/adapters/recent_context.py` (FR-028, FR-034)
- [x] T113 [US3] Lane C — Implement outbox-based hot-view reconciliation and Aurora fallback in `backend/src/interview_evidence/interview_engine/application/context_reconciliation.py` (FR-034)
- [x] T114 [P] [US3] Lane C — Implement streaming speech recognition adapter and confidence handling in `backend/src/interview_evidence/interview_engine/adapters/transcribe.py` (FR-026, FR-031)
- [x] T115 [US3] Lane C — Implement token-budgeted ContextBuilder with summaries and remaining criteria in `backend/src/interview_evidence/interview_engine/application/context_builder.py` (FR-028)
- [x] T116 [P] [US3] Lane C — Implement Lane B retrieval consumer with no-result fallback in `backend/src/interview_evidence/interview_engine/adapters/retrieval_client.py` (FR-028, FR-030, FR-035)
- [x] T117 [US3] Lane C — Implement structured next-question generation in `backend/src/interview_evidence/interview_engine/application/question_generator.py` (FR-024-FR-025, FR-028)
- [x] T118 [US3] Lane C — Implement deterministic question policy and secondary safety checks in `backend/src/interview_evidence/interview_engine/application/question_policy.py` (FR-029, QG-07)
- [x] T119 [P] [US3] Lane C — Implement speech synthesis, viseme and text-only fallback adapter in `backend/src/interview_evidence/interview_engine/adapters/polly.py` (FR-025, FR-035)
- [x] T120 [P] [US3] Lane C — Implement recording chunk upload authorization and verification in `backend/src/interview_evidence/interview_engine/application/recording_service.py` (FR-031-FR-034)
- [x] T121 [US3] Lane C — Implement answer-finalize-to-next-question orchestration in `backend/src/interview_evidence/interview_engine/application/interview_service.py` (FR-024-FR-036)
- [x] T122 [US3] Lane C — Implement the protocol stream endpoint in `backend/src/interview_evidence/interview_engine/api/websocket.py` (FR-025-FR-035)
- [x] T123 [US3] Lane C — Implement equipment, session, resume and media-intent routes with protected-resource audit events in `backend/src/interview_evidence/interview_engine/api/applicant_routes.py` (FR-023, FR-031-FR-035, FR-048)
- [x] T124 [P] [US3] Lane C — Implement device and network readiness UI in `apps/applicant-interview/src/features/interview/EquipmentCheck.tsx` (FR-023)
- [x] T125 [P] [US3] Lane C — Implement chunked recorder, audio worklet and local retry buffer in `apps/applicant-interview/src/features/interview/media.ts` (FR-026-FR-027, FR-031)
- [x] T126 [US3] Lane C — Implement server-sequence Zustand store and resume reconciliation in `apps/applicant-interview/src/features/interview/sessionStore.ts` (FR-032-FR-035)
- [x] T127 [US3] Lane C — Implement Korean AI disclosure, question, answer, processing, pause and completion room UI in `apps/applicant-interview/src/features/interview/InterviewRoom.tsx` (FR-001-FR-002, FR-024-FR-036)
- [x] T128 [P] [US3] Lane C — Implement 2D avatar speech-mark synchronization and text-only mode in `apps/applicant-interview/src/features/interview/Avatar.tsx` (FR-025, FR-035)
- [x] T129 [P] [US3] Lane C — Implement owned Turn/checkpoint/hot-view/media-chunk deletion targets in `backend/src/interview_evidence/interview_engine/application/deletion_targets.py` (FR-047, QG-06)
- [x] T130 [US3] Lane C — Complete the isolated reconnect/degraded Lane C journey in `backend/tests/integration/interview_engine/test_lane_c_quickstart.py` (US3, SC-007-SC-008, QG-08)

**Checkpoint**: Lane C completes one interview against fakes, survives reconnect and produces no
duplicate Turn or assessment signal from technical failures.

---

## Phase 6: User Story 4 — Evidence Review and Human Decision (Lane D, Priority P1)

**Goal**: A company reviews transcript/video-linked Evidence, preserves AI and human versions, records
a human-only decision, and verifies privacy deletion.

**Independent Test**: Run `pytest backend/tests/{unit,integration}/reporting` with a completed-session fixture.

### Tests for User Story 4

- [x] T131 [P] [US4] Lane D — Add report, timeline, review, final-decision and deletion HTTP contract tests in `backend/tests/contract/reporting/test_http_contract.py` (FR-037-FR-048)
- [x] T132 [P] [US4] Lane D — Add confirmed/partial Evidence constraints and invalid-range tests in `backend/tests/unit/reporting/test_evidence_integrity.py` (FR-039-FR-041, SC-016, QG-02)
- [x] T133 [P] [US4] Lane D — Add SourceReference-versus-Evidence separation tests in `backend/tests/unit/reporting/test_source_evidence_separation.py` (FR-040-FR-041)
- [x] T134 [P] [US4] Lane D — Add transcript, media manifest, missing-range and session-clock tests in `backend/tests/integration/reporting/test_timeline_alignment.py` (FR-037-FR-038)
- [x] T135 [P] [US4] Lane D — Add immutable AI original and append-only human override tests in `backend/tests/unit/reporting/test_human_review.py` (FR-043-FR-044)
- [x] T136 [P] [US4] Lane D — Add AI/system-role final-decision denial tests in `backend/tests/integration/reporting/test_human_only_decision.py` (FR-003, FR-045, SC-011, QG-03)
- [x] T137 [P] [US4] Lane D — Add deletion enumeration, retry and residue-verification tests in `backend/tests/integration/reporting/test_deletion_manifest.py` (FR-046-FR-047, SC-015, QG-05-QG-06)
- [x] T138 [P] [US4] Lane D — Add cross-tenant report, Evidence, media locator and deletion denial tests in `backend/tests/integration/reporting/test_tenant_isolation.py` (FR-005, SC-014, QG-04)
- [x] T139 [P] [US4] Lane D — Add report/timeline/human-review component tests in `apps/company-console/src/features/review/__tests__/reviewJourney.test.tsx` (FR-037-FR-045)
- [x] T140 [P] [US4] Lane D — Add Evidence-to-video start-within-two-seconds browser test in `apps/company-console/src/features/review/__tests__/evidenceSeek.spec.ts` (FR-038, SC-012)

### Implementation for User Story 4

- [x] T141 [US4] Lane D — Create transcript, media, report, Evidence, review and deletion tables in `backend/alembic/versions/reporting/d_001_reporting.py` (FR-037-FR-048)
- [x] T142 [P] [US4] Lane D — Implement TranscriptSegment, RecordingAsset and SessionEvent models in `backend/src/interview_evidence/reporting/domain/timeline.py` (FR-037-FR-038)
- [x] T143 [P] [US4] Lane D — Implement Report, ReportItem and Evidence invariants in `backend/src/interview_evidence/reporting/domain/report.py` (FR-039-FR-042)
- [x] T144 [P] [US4] Lane D — Implement HumanReview and human-only final decision model in `backend/src/interview_evidence/reporting/domain/review.py` (FR-043-FR-045)
- [x] T145 [P] [US4] Lane D — Implement DeletionRequest, Manifest and Target state model in `backend/src/interview_evidence/reporting/domain/deletion.py` (FR-046-FR-047)
- [x] T146 [US4] Lane D — Implement tenant-mandatory reporting repositories in `backend/src/interview_evidence/reporting/repositories/postgres.py` (FR-005)
- [x] T147 [US4] Lane D — Implement final-Turn transcript ingestion and correction history in `backend/src/interview_evidence/reporting/application/transcript_service.py` (FR-037)
- [x] T148 [US4] Lane D — Implement recording validation, media post-processing and manifest generation in `backend/src/interview_evidence/workers/reporting/media.py` (FR-037-FR-038)
- [x] T149 [US4] Lane D — Implement structured report generation and state assignment in `backend/src/interview_evidence/workers/reporting/report.py` (FR-039-FR-042)
- [x] T150 [US4] Lane D — Implement transactional Evidence validation and rejection in `backend/src/interview_evidence/reporting/application/evidence_service.py` (FR-039-FR-041, QG-02)
- [x] T151 [US4] Lane D — Implement append-only human assessment, note, bookmark and final-decision services in `backend/src/interview_evidence/reporting/application/review_service.py` (FR-043-FR-045)
- [x] T152 [US4] Lane D — Implement transcript keyword and criterion timeline projection in `backend/src/interview_evidence/reporting/application/timeline_service.py` (FR-037-FR-038)
- [x] T153 [P] [US4] Lane D — Implement scoped short-lived playback locator adapter in `backend/src/interview_evidence/reporting/adapters/playback.py` (FR-038, FR-049)
- [x] T154 [US4] Lane D — Consume retention-expired events and implement cross-lane deletion orchestration in `backend/src/interview_evidence/reporting/application/deletion_service.py` (FR-046-FR-047, QG-05-QG-06)
- [x] T155 [US4] Lane D — Implement report, timeline, review and privacy route fragments with protected-resource audit events in `backend/src/interview_evidence/reporting/api/company_routes.py` (FR-037-FR-048)
- [x] T156 [P] [US4] Lane D — Implement Korean report list/detail and criterion state UI in `apps/company-console/src/features/review/ReportView.tsx` (FR-001, FR-039-FR-045)
- [x] T157 [P] [US4] Lane D — Implement synchronized transcript, video, search, bookmark and Evidence seek UI in `apps/company-console/src/features/review/TimelineView.tsx` (FR-037-FR-038, SC-012)
- [x] T158 [P] [US4] Lane D — Implement review history, final decision and deletion status UI in `apps/company-console/src/features/review/HumanReview.tsx` (FR-043-FR-047)
- [x] T159 [US4] Lane D — Complete the isolated Evidence/review/deletion Lane D journey in `backend/tests/integration/reporting/test_lane_d_quickstart.py` (US4, QG-02-QG-07)

**Checkpoint**: Lane D rejects unsupported assessments, preserves AI originals, accepts only human
decisions and cannot complete deletion while any target remains.

---

## Phase 7: Integration, AWS Parity and Cross-Cutting Gates

**Purpose**: Merge in A→B→C→D order, replace fakes one boundary at a time, and satisfy all release gates.

### Infrastructure and Deployment (Lane A Owns `infra/`)

- [x] T160 [P] Lane A — Implement reusable VPC, subnet, endpoint and security-group resources in `infra/modules/network/main.tf` (QG-14, QG-16)
- [x] T161 [P] Lane A — Implement private S3 origins, CloudFront OAC, WAF, DNS and certificate resources in `infra/modules/edge/main.tf` (QG-14)
- [x] T162 [P] Lane A — Implement ECR, ALB, ECS API/worker services and autoscaling ownership rules in `infra/modules/compute/main.tf` (PD-05, QG-13)
- [x] T163 [P] Lane A — Implement Aurora, DynamoDB, S3, KMS and Secrets Manager resources in `infra/modules/data/main.tf` (PD-21, PD-23, QG-14)
- [x] T164 [P] Lane A — Implement SQS/DLQ, Step Functions and EventBridge resources in `infra/modules/async-workflow/main.tf` (FR-050)
- [x] T165 [P] Lane A — Implement OpenSearch Serverless, index mapping, Bedrock Knowledge Base and guardrail resources in `infra/modules/ai-search/main.tf` (PD-06, PD-22, QG-15)
- [x] T166 [P] Lane A — Implement Cognito and SES resources with least-privilege roles in `infra/modules/identity/main.tf` (PD-13, PD-24)
- [x] T167 [P] Lane A — Implement CloudWatch, X-Ray, alarms, budgets and audit resources in `infra/modules/observability/main.tf` (FR-051)
- [x] T168 Lane A — Compose separated dev roots and S3 lockfile backends in `infra/environments/dev/foundation/main.tf`, `infra/environments/dev/data-ai/main.tf`, and `infra/environments/dev/application/main.tf` (PD-26, QG-16)
- [x] T169 [P] Lane A — Add stage and prod roots with independent state, roles, KMS and data stores in `infra/environments/stage/main.tf` and `infra/environments/prod/main.tf` (QG-16)
- [x] T170 Integration — Add saved-plan, approval, migration, ECS and frontend deployment stages in `.github/workflows/deploy.yml` (QG-13-QG-16)

### Merge Train and Real Adapters (Integration Owner)

- [x] T171 Integration — Merge lane Alembic heads and prove empty/previous-snapshot upgrade in `backend/alembic/versions/merge/m_001_lane_merge.py` (QG-16)
- [x] T172 Integration — Replace Lane A position-hiring/consent fakes for Lane B and add real boundary tests in `backend/tests/integration/cross_module/test_a_to_b.py`
- [x] T173 Integration — Replace Lane B strategy/retrieval fakes for Lane C and add real boundary tests in `backend/tests/integration/cross_module/test_b_to_c.py`
- [x] T174 Integration — Replace Lane C Turn/media fakes for Lane D and add real boundary tests in `backend/tests/integration/cross_module/test_c_to_d.py`
- [x] T175 Integration — Connect Lane D report/deletion projections to Lane A company views in `backend/tests/integration/cross_module/test_d_to_a.py`
- [x] T176 Integration — Wire all router fragments and worker handlers in `backend/src/interview_evidence/main.py`
- [x] T177 Integration — Wire all feature routes without changing lane feature internals in `apps/company-console/src/app/featureRoutes.ts` and `apps/applicant-interview/src/app/featureRoutes.ts`
- [x] T178 Integration — Complete local production-contract composition and health checks in `compose.yaml` (QG-11)

### Full Quality Gates

- [x] T179 [P] Integration — Add the company-to-human-decision thin journey in `tests/e2e/test_thin_journey.py` (FR-001-FR-052, QG-01)
- [x] T180 [P] Integration — Add cross-route, worker, search, object and hot-view tenant isolation suite in `tests/e2e/test_tenant_isolation.py` (SC-014, QG-04, QG-10)
- [x] T181 [P] Integration — Add full-store deletion residue and retry suite in `tests/e2e/test_deletion_residue.py` (SC-015, QG-05-QG-06)
- [x] T182 [P] Integration — Add no-AI-final-decision and no-nonverbal-scoring static/runtime suite in `tests/e2e/test_human_control.py` (SC-011, QG-03, QG-07)
- [x] T183 [P] Lane B — Add fixed Korean document/code retrieval corpus and expected sources in `tests/regression/retrieval/cases.jsonl` (SC-002, QG-09-QG-10, QG-15)
- [x] T184 [P] Lane C — Add fixed safe-question, duplicate, forbidden and degraded-mode corpus in `tests/regression/questions/cases.jsonl` (FR-029, QG-12)
- [x] T185 [P] Lane D — Add Evidence-state and unsupported-claim regression corpus in `tests/regression/evidence/cases.jsonl` (SC-004-SC-005, SC-016, QG-02, QG-12)
- [x] T186 Integration — Add configuration-version regression runner and thresholds in `tests/regression/run_regression.py` (FR-051-FR-052, QG-12)
- [x] T187 [P] Lane C — Add five-concurrent-session and long-running pipeline load scenarios in `tests/load/interview_load.py` (SC-007, SC-013)
- [x] T188 [P] Lane D — Add Evidence seek performance measurement in `tests/load/evidence_seek.py` (SC-012)
- [x] T189 Integration — Add stage CloudFront-to-AWS-service smoke journey in `tests/e2e/test_stage_smoke.py` (QG-13-QG-14)
- [x] T190 Integration — Run and record every command/outcome from `specs/001-interview-evidence-platform/quickstart.md`
- [x] T191 Integration — Record FR/SC/QG-to-test coverage and zero unresolved critical gaps in `specs/001-interview-evidence-platform/validation-report.md`
- [x] T192 Integration — Run `$speckit-converge` and append every remaining spec/plan/code gap to `specs/001-interview-evidence-platform/tasks.md`

**Final Checkpoint**: QG-01 through QG-16 pass, contract generation is clean, all migrations have one
merged head, all four lane suites and the thin end-to-end journey pass, and no critical convergence
gap remains.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: starts immediately; Integration Owner coordinates root files.
- **Phase 2 Foundation**: depends on Setup and blocks all user-story implementation.
- **Phases 3-6**: start simultaneously from the same `foundation-v1` commit:
  - Phase 3 / US1 = Lane A
  - Phase 4 / US2 = Lane B
  - Phase 5 / US3 = Lane C
  - Phase 6 / US4 = Lane D
- **Phase 7 Integration**: lane work may be reviewed while others continue, but the merge train
  follows A → B → C → D.

### User Story Dependencies

- **US1 / Lane A**: no runtime dependency on other stories; uses report/analysis/interview projections as fakes.
- **US2 / Lane B**: consumes frozen position/criterion/consent contracts; can finish against fixtures.
- **US3 / Lane C**: consumes frozen strategy/retrieval contracts; can finish against fixtures.
- **US4 / Lane D**: consumes frozen Turn/media/source contracts; can finish against fixtures.
- Real producer replacement occurs only in T172-T175, after each producing lane merges.

### Within Each Lane

1. Complete and observe failing contract/domain tests.
2. Add the lane-prefixed migration and domain models.
3. Implement repositories and adapters behind frozen ports.
4. Implement application services and policy rules.
5. Implement route/event fragments and owned UI.
6. Run the lane quickstart against fakes.
7. Update from the integration branch and run the same tests against real merged producers.

## Parallel Opportunities

- T002-T012 are independent setup files after T001 defines root conventions.
- T016-T017 and T020-T025 are independent foundation artifacts before composition tasks.
- After T035, all tasks in Phases 3, 4, 5 and 6 run as four parallel workstreams.
- Within a lane, test files marked [P] can be authored in parallel before implementation.
- Domain model files marked [P] are exclusive and can be implemented after their tests exist.
- T160-T167 Terraform modules are independent; only T168 composes them.
- T179-T185 are independent cross-cutting test/data artifacts before the final report.

## Four-Person Invocation

After the start gate is reviewed, each person opens their worktree and gives Codex one bounded task:

```text
Person 1 / Lane A:
$speckit-implement Implement only unchecked tasks whose description starts "Lane A —" in
specs/001-interview-evidence-platform/tasks.md. Do not edit integration-owned or other-lane paths.

Person 2 / Lane B:
$speckit-implement Implement only unchecked tasks whose description starts "Lane B —" in
specs/001-interview-evidence-platform/tasks.md. Use frozen fakes for unmerged producers.

Person 3 / Lane C:
$speckit-implement Implement only unchecked tasks whose description starts "Lane C —" in
specs/001-interview-evidence-platform/tasks.md. Use frozen fakes for unmerged producers.

Person 4 / Lane D:
$speckit-implement Implement only unchecked tasks whose description starts "Lane D —" in
specs/001-interview-evidence-platform/tasks.md. Use frozen fakes for unmerged producers.
```

The Integration Owner handles only tasks whose description starts `Integration —`; this role does
not authorize edits to a lane's exclusive implementation path.

## Parallel Example

```text
After foundation-v1:
  Worktree A -> T036-T063
  Worktree B -> T064-T093
  Worktree C -> T094-T130
  Worktree D -> T131-T159

Review can happen in any order.
Merge and real-adapter replacement happen A -> B -> C -> D using T171-T178.
```

## Implementation Strategy

### Thin Slice First

Each lane first implements the smallest path needed by its independent test:

- Lane A: position → criterion version → invitation → consent.
- Lane B: submitted fixtures → source retrieval → strategy.
- Lane C: start → answer → next question → reconnect → complete.
- Lane D: completed fixture → Evidence report → human decision → deletion.

Only after all four thin slices pass should a lane add breadth such as CSV scale, deeper Git context,
additional degraded modes or richer review UI.

### Merge Discipline

- One task or tightly coupled test/implementation pair per commit.
- Every PR lists lane, foundation hash, task IDs, FR/SC/QG IDs, contracts and migration head.
- No lane PR edits `tasks.md`, generated output, a shared root or another lane path.
- Shared contract changes merge separately before consumer implementation.
- A completed task checkbox is updated on the integration branch after its commit is accepted.
- Final completion requires the merged quickstart and convergence pass, not four isolated green lanes.

## Phase 8: Convergence

- [X] T193 Integration — CRITICAL: Replace the deployment entry points with an environment-selected production runtime that wires durable repositories and cloud adapters while preserving the explicit local runtime per plan R-001/R-006 and the fixed AWS topology (contradicts)
- [X] T194 Integration — CRITICAL: Add shared durable OutboxEvent, ProcessedMessage, AuditEvent, upload-intent, applicant-session and command-idempotency persistence with request-scoped transactions per Constitution V, plan R-005 and the shared data model (missing)
- [X] T195 Integration — CRITICAL: Implement tenant-scoped production adapters for S3, SQS, SES, Cognito, DynamoDB, OpenSearch Serverless, Bedrock, Transcribe, Polly, Textract and MediaConvert per the fixed AWS constraints and QG-13-QG-15 (missing)
- [X] T196 Integration — CRITICAL: Implement outbox dispatch, SQS long polling, processed-message idempotency and the real document/Git/strategy/media/report/deletion worker pipelines per FR-017-FR-022, FR-037-FR-042 and FR-050 (partial)
- [X] T197 Lane C — CRITICAL: Connect the applicant interview route to the WebSocket protocol, server sequence store, audio worklet/STT stream, recording chunk upload, reconnect and degraded-mode controls per FR-023-FR-036 and US3 (partial)
- [X] T198 Lane A — CRITICAL: Implement Cognito-backed company authentication plus durable invitation-token and applicant-session exchange, expiry and revocation per FR-006 and FR-013-FR-015 (partial)
- [X] T199 Lane A — Complete the company criteria and position-management UI for detailed evidence rules, prohibited topics, duration and interviewer persona/voice preview per FR-007-FR-009 (partial)
- [X] T200 Lane A — Present server-versioned AI role, recording, retention and deletion policy content before consent and bind the accepted digest to the displayed policy per FR-002 and FR-014 (partial)
- [X] T201 Integration — Add production store deletion verification, dependency-aware readiness and queue/latency/deletion metrics per FR-047 and FR-050-FR-051 (partial)
- [X] T202 Integration — Add LocalStack/PostgreSQL production-composition parity tests covering API, worker, auth, persistence, AWS adapters, restart recovery and failure isolation per plan R-014 and QG-13-QG-15 (missing)

## Phase 9: Convergence

- [X] T203 Lane C — CRITICAL: Wire production WebSocket audio transcription, answer finalization, initial question and follow-up question generation into the real interview runtime per FR-023-FR-036 and US3 (partial)
- [X] T204 Lane C — CRITICAL: Replace production interview command in-memory idempotency with PostgreSQL-backed result persistence across API task restarts per Constitution V and FR-032/FR-034 (contradicts)
- [X] T205 Lane B — Connect bounded public Git fetch, commit identity, code-unit and exact-symbol analysis to the production submission worker pipeline per FR-017-FR-022 (partial)
- [X] T206 Integration — Inject environment-specific applicant invitation access URLs into local, stage and production hiring routes per FR-013 and US2/AC1 (partial)
- [X] T207 Integration — Extend local-production parity with a real outbox-to-SQS-to-worker-to-PostgreSQL processing round trip per plan R-014, T202 and QG-14 (partial)

## Phase 10: Company Console UI/UX

- [X] T208 Integration — Build the responsive company-console application shell, navigation, page hierarchy, shared design tokens and route-level loading/error states based on the approved Figma Make reference without changing public API contracts
- [X] T209 Lane A — Redesign the position, competency model and invitation workflow as a dense, accessible enterprise hiring workspace while preserving the validated T199 business flow
- [X] T210 Lane D — Redesign the report, Evidence timeline, human review, decision and deletion-status experience as a synchronized review workspace while preserving Evidence and human-decision boundaries

## Phase 11: Figma Reference Alignment

**Purpose**: Adapt the approved Figma Make information hierarchy to the real product without
copying demo data, unsupported controls, inline-style structure or the reference's clipped mobile
layout.

- [X] T211 Integration — Analyze the superseded Figma Make company/candidate screens and map their screen intent to API ownership before the approved recruiter-operations visual baseline replaced the retained captures (FR-053, SC-017)
- [X] T212 Integration — Align the remaining shared applicant shell, navigation, design tokens and route hierarchy with the approved reference while preserving existing public API contracts (FR-053, FR-055, SC-019)
- [X] T213 Lane A — Implement the reference-aligned company overview, position list, guided position design and contract-backed AI interviewer configuration experience in `apps/company-console/src/features/company/` and `apps/company-console/src/features/hiring/` (FR-054, FR-056, SC-018)
- [X] T214 Lane D — Keep the contract-backed session review overview synchronized across video, transcript, Evidence, immutable AI output and human decision while omitting an unsupported candidate-list pipeline rather than introducing mock business records in `apps/company-console/src/features/review/` (FR-054, FR-057)
- [X] T215 Lane A — Align applicant invitation, identity and consent screens with the reference in `apps/applicant-interview/src/features/access/` (FR-053, FR-055, SC-019)
- [X] T216 Lane B — Align applicant material submission and analysis-readiness screens with the reference in `apps/applicant-interview/src/features/submissions/` (FR-053-FR-055, SC-019)
- [X] T217 Lane C — Align equipment check, interview room, reconnect/degraded states and completion screens with the reference in `apps/applicant-interview/src/features/interview/` (FR-053, FR-055, SC-019)
- [X] T218 Integration — Add desktop/mobile visual and browser E2E coverage for every implemented route, assert no mock business records, and record accepted screenshots under `tests/browser/artifacts/` after T212-T217 (FR-053-FR-057, SC-017-SC-019)

## Phase 12: Recruiter Operations and Applicant Experience

**Purpose**: Replace the superseded Figma capture exercise with a production-oriented recruiter
console and applicant journey based on the approved sidebar/dashboard references, while using only
existing public APIs and domain states.

- [X] T219 Integration — Rebuild the company application shell, responsive sidebar, route hierarchy and shared visual tokens for dashboard, positions, recruiting calendar, hiring settings and applicant portal handoff in `apps/company-console/src/app/` without changing public API contracts (FR-053-FR-055)
- [X] T220 Lane A — Implement the recruiter operations dashboard, tenant-backed position setup progress, monthly recruiting calendar and configured-position inspection in `apps/company-console/src/features/company/` using only `/v1/me` and `/v1/positions` data (FR-007-FR-012, FR-054-FR-056)
- [X] T221 Lane A — Refine applicant invitation, identity and consent screens in `apps/applicant-interview/src/features/access/` to the shared visual system while preserving token, policy-digest and consent behavior (FR-013-FR-015, FR-053-FR-055)
- [X] T222 Lane B — Refine applicant submission and readiness screens in `apps/applicant-interview/src/features/submissions/` to the shared visual system while preserving upload, Git and partial-analysis behavior (FR-016-FR-022, FR-053-FR-055)
- [X] T223 Lane C — Refine equipment check, interview, reconnect/degraded and completion screens in `apps/applicant-interview/src/features/interview/` to the shared visual system while preserving WebSocket, media and recovery behavior (FR-023-FR-036, FR-053-FR-055)
- [X] T224 Integration — Remove superseded reference captures and capture tooling, add desktop/mobile Chrome E2E for the recruiter calendar and applicant journey, run full React/accessibility verification and record accepted implementation screenshots under `tests/browser/artifacts/` (FR-053-FR-057, SC-018-SC-019)

## Phase 13: Position Invitation Operations

**Purpose**: Turn the existing position invitation contracts into a recruiter-facing operating
workspace without adding a parallel API or client-only business state.

- [X] T225 Integration — Add position invitation routes, sidebar handoff and route-level API composition in `apps/company-console/src/app/` using the existing `listInvitations` and `createInvitations` contracts (FR-011-FR-012, FR-053-FR-055)
- [X] T226 Lane A — Implement bulk recipient entry, validation, issuance summary, recipient search/filter, progress/status projection and safe resend actions in `apps/company-console/src/features/hiring/` without logging applicant PII or inventing unsupported business data (FR-011-FR-012, FR-049, FR-054-FR-056)
- [X] T227 Integration — Add component and real-Chrome E2E coverage for position creation handoff, bulk invitation issuance, recipient status inspection and responsive sidebar behavior, then rebuild the local company console for review (SC-001, SC-017-SC-019)

## Phase 14: Position-Centric Recruiting Operations

**Purpose**: Reframe the recruiter console around applicant throughput and review work instead of
configuration progress, while reusing the existing position and invitation contracts.

- [X] T228 Integration — Add a position operations route and tenant-backed invitation aggregation in `apps/company-console/src/app/` without introducing a new business API or client-authored applicant state (FR-011-FR-012, FR-053-FR-055)
- [X] T229 Lane A — Replace the setup-oriented dashboard with applicant funnel, review queue and attention work, and implement a position operations workspace with overview, applicant list and bulk email invitation views in `apps/company-console/src/features/company/` (FR-007-FR-012, FR-054-FR-056)
- [X] T230 Integration — Add component and real-Chrome E2E coverage for dashboard operations, position drill-down, applicant inspection and bulk invitation handoff, then rebuild API, worker and both SPAs for recruiter review (SC-001, SC-017-SC-019)

## Phase 15: Recruiter Dashboard Information Architecture

**Purpose**: Make the first company-console view answer the recruiter's daily operating questions
using only existing position and invitation projections.

- [X] T231 Lane A — Recompose the recruiter dashboard around active positions, interviews in progress, reviews pending, completed reviews, position-level operating status, real timestamped activity and priority work in `apps/company-console/src/features/company/`, with component and Chrome regression coverage and no new public API (FR-011-FR-012, FR-053-FR-056, SC-017-SC-019)

## Phase 16: Reusable AI Interviewer Profiles

**Purpose**: Let a company define reusable AI interviewer personas, select one while configuring a
position and freeze the selected persona into the existing competency version without
granting the AI any hiring-decision authority.

- [X] T232 Integration — Add backward-compatible company HTTP contracts and generated types for listing and creating tenant-scoped AI interviewer profiles with name, tone and voice only, preserving `persona_definition` as the immutable criterion-version snapshot (FR-003, FR-009-FR-010)
- [X] T233 Lane A — Implement the AI interviewer profile domain model, tenant-scoped repository, Alembic migration, application service and company API with contract, isolation and quickstart tests in `backend/src/interview_evidence/company_management/` (FR-005-FR-006, FR-009)
- [X] T234 Integration — Add the `AI 면접관` company navigation route and API adapter in `apps/company-console/src/app/`, keeping shared route code free of Lane A domain state (FR-053-FR-055)
- [X] T235 Lane A — Build the reusable interviewer profile workspace, position-setup profile selector and inline profile creation flow, and recompose position title/scope entry as a progressive one-decision-at-a-time experience in `apps/company-console/src/features/company/` and `apps/company-console/src/features/hiring/` (FR-007, FR-009-FR-010, FR-056)
- [X] T236 Integration — Add component and real-Chrome E2E coverage for interviewer creation, reuse inside position setup, inline creation, immutable persona snapshot submission and responsive navigation, then rebuild API, worker and both SPAs (SC-001, SC-017-SC-019)

## Phase 17: Position-Owned Recruiting

**Purpose**: Make Position the single recruiter-facing and technical owner of published criteria,
applicant invitations and recruiting operations, replacing the superseded intermediate aggregate.

- [X] T237 Integration — Replace superseded recruiting HTTP/module contracts with position-owned invitation and immutable hiring-snapshot contracts, regenerate Python/TypeScript types and update spec/data-model compatibility notes (FR-007-FR-012)
- [X] T238 Lane A — Remove the superseded recruiting domain/repository/service runtime, migrate invitations to direct `position_id` and `competency_model_version_id` ownership, drop the obsolete intermediary table, and implement position invitation APIs with tenant/version tests (FR-005, FR-010-FR-012)
- [X] T239 Integration — Update submission, interview, reporting, E2E and worker consumers to use the position hiring snapshot and invitation-fixed criterion version without private cross-module access (FR-010, FR-021, FR-024)
- [X] T240 Integration — Remove obsolete recruiting and calendar routes/navigation/client storage, rename `채용 설정` to `채용 관리`, and make position detail open directly on the applicant roster and invitation controls (FR-053-FR-056)
- [X] T241 Lane A — Redesign the AI interviewer workspace as a guided style, voice-preview and identity configuration experience and simplify position management to `직무 설정 → 면접 설계 → 지원자 초대` (FR-007-FR-011, FR-056)
- [X] T242 Integration — Add migration, contract, tenant, component and real-Chrome E2E coverage for position-owned invitations, direct applicant roster, removed routes and responsive AI interviewer management; rebuild API, worker and both SPAs (SC-001, SC-014, SC-017-SC-019)

## Phase 18: Structured Applicant Import and Roster Review

**Purpose**: Replace free-form bulk invitation entry with a recruiter-oriented table workflow that
validates imported recipients before transmission and provides a populated local review surface
without mixing demo records into production data.

- [X] T243 Lane A — Redesign the position applicant workspace and invitation composer in `apps/company-console/src/features/company/` and `apps/company-console/src/features/hiring/` as dense operational tables with editable name/email rows, CSV/JSON import, post-entry validation summaries, case-insensitive duplicate exclusion, valid-row-only issuance and component regression coverage (FR-011-FR-012, FR-049, FR-053-FR-056, SC-001)
- [X] T244 Integration — Add an explicitly local-only server-backed applicant demo seed and real-browser desktop/mobile verification in `backend/src/interview_evidence/runtime/local_seed.py` and `tests/browser/` for the populated roster and structured import flow, without client-authored production records (FR-054-FR-055, SC-017-SC-019)

## Phase 19: Applicant-Centered Review

**Purpose**: Make each applicant row a navigable operating record and provide one cross-position
applicant workspace that leads recruiters to source submissions, interview playback, final answers
and analysis without treating invitation progress as the final review surface.

- [X] T245 Integration — Extend the invitation projection contract with an optional tenant-scoped `interview_session_id`, resolve it only through the Lane C public boundary, regenerate contracts and add contract/isolation coverage (FR-012, FR-030-FR-031, FR-049)
- [X] T246 Lane A — Add `지원자 관리` navigation, a cross-position applicant table, position-row navigation and an applicant detail route with status/submission/interview-analysis availability states in `apps/company-console/src/app/` and `apps/company-console/src/features/company/` (FR-049, FR-053-FR-056, SC-001)
- [X] T247 Integration — Seed one explicitly local-only reviewable applicant session with transcript and report projections and connect the applicant detail to the existing evidence review route without creating production demo records (FR-030-FR-034, FR-054-FR-055)
- [X] T248 Integration — Add component and real-Chrome desktop/mobile coverage for global applicant navigation, position-row detail entry, pre-interview detail states and reviewable interview evidence; rebuild the local API and company SPA (SC-001, SC-017-SC-019)

## Phase 20: Recruiter Operations Visual Refinement

**Purpose**: Give position and applicant operations a coherent recruiter-specific information
hierarchy with readable typography, restrained surfaces and consistent progress summaries.

- [X] T249 Lane A — Refine `PositionOperations`, `ApplicantManagement`, applicant tables and invitation panels with recruiter-focused KPI summaries, consistent state filtering, 12px+ operational typography, restrained 6-8px surfaces and responsive component coverage in `apps/company-console/src/features/company/` and `apps/company-console/src/features/hiring/` (FR-053-FR-056, SC-001)
- [X] T250 Integration — Rebuild the company SPA and perform real-browser desktop/mobile visual QA for position operations and applicant management with populated local data, including overflow and interaction checks (SC-017-SC-019)

## Phase 21: Applicant Comprehensive Report

**Purpose**: Turn the applicant detail route into one recruiter-readable report surface with
clear progress, source, interview and analysis navigation without fabricating unavailable data.

- [X] T251 Lane A — Redesign `ApplicantDetail` as a responsive comprehensive report with a compact identity header, operational KPI band, accessible `종합 개요 / 제출 자료 / 면접 기록 / 분석 리포트` tabs, status-aware empty states and handoff to existing evidence review in `apps/company-console/src/features/company/` (FR-049, FR-053-FR-056, SC-001)
- [X] T252 Integration — Rebuild the company SPA and perform populated pre-interview and reviewable-applicant desktop/mobile browser QA for the applicant report, including tab navigation, overflow, focus and evidence-review handoff checks (SC-017-SC-019)

## Phase 22: Recruiter-Facing Applicant Progress

**Purpose**: Keep detailed invitation states internal while presenting a stable four-phase
recruiting journey that matches the applicant report timeline.

- [X] T253 Lane A — Map internal invitation stages to recruiter-facing `초대·확인 / 자료 제출·분석 / 면접 / 결과 검토` phases and remove user-visible `/9` implementation detail from `ApplicantDetail` with component regression coverage (FR-049, FR-053-FR-056, SC-001)
- [X] T254 Integration — Rebuild the company SPA and verify four-phase progress in pre-interview and reviewable desktop/mobile applicant reports (SC-017-SC-019)

## Phase 23: Editable Position Operations

**Purpose**: Make a position the complete operating workspace for status, settings, applicants,
invitations and immutable interview-criterion versions.

- [X] T255 Integration — Add tenant-scoped, optimistic-locking contracts for replacing position settings/status and listing position criterion versions; regenerate shared clients without changing published criterion immutability (FR-007-FR-012, FR-049)
- [X] T256 Lane A — Implement position revision and `draft → active → closed` transitions with published-criterion activation guard, audit events, tenant/version tests and current criterion-version listing in `backend/src/interview_evidence/company_management/` (FR-005-FR-012, SC-001)
- [X] T257 Lane A — Refactor `PositionOperations` into recruiter-focused `운영 개요 / 지원자 / 초대 / 채용 설정` tabs, add editable position fields, draft confirmation/closing controls and criterion new-version publishing while keeping applicant rows linked to comprehensive reports (FR-007-FR-012, FR-049, FR-053-FR-056)
- [X] T258 Integration — Add component and real-browser desktop/mobile coverage for position editing, draft confirmation, four-tab navigation, separated invitation workflow and applicant-detail handoff; rebuild the local API and company SPA (SC-001, SC-017-SC-019)

## Phase 24: Recruiter Position Workspace Redesign

**Purpose**: Recompose a position around applicant operations while keeping quick edits modal,
criterion history internal and invitation work available without leaving the applicant list.

- [X] T259 Lane A — Redesign `PositionOperations` and `PositionInvitations` as `지원자 목록 / 지원자 통계 / 면접 단계 / 포지션 정보`, add a collapsible right invitation panel, keep applicant-detail links, expose current configured criteria without version language, and move basic/criterion editing into accessible modals in `apps/company-console/src/features/company/` and `apps/company-console/src/features/hiring/` (FR-007-FR-012, FR-049, FR-053-FR-056, SC-001)
- [X] T260 Integration — Rebuild the company SPA and add real-browser desktop/mobile coverage for the redesigned position workspace, invitation-panel collapse, quick-edit and criterion-edit modals, version-language exclusion and applicant-detail handoff (SC-017-SC-019)

## Phase 25: Relational Integrity and Hot-Path Access Paths

**Purpose**: Make the database enforce the criterion axis it already assumed, remove a duplicated
guidance column, and give the reporting and interview read paths index access instead of sequential
scans. Recommendations were validated against the code and measured before being applied; two were
rejected on evidence rather than implemented.

- [X] T261 Integration — Align the ORM composite primary keys, unique constraints and foreign keys with the migration DDL and add parity tests over shared tables, composite PKs, named indexes, foreign keys and unique constraints in `backend/tests/integration/migrations/test_orm_matches_migrations.py` (Principle II, Principle IV)
- [X] T262 Lane D — Add 20 foreign-key and lookup indexes for report, transcript, recording, session-event, submission-chunk, invitation and deletion read paths in `backend/alembic/versions/integration/i_004_hot_path_indexes.py`, verified by `EXPLAIN` showing `Index Cond` rather than `Filter` (SC-017)
- [X] T263 Lane D — Replace the per-report-item evidence and review lookups with set-based loads in `backend/src/interview_evidence/reporting/repositories/postgres.py` (SC-017)
- [X] T264 Lane A — Enforce the JobRequirement criterion axis with `fk_job_requirements_criterion` over `(company_id, competency_model_version_id, criterion_code)` in `backend/alembic/versions/integration/i_005_job_requirement_criterion_fk.py`, using batch mode so SQLite-backed test databases recreate the table (FR-007-FR-012, Principle I)
- [X] T265 Lane A — Drop the unread `good_evidence` and `weak_evidence` columns that duplicate `verification_guide.strong_answer_signals` / `weak_answer_signals` in `backend/alembic/versions/integration/i_006_drop_duplicate_evidence.py`, and remove them from the domain, API schema, service snapshot, repository and published contract (FR-007-FR-012)
- [X] T266 Lane A — Delete requirement rows before the criteria they reference when replacing a criterion version in `backend/src/interview_evidence/company_management/repositories/postgres.py`, covered by a regression test that enforces SQLite foreign keys because the existing publish tests use the in-memory repository (FR-007-FR-012, Principle IV)
- [X] T267 Lane A — Report domain criterion-version validation failures as 422 and publish conflicts as 409 instead of 500 in `backend/src/interview_evidence/company_management/api/company_routes.py`, matching the existing `updatePosition` convention (FR-007-FR-012, SC-001)
- [X] T268 Integration — Reject the HNSW plus full-text GIN index recommendation on measurement: the weighted-sum `ORDER BY` in `backend/src/interview_evidence/submission_analysis/adapters/postgres_hybrid.py` cannot use a vector index (26.4ms to 24.5ms, unchanged), and at realistic selectivity the scoped query already runs 1.75ms through `ix_retrieval_scope`, so both indexes would add write cost to the live interview path for no read gain (PD-06, SC-017)
- [X] T269 Integration — Reject the dead-column removal recommendation on code reading: the `submission_analyses` JSON columns are reconstructed by `_analysis_from_row` for the idempotency check and deletion-target enumeration, and `applicant_profiles.display_name` backs applicant identity verification (FR-013-FR-015, Principle II)

## Phase 26: Deferred Product Decisions

**Purpose**: Hold the work the product owner has explicitly postponed, so it is not lost and not
started early. None of these are defects. Each needs a product decision before implementation, and
the first one needs a constitution decision.

- [ ] T270 Product — Decide whether a comparable evaluation rubric and score sheet (평가기준표·점수표) may exist, and if so at which layer. Motivation from the product owner: with hundreds of applicants per position a human cannot review each report individually, so recruiters need a comparable ranking or screening aid. This is not blocked by code — `weight` already exists on EvaluationCriterion and nothing forbids a report-level total — but Principle I currently states that retrieval signals MUST NOT become competency scores and that AI MUST NOT set a final decision. A rubric that only aggregates human-reviewable, Evidence-backed criterion states is compatible with Principle I; one derived from retrieval or nonverbal signals is not. Requires an explicit constitution amendment decision recorded in `.specify/memory/constitution.md` before any task is written (Principle I, FR-042-FR-045)
- [ ] T271 Product — Define the arithmetic meaning of `EvaluationCriterion.weight`. It is collected, validated and persisted but has no arithmetic consumer anywhere in the codebase; question ordering uses `job_requirements.priority` in `submission_analysis/application/verification_map.py`. Either give it a consumer or stop presenting it as a weight. Blocks T270 (FR-007-FR-012)
- [X] T272 Lane C — Build an LLM prompt layer before any prompt-level tuning is attempted. `interview_engine/application/question_generator.py` passes a structured dict that `AwsBedrockModel.generate()` serializes directly as the Bedrock body; there is no system prompt, persona instruction or `max_tokens` to swap. Prerequisite for T273 (FR-028-FR-030)
- [X] T273 Lane C — Add the 신입/주니어/시니어 interview difficulty toggle once T272 exists: accept the level as position configuration and vary the generated question depth and follow-up policy. Today the only working difficulty lever is `max_follow_ups`; `time_budget_seconds` is stored on CriterionVerificationGuide but never read by the interview loop. Depends on T271 and T272 (FR-028-FR-030)
- [X] T274 Lane D — Show criterion names instead of raw UUIDs in the review report. `apps/company-console/src/app/routeAdapters.tsx` maps `criterionName: item.criterion_id` because `getInterviewSessionReport` returns only `criterion_id`; the component tests pass a readable `"문제 해결"` and therefore do not catch it. Requires adding the criterion name to the report projection or resolving it in the console (FR-042-FR-045, FR-053-FR-056)
- [X] T275 Lane D — Serve real transcript captions on the review video. `TimelineView` renders `<track kind="captions" />` with no `src`, so the caption track is always empty; the transcript is shown only as the clickable timeline list beside the player. Requires a tenant-scoped WebVTT projection of TranscriptSegment or removing the empty element (FR-037-FR-041)
- [ ] T301 Lane A — Decide the fate of two task environment values that no code reads. `COGNITO_USER_POOL_ID` is supplied by both application roots and `EVENT_BUS_ARN` by the dev root, but neither name appears anywhere in `backend/`, `apps/`, `scripts/` or `packages/`: `AwsCognitoPrincipalProvider` takes only a client, and no EventBridge publisher exists. They are harmless as passed — an unread environment entry costs nothing at runtime — but each one reads as a dependency the application does not have, and the pool id in particular suggests a token-validation path that is not implemented. Either give them a consumer or stop supplying them; left in place deliberately rather than deleted, since neither is this session's to remove (QG-16)

## Phase 27: Two-Environment Deployment Topology

**Purpose**: Reduce the deployment topology from three environments to two on the product owner's
decision. `infra/environments/stage/main.tf` differed from `prod/main.tf` in six values only (NAT
gateway per AZ, Aurora capacity, API and worker desired count, deletion protection, and the state
key), and no environment had ever been applied, so removing it cost no live state and removed a
duplicate root that had to be kept in sync by hand. The dev split into `foundation`, `data-ai` and
`application` is unchanged.

- [X] T276 Lane A — Move the mock-provider plan test from the deleted stage root to `infra/environments/prod/local-plan.tftest.hcl` and rename the Makefile target `infra-plan-dev` to `infra-plan-check`, because the target never planned a dev root and the prod root exercises the wider `nat_gateway_per_az`/Aurora 2-64 path (QG-16)
- [X] T277 Lane A — Delete `infra/environments/stage/` and drop stage from the `infra-validate` root loop, leaving four Terraform roots (QG-16)
- [X] T278 Lane A — Retarget the state-independence and production-protection contract in `infra/tests/test_terraform_contracts.py` from stage-versus-prod to dev-versus-prod, so the unprotected control group is a root that still exists, and remove stage from the three root enumerations (QG-16)
- [X] T279 Integration — Reduce the `.github/workflows/deploy.yml` environment choice to `[dev, prod]`; the existing dev-or-else branch resolves the Terraform root without further change (QG-13-QG-16)
- [X] T280 Integration — Rename `tests/e2e/test_stage_smoke.py` to `tests/e2e/test_prod_smoke.py` and its activation variables from `STAGE_*_URL` to `PROD_*_URL`, keeping the mock-transport path as the local contract and the live request skipped until endpoints exist (QG-13-QG-14)

## Phase 28: Public Repository Analysis Throughput

**Purpose**: Make public Git analysis fast enough and broad enough to be worth showing a recruiter.
`GitHubPublicTransport` had no tests, and three defects survived behind that gap: it deep-fetched
exactly one commit while `GitFetchLimits.max_commits=500` advertised five hundred, it issued every
HTTPS call sequentially, and it read whichever commits were newest on the default branch rather than
the applicant's own. Measured on `pallets/click`, ten commits took 6.16s serially and 1.05s at the
new eight-worker default over the same 72 requests; four consecutive anonymous fetches exhausted the
60-request hourly quota outright, which is what `GITHUB_TOKEN` now addresses.

- [X] T281 Lane B — Analyze up to `max_analyzed_commits` (default 20) commits instead of only the branch head, and keep `commit_count` reporting the full listing so `limits_applied` records that the history was larger than the budget. Order follows the listing rather than completion order, because two runs over one repository must yield the same evidence (FR-016-FR-020)
- [X] T282 Lane B — Issue the commit-detail and blob calls through a bounded `ThreadPoolExecutor` (`max_workers`, default 8). The fetch is entirely network-bound, so this is the difference between an analysis a recruiter waits out and one they abandon (FR-016-FR-020, SC-017)
- [X] T283 Lane B — Filter the commit listing by the applicant's claimed handles and emails server-side via GitHub's `author` parameter, so the request budget is spent on attributable commits. An identity that matches nothing falls back to the branch listing, because applicants mistype handles and the ownership classifier already marks unattributed commits as such (FR-016-FR-020)
- [X] T284 Integration — Pass `GITHUB_TOKEN` through `compose.yaml`, `.env.example` and the README. Anonymous callers get 60 API requests an hour and one analysis can spend all of them; a read-only token needs no scopes for public repositories and raises the ceiling to 5000. The token is sent only as a request header and never reaches a snapshot, an error code or a log line (Principle IV)
- [X] T285 Lane B — Key blobs by the commit they were read at in `workers/analysis/pipeline.py`. One path exists at several contents once more than one commit is analyzed, and keying by path alone would make every commit quote whichever revision was stored last — a question built on the wrong revision is one the applicant cannot answer (FR-016-FR-020)
- [X] T286 Lane B — Tolerate the failures that only appear at multi-commit scale: a root commit with no parent now diffs against Git's empty tree instead of failing the fetch, a deleted file or a blob GitHub no longer serves is skipped, a commit left with no readable file is dropped rather than stored without changed paths, an undecodable file is dropped by the bound, and a `.py` file this interpreter cannot parse costs its own evidence instead of the repository's (FR-016-FR-020)
- [X] T287 Lane B — Cover `GitHubPublicTransport`, which had no tests, in `backend/tests/unit/submission_analysis/test_git_transport.py`. Concurrency is proven with a `threading.Barrier` that deadlocks unless the blob fetches genuinely overlap, so a regression to sequential fetching fails the suite instead of merely running slower. Each of the eight behaviours above was confirmed by injecting the defect and watching a named test fail (QG-04)

## Phase 29: Evidence-Grounded Axis Scores and the Printable Report

**Purpose**: Give the reviewer a per-criterion score they can check against the quote it came from,
and print the result as an A4 document. The product owner asked for section scores so a recruiter can
weigh the system's reasoning rather than read prose alone, and asked that the model rather than a
formula do the judging. Principle I is not amended: what it forbids is a retrieval signal becoming a
competency score and AI setting a final decision, so the axis scores trace to answer intervals only
and no pass/fail verdict is produced anywhere. An earlier formula-based implementation was written and
reverted on the product owner's instruction.

- [X] T288 Lane D — Score each criterion on five fixed axes (`correctness` 정확성, `depth` 깊이, `fundamentals` CS 기본기, `ownership` 본인 기여, `communication` 설명력) declared once in `backend/src/interview_evidence/reporting/application/assessment_prompt.py`. The axis set is fixed and the model may not extend it: `AxisScore` rejects an unknown key, so a model that invents an axis fails validation instead of widening the evaluation axis the company published (Principle I, FR-042-FR-045)
- [X] T289 Lane D — Have the model return the score and the ids of the quotes it relied on, rather than deriving a number in code from counts or similarity. `score` is nullable and `None` means the answers gave no basis to judge that axis; it is never stored as a zero, because a zero reads as a judgement against the applicant when the truth is that the interview never reached the topic (Principle I, FR-042-FR-045)
- [X] T290 Lane D — Persist the axis scores on the report item in `backend/alembic/versions/integration/i_010_report_item_axis_scores.py` and expose them through `AxisAssessmentView` in the published contract, so the console renders what the model actually returned instead of recomputing it (FR-042-FR-045)
- [X] T291 Lane D — Derive `Report.overall_score` as the mean over the criteria that could be scored, and return `unscored_criteria_count` beside it in `backend/src/interview_evidence/reporting/api/company_routes.py`. The mean alone would silently reward an interview that covered less, so the console shows both and the docstring records that this is not a hiring score (Principle I, FR-042-FR-045)
- [X] T292 Lane D — Lay the report out as a tabbed A4 document in `apps/company-console/src/features/review/ReportView.tsx` (종합평가 / 기준별 평가 / 추가 확인), each sheet sized `210mm` by the A4 ratio so the on-screen page matches what prints (FR-053-FR-056)
- [X] T293 Lane D — Print the report as a document rather than a screenshot of the console. Four defects lived behind a green suite, sharing one cause: an equal-specificity print rule loses on source order to the stylesheet that owns the selector, and a container that clips or grids cannot fragment across sheets. The console chrome printed on every page (fixed in `shell.css`, which owns `display` on those selectors); `overflow: hidden` on the panel discarded everything past the first page break instead of paginating; `.report-page` as a three-row grid kept its footer row with the first fragment and printed it over the last criterion; and `.page-content` padding left the sheet inset with the canvas printed around it. The page canvas needed an explicit colour in `base.css` because a transparent root has a background propagated up from the body (FR-053-FR-056)
- [X] T294 Integration — Cover printing in `tests/browser/company-console.spec.ts`, which is the only place the `@media print` rules, the `@page` size and fragmentation exist at all; jsdom has neither layout nor print media. Each clip is asserted as a computed style and pagination as a page count read from the PDF, because Chrome subsets its fonts and the printed text is not extractable. The first footer assertion written here passed with the grid defect reinstated -- `emulateMedia` does not paginate, so bounding boxes stay continuous -- and was replaced with one that fails, then every assertion was confirmed by reverting the fix it guards (QG-04, Principle IV)
- [X] T295 Integration — Repair `scripts/cleanup_test_positions.sql`, which had rotted into two silent failures: `session_checkpoints`, `session_events`, `transcript_segments` and `verification_progress` were never deleted from, and `submission_chunks` was ordered after the analyses it references. Every FK is NO ACTION, so the first violation aborted the whole transaction and left the database untouched — surfacing as two unrelated-looking browser failures over demo applicant counts. Both failure modes are now checked against the migrated schema in `backend/tests/integration/migrations/test_cleanup_script_matches_the_schema.py`, each assertion confirmed by reinstating the defect it catches (QG-04)

## Phase 30: Deployable Container Definitions

**Purpose**: Bring the Terraform roots to the point where an apply would produce a working
deployment, which they were not. Nothing here was visible to `terraform validate`, to the existing
contract tests or to any suite in CI, because the defects lived in the *contents* of a rendered
container definition rather than in the shape of the configuration. Two of them would have surfaced
only as a running deployment failing: the worker task crash-looping before any of our code ran, and
public-repository analysis stopping mid-fetch against GitHub's anonymous quota. The structural cause
is recorded as its own task — CI ran no infrastructure gate at all, so `infra/` was the one tree in
the repository whose breakage no pull request could detect. No environment has been applied, so all
of this is target state, verified by plan and never by a live resource.

- [X] T296 Lane A — Launch the worker through the image virtualenv in `infra/modules/compute/main.tf`. The task specified `command = ["python", "-m", "interview_evidence.worker"]`, but `backend/Containerfile` installs the package with `uv sync --frozen --no-dev --no-editable`, so the interpreter on `PATH` cannot import it: run against the built image, that command exits with `No module named 'interview_evidence'` while the api container beside it, which already used `uv run`, was fine. The worker service would have crash-looped on every deploy, and `deployment_circuit_breaker` would have rolled it back with no application log to explain why. The api command, the `Containerfile` worker `CMD` and the `migrate_database` override in `deploy.yml` all already agreed on `uv run --no-sync`; only this one place did not (QG-16)
- [X] T297 Lane A — Deliver `GITHUB_TOKEN` to both containers as a Secrets Manager reference through a new `task_secrets` variable, wired in `infra/environments/prod/main.tf` and `infra/environments/dev/application/main.tf` from `${name}/application/config:github_token::`. `workers/analysis/runtime.py` reads the variable, and T284 had already established why the analysis needs it — anonymous GitHub allows 60 requests an hour and one real repository analysis can spend that by itself — but no Terraform root passed it, so a deployed reviewer would have seen submission analysis stop mid-fetch. It is delivered as a `secrets` entry and never as a `task_environment` value: a plaintext entry would put the credential in the task definition, in every saved plan and in the deploy log. The container `secrets` block is resolved by the execution role rather than the task role, and the application secret is encrypted with the customer key, so `aws_iam_role_policy.execution_secrets` gained the matching `kms:Decrypt` — without it the task fails to start with an `AccessDeniedException` before any code runs (Principle IV, FR-016-FR-020, QG-16)
- [X] T298 Lane A — Assert the *rendered* task definition in `infra/modules/compute/task-definition.tftest.hcl`, because neither defect above was reachable from a text assertion: the pre-existing contract checked the worker's module name and would have passed with the broken launcher, and a credential that reaches no container is an absence no grep can see. `container_definitions` is unknown until after apply, so the probe runs `command = apply` under `mock_provider` with `override_resource` supplying real-shaped ARNs; scoped to the module, since a mock apply across the prod root fails provider-side ARN validation in network and observability. It decodes the JSON and asserts both containers resolve `GITHUB_TOKEN` from a Secrets Manager ARN, that neither renders it as a plaintext environment entry, and that the worker's argv is exactly the `uv run` form. Two file-level contracts in `infra/tests/test_terraform_contracts.py` back it up, one asserting every container command launches through `uv run --no-sync` rather than banning one broken spelling. All six defect injections were confirmed to fail the intended assertion (QG-04, QG-16)
- [X] T299 Integration — Add an `infrastructure` job to `.github/workflows/ci.yml` running `infra-format-check`, `infra-validate`, `infra-security-check` and `infra-plan-check`. CI ran no infrastructure gate whatsoever, which is why a container command that could never start survived in the repository; every one of these four targets needs no AWS credentials, since fmt and validate are local, the contract tests read files and both plan tests use mock providers (QG-13-QG-16)
- [X] T300 Lane A — Confirm apply-readiness with a real `terraform plan`, which resolves what `validate` cannot: the actual AWS provider's argument validation across every resource, and the four read-only plan-time data sources (`aws_region`, `aws_caller_identity`, `aws_availability_zones`, and the CloudFront origin-facing prefix list). Planned against a throwaway copy with the S3 backend stripped and local state, since no state bucket exists: `prod` plans 161 to add / 0 to change / 0 to destroy across all eight modules, and `dev/foundation` 46 to add. The remaining two dev roots read `terraform_remote_state` from a bucket that does not exist yet, so they cannot be planned until foundation is applied; they compose the same modules the prod plan already covers. The saved plan was also checked to contain no trace of the developer's real token — `container_definitions` is unknown at plan time precisely because it derives from the secret ARN, so the credential cannot reach a plan file (Principle IV, QG-16)
- [X] T302 Lane A — Document the deploy prerequisite Terraform deliberately does not own, in `infra/README.md`: `${name}/application/config` is created as an empty secret with no `aws_secretsmanager_secret_version` anywhere in the tree, because a version resource would put the credential in state. Its `github_token` key must therefore be written out of band before the application root is first applied — a `secrets` entry pointing at a missing key makes the task fail to start with a `ResourceNotFoundException`, again before any application log exists. The root `README.md` claim that the workspace suite "is exactly what CI runs" was also corrected, since CI now runs a second infrastructure job (QG-16)

## Phase 31: Question Rationale Over HTTP

**Purpose**: Make the question rationale actually reach the reviewer. Phase 29 gave every axis score
a traceable quote, but the reviewer's first question about a generated question is why it was asked,
and over HTTP the answer was null for every session — while the unit tests covering the projection
passed, because they constructed the service directly with a provider the running application never
gave it. The lesson is the one this phase is named for: a dependency that is optional in a
constructor signature is a dependency the composition root can silently forget, and only a test that
goes through the composition root can see it.

- [X] T303 Lane D — Pass `rationale_provider=interview_public` where the reporting router is actually composed. `TimelineService` takes the provider as `QuestionRationaleProvider | None`, and with `None` it returns an empty rationale map rather than failing, so every question in every timeline came back with `question_rationale: null` over HTTP — the console showed each question with nothing behind it, exactly as if the model had invented it. The router is composed in two places and both were missing it: `main.py` and `runtime/production.py`, the latter twice over, where a comment now records that this router and not `lane_d.app` is what serves the timeline (FR-037-FR-041, FR-053-FR-056)
- [X] T304 Integration — Cover the wiring through the real composition root in `backend/tests/integration/test_timeline_question_rationale_http.py`, building the app with `create_production_runtime` and walking the recruiter's own path — positions, invitations, then the timeline — rather than calling the service directly, because a direct call is what let the defect through. It asserts every question carries an objective, an accepted policy result and at least one source reference with an excerpt and a locator, and that answers carry no rationale at all, since submitted material must never be attached to what the applicant said (QG-04, Principle I)
- [X] T305 Integration — Fix the demo seed so the reviewable session has rationales to show, verified in `backend/tests/integration/test_local_review_seed.py`. Two defects: follow-up questions were seeded without a rationale, and the timeline joins a rationale to its question through the transcript's `turn_id`, so an interviewer segment written against a different id renders the question with no rationale even when one exists. The test asserts the counts match across all three questions rather than checking only the first — a follow-up with no rationale is precisely the one a reviewer would question — and that every cited source reference belongs to the turn that cited it (FR-030-FR-034, QG-04)
