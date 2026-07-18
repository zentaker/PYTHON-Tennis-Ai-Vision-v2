# GPU provider acceptance gate

No provider is selected yet. A future provider must pass every check before Stage P1
real inference is authorised.

| # | Requirement | Evidence | Status |
|---:|---|---|---|
| 1 | No user-managed IP |  | PENDING |
| 2 | SSH not required for normal flow |  | PENDING |
| 3 | Data independent of physical host |  | PENDING |
| 4 | Disposable worker |  | PENDING |
| 5 | Storage separate from worker |  | PENDING |
| 6 | One manual authentication step |  | PENDING |
| 7 | One execution command |  | PENDING |
| 8 | Same container local/remote |  | PENDING |
| 9 | Ten-frame smoke before full job |  | PENDING |
| 10 | Automatic result download |  | PENDING |
| 11 | Retry on different hardware |  | PENDING |
| 12 | Configurable budget limit |  | PENDING |
| 13 | CLI-accessible logs |  | PENDING |
| 14 | CLI cancellation |  | PENDING |
| 15 | No provider-specific code |  | PENDING |
| 16 | Recovery procedure tested |  | PENDING |
| 17 | Preparation under 15 minutes after setup |  | PENDING |

This execution does not configure, recommend or access any provider.

## Modal P1 adapter evaluation

The isolated adapter in `infrastructure/modal/` is prepared from the validated
`containers/player-perception/Dockerfile` and pins the official `modal==1.5.2`
SDK. GitHub Actions run `29629324522` instantiated the real SDK objects in memory;
the offline dry-run reports `READY_FOR_MODAL_SDK_OFFLINE` without authentication or
a cloud call. Static evidence
is present for no managed IP, no normal SSH, disposable workers, v1 Volumes independent
of the worker, one future authentication, one future command, the same Dockerfile,
ten-frame input packaging, automatic upload/download design, L4 → A10 → T4 fallback,
900-second/zero-retry guards, CLI logs/cancellation, provider-neutral core and budget
guards.

| Modal requirement | Evidence | Status |
|---|---|---|
| Same validated Dockerfile | `infrastructure/modal/p1_smoke.py` uses `Image.from_dockerfile` | PASS (static) |
| Official SDK API shape | `modal==1.5.2`, workflow `29629324522` | PASS (offline) |
| Disposable GPU worker | `single_use_containers=True`, no deploy/web/schedule/detach | PASS (static) |
| GPU fallback | L4, A10, T4 in `config/providers/modal_p1_smoke.json` | PASS (static) |
| Independent v1 storage | `Volume.from_name(..., create_if_missing=True)` at `/assets` and `/results` | PASS (static) |
| Ten-frame smoke and guarded cost | exact package, 900 s, one GPU, zero retries, approval file | PASS (static) |
| Authentication and workspace budget | approval file remains absent/false | PENDING |
| Recovery and cleanup | CLI checklist prepared, not executed remotely | PENDING |
| GPU execution and visual outputs | no Modal call has been made | PENDING |
| Preparation under 15 minutes after setup | not measured | PENDING |

Provider status: `READY_FOR_MODAL_ACCOUNT_REVIEW`; SDK/API gate passed, but Modal is
not authenticated or accepted and no GPU smoke has been executed.
