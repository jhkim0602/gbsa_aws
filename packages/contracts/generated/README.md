# Generated Contracts

These files were generated from `packages/contracts/openapi/` and
`packages/contracts/events/`. **There is no longer a generator, so they are now edited by
hand.**

Commit `7d977f7` removed `scripts/generate_contracts.py` together with everything it
needed: its input spec, `datamodel-code-generator`, `openapi-typescript`,
`json-schema-to-typescript`, and the `generate` / `check` scripts this file used to
document. `npm run contracts:generate` and `npm run contracts:check` do not exist.

## What that means when you change a response

`typescript/openapi.d.ts` is imported by both SPAs — `apps/company-console/src/app/api/companyClient.ts`
and each app's `src/app/routeAdapters.tsx`, through `@iep/contracts`. A field the frontend
reads must exist here or `npm run typecheck` fails. That is the only automatic check left,
and it covers only the fields the frontend actually uses.

So a new response field is three hand edits, in this order:

1. `packages/contracts/openapi/` — the contract. **Nothing verifies this one.**
2. `generated/typescript/openapi.d.ts` — what the SPAs compile against.
3. The route itself.

Skipping step 1 leaves the published contract describing an API that no longer exists, with
no test failure to say so.

`python/` is imported by nothing. It has no consumer and no check; treat it as stale
documentation rather than a contract.
