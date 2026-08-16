# Module Boundary Changes

## Lane A

`get_criterion_version` adds immutable requirements and verification guides while retaining existing
criterion fields during rollout.

## Lane B

| Interface | Input | Output |
|---|---|---|
| `index_criterion_version` | scoped version | receipt |
| `build_verification_map` | invitation/applicant/version | immutable map |
| `get_verification_map` | map ID | targets, versions and budgets |
| `retrieve_context` | scope, criterion, target, query, config | ranked excerpts and scores |
| `resolve_source_reference` | scoped source ID | protected excerpt and locator |

Raw text never appears in events or logs.

## Lane C

Session snapshots add verification progress. Final Turn interfaces remain the only assessment input.

## Lane D

Review projections add QuestionRationale display fields. Evidence contracts reject retrieval or
claim IDs as Evidence.
