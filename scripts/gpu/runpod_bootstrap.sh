#!/usr/bin/env bash
# Prepare a RunPod Ubuntu GPU Pod without starting WASB inference.

set -euo pipefail

REPO_DIR="${RUNPOD_REPO_DIR:-/workspace/PYTHON-Tennis-Ai-Vision-v2}"
PYTHON_VERSION="${RUNPOD_PYTHON_VERSION:-3.11}"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "ERROR: bootstrap requires Linux; found $(uname -s)." >&2
  exit 1
fi
if [[ ! -r /etc/os-release ]]; then
  echo "ERROR: /etc/os-release is unavailable." >&2
  exit 1
fi
# shellcheck disable=SC1091
source /etc/os-release
if [[ "${ID:-}" != "ubuntu" ]]; then
  echo "ERROR: bootstrap requires Ubuntu; found ${PRETTY_NAME:-unknown}." >&2
  exit 1
fi
if [[ ! -d "$REPO_DIR/.git" ]]; then
  echo "ERROR: clone the repository at $REPO_DIR before bootstrap." >&2
  exit 1
fi
if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "ERROR: nvidia-smi is unavailable; the Pod has no usable NVIDIA runtime." >&2
  exit 1
fi

echo "== RunPod GPU =="
NVIDIA_SMI_OUTPUT="$(nvidia-smi)"
printf '%s\n' "$NVIDIA_SMI_OUTPUT"
if ! grep -q "CUDA Version:" <<< "$NVIDIA_SMI_OUTPUT"; then
  echo "ERROR: NVIDIA driver does not report CUDA capability." >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1 || ! command -v git >/dev/null 2>&1 \
  || ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends ca-certificates curl git ffmpeg
fi

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
command -v uv >/dev/null 2>&1 || { echo "ERROR: uv installation failed." >&2; exit 1; }

cd "$REPO_DIR"
LOCK_BEFORE="$(sha256sum uv.lock | awk '{print $1}')"
uv python install "$PYTHON_VERSION"
uv sync --frozen --python "$PYTHON_VERSION" --extra dev --extra tracker
LOCK_AFTER="$(sha256sum uv.lock | awk '{print $1}')"
if [[ "$LOCK_BEFORE" != "$LOCK_AFTER" ]]; then
  echo "ERROR: uv.lock changed during frozen synchronization." >&2
  exit 1
fi

for required in \
  data/clips/nivel_a2_01/source.mp4 \
  data/clips/nivel_a2_01/clip_manifest.json \
  data/clips/nivel_a2_01/homography.json \
  data/clips/nivel_a2_01/court_corners_pixel.json \
  models/wasb/wasb_tennis_best.pth.tar; do
  [[ -f "$required" ]] || { echo "ERROR: missing $REPO_DIR/$required" >&2; exit 1; }
done
[[ -d third_party/WASB-SBDT/src ]] \
  || { echo "ERROR: missing $REPO_DIR/third_party/WASB-SBDT/src" >&2; exit 1; }

bash scripts/gpu/verify_runpod_environment.sh

uv run --frozen pytest -q \
  tests/test_clip_manifest.py \
  tests/test_canonical_frames.py \
  tests/test_stage2_a2_preflight.py \
  tests/test_wasb_runner_a2.py

mkdir -p outputs/nivel_a2_01/stage_2/logs
uv run --frozen python scripts/stage2_a2_preflight.py \
  --video data/clips/nivel_a2_01/source.mp4 \
  --manifest data/clips/nivel_a2_01/clip_manifest.json \
  --homography data/clips/nivel_a2_01/homography.json \
  --checkpoint models/wasb/wasb_tennis_best.pth.tar \
  --wasb-root third_party/WASB-SBDT \
  --output-csv data/clips/nivel_a2_01/wasb_detections.csv \
  --output-overlay outputs/nivel_a2_01/stage_2/wasb_detections_overlay.mp4 \
  --require-runtime \
  > outputs/nivel_a2_01/stage_2/logs/bootstrap_preflight.json

echo "Bootstrap PASS. Preflight completed without inference."
echo "WASB was NOT executed. Run Stage 2 explicitly with run_stage2_a2_remote.sh."
