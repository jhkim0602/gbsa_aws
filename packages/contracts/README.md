# Contracts

Canonical REST, WebSocket and asynchronous event contracts for all four lanes.

- `openapi/root.yaml` is generated from the approved feature OpenAPI document and references
  lane-owned path fragments.
- `events/` contains canonical JSON Schema sources.
- `generated/` contains read-only Python and TypeScript output.

Run `npm run contracts:generate` after an approved contract change and
`npm run contracts:check` before review. Do not edit generated files by hand.
