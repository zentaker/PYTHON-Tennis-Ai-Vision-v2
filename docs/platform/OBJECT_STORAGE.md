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

MinIO CORS is versioned at `infrastructure/session-platform/minio/cors.xml`.
`minio-init` applies that file with `mc cors set local/$S3_BUCKET
/config/cors.xml`, verifies it with `mc cors info` (falling back to `mc cors
get` on older clients), and checks that the bucket remains private. The
runtime evidence exporter additionally performs a real preflight from
`http://localhost:5173` and requires PUT. `MINIO_API_CORS_ALLOW_ORIGIN` remains
configured for compatibility with the pinned MinIO image.

Completion performs an object `HEAD` and compares size and content type with the
initiation metadata. Success records `STORAGE_VERIFIED`; it does not claim
`HASH_VERIFIED` unless a future integrity worker actually computes a checksum.
Missing or mismatched objects return typed domain errors and do not advance the
session to `UPLOADED`. A repeated complete request is idempotent only after the
session is `UPLOADED`, metadata matches, and integrity is already
`STORAGE_VERIFIED`.
