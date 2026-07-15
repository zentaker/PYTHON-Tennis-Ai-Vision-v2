#!/usr/bin/env bash
# Execute one remote command through either RunPod SSH connection mode.

set -euo pipefail

CONFIG_FILE="${RUNPOD_ENV_FILE:-$HOME/.config/tennis-vision-ai/stage2_a2.env}"
if [[ -f "$CONFIG_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
fi

if [[ "$#" -ne 1 || -z "$1" ]]; then
  echo "Usage: $0 <REMOTE_COMMAND>" >&2
  exit 2
fi
REMOTE_COMMAND="$1"
SSH_MODE="${RUNPOD_SSH_MODE:-exposed_tcp}"
SSH_KEY="${RUNPOD_SSH_KEY:-}"

[[ -n "$SSH_KEY" ]] || { echo "ERROR: RUNPOD_SSH_KEY is required." >&2; exit 2; }
[[ -f "$SSH_KEY" ]] || { echo "ERROR: configured SSH key does not exist." >&2; exit 1; }

SSH_ARGS=(-o BatchMode=yes -o StrictHostKeyChecking=accept-new -i "$SSH_KEY")
case "$SSH_MODE" in
  proxy)
    SSH_TARGET="${RUNPOD_SSH_TARGET:-}"
    [[ "$SSH_TARGET" =~ ^[A-Za-z0-9_.-]+@ssh\.runpod\.io$ ]] \
      || { echo "ERROR: invalid or missing proxy RUNPOD_SSH_TARGET." >&2; exit 2; }
    ;;
  exposed_tcp)
    SSH_TARGET="${RUNPOD_SSH_TARGET:-}"
    if [[ -z "$SSH_TARGET" ]]; then
      RUNPOD_HOST="${RUNPOD_HOST:-}"
      RUNPOD_SSH_USER="${RUNPOD_SSH_USER:-root}"
      [[ "$RUNPOD_HOST" =~ ^[A-Za-z0-9_.:-]+$ && "$RUNPOD_HOST" != -* ]] \
        || { echo "ERROR: invalid or missing RUNPOD_HOST." >&2; exit 2; }
      SSH_TARGET="$RUNPOD_SSH_USER@$RUNPOD_HOST"
    fi
    RUNPOD_SSH_PORT="${RUNPOD_SSH_PORT:-}"
    [[ "$RUNPOD_SSH_PORT" =~ ^[0-9]+$ ]] \
      || { echo "ERROR: RUNPOD_SSH_PORT is required for exposed_tcp." >&2; exit 2; }
    SSH_ARGS+=(-p "$RUNPOD_SSH_PORT")
    ;;
  *)
    echo "ERROR: RUNPOD_SSH_MODE must be proxy or exposed_tcp." >&2
    exit 2
    ;;
esac

exec ssh "${SSH_ARGS[@]}" "$SSH_TARGET" "$REMOTE_COMMAND"
