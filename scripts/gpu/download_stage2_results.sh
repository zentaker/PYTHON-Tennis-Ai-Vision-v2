#!/usr/bin/env bash
# Download only Stage 2 results/logs, backing up local files and verifying SHA-256.

set -euo pipefail

if [[ "$#" -lt 1 || "$#" -gt 2 ]]; then
  echo "Usage: $0 <RUNPOD_HOST> [LOCAL_REPO_DIR]" >&2
  exit 2
fi

HOST="$1"
LOCAL_REPO_DIR="${2:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
REMOTE_REPO_DIR="${RUNPOD_REPO_DIR:-/workspace/PYTHON-Tennis-Ai-Vision-v2}"
SSH_USER="${RUNPOD_SSH_USER:-root}"
SSH_PORT="${RUNPOD_SSH_PORT:-22}"
SSH_KEY="${RUNPOD_SSH_KEY:-$HOME/.ssh/id_ed25519}"
[[ "$SSH_PORT" =~ ^[0-9]+$ ]] || { echo "ERROR: invalid RUNPOD_SSH_PORT." >&2; exit 2; }
[[ "$HOST" =~ ^[A-Za-z0-9_.@:-]+$ && "$HOST" != -* ]] \
  || { echo "ERROR: invalid RUNPOD_HOST." >&2; exit 2; }
[[ "$REMOTE_REPO_DIR" == "/workspace/PYTHON-Tennis-Ai-Vision-v2" ]] \
  || { echo "ERROR: unexpected RUNPOD_REPO_DIR." >&2; exit 2; }
[[ -f "$SSH_KEY" ]] || { echo "ERROR: SSH key not found: $SSH_KEY" >&2; exit 1; }
[[ -d "$LOCAL_REPO_DIR/.git" ]] || { echo "ERROR: local repository not found." >&2; exit 1; }
if [[ "$HOST" != *@* ]]; then
  HOST="$SSH_USER@$HOST"
fi

SSH_ARGS=(-p "$SSH_PORT" -i "$SSH_KEY" -o BatchMode=yes)
SCP_ARGS=(-P "$SSH_PORT" -i "$SSH_KEY" -o BatchMode=yes)
REMOTE_FILES=(
  "$REMOTE_REPO_DIR/data/clips/nivel_a2_01/wasb_detections.csv"
  "$REMOTE_REPO_DIR/outputs/nivel_a2_01/stage_2/wasb_detections_overlay.mp4"
  "$REMOTE_REPO_DIR/outputs/nivel_a2_01/stage_2/inference_report.json"
)

while IFS= read -r log_path; do
  [[ -n "$log_path" ]] && REMOTE_FILES+=("$log_path")
done < <(ssh "${SSH_ARGS[@]}" "$HOST" \
  "find '$REMOTE_REPO_DIR/outputs/nivel_a2_01/stage_2/logs' -maxdepth 1 -type f -name '*.log' -print | sort")

if [[ "${#REMOTE_FILES[@]}" -eq 3 ]]; then
  echo "ERROR: no remote Stage 2 logs were found." >&2
  exit 1
fi

BACKUP_ROOT="$LOCAL_REPO_DIR/outputs/nivel_a2_01/stage_2/backups/$(date -u +%Y%m%dT%H%M%SZ)"
for remote_path in "${REMOTE_FILES[@]}"; do
  if [[ ! "$remote_path" =~ ^[A-Za-z0-9_./-]+$ ]]; then
    echo "ERROR: unsafe remote path: $remote_path" >&2
    exit 1
  fi
  relative_path="${remote_path#"$REMOTE_REPO_DIR"/}"
  if [[ "$relative_path" == "$remote_path" ]]; then
    echo "ERROR: remote result is outside repository: $remote_path" >&2
    exit 1
  fi
  local_path="$LOCAL_REPO_DIR/$relative_path"
  mkdir -p "$(dirname "$local_path")"
  temp_path="${local_path}.download.$$"
  rm -f "$temp_path"

  remote_sha="$(ssh "${SSH_ARGS[@]}" "$HOST" "sha256sum '$remote_path'" | awk '{print $1}')"
  [[ "$remote_sha" =~ ^[0-9a-f]{64}$ ]] || { echo "ERROR: invalid remote checksum." >&2; exit 1; }
  scp "${SCP_ARGS[@]}" "$HOST:$remote_path" "$temp_path"
  local_sha="$(shasum -a 256 "$temp_path" | awk '{print $1}')"
  if [[ "$local_sha" != "$remote_sha" ]]; then
    rm -f "$temp_path"
    echo "ERROR: checksum mismatch for $relative_path" >&2
    exit 1
  fi

  if [[ -e "$local_path" ]]; then
    backup_path="$BACKUP_ROOT/$relative_path"
    mkdir -p "$(dirname "$backup_path")"
    mv "$local_path" "$backup_path"
    echo "backup=$backup_path"
  fi
  mv "$temp_path" "$local_path"
  echo "downloaded=$local_path sha256=$local_sha"
done

echo "Download PASS: CSV, MP4, JSON and logs verified."
