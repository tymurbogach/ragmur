"""Punto de entrada del servicio."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ragmur.api.deps import Resources
from ragmur.api.routes import health
from ragmur.core.config import get_settings
from ragmur.core.logging import configure_logging
from ragmur.db.session import create_engine, create_session_factory
from ragmur.retrieval.store import create_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Abre las conexiones al arrancar y las cierra al parar.

    Todo lo que sea caro de crear va aquí: el proceso vive entre peticiones, así que
    lo que se construya una vez se reutiliza en todas. Es también el único sitio
    correcto para cargar los modelos de ML de la fase 1.
    """
    settings = get_settings()
    engine = create_engine(settings.database_url)
    qdrant = create_client(settings.qdrant_url, settings.health_timeout_seconds)
    app.state.resources = Resources(
        engine=engine,
        sessions=create_session_factory(engine),
        qdrant=qdrant,
    )
    logger.info("servicio arrancado", extra={"qdrant_url": settings.qdrant_url})

    try:
        yield
    finally:
        # En un `finally` para que las conexiones se cierren también si el arranque
        # falla a mitad; si no, quedan sockets abiertos hasta que el proceso muere.
        await qdrant.close()
        await engine.dispose()
        logger.info("servicio detenido")


def create_app() -> FastAPI:
    """Construye la aplicación.

    Es una función y no un objeto suelto para que los tests puedan levantar una
    instancia limpia por cada caso, sin estado heredado del anterior.

    El logging se configura aquí y no en `lifespan` porque uvicorn importa la
    aplicación antes de arrancarla: haciéndolo en `lifespan`, sus primeras líneas
    («Started server process») saldrían en texto plano y romperían el formato.
    """
    configure_logging(get_settings().log_level)

    app = FastAPI(
        title="Ragmur",
        description="Servicio RAG multi-tenant: ingiere documentos y responde citando la fuente.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    return app


app = create_app()
