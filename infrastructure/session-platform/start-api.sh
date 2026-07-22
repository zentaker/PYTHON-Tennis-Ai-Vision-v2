#!/usr/bin/env sh
set -eu

alembic upgrade head
current="$(alembic current 2>/dev/null || true)"
case "$current" in
  *"0001_session_platform"*"(head)"*) ;;
  *) echo "migration did not reach Alembic head" >&2; exit 1 ;;
esac

exec uv run --frozen --no-sync uvicorn src.platform.api.app:create_app \
  --factory --host "${TENNISAI_API_HOST:-0.0.0.0}" --port "${TENNISAI_API_PORT:-8000}"
