"""Estado del proceso y preparación de recursos."""

import asyncio
import logging
from collections.abc import Awaitable

from fastapi import APIRouter, Response, status

from ragmur.api.deps import ResourcesDep
from ragmur.api.schemas import DependencyHealth, HealthResponse
from ragmur.core.config import get_settings
from ragmur.db import health as db_health
from ragmur.retrieval import store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


async def _comprobar(
    nombre: str, comprobacion: Awaitable[str], limite_segundos: float
) -> DependencyHealth:
    """Ejecuta una comprobación con límite de tiempo y traduce el fallo a un estado.

    Un chequeo de salud nunca debe propagar la excepción: su trabajo es informar de
    que algo está caído, no caerse también.
    """
    try:
        async with asyncio.timeout(limite_segundos):
            version = await comprobacion
    except TimeoutError:
        logger.warning("dependencia sin responder", extra={"dependencia": nombre})
        return DependencyHealth(status="error", detail=f"sin respuesta en {limite_segundos}s")
    except Exception as exc:
        logger.warning(
            "dependencia inaccesible",
            extra={"dependencia": nombre, "error": type(exc).__name__},
        )
        return DependencyHealth(status="error", detail=f"{type(exc).__name__}: {exc}")
    return DependencyHealth(status="ok", detail=str(version))


@router.get("/health", summary="Proceso vivo")
async def health() -> dict[str, str]:
    """Indica que el proceso responde, sin comprobar dependencias.

    El orquestador usa `/ready` para decidir si envía tráfico; `/health` solo
    dice que el proceso sigue vivo.
    """
    return {"status": "ok"}


@router.get(
    "/ready",
    response_model=HealthResponse,
    summary="Recursos preparados para tráfico",
    responses={503: {"description": "Alguna dependencia no responde"}},
)
async def ready(response: Response, resources: ResourcesDep) -> HealthResponse:
    """Comprueba PostgreSQL, Qdrant y modelos cargados.

    Los modelos tardan decenas de segundos en cargar; si el chequeo respondiera
    200 antes de tenerlos, el orquestador mandaría tráfico y las primeras
    peticiones expirarían. Van en paralelo para no sumar esperas.
    """
    timeout = get_settings().health_timeout_seconds

    async def _modelos() -> str:
        dimension = resources.models.dense.dimension
        if dimension != 1024 or resources.verifier is None:
            raise RuntimeError("Models not loaded")
        return f"dense-{dimension}+nli"

    postgres, qdrant, modelos = await asyncio.gather(
        _comprobar("postgres", db_health.ping(resources.engine), timeout),
        _comprobar("qdrant", store.ping(resources.qdrant), timeout),
        _comprobar("models", _modelos(), timeout),
    )

    dependencies = {"postgres": postgres, "qdrant": qdrant, "models": modelos}
    todo_ok = all(d.status == "ok" for d in dependencies.values())

    if not todo_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(status="ok" if todo_ok else "degraded", dependencies=dependencies)
