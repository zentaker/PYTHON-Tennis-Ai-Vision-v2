# Object storage and upload lifecycle

Object keys are generated server-side and validated as safe POSIX paths:

- source video: `sessions/{session_id}/source/{video_id}/{safe_filename}`
- bundle artifact: `runs/{run_id}/bundle/{relative_path}`

The browser never chooses an arbitrary bucket key. `POST .../uploads` validates
the media type (`video/mp4` or `video/quicktime`), matching extension, positive
size, and the configured maximum. It returns a short-lived presigned PUT URL.
The browser uploads directly to MinIO/S3, then calls the complete endpoint.

The API uses two endpoints: `TENNISAI_S3_INTERNAL_ENDPOINT_URL` is used for
HEAD/PUT/GET/DELETE and existence checks, while
`TENNISAI_S3_PUBLIC_ENDPOINT_URL` is used only by the signing client. Local
Compose uses `http://minio:9000` internally and `http://localhost:9000` for
browser URLs. The signer uses MinIO-compatible path addressing; the public
endpoint is validated and never permits the internal `minio` host.

The local runtime selects and records one explicit CORS mode. The preferred
mode is `bucket_policy`: `minio-init` applies
`infrastructure/session-platform/minio/cors.xml`, verifies it with `mc cors
info/get`, and checks that the bucket remains private. If the pinned client
cannot apply a bucket policy, the explicit fallback is
`global_api_local_development`, which sets the MinIO API CORS origin only to
`http://localhost:5173`; it never marks `bucket_policy_applied` true and the
bucket remains private. Production S3 configuration must define its own CORS
policy. The runtime evidence exporter publishes the observed mode and only
publishes GET/HEAD when an Origin request actually returns CORS headers.

Completion performs an object `HEAD` and compares size and content type with the
initiation metadata. Success records `STORAGE_VERIFIED`; it does not claim
`HASH_VERIFIED` unless a future integrity worker actually computes a checksum.
Missing or mismatched objects return typed domain errors and do not advance the
session to `UPLOADED`. A repeated complete request is idempotent only after the
session is `UPLOADED`, metadata matches, and integrity is already
`STORAGE_VERIFIED`.
