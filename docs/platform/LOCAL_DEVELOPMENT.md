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

The API image installs locked dependencies during build with
`uv sync --frozen --extra platform`. `start-api.sh` applies Alembic migrations,
verifies the database is at head, and only then `exec`s Uvicorn. The Compose API
healthcheck probes `GET /healthz`. MinIO images are pinned to
`minio/minio:RELEASE.2024-01-16T16-07-38Z` and
`minio/mc:RELEASE.2024-08-26T10-49-58Z`.

On hosts without Docker, report `DOCKER_RUNTIME_MISSING_LOCAL`. Unit tests and
static validation remain valid; the approved CI run supplies the PostgreSQL/
MinIO runtime evidence. This release records 12 unit tests, 2 integration tests,
and 44 real HTTP observations (27 positive and 17 negative).

The CI runtime evidence is generated from the integration JUnit XML, the real
HTTP observations, the doctor report, the MinIO `mc cors info/get` check and
the browser preflight. It fails closed on test failures/skips, non-localhost
presigned endpoints, an unready doctor, a public bucket, missing localhost
CORS PUT, secrets, full presigned URLs or video bytes. The four derived reports
are `cors-report.json`, `presigned-endpoint-report.json`, `security-summary.json`
and `runtime-test-summary.json`. The summary distinguishes the two pytest
integration functions from positive and negative HTTP observations; an
observation is never relabeled as a test.

The release is local-only and not exposed to the public Internet. Authentication
and an analysis worker are intentionally absent; no inference is run and no
video is versioned.
