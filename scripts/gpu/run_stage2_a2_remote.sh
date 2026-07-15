#!/usr/bin/env bash
# From macOS, execute Stage 2 on RunPod; in remote mode, pin Git and run WASB once.

set -euo pipefail

REPO_DIR="${RUNPOD_REPO_DIR:-/workspace/PYTHON-Tennis-Ai-Vision-v2}"
THRESHOLD="${RUNPOD_CONFIDENCE_THRESHOLD:-0.5}"
EXPECTED_REPO_DIR="/workspace/PYTHON-Tennis-Ai-Vision-v2"

validate_sha() {
  [[ "$1" =~ ^[0-9a-f]{40}$ ]] || {
    echo "ERROR: COMMIT_SHA must contain exactly 40 lowercase hexadecimal characters." >&2
    exit 2
  }
}

if [[ "${RUNPOD_REMOTE_EXECUTION:-0}" != "1" ]]; then
  if [[ "$#" -ne 2 ]]; then
    echo "Usage: $0 <RUNPOD_HOST> <COMMIT_SHA>" >&2
    exit 2
  fi
  HOST="$1"
  COMMIT_SHA="$2"
  validate_sha "$COMMIT_SHA"
  SSH_USER="${RUNPOD_SSH_USER:-root}"
  SSH_PORT="${RUNPOD_SSH_PORT:-22}"
  SSH_KEY="${RUNPOD_SSH_KEY:-$HOME/.ssh/id_ed25519}"
  [[ "$SSH_PORT" =~ ^[0-9]+$ ]] || { echo "ERROR: invalid RUNPOD_SSH_PORT." >&2; exit 2; }
  [[ "$HOST" =~ ^[A-Za-z0-9_.@:-]+$ && "$HOST" != -* ]] \
    || { echo "ERROR: invalid RUNPOD_HOST." >&2; exit 2; }
  [[ "$THRESHOLD" =~ ^(0(\.[0-9]+)?|1(\.0+)?)$ ]] \
    || { echo "ERROR: confidence threshold must be between 0 and 1." >&2; exit 2; }
  [[ "$REPO_DIR" == "$EXPECTED_REPO_DIR" ]] \
    || { echo "ERROR: remote repository must be $EXPECTED_REPO_DIR." >&2; exit 2; }
  [[ -f "$SSH_KEY" ]] || { echo "ERROR: SSH key not found: $SSH_KEY" >&2; exit 1; }
  if [[ "$HOST" != *@* ]]; then
    HOST="$SSH_USER@$HOST"
  fi
  echo "Remote host: $HOST"
  echo "Exact commit: $COMMIT_SHA"
  echo "No ignored assets will be deleted by this workflow."
  LOCAL_REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  git -C "$LOCAL_REPO_DIR" cat-file -e "${COMMIT_SHA}^{commit}"
  git -C "$LOCAL_REPO_DIR" cat-file -e \
    "${COMMIT_SHA}:scripts/gpu/run_stage2_a2_remote.sh"
  git -C "$LOCAL_REPO_DIR" show \
    "${COMMIT_SHA}:scripts/gpu/run_stage2_a2_remote.sh" | \
    ssh -p "$SSH_PORT" -i "$SSH_KEY" -o BatchMode=yes "$HOST" \
    "RUNPOD_REMOTE_EXECUTION=1 RUNPOD_REPO_DIR='$REPO_DIR' RUNPOD_CONFIDENCE_THRESHOLD='$THRESHOLD' bash -s -- '$COMMIT_SHA'"
  exit 0
fi

if [[ "$#" -ne 1 ]]; then
  echo "ERROR: remote mode expects one COMMIT_SHA." >&2
  exit 2
fi
COMMIT_SHA="$1"
validate_sha "$COMMIT_SHA"
[[ "$(uname -s)" == "Linux" ]] || { echo "ERROR: remote mode requires Linux." >&2; exit 1; }
[[ "$REPO_DIR" == "$EXPECTED_REPO_DIR" ]] \
  || { echo "ERROR: remote repository must be $EXPECTED_REPO_DIR." >&2; exit 2; }
[[ -d "$REPO_DIR/.git" ]] || { echo "ERROR: repository missing at $REPO_DIR." >&2; exit 1; }
cd "$REPO_DIR"

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "ERROR: tracked remote changes exist; refusing checkout to avoid data loss." >&2
  exit 1
fi
git fetch origin --prune
git cat-file -e "${COMMIT_SHA}^{commit}"
RESOLVED_SHA="$(git rev-parse "${COMMIT_SHA}^{commit}")"
[[ "$RESOLVED_SHA" == "$COMMIT_SHA" ]] || { echo "ERROR: commit resolution mismatch." >&2; exit 1; }
git checkout --detach "$RESOLVED_SHA"
[[ "$(git rev-parse HEAD)" == "$COMMIT_SHA" ]] || { echo "ERROR: checkout did not pin commit." >&2; exit 1; }

for required in \
  data/clips/nivel_a2_01/source.mp4 \
  data/clips/nivel_a2_01/clip_manifest.json \
  data/clips/nivel_a2_01/homography.json \
  data/clips/nivel_a2_01/court_corners_pixel.json \
  models/wasb/wasb_tennis_best.pth.tar; do
  [[ -f "$required" ]] || { echo "ERROR: missing ignored input $required" >&2; exit 1; }
done
[[ -d third_party/WASB-SBDT/src ]] || { echo "ERROR: missing third_party/WASB-SBDT/src" >&2; exit 1; }

OUTPUT_DIR="outputs/nivel_a2_01/stage_2"
LOG_DIR="$OUTPUT_DIR/logs"
mkdir -p "$LOG_DIR"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)_${COMMIT_SHA:0:12}"
LOG_PATH="$LOG_DIR/stage2_${RUN_ID}.log"
exec > >(tee -a "$LOG_PATH") 2>&1

echo "stage=2"
echo "git_commit=$COMMIT_SHA"
echo "started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "repository=$REPO_DIR"

bash scripts/gpu/verify_runpod_environment.sh

uv run --frozen python scripts/stage2_a2_preflight.py \
  --video data/clips/nivel_a2_01/source.mp4 \
  --manifest data/clips/nivel_a2_01/clip_manifest.json \
  --homography data/clips/nivel_a2_01/homography.json \
  --checkpoint models/wasb/wasb_tennis_best.pth.tar \
  --wasb-root third_party/WASB-SBDT \
  --output-csv data/clips/nivel_a2_01/wasb_detections.csv \
  --output-overlay "$OUTPUT_DIR/wasb_detections_overlay.mp4" \
  --require-runtime

uv run --frozen python -m src.tracker.wasb_runner \
  --video data/clips/nivel_a2_01/source.mp4 \
  --manifest data/clips/nivel_a2_01/clip_manifest.json \
  --checkpoint models/wasb/wasb_tennis_best.pth.tar \
  --wasb-root third_party/WASB-SBDT \
  --output-csv data/clips/nivel_a2_01/wasb_detections.csv \
  --output-overlay "$OUTPUT_DIR/wasb_detections_overlay.mp4" \
  --output-report "$OUTPUT_DIR/inference_report.json" \
  --confidence-threshold "$THRESHOLD" \
  --device cuda

uv run --frozen python - "$OUTPUT_DIR/inference_report.json" "$COMMIT_SHA" "$LOG_PATH" <<'PY'
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

report_path = Path(sys.argv[1])
report = json.loads(report_path.read_text(encoding="utf-8"))
report["execution"] = {
    "git_commit": sys.argv[2],
    "completed_at_utc": datetime.now(timezone.utc).isoformat(),
    "hostname": platform.node(),
    "gpu": subprocess.run(
        ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip(),
    "log": sys.argv[3],
    "stage_3_executed": False,
}
report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY

uv run --frozen python - \
  data/clips/nivel_a2_01/wasb_detections.csv \
  "$OUTPUT_DIR/inference_report.json" <<'PY'
import csv
import json
import sys
from pathlib import Path

with Path(sys.argv[1]).open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
if len(rows) != 527:
    raise SystemExit(f"CSV row count mismatch: {len(rows)}")
if [int(row["frame_id"]) for row in rows] != list(range(527)):
    raise SystemExit("CSV frame IDs are not exactly 0..526")
report = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
if report.get("frames_expected") != 527 or report.get("frames_processed") != 527:
    raise SystemExit("inference_report does not confirm 527 processed frames")
print("csv_frames_verified=527")
print("report_frames_verified=527")
PY

OVERLAY_FRAMES="$(ffprobe -v error -count_frames -select_streams v:0 \
  -show_entries stream=nb_read_frames -of default=nokey=1:noprint_wrappers=1 \
  "$OUTPUT_DIR/wasb_detections_overlay.mp4")"
[[ "$OVERLAY_FRAMES" == "527" ]] || { echo "ERROR: overlay has $OVERLAY_FRAMES frames." >&2; exit 1; }
echo "overlay_frames_verified=527"

sha256sum \
  data/clips/nivel_a2_01/wasb_detections.csv \
  "$OUTPUT_DIR/wasb_detections_overlay.mp4" \
  "$OUTPUT_DIR/inference_report.json" \
  "$LOG_PATH"
echo "completed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Stage 2 complete. Stage 3 was NOT executed."
