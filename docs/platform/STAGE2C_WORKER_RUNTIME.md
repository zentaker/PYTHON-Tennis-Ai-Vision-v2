# Core Stage 2C — Worker Runtime Foundation

Stage 2C adds the production-shaped execution shell around the frozen Analysis
Job contract. `tennisai worker run` claims one queued run at a time, renews its
lease from an independent database session, watches cancellation, publishes
validated objects through the storage adapter, and finalizes through the
existing internal worker contract.

The default `contract-fixture` processor writes two small JSON files in
`<worker-root>/<run-id>/<attempt>/`. It performs no video processing, model
loading, tracking, inference, GPU work, or cloud execution. `STANDARD` produces
`COMPLETE`, `FAST` produces `PARTIAL`, and `TACTICAL` deliberately exercises the
public `FAILED` path for deterministic integration evidence.

## Local execution

```sh
uv run --extra platform tennisai worker run --once \
  --worker-id local-worker --worker-version stage2c-contract-fixture
```

The Compose `worker` service uses the same command and internal MinIO/Postgres
endpoints. It is started explicitly for runtime integration evidence; the
Session and Analysis HTTP contracts remain unchanged.

Lease ownership belongs to the attempt that claimed the run. Heartbeats use a
new SQLAlchemy session and a stale or lost lease causes the runtime to abandon
publication and remove any objects it staged. Expired attempts are requeued by
the approved Stage 2B service up to `max_attempts`; a worker never retries by
mutating the state machine itself. Cancellation is observed from a separate
polling session, signalled to the processor, and acknowledged only with the
current lease. SIGINT/SIGTERM stop new claims and allow the current attempt to
clean its workspace.

The processor seam is intentionally narrow:

- `AnalysisContext` contains immutable run metadata, an attempt workspace, and
  a cancellation event;
- `AnalysisResult` contains a terminal status and local artifact paths;
- `AnalysisProcessor` has one `process` method.

Only the runtime publishes objects or changes run state. Logs contain event,
run status, and duration fields, never lease tokens, credentials, signed URLs,
local paths, or exception traces.

Runtime events (`claim`, `run_finished`, `run_failed`, `lease_lost`,
`cleanup_failed`, and idle polls) are structured log records. No external
metrics service is introduced in this foundation stage. A later stage may
replace the fixture with a real analysis processor after a separate contract
and evidence gate.
