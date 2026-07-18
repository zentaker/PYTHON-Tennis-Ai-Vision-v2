# Last result

- Branch: `agent/player-perception-p1-free-ci-gate`.
- CI gate commit: `85a70b593ecf198a5bdcb3dd5f7eebe6f3f0d3a0`.
- Workflow run: `29623031561` — success.

## Runtime gate

- Container build: passed.
- Dependency preflight: `python -m pip check` passed.
- Matrix: PyTorch 2.1.2 / CUDA 12.1 / MMCV 2.1.0 / MMEngine 0.10.4 /
  MMDetection 3.2.0 / MMPose 1.3.2.
- Official configs and checkpoints: downloaded and SHA-256 verified.
- Real CPU inference: passed on one licensed fixture image.
- Whole-body output: 133 keypoints; detector and tracker outputs generated.

## Local validation

- `uv run pytest` — 200 passed.
- `uv run ruff check .` — passed.
- `uv run python -m compileall src scripts tests` — passed.
- `uv run python scripts/replit_smoke_test.py` — passed.
- `git diff --check` — passed.

## Scope remaining

This status means only that the container, dependency stack, official assets and
minimal CPU inference are ready for a separately authorized freemium GPU smoke. No
RunPod, Modal, SSH, paid GPU, 527-frame job, WASB, Stage 5B, Stage 5C or Stage 6 was
executed. `SimpleIoUTracker` remains an explicit fallback rather than validated
ByteTrack.
