FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY alembic.ini ./alembic.ini
COPY infrastructure/session-platform/alembic ./infrastructure/session-platform/alembic
RUN pip install uv
COPY . .
