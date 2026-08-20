# Interview Evidence Platform

Structured interview platform with React, FastAPI, and Terraform.

## Structure

`apps/` contains the web clients, `backend/` the API and workers, and `infra/` the AWS resources.

## Run it locally

```bash
make dev-install
cp .env.example .env    # fill in the AWS section
make up
make api                # then `make worker` and `npm run dev:company` alongside
```

See [docs/local-development.md](docs/local-development.md) — in particular which AWS services have
no local substitute and are billed on your credentials.

## Build

```bash
make bootstrap
npm run format:check
npm run lint
npm run typecheck
npm run build
```
