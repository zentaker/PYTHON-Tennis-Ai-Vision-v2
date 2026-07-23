# Session API V1 candidate

The FastAPI application is created by `src.platform.api.app:create_app` and is
versioned as `v1`:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/healthz` | process health |
| POST | `/api/v1/sessions` | create a session |
| GET | `/api/v1/sessions` | list sessions with cursor/status/order |
| GET | `/api/v1/sessions/{session_id}` | fetch session metadata |
| POST | `/api/v1/sessions/{session_id}/uploads` | issue a presigned upload |
| POST | `/api/v1/sessions/{session_id}/uploads/{video_id}/complete` | verify upload by object HEAD |
| GET | `/api/v1/sessions/{session_id}/media` | issue a presigned media download |
| GET | `/api/v1/sessions/{session_id}/analysis-runs` | list analysis runs |
| GET | `/api/v1/sessions/{session_id}/artifacts` | list run artifacts |

The canonical OpenAPI snapshot is frozen at
`config/platform/session_api_v1.openapi.json` (SHA-256
`1747670500014598e6d18f5130e8c7f341323f4fe15f96559d9c5da0550f346b`). It was
generated from source commit
`d599e468f618d798916432b0f68ddb527969c80a` with:

```bash
uv run --extra platform python scripts/export_session_api_openapi.py
```

It must remain deterministic. The API deliberately has no auth claims and no
passwords or secrets in its schema.

FastAPI serves the snapshot at `/api/v1/openapi.json`, interactive docs at
`/docs`, and ReDoc at `/redoc`. Every operation has a stable `operationId`, a
tag, request/response schemas, status-code documentation, examples, and the
uniform `{ "error": { "code", "message", "details", "request_id" } }`
error envelope.

Documented domain error codes are status-specific: 400 (`INVALID_CURSOR`),
404 (`SESSION_NOT_FOUND`, `VIDEO_NOT_FOUND`,
`STORAGE_OBJECT_MISSING`), 409 (`SOURCE_VIDEO_ALREADY_EXISTS`,
`INVALID_SESSION_STATE`, `UPLOAD_METADATA_MISMATCH`, `UPLOAD_SHA_MISMATCH`,
`STORAGE_OBJECT_MISMATCH`), 413 (`VIDEO_SIZE_EXCEEDED`), 422
(`VALIDATION_ERROR`, `INVALID_SHA256`, `UNSUPPORTED_VIDEO_CONTENT_TYPE`,
`VIDEO_EXTENSION_MISMATCH`) and 503 (`STORAGE_SIGNING_FAILED`). Every response
uses the `ErrorResponse` envelope and includes a request ID example.

`STORAGE_SIGNING_FAILED` is returned as HTTP 503 when either signer fails. The
download path uses the exact message `storage could not sign the download` and
`details.operation = "download"`; upload failures use the corresponding upload
operation detail. No storage exception is exposed.

Response DTOs use domain enums for session, media, integrity, analysis-run,
processing-profile and artifact values. SHA-256 fields are 64 hexadecimal
characters (`^[0-9a-fA-F]{64}$`) and are normalized to lowercase internally.
The same exact constraint applies to `bundle_fingerprint` in session and run
responses.

Release gates: `CHATGPT_CORE_STAGE2A_RELEASE_AUDIT_PASSED`,
`SESSION_PLATFORM_API_V1_FROZEN`, and `CORE_STAGE2A_SESSION_PLATFORM_ACCEPTED`.
