# Security boundary

Stage 2A is a local development foundation, not a production deployment.
Credentials are supplied through environment variables and the example file
contains development-only MinIO values. No secrets, tokens, videos, models, or
cache volumes are committed.

The API has CORS configured from `TENNISAI_CORS_ORIGINS` with credentials
disabled and browser PUT/GET/HEAD/OPTIONS enabled. Local object storage records
the selected `cors_mode` explicitly: the normal mode is `bucket_policy` with
the versioned localhost:5173 policy; the explicit compatibility mode is
`global_api_local_development`, limited to localhost:5173 with
`bucket_policy_applied: false`. Both modes keep the bucket private, and
production S3 must configure its own CORS policy. Runtime evidence reports GET
and HEAD only when those Origin requests are actually observed.
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
