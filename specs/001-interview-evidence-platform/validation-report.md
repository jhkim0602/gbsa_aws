# Predeployment Validation Report

**Validated commit**: `1622f749951a5ed5a29dbe33800777f6b4d054a5`  
**Executed**: 2026-08-15, Asia/Seoul  
**Environment**: macOS local development host and Docker Engine 28.1.1  
**Integration reviewer**: Codex Integration Owner (automated implementation review)  
**Human release reviewer**: Unassigned; required before the saved Terraform plan or production
promotion is approved

## Verdict

The implementation is ready for deployment preparation. All locally executable contracts,
application paths, failure modes, privacy controls, migrations, container health checks, regression
gates, and stage-equivalent Terraform planning pass. No unresolved critical implementation or local
verification gap is known.

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
| Integration head | `merge_001_lane_heads` |

`make contracts-generate`, `make contracts-check`, and `make migration-check` pass without drift.
Empty databases and databases already at the four lane heads both converge on the integration head.

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

These items do not require local code reconstruction. They are intentionally outside a no-apply
predeployment validation.
