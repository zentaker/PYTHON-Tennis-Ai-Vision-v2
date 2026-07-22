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
`videoId`, and `analysisRunId`; it contains no credentials or secrets. The
collection variables `uploadUrl`, `uploadContentType`, `uploadSizeBytes`, and
`uploadSha256` are populated by the initiate request and are not environment
secrets.

Executable workflow:

1. Create a session; the test script stores `sessionId`.
2. Initiate an upload with the source filename, content type, positive size and
   optional 64-hex SHA-256; the test script stores `videoId` and `uploadUrl`.
3. Run **Upload bytes to presigned URL**, select the local file in Postman's
   binary file picker, and send the PUT with `{{uploadContentType}}`. No bytes
   or video files are embedded in this collection.
4. Complete the upload with the same content type, byte size and SHA-256 used
   during initiation. The API verifies object HEAD metadata before marking it
   `STORAGE_VERIFIED`.
5. List session media, analysis runs and artifacts. The generated collection
   keeps these requests derived from the same OpenAPI snapshot.
