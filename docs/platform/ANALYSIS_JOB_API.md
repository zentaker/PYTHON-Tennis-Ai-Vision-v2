# Analysis Job API V1 (candidate)

The additive FastAPI application is `src.platform.api.analysis_app:create_analysis_app`.
It is deliberately separate from the frozen Session API application and is
served by the local Compose `analysis-api` service on port 8001.

| Method | Path | Operation ID | Purpose |
| --- | --- | --- | --- |
| POST | `/api/v1/analysis-runs` | `requestAnalysisRun` | idempotently queue a run |
| GET | `/api/v1/analysis-runs/{run_id}` | `getAnalysisRun` | read run state |
| GET | `/api/v1/sessions/{session_id}/analysis-runs` | `listSessionAnalysisRuns` | list session runs |
| POST | `/api/v1/analysis-runs/{run_id}/cancel` | `cancelAnalysisRun` | cancel or request cancellation |

The snapshot is `config/platform/analysis_job_api_v1.openapi.json`; its current
SHA-256 is recorded by `scripts/validate_analysis_job_contract.py`. The
snapshot is generated from the FastAPI application and is the only HTTP
contract source. Operation IDs, DTOs, examples, status codes, and the uniform
error envelope are checked in CI.

OpenAPI is served at `/api/v1/analysis/openapi.json`, with interactive docs at
`/analysis-docs` and ReDoc at `/analysis-redoc`. No route executes SQL or calls
object storage directly.
