#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLIP_ID="${P1_CLIP_ID:-nivel_a2_01}"
OUTPUT_DIR="${P1_OUTPUT_DIR:-$ROOT_DIR/outputs/$CLIP_ID/stage_p1}"
MODEL_BUNDLE="${P1_MODEL_BUNDLE:-$ROOT_DIR/config/player_perception/p1_openmmlab.json}"
cd "$ROOT_DIR"
FRAMES="$(uv run python - <<'PY'
import json
from pathlib import Path
print(",".join(str(item) for item in json.loads(Path("config/player_perception/p1_smoke_frames.json").read_text())["frames"]))
PY
)"
uv run python -m src.player_perception.cli \
  --clip-id "$CLIP_ID" \
  --backend "${P1_BACKEND:-openmmlab}" \
  --device "${P1_DEVICE:-cuda}" \
  --model-bundle "$MODEL_BUNDLE" \
  --config-root "${P1_CONFIG_ROOT:-.}" \
  --video "${P1_VIDEO:-data/clips/$CLIP_ID/source.mp4}" \
  --manifest "${P1_MANIFEST:-data/clips/$CLIP_ID/clip_manifest.json}" \
  --homography "${P1_HOMOGRAPHY:-data/clips/$CLIP_ID/homography.json}" \
  --trajectory "${P1_TRAJECTORY:-outputs/$CLIP_ID/stage_3/smoothed_trajectory.csv}" \
  --events "${P1_EVENTS:-outputs/$CLIP_ID/stage_4/events.json}" \
  --output-dir "$OUTPUT_DIR" \
  --frames "$FRAMES" \
  --render \
  --fail-on-missing-models
uv run python scripts/validate_stage_p1_outputs.py "$OUTPUT_DIR" --frames "$FRAMES"
