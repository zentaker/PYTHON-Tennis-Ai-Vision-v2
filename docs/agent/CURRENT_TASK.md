# Current task

Core Stage 1B — real Single Rally bundle accepted and released.

Core Stage 2A — Session Platform foundation is implemented on
`agent/session-platform-stage2a` and is ready for final contract review. The FastAPI Session API
V1, PostgreSQL/Alembic model, MinIO/S3 adapter, presigned upload lifecycle, CLI,
OpenAPI candidate, Compose stack, tests and documentation are included. Docker
was unavailable locally (`DOCKER_RUNTIME_MISSING`), so PostgreSQL/MinIO
integration is explicitly pending locally; no inference, GPU, cloud, video or
model work was performed.

The API architecture addendum is implemented: FastAPI remains the HTTP layer;
repositories isolate SQLAlchemy queries; routes return DTOs only; errors use a
uniform request-ID envelope; structured request logging excludes presigned URLs
and credentials; and the Postman collection/environment are derived and checked
against the OpenAPI snapshot in CI.

Runtime patch status: browser-facing public storage URLs, pinned MinIO images,
build-time dependency installation, migration-gated API startup, real doctor
checks and HTTP integration coverage are implemented. The final contract
precision patch and derived runtime evidence semantics are implemented; the
release audit remains pending as `SESSION_PLATFORM_API_V1_CONTRACT_PENDING_RELEASE_AUDIT`.

The patch fixes exact 64-hex SHA-256/fingerprint constraints, removes impossible
session `INVALID_REQUEST` documentation, normalizes download signer failures to
a safe HTTP 503 envelope, and keeps Postman upload metadata in collection
variables only. `SESSION_PLATFORM_API_V1_FROZEN` has not been declared.
