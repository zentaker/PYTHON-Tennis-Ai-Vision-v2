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

The canonical OpenAPI snapshot is generated with:

```bash
uv run --extra platform python scripts/export_session_api_openapi.py
```

It must remain deterministic. The API deliberately has no auth claims and no
passwords or secrets in its schema.
