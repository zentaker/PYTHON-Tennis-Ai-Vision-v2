# Modal P1 GPU smoke adapter

This directory is the only provider-specific integration. The validated
`containers/player-perception/Dockerfile` is reused verbatim through
`modal.Image.from_dockerfile`; no second dependency matrix exists.

The adapter is intentionally guarded. It does not authenticate, create a remote
App, create Volumes, or spend credits during a dry-run. After one manual Modal
authentication and local budget/credit confirmation, the only execution command is:

```bash
modal run infrastructure/modal/p1_smoke.py
```

Prepare or refresh the local ten-frame package first when source inputs change:

```bash
uv run python scripts/prepare_p1_modal_smoke_inputs.py
uv run python -m infrastructure.modal.p1_smoke --dry-run
```

The dry-run must print `READY_FOR_MODAL_AUTH`. It checks the Dockerfile, the exact
ten frame IDs and SHA-256 values, pinned model checksums, required inputs/outputs,
the L4 → A10 → T4 fallback, 900-second timeout, zero retries, provider-neutral core,
and the `NOT_CONFIGURED` financial/authentication state.

Persistent v1 Volumes are `tennisai-p1-assets` mounted at `/assets` and
`tennisai-p1-results` mounted at `/results`. The local entrypoint uploads only the
frame package and approved Stage 3/4 inputs, waits for the disposable worker, then
downloads outputs into `outputs/nivel_a2_01/stage_p1_modal_smoke/` and validates them.
Checkpoints are downloaded by the worker only when absent and are SHA-256 verified
against the manifest. No video, Git repository, credentials, caches or old outputs
are uploaded.

The untracked `.modal_smoke_approval.json` must contain all four boolean approvals
before any remote call. The repository never creates it or supplies true values.

Cancellation and cleanup are CLI-only. Use `Ctrl+C` for the current ephemeral App,
then inspect/stop it with `modal app list` and `modal app stop APP_ID`; inspect
containers with `modal container list`. `scripts/audit_modal_cleanup.py` prepares a
non-executing checklist and local persistence checks. Results already committed to a
Volume can be recovered with the adapter's automatic download path; retrying uses the
same Volumes and the documented GPU fallback. Volume deletion is an explicit manual
cleanup action and is never performed automatically.

This adapter does not claim visual accuracy, GPU execution, zero cost, P1 approval or
provider acceptance. Those remain pending human/provider gates.
