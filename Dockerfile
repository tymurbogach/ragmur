FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
COPY README.md ./
COPY alembic.ini ./
COPY src ./src

ARG INSTALL_CUDA=false

RUN if [ "$INSTALL_CUDA" = "true" ]; then \
      uv sync --locked --no-dev --no-group cpu --extra cuda; \
    else \
      uv sync --locked --no-dev; \
    fi

COPY eval ./eval

ENV MODEL_CACHE_DIR=/app/models/huggingface \
    STORAGE_DIR=/app/storage

VOLUME ["/app/models", "/app/storage"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["sh", "-c", "/app/.venv/bin/alembic upgrade head && /app/.venv/bin/uvicorn ragmur.main:app --host 0.0.0.0 --port 8000"]
