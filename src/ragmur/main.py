"""Punto de entrada del servicio."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from ragmur.api.deps import Resources
from ragmur.api.routes import documents, health
from ragmur.api.upload_limit import UploadLimitMiddleware
from ragmur.core.config import get_settings
from ragmur.core.logging import configure_logging
from ragmur.db.session import acquire_database_lock, create_engine, create_session_factory
from ragmur.ingestion.pipeline import IngestionCoordinator
from ragmur.ingestion.storage import acquire_instance_lock
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
        ingestion = IngestionCoordinator(sessions, settings)
        await ingestion.reconcile()
        app.state.resources = Resources(
            engine=engine,
            sessions=sessions,
            qdrant=qdrant,
            ingestion=ingestion,
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

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        """Oculta parámetros y excepciones del controlador de base de datos."""
        logger.warning("base de datos inaccesible")
        return JSONResponse(
            status_code=503, content={"code": "http_503", "detail": "Database unavailable"}
        )

    settings = get_settings()
    app.add_middleware(
        UploadLimitMiddleware,
        max_bytes=settings.max_upload_bytes,
        overhead_bytes=settings.multipart_overhead_bytes,
    )
    app.include_router(health.router)
    app.include_router(documents.router)
    return app


app = create_app()
