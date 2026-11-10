"""Punto de entrada del servicio."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

import asyncpg  # type: ignore[import-untyped]
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from ragmur.api.deps import Resources
from ragmur.api.routes import documents, health, search
from ragmur.api.timing import RequestTimingMiddleware
from ragmur.api.upload_limit import UploadLimitMiddleware
from ragmur.core.config import get_settings
from ragmur.core.logging import configure_logging
from ragmur.db.session import (
    acquire_database_lock,
    create_engine,
    create_session_factory,
    first_tenant,
)
from ragmur.ingestion.indexer import Indexer
from ragmur.ingestion.pipeline import IngestionCoordinator
from ragmur.ingestion.storage import acquire_instance_lock
from ragmur.retrieval.models import load_models
from ragmur.retrieval.store import create_client, ensure_collection, ping

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Abre las conexiones al arrancar y las cierra al parar.

    Todo lo que sea caro de crear va aquí: el proceso vive entre peticiones, así que
    lo que se construya una vez se reutiliza en todas. Es también el único sitio
    correcto para cargar los modelos de ML de la fase 1.
    """
    settings = get_settings()
    async with AsyncExitStack() as stack:
        instance_lock = await asyncio.to_thread(acquire_instance_lock, settings.storage_dir)
        stack.callback(instance_lock.close)
        engine = create_engine(settings.database_url)
        stack.push_async_callback(engine.dispose)
        qdrant = create_client(settings.qdrant_url, settings.health_timeout_seconds)
        stack.push_async_callback(qdrant.close)
        database_lock = await acquire_database_lock(engine)
        stack.push_async_callback(database_lock.close)
        sessions = create_session_factory(engine)
        await ping(qdrant)
        models = await asyncio.to_thread(load_models, settings)
        indexer = Indexer(qdrant, models, settings)
        ingestion = IngestionCoordinator(sessions, settings, indexer)
        await ingestion.reconcile()
        tenant_id = await first_tenant(sessions)
        if tenant_id is not None:
            await ensure_collection(
                tenant_id,
                qdrant,
                settings.qdrant_collection,
                models.dense.dimension,
                indexer.metadata(),
            )
        app.state.resources = Resources(
            engine=engine,
            sessions=sessions,
            qdrant=qdrant,
            ingestion=ingestion,
            models=models,
        )
        logger.info("servicio arrancado", extra={"qdrant_url": settings.qdrant_url})
        yield
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

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Evita reflejar contenido privado en errores de validación."""
        return JSONResponse(
            status_code=422, content={"code": "invalid_request", "detail": "Invalid request"}
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Entrega un código de error estable sin reflejar datos de la petición."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": f"http_{exc.status_code}", "detail": exc.detail},
            headers=exc.headers,
        )

    @app.exception_handler(OSError)
    @app.exception_handler(asyncpg.PostgresError)
    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: Exception) -> JSONResponse:
        """Oculta parámetros y excepciones del controlador de base de datos."""
        logger.warning("dependencia inaccesible")
        return JSONResponse(
            status_code=503, content={"code": "http_503", "detail": "Service unavailable"}
        )

    settings = get_settings()
    app.add_middleware(
        UploadLimitMiddleware,
        max_bytes=settings.max_upload_bytes,
        overhead_bytes=settings.multipart_overhead_bytes,
    )
    app.add_middleware(RequestTimingMiddleware)
    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(search.router)
    return app


app = create_app()
