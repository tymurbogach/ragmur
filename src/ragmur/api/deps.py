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

# Importado de `store` y no de `qdrant_client`: la regla es que solo `store.py` toca
# la biblioteca de Qdrant, y una anotación de tipo no es motivo para romperla.
from ragmur.retrieval.store import AsyncQdrantClient

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


def get_resources(request: Request) -> Resources:
    """Recupera los recursos que `lifespan` dejó en la aplicación.

    El `cast` es necesario porque `app.state` es un contenedor de atributos libres y
    el revisor de tipos no puede saber qué hay dentro.
    """
    return cast(Resources, request.app.state.resources)


ResourcesDep = Annotated[Resources, Depends(get_resources)]


async def get_current_tenant(
    resources: ResourcesDep,
    api_key: Annotated[str | None, Depends(api_key_header)],
) -> UUID:
    """Obtiene el tenant de la clave presentada."""
    if api_key:
        async with resources.sessions() as session:
            tenant_id = await authenticate(
                session, api_key, get_settings().api_key_hmac_secret.get_secret_value()
            )
            if tenant_id is not None:
                return tenant_id
    raise HTTPException(status_code=401, detail="Invalid API key")


CurrentTenant = Annotated[UUID, Depends(get_current_tenant)]
