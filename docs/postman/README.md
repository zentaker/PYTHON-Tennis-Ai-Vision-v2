# TennisAI Session API Postman contract

`TennisAI-Session-API.postman_collection.json` is generated from the canonical
OpenAPI snapshot. It is evidence and a client convenience, not a second HTTP
contract. Regenerate it after changing routes or schemas:

```bash
uv run --extra platform python scripts/export_session_api_openapi.py
uv run --extra platform python scripts/export_session_api_postman.py
```

Import the collection and `TennisAI-Local.postman_environment.json` into
Postman. The environment intentionally contains only `baseUrl`, `sessionId`,
`videoId`, and `analysisRunId`; it contains no credentials or secrets.
