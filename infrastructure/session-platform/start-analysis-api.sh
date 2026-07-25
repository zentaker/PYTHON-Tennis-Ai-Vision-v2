#!/usr/bin/env sh
set -eu

uv run --frozen --no-sync alembic upgrade head
current="$(uv run --frozen --no-sync alembic current 2>/dev/null || true)"
case "$current" in
  *"0002_analysis_job_orchestration"*"(head)"*) ;;
  *) echo "migration did not reach Alembic head" >&2; exit 1 ;;
esac

exec uv run --frozen --no-sync uvicorn src.platform.api.analysis_app:create_analysis_app \
  --factory --host "${TENNISAI_API_HOST:-0.0.0.0}" --port "${TENNISAI_ANALYSIS_API_PORT:-8001}"
