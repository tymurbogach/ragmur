"""Recursos compartidos del proceso y cómo llegan a cada endpoint."""

from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

# Importado de `store` y no de `qdrant_client`: la regla es que solo `store.py` toca
# la biblioteca de Qdrant, y una anotación de tipo no es motivo para romperla.
from ragmur.retrieval.store import AsyncQdrantClient


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


def get_resources(request: Request) -> Resources:
    """Recupera los recursos que `lifespan` dejó en la aplicación.

    El `cast` es necesario porque `app.state` es un contenedor de atributos libres y
    el revisor de tipos no puede saber qué hay dentro.
    """
    return cast(Resources, request.app.state.resources)


ResourcesDep = Annotated[Resources, Depends(get_resources)]
