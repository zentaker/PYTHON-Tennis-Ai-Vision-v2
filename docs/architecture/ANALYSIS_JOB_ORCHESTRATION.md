# Core Stage 2B analysis-job contract

This document describes the candidate orchestration contract. It is not a
production worker specification and does not claim release acceptance.

## Cancellation linearization

Cancellation is serialized with worker mutations by the PostgreSQL row lock on
the analysis-run row. The linearization rule is:

1. If `cancel_requested_at` is committed while the run is `RUNNING`, subsequent
   `complete`, `partial`, and `fail` operations reject with
   `ANALYSIS_CANCELLATION_INVALID`.
2. The worker must acknowledge the request through the internal cancellation
   contract. Acknowledgement transitions the run to `CANCELLED` and invalidates
   the lease.
3. If a terminal state is committed first, a later cancellation request rejects
   and never changes the terminal result.

Queued and pending runs are cancelled directly and never become claimable.
Heartbeat, finalization, acknowledgement, and cancellation all lock the row;
lease tokens and expiry are checked while holding that lock. Expired lease
recovery uses `FOR UPDATE SKIP LOCKED`, clears the old token, and requeues only
the currently expired running attempt. A stale worker therefore cannot renew,
publish, or finalize after reclaim.

Artifact references are canonical object keys under
`runs/{run_id}/bundle/`. URL forms, traversal, encoded traversal, local paths,
cross-run references, duplicate keys, and non-positive sizes are rejected.
Worker failure text is never persisted as a public message; only allow-listed
codes and fixed safe messages are exposed.

Only one non-terminal run may exist for a session at a time, regardless of
processing profile. Different profiles are legitimate requests once the prior
run is terminal (or cancelled), and idempotency keys are scoped to the
session/request fingerprint so they cannot collapse different payloads.
When no key is supplied, the request is protected from concurrent duplicate
enqueue by the active-session constraint but a later terminal request may
legitimately create a new run.
