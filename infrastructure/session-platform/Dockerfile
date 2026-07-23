FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN pip install --no-cache-dir uv
COPY . .
RUN uv sync --frozen --extra platform

CMD ["/app/infrastructure/session-platform/start-api.sh"]
