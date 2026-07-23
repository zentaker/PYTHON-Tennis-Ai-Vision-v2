# Stage 2A Session Platform foundation

Status: `CORE_STAGE2A_SESSION_PLATFORM_ACCEPTED`

Gates: `STAGE2A_LAYERED_API_ARCHITECTURE_PASSED`,
`STAGE2A_BROWSER_UPLOAD_RUNTIME_AUDIT_PASSED`,
`STAGE2A_PERSISTENCE_FOUNDATION_PASSED`,
`STAGE2A_FINAL_CONTRACT_PRECISION_PATCH_IMPLEMENTED`,
`CHATGPT_CORE_STAGE2A_RELEASE_AUDIT_PASSED`,
`SESSION_PLATFORM_API_V1_FROZEN`,
`CORE_STAGE2A_SESSION_PLATFORM_ACCEPTED`

Next product step: TennisWebAI Stage 0C — Session Library and managed uploads.

This candidate adds the Session API V1, PostgreSQL/Alembic metadata model,
S3-compatible object-storage adapter, MinIO/PostgreSQL Compose stack, CLI
doctor/migration/seed commands, deterministic OpenAPI evidence, and isolated
`platform` dependencies. `src.platform` imports do not load torch, torchvision,
ultralytics, OpenCV, models, tracking, or inference code.

API style registration:
`SESSION_PLATFORM_API_STYLE = LAYERED_FASTAPI_COMPATIBLE_WITH_EXISTING_EXPRESS_MENTAL_MODEL`.
The Postman collection is generated from the OpenAPI snapshot and validated in
CI; its environment contains no credentials.

The local unit suite covers transition rules, object-key safety, SQLite model
behaviour, upload HEAD verification, import isolation, OpenAPI stability, and
the metadata-only Stage 1B seed. Docker was unavailable in the execution
environment (`DOCKER_RUNTIME_MISSING`), so no PostgreSQL/MinIO integration run
is claimed. Cloud calls, GPU calls, inference, videos committed, secrets
committed, and spend are all zero. The release evidence contains 12 unit tests,
2 integration tests, and 44 real HTTP observations (27 positive, 17 negative).

The final precision patch constrains every public SHA-256 and bundle fingerprint
to exactly 64 hexadecimal characters, removes impossible `INVALID_REQUEST`
documentation from session create/list, and maps download signing failures to
HTTP 503 `STORAGE_SIGNING_FAILED` with `operation: download`. Postman keeps the
four-key environment free of presigned URLs; upload metadata lives in temporary
collection variables and is cleaned after completion.

The Docker-backed HTTP integration suite exercises health, session creation and
pagination in both directions, independent sessions, public-host presigned
PUT/GET, MinIO CORS preflight, upload completion, download bytes/metadata,
idempotent completion, typed error envelopes and every documented negative
domain case. Runtime reports are derived from those results and the real MinIO
policy check. The approved CORS mode is
`global_api_local_development` with a private bucket. The frozen OpenAPI SHA is
`1747670500014598e6d18f5130e8c7f341323f4fe15f96559d9c5da0550f346b`, sourced from
`d599e468f618d798916432b0f68ddb527969c80a`. The platform is local-only, has no
authentication or analysis worker, and no inference was executed.
