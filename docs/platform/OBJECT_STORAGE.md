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

MinIO CORS is versioned at `infrastructure/session-platform/minio/cors.xml` and
Compose pins the same origin through `MINIO_API_CORS_ALLOW_ORIGIN`; only
`http://localhost:5173` may issue PUT/GET/HEAD with the documented headers.
The bucket remains private and creation is idempotent in `minio-init`.

Completion performs an object `HEAD` and compares size and content type with the
initiation metadata. Success records `STORAGE_VERIFIED`; it does not claim
`HASH_VERIFIED` unless a future integrity worker actually computes a checksum.
Missing or mismatched objects return typed domain errors and do not advance the
session to `UPLOADED`. A repeated complete request is idempotent only after the
session is `UPLOADED`, metadata matches, and integrity is already
`STORAGE_VERIFIED`.
