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
precision patch and derived runtime evidence semantics are implemented. The
release audit passed as `CHATGPT_CORE_STAGE2A_RELEASE_AUDIT_PASSED`; Session API
V1 is frozen as `SESSION_PLATFORM_API_V1_FROZEN` and Stage 2A is accepted as
`CORE_STAGE2A_SESSION_PLATFORM_ACCEPTED`.

The patch fixes exact 64-hex SHA-256/fingerprint constraints, removes impossible
session `INVALID_REQUEST` documentation, normalizes download signer failures to
a safe HTTP 503 envelope, and keeps Postman upload metadata in collection
variables only. The release tag is `tennisai-session-platform-v1.0.0`.

Core Stage 2B is implemented on `agent/analysis-jobs-stage2b` from frozen main
`b3703003fe2aa23f8703097b0dc155c7825f5363`. The additive analysis API,
Alembic migration, idempotent queue, atomic lease/heartbeat/reclaim logic,
artifact finalization contract, worker harness, OpenAPI snapshot, Compose
analysis-api service, tests and documentation are present. No worker,
inference, GPU, cloud, video or secret work was performed. Candidate gates are
review-pending; do not merge or create a release tag before the release audit.
