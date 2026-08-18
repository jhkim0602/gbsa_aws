# Predeployment and UI Alignment Validation Report

**Validated baseline**: `b803918` plus the Phase 10/11 acceptance tree; the accepted tree is committed
after this report and its hash is recorded in the following documentation commit
**Executed**: 2026-08-15, Asia/Seoul  
**Environment**: macOS local development host and Docker Engine 28.1.1  
**Integration reviewer**: Codex Integration Owner (automated implementation review)  
**Human release reviewer**: Unassigned; required before the saved Terraform plan or production
promotion is approved

## Verdict

The core implementation is ready for deployment preparation. All locally executable contracts,
application paths, failure modes, privacy controls, migrations, container health checks, regression
gates, and stage-equivalent Terraform planning pass. No unresolved critical implementation or local
verification gap is known. The company shell, Overview, position list, guided position flow and
Evidence review workspace have entered the approved Figma-reference alignment baseline.

Reference alignment is intentionally incomplete rather than represented by demo screens. Applicant
shell/access/submission/interview work, company candidate pipeline/overview, and the final cross-route
visual gate remain assigned to T212 and T214-T218.

The following are release gates, not hidden implementation passes:

- live stage CloudFront/API smoke requires provisioned stage endpoints;
- pilot usability, review-time, question-relevance, and applicant survey targets require human users;
- AWS quota, managed-service latency, and cumulative pilot volume require the deployed stage.

No AWS apply or production mutation was performed.

## Contract and Migration Baseline

| Artifact | Accepted version |
|---|---|
| REST | OpenAPI 3.1, application contract `1.0.0` |
| WebSocket | JSON Schema draft 2020-12, protocol `v1` |
| Async events | `event_version: 1` |
| Lane A migration | `a_001_company_hiring` |
| Lane B migration | `b_001_submission_analysis` |
| Lane C migration | `c_001_interview_session` |
| Lane D migration | `d_001_reporting` |
| Integration merge | `merge_001_lane_heads` |
| Integration head at this baseline | `m_002_runtime_persistence` |

The head advanced after this report was written; see the Phase 25 addendum at the end of this
document for the current value.

`make contracts-generate`, `make contracts-check`, and `make migration-check` pass without drift.
Empty databases and databases already at the four lane heads both converge through the merge
revision to the current integration head. UI reference alignment did not change REST, WebSocket or
event schemas.

## Functional Requirement Coverage

| Requirements | Primary executable evidence | Result |
|---|---|---|
| FR-001-FR-005 | `tests/e2e/test_thin_journey.py`, `test_human_control.py`, `test_tenant_isolation.py` | PASS |
| FR-006-FR-012 | Lane A contract/unit/integration suite and isolated quickstart | PASS |
| FR-013-FR-015 | Invitation exchange, identity, consent, withdrawal, and analysis authorization tests | PASS |
| FR-016-FR-022 | Lane B document/Git analysis, partial failure, provenance, retrieval, and strategy tests | PASS |
| FR-023-FR-027 | Equipment, authoritative session, answer finalization, recording, and recovery tests | PASS |
| FR-028-FR-030 | Context builder, tenant-filtered retrieval, question policy, and SourceReference tests | PASS |
| FR-031-FR-036 | Timeline sequence, idempotency, state machine, reconnect, degraded mode, and completion tests | PASS |
| FR-037-FR-041 | Timeline/media alignment, Evidence integrity, and SourceReference separation tests | PASS |
| FR-042-FR-045 | Report generation, append-only human review, and human-only final decision tests | PASS |
| FR-046-FR-049 | Retention, full-store deletion, audit redaction, and protected logging tests | PASS |
| FR-050 | Retry, DLQ, timeout, degraded-mode, and deletion-resume tests | PASS |
| FR-051-FR-052 | Versioned 19-case regression runner and local load/latency reports | PASS |
| FR-053-FR-057 | Checked-in reference captures, company shell, API-backed company views, guided hiring, synchronized Evidence review and browser tests | PARTIAL: company baseline passes; T212 and T214-T218 remain |

The complete company-to-human-decision journey also exercises FR-001 through FR-052 through the
composed FastAPI runtime and the real cross-lane public adapters.

## Success Criteria Coverage

| Criterion | Local evidence | Status before deployment |
|---|---|---|
| SC-001 | Lane A isolated publish journey | LOCAL PASS; 30-minute novice usability measurement is a pilot gate |
| SC-002 | Retrieval/question corpus 4/4 with recall@k 1.0 | LOCAL PASS; 80% company relevance survey is a pilot gate |
| SC-003 | Review projection, timeline search, and Evidence seek | FUNCTIONAL PASS; comparative review-time study is a pilot gate |
| SC-004 | Evidence corpus 7/7; unsupported confirmed/partial states rejected | PASS |
| SC-005 | Required items resolve to Evidence or explicit insufficient state | PASS |
| SC-006 | Complete review, override, note, bookmark, and decision UI paths | FUNCTIONAL PASS; 80% reviewer survey is a pilot gate |
| SC-007 | 15/15 local interview journeys completed, 0 failures | LOCAL PASS; managed-service completion rate is a stage/pilot gate |
| SC-008 | Duplicate/reconnect suite 5/5, no duplicate Turn | PASS |
| SC-009 | One-question policy, repeat/explanation, and additional-answer states | FUNCTIONAL PASS; 80% applicant survey is a pilot gate |
| SC-010 | Consent is recorded before analysis, recording, or assessment | PASS |
| SC-011 | AI/system final decisions rejected; automated final decisions 0 | PASS |
| SC-012 | Evidence seek p95 0.0015 seconds over 20 local samples, threshold 2 seconds | PASS |
| SC-013 | Five concurrent sessions over three batches, 15/15 complete | LOCAL PASS; cumulative hundreds and AWS quotas are a stage/pilot gate |
| SC-014 | Cross-route, worker, search, object, and hot-view leakage cases 0 | PASS |
| SC-015 | 31/31 deletion targets verified absent after injected retry | PASS |
| SC-016 | Unsupported confirmed/partial regression cases 0 | PASS |
| SC-017 | 13 desktop + 13 mobile reference captures and manifest | PASS |
| SC-018 | Real Chrome `/company -> /positions -> /hiring`, API and asset checks | PASS |
| SC-019 | 390px company hiring capture has no clipped primary action | PARTIAL: applicant routes remain under T212/T215-T218 |

## Quality Gate Coverage

| Gate | Evidence | Result |
|---|---|---|
| QG-01 | Full thin end-to-end journey | PASS |
| QG-02 | Evidence integrity and unsupported-claim regression | PASS |
| QG-03 | Human-only decision and nonverbal-scoring denial | PASS |
| QG-04 | Tenant isolation across every access surface | PASS |
| QG-05 | Consent, retention, and incomplete-deletion state controls | PASS |
| QG-06 | Durable and derived deletion residue verification | PASS |
| QG-07 | Deterministic forbidden/duplicate/multipart/axis-change question policy | PASS |
| QG-08 | WebSocket envelope, sequence, idempotency, and reconnect | PASS |
| QG-09 | Immutable source locator and strategy provenance | PASS |
| QG-10 | Tenant/applicant pre-filtered hybrid retrieval | PASS |
| QG-11 | Composed API/worker/two-SPA production-contract stack and review paths | PASS |
| QG-12 | Versioned retrieval, question, and Evidence regression corpora | PASS |
| QG-13 | ECS/deployment ownership contracts and local stage smoke client | PASS locally; live stage smoke required after apply |
| QG-14 | Private/encrypted infrastructure contracts and CloudFront edge plan | PASS locally; live stage smoke required after apply |
| QG-15 | Code-unit ownership, exact-symbol retrieval, AOSS/Bedrock plan | PASS |
| QG-16 | Independent state roots, saved-plan workflow, five root validates, merged Alembic head | PASS |

## Failure and Privacy Observations

- Repeating answer completion, uploads, and jobs returns the existing durable result.
- Recovery uses the last final Turn and durable checkpoint; stale sequence cannot overwrite server
  state.
- Retrieval failure uses a common criterion question, synthesis failure uses text-only mode, and
  model failure pauses with a retryable technical state.
- A forced OpenSearch deletion timeout leaves the manifest `retrying`; the next attempt completes
  only after all 31 targets verify absence.
- Logs and audit metadata contain opaque IDs, versions, counts, and error codes only. Applicant
  source text, answers, credentials, tokens, and signed URLs are prohibited by tests.
- SourceReference is stored only as question provenance. Only a final applicant answer with valid
  transcript/media ranges can become Evidence.

## Executed Artifacts

- Command-level results: `quickstart-results.md`
- Full E2E: `tests/e2e/test_thin_journey.py`
- Tenant isolation: `tests/e2e/test_tenant_isolation.py`
- Deletion residue: `tests/e2e/test_deletion_residue.py`
- Human control: `tests/e2e/test_human_control.py`
- Stage smoke: `tests/e2e/test_stage_smoke.py`
- Company browser E2E: `tests/browser/company-console.spec.ts`
- Accepted UI screenshots: `tests/browser/artifacts/`
- Regression: `tests/regression/run_regression.py`
- Load and seek: `tests/load/interview_load.py`, `tests/load/evidence_seek.py`
- Infrastructure contracts: `infra/tests/test_terraform_contracts.py`
- Stage-equivalent plan: `infra/environments/stage/local-plan.tftest.hcl`

## Remaining Release Gates

1. Assign a named human release reviewer.
2. Apply the reviewed saved plan to stage through the deployment workflow.
3. Set the three `STAGE_*_URL` values and run the live stage smoke test.
4. Confirm Transcribe, Bedrock, MediaConvert, SES, and other managed-service quotas and latency.
5. Run the pilot measurements explicitly marked above before claiming their population percentages.
6. Complete T212 and T214-T218, then run the final desktop/mobile visual and applicant browser
   regression before declaring reference UI alignment complete.

These items do not require local code reconstruction. They are intentionally outside a no-apply
predeployment validation.

## Addendum: Phase 25 Relational Integrity

**Executed**: 2026-08-16, Asia/Seoul

The baseline above is kept as the record of what was verified on 2026-08-15. Phase 25 (T261-T269)
changed the migration head and two HTTP status mappings after that date.

| Artifact | Value after Phase 25 |
|---|---|
| Current integration head | `m_006_drop_duplicate_evidence` |
| Added revisions | `m_004_hot_path_indexes`, `m_005_requirement_criterion_fk`, `m_006_drop_duplicate_evidence` |

- `fk_job_requirements_criterion` now enforces that a JobRequirement resolves to an
  EvaluationCriterion in the same company and criterion version.
- `createCompetencyModelVersion` returns 422 instead of 500 when a `criterion_code` has no matching
  criterion or a criterion code is duplicated. `publishCompetencyModelVersion` returns 409 instead
  of 500 on a stale `If-Match-Version` or an already-published version. Both were server faults
  reported for client mistakes.
- The regression suite grew to 203 passing tests. Tenant-isolation integration tests now enable
  `PRAGMA foreign_keys=ON`, without which SQLite silently ignores every foreign key and the
  delete-ordering defect fixed in T266 could not be observed.
- REST, WebSocket and event schemas are unchanged. Error responses continue to resolve through the
  single `default` response, so no operation enumerates 4xx codes.

## Addendum: Phase 27 Two-Environment Topology

**Executed**: 2026-08-17, Asia/Seoul

The report above was written when three environments existed. On the product owner's decision the
stage environment was removed, so the following entries above are superseded rather than corrected.

| Item above | Value after Phase 27 |
|---|---|
| Terraform roots | 4: `dev/foundation`, `dev/data-ai`, `dev/application`, `prod` |
| "Stage-equivalent plan" artifact | `infra/environments/prod/local-plan.tftest.hcl` |
| "Stage smoke" artifact | `tests/e2e/test_prod_smoke.py` |
| Live smoke activation variables | `PROD_COMPANY_URL`, `PROD_APPLICANT_URL`, `PROD_API_URL` |
| Deployment workflow environments | `dev`, `prod` |
| Plan verification command | `make infra-plan-check` |

- `infra/environments/stage/` held no `terraform.tfstate`, consistent with the "No AWS apply or
  production mutation was performed" statement above, so deletion released no live infrastructure.
- Every release gate below that names stage now applies to prod. Gate 2 reads as applying the
  reviewed saved plan to prod, and gate 3 as setting the three `PROD_*_URL` values. The QG-13 and
  QG-14 rows keep their local PASS; the live request they defer to is now a prod request.
- QG-16 read "five root validates" and now covers four. The relocated plan test asserts the same
  three conditions and additionally exercises the prod-only `nat_gateway_per_az = true` and Aurora
  2-64 configuration that the stage root did not plan, so plan-time coverage widened.
- The stage-versus-prod protection contract became dev-versus-prod: the unprotected control group is
  now `dev/foundation` and `dev/data-ai`, which are roots that still exist.
- No application code, REST, WebSocket, event schema or migration changed.

## Addendum: Phase 30-31 Deployable Container Definitions

**Executed**: 2026-08-18, Asia/Seoul

The report above validated infrastructure by static analysis, root `validate` and a mock-provider
plan test. That was not sufficient, and two defects passed all of it. Both lived in the *contents* of
a rendered container definition, which the configuration's shape does not constrain.

| Item above | Value after Phase 30-31 |
|---|---|
| QG-16 "four root validates" | Unchanged, plus a real `terraform plan`: `prod` 161 to add / 0 change / 0 destroy, `dev/foundation` 46 to add |
| Plan verification command | `make infra-plan-check` now also runs `infra/modules/compute/task-definition.tftest.hcl` |
| Infrastructure gates in CI | Previously none. A second `infrastructure` job runs all four `make infra-*` targets |
| Contract test count | `infra/tests/test_terraform_contracts.py` 9 → 11 |
| Provider lock files | 4 → 5, all pinning aws `5.100.0`; `infra/modules/compute/` acquired one because the plan gate now inits it |

- The ECS worker would not have started. Its `command` was `["python", "-m",
  "interview_evidence.worker"]` while the image installs the package into a uv virtualenv, so the
  task exits on `ModuleNotFoundError` before any application code runs — confirmed against the built
  image, not inferred. The report's "no AWS apply was performed" is why this was still catchable.
- `GITHUB_TOKEN` reached no deployed container, so public-repository analysis would have run against
  the 60-request anonymous quota. It is now a `secrets` reference resolved by the execution role,
  never a plaintext environment entry.
- `validate` resolves no data sources and runs no provider-side argument validation; a saved plan
  does both. The plan additionally proves the credential cannot leak into a plan file:
  `container_definitions` is unknown at plan time because it derives from the secret ARN, and the
  developer's real token appears nowhere in the saved plan JSON.
- Question rationale was null over HTTP for every session while its unit tests passed, because the
  reporting router is composed in two runtime files and neither passed the optional
  `rationale_provider`. Coverage now goes through `create_production_runtime` rather than
  constructing the service directly, which is what let the defect through.
- The two dev roots that read `terraform_remote_state` still cannot be planned before
  `dev/foundation` is applied. They compose the same modules the prod plan covers.
- Release gate 2 acquires a prerequisite: `${name}/application/config` is created empty, and its
  `github_token` key must be written before the application root is first applied, or the task fails
  to start with a `ResourceNotFoundException`.
- No REST, WebSocket, event schema or migration changed. `COGNITO_USER_POOL_ID` and `EVENT_BUS_ARN`
  remain supplied to tasks and read by no code, recorded as T301 rather than removed.

## Addendum: Phase 32 Playable Recording

**Executed**: 2026-08-18, Asia/Seoul

FR-037 and FR-038 were recorded as covered above, and the reviewer could not play a single second of
video. Three defects on one path, none of them visible to a passing suite:

| Layer | What shipped | What the tests saw |
|---|---|---|
| Playback locator | `https://media.local/playback`, then `url: null` once the presigner became optional and every root omitted it | Locator unit tests passed — they asserted the shape of the response, not that the URL resolved |
| Media worker | A recording asset naming a `.m3u8` manifest no code produced | Manifest tests passed — `build_manifest` was handed the key as a parameter |
| Local seed | An asset with `status: ready` and no bytes uploaded anywhere | `test_local_review_seed.py` asserted `ready` for a bucket-less seed, so the test encoded the defect |

- The root cause is uniform: **no test followed the URL the endpoint returned.** Each layer was
  covered in isolation, and the contract between them — that a `ready` asset names bytes a presigner
  can sign — was asserted nowhere. `head-object` on the key the console put in `<video src>` returned
  404 the entire time.
- `assembled_recording_key()` is now the one definition of the assembled object's layout. The second
  copy of that f-string is what let the worker and the review screen disagree about where the
  recording lives, so it is a function rather than a repeated literal.
- Two keys per session are intentional and documented: transcripts and Evidence cite the chunk they
  were transcribed from, while the reviewer plays the assembled object. Deletion enumerates them
  separately.
- Verified live against the compose stack on a clean volume, not inferred: `head-object` 200 with
  `ContentType: video/webm`, `ContentLength 73596` and `ServerSideEncryption: aws:kms`; the timeline
  endpoint returning `status: ready` with a 5-minute expiry; `curl` on the signed URL returning 200
  and bytes beginning `1a45 dfa3`; `ffprobe` reporting `vp9`, `320x180`, `duration=160.000000`.
- Both new tests are mutation-verified. Reverting the presigner wiring fails the HTTP test with
  `assert 'unavailable' == 'ready'`; repointing `<video src>` at a nonexistent key fails the browser
  test with the element's own `error` event. A test that cannot fail is what produced this phase.
- Local-stack caveat: a database seeded before this change cannot be repaired by re-seeding. Both
  seed helpers return early once a session exists, and Lane D's report projections are deliberately
  write-once (`save_report` raises `"AI original report is immutable"`), so a stale asset row keeps
  pointing at the old key while S3 holds the new object. `docker compose down -v` is the reset path.
- Gates after the change: backend 313 passed; frontend 93 passed (23 applicant + 70 company);
  company e2e 13 passed, applicant e2e 2 passed; `ruff format --check`, `ruff check`, `mypy` (157
  files), eslint, tsc, `make contracts-check`, `make boundaries-check`, `make migration-check`,
  `make infra-format-check`, `make infra-validate` and `make infra-security-check` all clean.
- No REST, WebSocket, event schema, migration or Terraform resource changed. The MediaConvert
  adapter, port and IAM role now have no consumer at all — assembly needs no transcode — and are
  recorded as T311 rather than removed.
