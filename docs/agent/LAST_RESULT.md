# Last result

- Branch: `agent/player-perception-p1-free-ci-gate`.
- CI-gate commit: `a7946bd32b068d2d14ec29bf6dcdca1eadff116c`.
- Workflow run: `29605537750` (third and final permitted iteration for this pass).

## Validation

- `uv run pytest` — 200 passed.
- `uv run ruff check .` — passed.
- `uv run python -m compileall src scripts tests` — passed.
- `uv run python scripts/replit_smoke_test.py` — passed.
- `git diff --check` — passed.

## Blocker

The container built and the OpenMMLab imports completed, but the asset gate was invoked
as `python scripts/ci_free_runtime_gate.py` and failed before downloading assets with
`ModuleNotFoundError: No module named 'src'`. Because that step was allowed to continue,
the next step ran without downloaded models and failed with `missing detector checkpoint`.
The branch contains the corrected module invocation (`python -m scripts.ci_free_runtime_gate`),
but the three-iteration limit prevents claiming a validated rerun in this pass.

## Intentionally unexecuted

- No GPU provider, RunPod, Modal, SSH or browser.
- No Mac model downloads.
- No 527-frame job, WASB, Stage 5B, Stage 5C or Stage 6.

## Next action

Rerun the corrected free CI gate only in a separately authorized pass; keep runtime
readiness blocked until the complete CPU whole-body inference and checksum report pass.
