# Core Stage 2B — Analysis job orchestration

Stage 2B is an additive orchestration boundary after the accepted Session API
V1. It persists an analysis run, queues it idempotently, leases it to a future
worker, and finalizes only validated artifact metadata. It does not execute
inference, decode video, load models, or call a cloud provider.

The independent release audit passed as `CORE_STAGE2B_RELEASE_AUDIT_PASSED` at
head `4d5fde966bd36354b77151ece5b28f47c4f3d0e2`. The accepted orchestration
contract is frozen as `CORE_STAGE2B_ANALYSIS_ORCHESTRATION_ACCEPTED`; the public
Analysis Job API is frozen as `ANALYSIS_JOB_API_V1_CONTRACT_FROZEN`. This stage
does not implement the production worker, process video, execute inference, or
call GPU/cloud infrastructure. The worker is a separately scoped future stage.

Frozen gates: `STAGE2B_ANALYSIS_RUN_STATE_MACHINE_PASSED`,
`STAGE2B_IDEMPOTENT_JOB_ORCHESTRATION_PASSED`,
`STAGE2B_ATOMIC_WORKER_LEASE_PASSED`,
`STAGE2B_ARTIFACT_FINALIZATION_CONTRACT_PASSED`,
`STAGE2B_RUNTIME_SECURITY_AUDIT_PASSED`,
`ANALYSIS_JOB_API_V1_CONTRACT_FROZEN`, and
`CORE_STAGE2B_ANALYSIS_ORCHESTRATION_ACCEPTED`.

## State and transitions

Runs start `PENDING` and are atomically moved to `QUEUED`. A worker claims a
queued run as `RUNNING`; successful finalization is `COMPLETE` or `PARTIAL`,
and terminal failures are `FAILED` or `CANCELLED`. An expired running lease is
requeued until `max_attempts` is exhausted, then fails with
`MAX_ATTEMPTS_EXCEEDED`. Cancellation of a queued run is immediate; running
cancellation is cooperative and requires worker acknowledgement.

The session lifecycle remains the frozen Stage 2A enum. Queueing moves
`UPLOADED → QUEUED`, claiming moves `QUEUED → PROCESSING`, and finalization
moves `PROCESSING → COMPLETE|PARTIAL|FAILED`. A queued run cancelled before a
worker claim leaves the session in `QUEUED` because the frozen session API has
no `CANCELLED` status.

## Idempotency and concurrency

`(session_id, processing_profile)` has a partial unique index for active runs
(`PENDING`, `QUEUED`, `RUNNING`). Repeated unkeyed requests may return the
existing active run; keyed requests reuse only an identical key and request
fingerprint, while incompatible keys return a conflict. Queue claiming uses a
row lock with `SKIP LOCKED` on PostgreSQL; the lease token is opaque and is
never derived from credentials.

The default lease is 60 seconds. Heartbeats renew it for another 60 seconds.
Reclaim clears all lease fields before requeueing. The default retry budget is
three attempts and each run may configure one to ten attempts.

## Artifact finalization

Workers submit metadata only. Every object key must be under
`runs/{run_id}/bundle/`, contain no query string, and have a non-negative size,
non-empty media type, unique key, and a 64-hex SHA-256. Bundle fingerprints
are also 64-hex SHA-256 values. No presigned URL, local path, video bytes, or
secret is accepted by the contract.

`result_manifest` uses one convention only: a complete canonical object key.
The worker harness must build it with `bundle_artifact_key(run_id,
relative_path)` before calling `complete` or `partial`; values such as
`manifest.json`, Windows paths and URL-like references are rejected rather than
having the bundle prefix added automatically.

The worker-facing Python contract is in
`src/platform/services/worker_contract.py`; it is a harness, not a worker
implementation.
