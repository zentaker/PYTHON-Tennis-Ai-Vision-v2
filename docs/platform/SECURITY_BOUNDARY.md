# Security boundary

Stage 2A is a local development foundation, not a production deployment.
Credentials are supplied through environment variables and the example file
contains development-only MinIO values. No secrets, tokens, videos, models, or
cache volumes are committed.

The API has CORS configured from `TENNISAI_CORS_ORIGINS` with credentials
disabled and browser PUT/GET/HEAD/OPTIONS enabled. MinIO applies and verifies
the versioned localhost:5173 policy while keeping the bucket private.
Presigned URLs expire after the configured interval. Object keys are
server-generated and traversal-resistant. Upload completion trusts storage
metadata only and reports `STORAGE_VERIFIED`; checksum verification is an
explicit later control.

The request middleware emits only method, path, request ID, status and duration;
it never logs request bodies, credentials, or complete presigned URLs. The
public storage endpoint is separated from the internal MinIO endpoint and is
checked before signing.

Authentication, authorization, tenant isolation, rate limiting, malware/video
scanning, TLS termination, retention enforcement, and production IAM remain
outside this gate and must be added before deployment.
