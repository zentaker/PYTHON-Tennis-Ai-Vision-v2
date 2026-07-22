# Session Platform architecture

Stage 2A adds a local-first session platform around the existing Core Analysis
Bundle. The boundary is deliberately narrow: FastAPI owns HTTP contracts,
SQLAlchemy/Alembic owns PostgreSQL persistence, and an `ObjectStorage` protocol
isolates S3-compatible storage (MinIO locally). Core analysis remains a separate
package and is never imported by `src.platform`.

```text
browser -> FastAPI Session API V1 -> PostgreSQL (metadata)
                      |             -> MinIO/S3 (video and bundle objects)
                      `-> Core bundle boundary (future worker, not Stage 2A)
```

There is no queue, worker, Redis, Celery, authentication provider, cloud
provider, tracking, detection, or inference in this stage. The API is suitable
for a local development stack only; production credentials and networking are
intentionally not supplied.

The contract candidate is frozen as `SESSION_PLATFORM_API_V1_CONTRACT_CANDIDATE`
in [session_api_v1.openapi.json](../../config/platform/session_api_v1.openapi.json).
