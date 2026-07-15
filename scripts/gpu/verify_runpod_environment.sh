#!/usr/bin/env bash
# Report and gate the Linux/CUDA runtime and every Stage 2 A2 input.

set -euo pipefail

REPO_DIR="${RUNPOD_REPO_DIR:-/workspace/PYTHON-Tennis-Ai-Vision-v2}"
FAILURES=0

report() {
  printf '%-24s %s\n' "$1" "$2"
}

require_file() {
  local label="$1"
  local path="$2"
  if [[ -f "$path" ]]; then
    report "$label" "FOUND ($path)"
  else
    report "$label" "MISSING ($path)"
    FAILURES=$((FAILURES + 1))
  fi
}

require_directory() {
  local label="$1"
  local path="$2"
  if [[ -d "$path" ]]; then
    report "$label" "FOUND ($path)"
  else
    report "$label" "MISSING ($path)"
    FAILURES=$((FAILURES + 1))
  fi
}

report "repository" "$REPO_DIR"
report "operating_system" "$(uname -srm)"

if command -v nvidia-smi >/dev/null 2>&1; then
  GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader | paste -sd ';' -)"
  GPU_VRAM="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | paste -sd ';' -) MiB"
  NVIDIA_DRIVER="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | paste -sd ';' -)"
  CUDA_DRIVER="$(nvidia-smi | sed -n 's/.*CUDA Version: \([0-9.]*\).*/\1/p' | sed -n '1p')"
  report "gpu" "$GPU_NAME"
  report "vram" "$GPU_VRAM"
  report "nvidia_driver" "$NVIDIA_DRIVER"
  report "cuda_driver_capability" "${CUDA_DRIVER:-UNKNOWN}"
else
  report "gpu" "MISSING (nvidia-smi unavailable)"
  report "vram" "UNKNOWN"
  report "nvidia_driver" "MISSING"
  report "cuda_driver_capability" "MISSING"
  FAILURES=$((FAILURES + 1))
fi

if command -v uv >/dev/null 2>&1; then
  report "uv" "$(uv --version)"
else
  report "uv" "MISSING"
  FAILURES=$((FAILURES + 1))
fi

if [[ -d "$REPO_DIR" ]]; then
  cd "$REPO_DIR"
else
  report "result" "FAIL ($FAILURES missing requirements)"
  exit 1
fi

if command -v uv >/dev/null 2>&1 && uv run --frozen python -c 'import sys; print(sys.version.split()[0])' >/dev/null 2>&1; then
  report "python" "$(uv run --frozen python -c 'import sys; print(sys.version.split()[0])')"
else
  report "python" "MISSING from locked project environment"
  FAILURES=$((FAILURES + 1))
fi

if command -v uv >/dev/null 2>&1 && uv run --frozen python -c 'import torch' >/dev/null 2>&1; then
  report "pytorch" "$(uv run --frozen python -c 'import torch; print(torch.__version__)')"
  report "pytorch_cuda" "$(uv run --frozen python -c 'import torch; print(torch.version.cuda)')"
  TORCH_CUDA_AVAILABLE="$(uv run --frozen python -c 'import torch; print(torch.cuda.is_available())')"
  report "torch.cuda.available" "$TORCH_CUDA_AVAILABLE"
  if [[ "$TORCH_CUDA_AVAILABLE" != "True" ]]; then
    FAILURES=$((FAILURES + 1))
  fi
else
  report "pytorch" "MISSING"
  report "pytorch_cuda" "UNKNOWN"
  report "torch.cuda.available" "False"
  FAILURES=$((FAILURES + 1))
fi

if command -v ffmpeg >/dev/null 2>&1; then
  report "ffmpeg" "$(ffmpeg -version | sed -n '1p')"
else
  report "ffmpeg" "MISSING"
  FAILURES=$((FAILURES + 1))
fi
if command -v ffprobe >/dev/null 2>&1; then
  report "ffprobe" "$(ffprobe -version | sed -n '1p')"
else
  report "ffprobe" "MISSING"
  FAILURES=$((FAILURES + 1))
fi

require_file "checkpoint" "$REPO_DIR/models/wasb/wasb_tennis_best.pth.tar"
require_directory "wasb_sbdt" "$REPO_DIR/third_party/WASB-SBDT/src"
require_file "video" "$REPO_DIR/data/clips/nivel_a2_01/source.mp4"
require_file "manifest" "$REPO_DIR/data/clips/nivel_a2_01/clip_manifest.json"
require_file "homography" "$REPO_DIR/data/clips/nivel_a2_01/homography.json"
require_file "court_corners" "$REPO_DIR/data/clips/nivel_a2_01/court_corners_pixel.json"

if [[ "$FAILURES" -ne 0 ]]; then
  report "result" "FAIL ($FAILURES missing or invalid requirements)"
  exit 1
fi
report "result" "PASS"
