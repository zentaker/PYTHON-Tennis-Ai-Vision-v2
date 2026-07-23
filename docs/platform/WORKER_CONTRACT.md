# Worker contract (internal)

`WorkerContractClient` is the internal boundary for a future analysis worker.
It provides claim, heartbeat, completion, partial completion, failure, and
cooperative-cancellation acknowledgement operations backed by the orchestration
service. The client carries only an opaque lease token and worker identity.

The contract does not start a worker, call inference, load a model, read a
video, or contact cloud infrastructure. A worker may finalize only while its
lease is valid and only with artifact metadata that passes the bundle-prefix,
size, media-type, and SHA-256 checks.

Worker identity is a bounded printable identifier. Authentication and durable
authorization are future seams; no credential is persisted or logged in Stage
2B. Lease expiry and retry recovery are deterministic and observable through
the service-level tests.
