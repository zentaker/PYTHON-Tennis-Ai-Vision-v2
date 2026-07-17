# Player perception runtime

Provider-neutral CPU/CUDA-capable contract. Mount the repository and external assets
at `/workspace`, inputs at `/input`, weights at `/models`, and outputs at `/output`.
The image never downloads weights during build. OpenMMLab extras are pinned in
`requirements-openmmlab.txt`; checkpoint files are external and verified by the model
bundle. The normal entrypoint is `python -m src.player_perception.cli`, and the image
supports `--validate-only` without loading weights.

The manifest may resolve configs from the checked-out repository or from the `/models`
mount. A provider smoke must therefore mount the exact config/checkpoint bundle and
verify its checksums before execution.

The ten-frame command is documented in `scripts/run_stage_p1_smoke.sh`. It is a provider
smoke contract, not a visual accuracy gate.
