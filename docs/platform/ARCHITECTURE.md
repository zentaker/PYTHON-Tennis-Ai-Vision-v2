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

The contract snapshot is frozen and auditable under
`SESSION_PLATFORM_API_V1_FROZEN`; it is stored at
[session_api_v1.openapi.json](../../config/platform/session_api_v1.openapi.json).
The Postman collection is derived from this same OpenAPI source. The platform
is local-only, not public Internet infrastructure, has no authentication, and
has no analysis worker yet.

The registered style is
`SESSION_PLATFORM_API_STYLE = LAYERED_FASTAPI_COMPATIBLE_WITH_EXISTING_EXPRESS_MENTAL_MODEL`.
The layers remain recognizable and intentionally one-directional:

`api/app.py` (bootstrap, CORS, handlers, routers) → `api/routes` (HTTP only) →
`api/dependencies` (DB/storage/config/auth seam) → `services` (use cases) →
`db/repositories` (SQLAlchemy queries) → `db/models` (persistence), with
`schemas`, `storage`, and `domain` providing DTOs, MinIO/S3, and invariants.

Routes do not execute SQL, call boto3, or expose ORM objects as public DTOs.
