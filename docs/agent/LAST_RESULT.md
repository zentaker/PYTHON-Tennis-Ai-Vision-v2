# Last result

- Branch: `agent/player-perception-p1-free-ci-gate`.
- CI commit: `ef6955314544c2ebb6820a93cb67fb2b377346de`.
- Workflow run: `29620560537`.

## Validation

- Assets and both checkpoint SHA-256 values verified in run `29620417425`.
- Container build, validate-only and OpenMMLab import inspection passed in run `29620560537`.
- Local `uv run pytest` — 200 passed.
- Local `uv run ruff check .` — passed.
- Local compileall, smoke and diff check — passed.

## Blocker

The real CPU inference step failed with `ModuleNotFoundError: No module named 'addict'`
while importing MMEngine. The two allowed corrections for this CI pass are exhausted;
runtime readiness remains `BLOCKED`.

## Intentionally unexecuted

No RunPod, Modal, SSH, paid GPU, 527-frame job, WASB, Stage 5B, Stage 5C or Stage 6.
