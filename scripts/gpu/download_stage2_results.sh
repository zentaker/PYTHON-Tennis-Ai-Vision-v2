#!/usr/bin/env bash
# Download Stage 2 results through runpodctl proxy mode or SCP exposed-TCP mode.

set -euo pipefail

CONFIG_FILE="${RUNPOD_ENV_FILE:-$HOME/.config/tennis-vision-ai/stage2_a2.env}"
if [[ -f "$CONFIG_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SSH_MODE="${RUNPOD_SSH_MODE:-exposed_tcp}"
TRANSFER_MODE="${RUNPOD_TRANSFER_MODE:-scp}"
REMOTE_REPO_DIR="${RUNPOD_REPO_DIR:-/workspace/PYTHON-Tennis-Ai-Vision-v2}"
[[ "$REMOTE_REPO_DIR" == "/workspace/PYTHON-Tennis-Ai-Vision-v2" ]] \
  || { echo "ERROR: unexpected RUNPOD_REPO_DIR." >&2; exit 2; }

backup_existing_results() {
  local local_repo_dir="$1"
  local backup_root="$2"
  local relative_path
  for relative_path in \
    data/clips/nivel_a2_01/wasb_detections.csv \
    outputs/nivel_a2_01/stage_2/wasb_detections_overlay.mp4 \
    outputs/nivel_a2_01/stage_2/inference_report.json \
    outputs/nivel_a2_01/stage_2/logs; do
    if [[ -e "$local_repo_dir/$relative_path" ]]; then
      mkdir -p "$(dirname "$backup_root/$relative_path")"
      mv "$local_repo_dir/$relative_path" "$backup_root/$relative_path"
      echo "backup=$backup_root/$relative_path"
    fi
  done
}

download_with_runpodctl() {
  [[ "$TRANSFER_MODE" == "runpodctl" ]] \
    || { echo "ERROR: proxy mode requires RUNPOD_TRANSFER_MODE=runpodctl." >&2; exit 2; }
  command -v runpodctl >/dev/null 2>&1 \
    || { echo "ERROR: runpodctl is required for proxy transfers." >&2; exit 1; }
  if [[ "$#" -gt 1 ]]; then
    echo "Usage in proxy mode: $0 [LOCAL_REPO_DIR]" >&2
    exit 2
  fi
  local local_repo_dir="${1:-$PROJECT_ROOT}"
  [[ -d "$local_repo_dir/.git" ]] || { echo "ERROR: local repository not found." >&2; exit 1; }

  local transfer_code="${RUNPOD_TRANSFER_CODE:-}"
  if [[ -z "$transfer_code" ]]; then
    read -r -s -p "RunPod temporary receive code: " transfer_code
    printf '\n'
  fi
  [[ -n "$transfer_code" && "$transfer_code" != *$'\n'* ]] \
    || { echo "ERROR: invalid runpodctl transfer code." >&2; exit 2; }
  local expected_sha="${RUNPOD_BUNDLE_SHA256:-}"
  [[ "$expected_sha" =~ ^[0-9a-f]{64}$ ]] \
    || { echo "ERROR: RUNPOD_BUNDLE_SHA256 must be the remote SHA-256." >&2; exit 2; }

  local temp_dir
  temp_dir="$(mktemp -d /tmp/tennis_stage2_a2_download.XXXXXX)"
  trap "rm -rf '$temp_dir'" EXIT
  (cd "$temp_dir" && runpodctl receive "$transfer_code")

  local bundles=("$temp_dir"/stage2_a2_results_*.tar.gz)
  [[ -f "${bundles[0]}" && "${#bundles[@]}" -eq 1 ]] \
    || { echo "ERROR: expected exactly one Stage 2 bundle." >&2; exit 1; }
  local bundle="${bundles[0]}"
  local local_sha
  local_sha="$(shasum -a 256 "$bundle" | awk '{print $1}')"
  [[ "$local_sha" == "$expected_sha" ]] \
    || { echo "ERROR: downloaded bundle checksum mismatch." >&2; exit 1; }

  local invalid_entry=0
  local entry
  while IFS= read -r entry; do
    case "$entry" in
      data/clips/nivel_a2_01/wasb_detections.csv|\
      outputs/nivel_a2_01/stage_2/wasb_detections_overlay.mp4|\
      outputs/nivel_a2_01/stage_2/inference_report.json|\
      outputs/nivel_a2_01/stage_2/logs/*) ;;
      *) invalid_entry=1 ;;
    esac
  done < <(tar -tzf "$bundle")
  [[ "$invalid_entry" -eq 0 ]] \
    || { echo "ERROR: bundle contains an unexpected path." >&2; exit 1; }

  local backup_root="$local_repo_dir/outputs/nivel_a2_01/stage_2/backups/$(date -u +%Y%m%dT%H%M%SZ)"
  backup_existing_results "$local_repo_dir" "$backup_root"
  tar -xzf "$bundle" -C "$local_repo_dir"
  echo "Download PASS: runpodctl bundle installed sha256=$local_sha"
}

download_with_scp() {
  [[ "$TRANSFER_MODE" == "scp" ]] \
    || { echo "ERROR: exposed_tcp mode requires RUNPOD_TRANSFER_MODE=scp." >&2; exit 2; }
  if [[ "$#" -lt 1 || "$#" -gt 2 ]]; then
    echo "Usage in exposed_tcp mode: $0 <RUNPOD_HOST> [LOCAL_REPO_DIR]" >&2
    exit 2
  fi
  local host="$1"
  local local_repo_dir="${2:-$PROJECT_ROOT}"
  local ssh_user="${RUNPOD_SSH_USER:-root}"
  local ssh_port="${RUNPOD_SSH_PORT:-}"
  local ssh_key="${RUNPOD_SSH_KEY:-}"
  [[ "$ssh_port" =~ ^[0-9]+$ ]] || { echo "ERROR: invalid RUNPOD_SSH_PORT." >&2; exit 2; }
  [[ "$host" =~ ^[A-Za-z0-9_.@:-]+$ && "$host" != -* ]] \
    || { echo "ERROR: invalid RUNPOD_HOST." >&2; exit 2; }
  [[ -f "$ssh_key" ]] || { echo "ERROR: configured SSH key does not exist." >&2; exit 1; }
  [[ -d "$local_repo_dir/.git" ]] || { echo "ERROR: local repository not found." >&2; exit 1; }
  [[ "$host" == *@* ]] || host="$ssh_user@$host"

  local ssh_args=(-p "$ssh_port" -i "$ssh_key" -o BatchMode=yes)
  local scp_args=(-P "$ssh_port" -i "$ssh_key" -o BatchMode=yes)
  local remote_files=(
    "$REMOTE_REPO_DIR/data/clips/nivel_a2_01/wasb_detections.csv"
    "$REMOTE_REPO_DIR/outputs/nivel_a2_01/stage_2/wasb_detections_overlay.mp4"
    "$REMOTE_REPO_DIR/outputs/nivel_a2_01/stage_2/inference_report.json"
  )
  local log_path
  while IFS= read -r log_path; do
    [[ -n "$log_path" ]] && remote_files+=("$log_path")
  done < <(ssh "${ssh_args[@]}" "$host" \
    "find '$REMOTE_REPO_DIR/outputs/nivel_a2_01/stage_2/logs' -maxdepth 1 -type f -name '*.log' -print | sort")
  [[ "${#remote_files[@]}" -gt 3 ]] || { echo "ERROR: no remote logs found." >&2; exit 1; }

  local backup_root="$local_repo_dir/outputs/nivel_a2_01/stage_2/backups/$(date -u +%Y%m%dT%H%M%SZ)"
  local remote_path relative_path local_path temp_path remote_sha local_sha backup_path
  for remote_path in "${remote_files[@]}"; do
    [[ "$remote_path" =~ ^[A-Za-z0-9_./-]+$ ]] \
      || { echo "ERROR: unsafe remote path." >&2; exit 1; }
    relative_path="${remote_path#"$REMOTE_REPO_DIR"/}"
    [[ "$relative_path" != "$remote_path" ]] \
      || { echo "ERROR: remote result outside repository." >&2; exit 1; }
    local_path="$local_repo_dir/$relative_path"
    mkdir -p "$(dirname "$local_path")"
    temp_path="${local_path}.download.$$"
    rm -f "$temp_path"
    remote_sha="$(ssh "${ssh_args[@]}" "$host" "sha256sum '$remote_path'" | awk '{print $1}')"
    [[ "$remote_sha" =~ ^[0-9a-f]{64}$ ]] || { echo "ERROR: invalid remote checksum." >&2; exit 1; }
    scp "${scp_args[@]}" "$host:$remote_path" "$temp_path"
    local_sha="$(shasum -a 256 "$temp_path" | awk '{print $1}')"
    [[ "$local_sha" == "$remote_sha" ]] \
      || { rm -f "$temp_path"; echo "ERROR: checksum mismatch." >&2; exit 1; }
    if [[ -e "$local_path" ]]; then
      backup_path="$backup_root/$relative_path"
      mkdir -p "$(dirname "$backup_path")"
      mv "$local_path" "$backup_path"
      echo "backup=$backup_path"
    fi
    mv "$temp_path" "$local_path"
    echo "downloaded=$local_path sha256=$local_sha"
  done
  echo "Download PASS: SCP files verified."
}

case "$SSH_MODE" in
  proxy) download_with_runpodctl "$@" ;;
  exposed_tcp) download_with_scp "$@" ;;
  *) echo "ERROR: RUNPOD_SSH_MODE must be proxy or exposed_tcp." >&2; exit 2 ;;
esac
