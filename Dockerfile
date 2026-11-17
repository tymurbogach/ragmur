FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Versión fijada: `latest` cambia el resolvedor sin avisar y rompe builds
# reproducibles. Digest de ghcr.io/astral-sh/uv:0.13.8 verificado en F05b.
COPY --from=ghcr.io/astral-sh/uv:0.13.8@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85 /uv /usr/local/bin/uv

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

# Usuario no root con UID fijo: el proceso nunca escribe como root y los
# permisos son predecibles entre reconstrucciones. Los directorios se crean
# antes de VOLUME para que los volúmenes nuevos hereden esta propiedad;
# los volúmenes existentes de Skynet (propiedad de root) los migra F05d
# con `chown` antes del primer arranque con esta imagen.
ARG APP_UID=10000
RUN useradd --uid "$APP_UID" --create-home --shell /usr/sbin/nologin ragmur \
    && mkdir -p /app/models /app/storage \
    && chown -R ragmur:ragmur /app /home/ragmur

VOLUME ["/app/models", "/app/storage"]

EXPOSE 8000

# Sin cambios: el chequeo sigue apuntando al loopback del propio contenedor
# y funciona con el usuario no root (puerto alto, sin capacidades extra).
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://127.0.0.1:8000/health || exit 1

USER ragmur

# `--host 0.0.0.0` escucha en la interfaz del contenedor para que nginx
# (otro contenedor de la red interna) alcance a la API. Hacia el anfitrión
# no se publica nada en la demo: el compose de despliegue publica
# `127.0.0.1:8000` y el overlay de demo retira ese mapeo (plan B del
# hallazgo 8 de F05a). Sin `--forwarded-allow-ips`: uvicorn solo confía en
# el loopback y el límite por IP real vive en nginx (hallazgo 9 de F05a).
CMD ["sh", "-c", "/app/.venv/bin/alembic upgrade head && /app/.venv/bin/uvicorn ragmur.main:app --host 0.0.0.0 --port 8000"]
