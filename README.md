# Interview Evidence Platform

Structured interview platform with React, FastAPI, and Terraform.

## Structure

`apps/` contains the web clients, `backend/` the API and workers, and `infra/` the AWS resources.

## Build

```bash
make bootstrap
npm run format:check
npm run lint
npm run typecheck
npm run build
```
