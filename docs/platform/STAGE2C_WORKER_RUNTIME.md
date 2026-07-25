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
  --processor contract-fixture --allow-contract-fixture \
  --worker-id local-worker --worker-version stage2c-contract-fixture
```

The normal CLI has no processor fallback and exits safely when no real
processor is configured. The fixture requires both `--processor
contract-fixture` and `--allow-contract-fixture`; it is not real analysis. The
Compose worker is isolated under the `stage2c-evidence` profile and is never
started by an unprofiled `docker compose up`.

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

Processor artifact descriptors contain controlled relative paths. The runtime
rejects traversal, symlink, directory, duplicate, hardlink, and size violations
before reading. Objects use exclusive keys such as
`runs/{run_id}/bundle/attempt-1/manifest.json`; partial uploads are compensated
and cleanup is restricted to the attempt's own publication set.

The configured worker root, run directory, and attempt directory are accepted
only as real directories. Their device/inode identities are captured before
processor execution and checked again before publication and cleanup. A
processor that deletes, renames, or replaces the workspace (including with a
symlink) fails closed; cleanup never resolves or follows a replacement. Artifact
reads use `lstat`, `O_NOFOLLOW` where available, `fstat`, a single-link check,
the filesystem size before reading, and a `max_artifact_bytes + 1` read bound.

Release evidence is generated from JUnit testcase names and fails closed when
required tests are skipped or absent. The Stage 2C security auditor scans the
generated reports, worker log, Compose state, and structured evidence for lease
tokens, signed URLs, credentials, local workspace paths, tracebacks, video
files, unsupported file types, and unsupported positive claims. A security
summary is produced by that scan; it is not a hardcoded status.

The evidence suite names the proof points explicitly: symlink-to-file inside
and outside the workspace, symlinked parent, hardlink, duplicate descriptor and
key, single and aggregate size limits, bounded sparse-file rejection, workspace
root/run/attempt replacement, lease loss before and after publication,
shutdown during processing and finalization, cancellation/lease-loss race,
partial-upload compensation, and stale-attempt recovery. The PostgreSQL/MinIO
scenario pauses Worker A after its first successful publication, expires and
requeues attempt 1 through Stage 2B, lets Worker B complete attempt 2, then
resumes Worker A; production cleanup removes attempt-1 objects automatically,
without a test-side delete. A skipped integration or PostgreSQL testcase
prevents evidence export and therefore prevents artifact publication.

Runtime events (`claim`, `run_finished`, `run_failed`, `lease_lost`,
`cleanup_failed`, and idle polls) are structured log records. No external
metrics service is introduced in this foundation stage. A later stage may
replace the fixture with a real analysis processor after a separate contract
and evidence gate.
