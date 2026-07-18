#!/usr/bin/env bash
set -euo pipefail

IMAGE="${P1_IMAGE:-tennis-player-perception:dev}"
docker run --rm --gpus "${P1_GPU_FLAG:-all}" \
  -v "${PWD}:/workspace:ro" -v "${P1_INPUT_DIR:-$PWD/data}:/input:ro" \
  -v "${P1_OUTPUT_DIR:-$PWD/outputs/player_perception}:/output" \
  -v "${P1_MODEL_DIR:-$PWD/models}:/models:ro" "$IMAGE" \
  --clip-id "${P1_CLIP_ID:-nivel_a2_01}" --backend "${P1_BACKEND:-openmmlab}" \
  --device "${P1_DEVICE:-cuda}" --output-dir /output
