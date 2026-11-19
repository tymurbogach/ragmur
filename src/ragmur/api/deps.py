"""Recursos compartidos del proceso y cómo llegan a cada endpoint."""

from dataclasses import dataclass
from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from ragmur.auth.service import authenticate
from ragmur.core.config import get_settings
from ragmur.ingestion.pipeline import IngestionCoordinator
from ragmur.retrieval.models import EmbeddingModels

# Importado de `store` y no de `qdrant_client`: la regla es que solo `store.py` toca
# la biblioteca de Qdrant, y una anotación de tipo no es motivo para romperla.
from ragmur.retrieval.store import AsyncQdrantClient
from ragmur.verification.nli import NliVerifier

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass(frozen=True, slots=True)
class Resources:
    """Lo que se crea una vez al arrancar y se reutiliza en todas las peticiones.

    El motor de base de datos y el cliente de Qdrant mantienen conexiones abiertas;
    crearlos por petición sería más caro que la propia consulta. En la fase 1 se suman
    aquí los modelos de ML, que tardan segundos en cargar y ocupan gigas.
    """

    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]
    qdrant: AsyncQdrantClient
    ingestion: IngestionCoordinator
    models: EmbeddingModels
    verifier: NliVerifier


def get_resources(request: Request) -> Resources:
    """Recupera los recursos que `lifespan` dejó en la aplicación.

    `lifespan` instala `Resources` al arrancar.
    El `cast` es necesario porque `app.state` es un contenedor de atributos libres y
    el revisor de tipos no puede saber qué hay dentro.
    """
    return cast(Resources, request.app.state.resources)


ResourcesDep = Annotated[Resources, Depends(get_resources)]


async def get_current_tenant(
    resources: ResourcesDep,
    request: Request,
    api_key: Annotated[str | None, Depends(api_key_header)],
) -> UUID:
    """Obtiene el tenant de la clave presentada con límite por clave."""
    from ragmur.api.rate_limit import auth_limiter, limiter

    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    settings = get_settings()
    retry_after = await auth_limiter.check(
        request.client.host if request.client else "unknown",
        settings.auth_rate_limit_requests,
        settings.auth_rate_limit_window_seconds,
        settings.rate_limit_max_keys,
    )
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(max(1, int(retry_after + 1)))},
        )
    async with resources.sessions() as session:
        tenant_id = await authenticate(
            session, api_key, settings.api_key_hmac_secret.get_secret_value()
        )
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    key_id = api_key.split("_", 2)[1]
    retry_after = await limiter.check(
        key_id,
        settings.rate_limit_requests,
        settings.rate_limit_window_seconds,
        settings.rate_limit_max_keys,
    )
    if retry_after is not None:
        raise HTTPException(
            429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(max(1, int(retry_after + 1)))},
        )
    return tenant_id


CurrentTenant = Annotated[UUID, Depends(get_current_tenant)]
