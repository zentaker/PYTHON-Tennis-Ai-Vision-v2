# Object storage and upload lifecycle

Object keys are generated server-side and validated as safe POSIX paths:

- source video: `sessions/{session_id}/source/{video_id}/{safe_filename}`
- bundle artifact: `runs/{run_id}/bundle/{relative_path}`

The browser never chooses an arbitrary bucket key. `POST .../uploads` validates
the media type (`video/mp4` or `video/quicktime`), matching extension, positive
size, and the configured maximum. It returns a short-lived presigned PUT URL.
The browser uploads directly to MinIO/S3, then calls the complete endpoint.

Completion performs an object `HEAD` and compares size and content type with the
initiation metadata. Success records `STORAGE_VERIFIED`; it does not claim
`HASH_VERIFIED` unless a future integrity worker actually computes a checksum.
Missing or mismatched objects are marked `FAILED` and do not advance the
session to `UPLOADED`.
