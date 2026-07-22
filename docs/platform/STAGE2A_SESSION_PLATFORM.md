# Stage 2A Session Platform foundation

Status: `CORE_STAGE2A_SESSION_PLATFORM_READY_FOR_REVIEW`

Gate: `CHATGPT_CORE_STAGE2A_SESSION_PLATFORM_AUDIT`

This candidate adds the Session API V1, PostgreSQL/Alembic metadata model,
S3-compatible object-storage adapter, MinIO/PostgreSQL Compose stack, CLI
doctor/migration/seed commands, deterministic OpenAPI evidence, and isolated
`platform` dependencies. `src.platform` imports do not load torch, torchvision,
ultralytics, OpenCV, models, tracking, or inference code.

The local unit suite covers transition rules, object-key safety, SQLite model
behaviour, upload HEAD verification, import isolation, OpenAPI stability, and
the metadata-only Stage 1B seed. Docker was unavailable in the execution
environment (`DOCKER_RUNTIME_MISSING`), so no PostgreSQL/MinIO integration run
is claimed. Cloud calls, GPU calls, inference, videos committed, secrets
committed, and spend are all zero.
