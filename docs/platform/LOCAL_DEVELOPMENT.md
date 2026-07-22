# Local development

Requirements: Python 3.11, `uv`, and Docker Engine with Compose. The checked-in
stack has PostgreSQL, MinIO, a one-shot bucket initializer, and the API:

```bash
cp infrastructure/session-platform/.env.example .env
docker compose -f infrastructure/session-platform/compose.yml up --build
uv run --extra platform tennisai platform doctor
uv run --extra platform tennisai platform migrate
uv run --extra platform tennisai platform seed-stage1b-reference
```

The seed is metadata-only: it records the accepted Stage 1B title and bundle
fingerprint and never copies a video or local path. `tennisai platform api` runs
the development server without starting any processing worker.

On hosts without Docker, report `DOCKER_RUNTIME_MISSING`. Unit tests and static
validation remain valid, but PostgreSQL/MinIO integration tests must not be
described as passed.
