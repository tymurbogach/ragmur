"""Utilidades compartidas por todos los tests."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from ragmur.core.config import get_settings
from ragmur.main import create_app


@pytest.fixture(autouse=True)
def configuracion_limpia() -> AsyncIterator[None]:
    """Descarta la configuración cacheada antes y después de cada test.

    `get_settings` guarda el resultado de la primera llamada, así que sin esto un test
    que cambia una variable de entorno se la dejaría puesta al siguiente, y el orden
    de ejecución decidiría el resultado.
    """
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _cliente() -> AsyncIterator[AsyncClient]:
    """Levanta la aplicación en memoria, sin abrir ningún puerto.

    `lifespan_context` es lo que ejecuta el arranque y el apagado. El transporte de
    httpx no lo hace por su cuenta, y sin él `app.state.resources` no existiría: el
    endpoint fallaría por un motivo que no es el que se está probando.
    """
    app = create_app()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Cliente contra PostgreSQL y Qdrant reales, levantados con Docker."""
    async for c in _cliente():
        yield c


@pytest.fixture
async def client_sin_dependencias(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncClient]:
    """Cliente apuntando a puertos donde no escucha nadie.

    Se apunta a puertos altos sin asignar en vez de simular el fallo: así se recorre
    el camino de error de verdad, con la excepción real que lanza cada biblioteca
    cuando no encuentra servidor al otro lado.
    """
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://nadie:nadie@127.0.0.1:59999/nada")
    monkeypatch.setenv("QDRANT_URL", "http://127.0.0.1:59998")
    monkeypatch.setenv("HEALTH_TIMEOUT_SECONDS", "2")
    get_settings.cache_clear()

    async for c in _cliente():
        yield c
