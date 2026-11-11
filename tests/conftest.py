"""Utilidades compartidas por todos los tests."""

import os
from collections.abc import AsyncIterator, Iterator
from unittest.mock import AsyncMock, Mock

import pytest
from httpx import ASGITransport, AsyncClient

from ragmur.core.config import get_settings


def pytest_configure() -> None:
    os.environ.setdefault("API_KEY_HMAC_SECRET", "test-only-hmac-secret")


@pytest.fixture(autouse=True)
def configuracion_limpia() -> Iterator[None]:
    """Descarta la configuración cacheada antes y después de cada test.

    `get_settings` guarda el resultado de la primera llamada, así que sin esto un test
    que cambia una variable de entorno se la dejaría puesta al siguiente, y el orden
    de ejecución decidiría el resultado.
    """
    from ragmur.api.rate_limit import auth_limiter, limiter

    get_settings.cache_clear()
    limiter.clear()
    auth_limiter.clear()
    yield
    get_settings.cache_clear()
    limiter.clear()
    auth_limiter.clear()


@pytest.fixture(autouse=True)
def modelos_simulados(monkeypatch: pytest.MonkeyPatch) -> None:
    """Evita descargar modelos en la suite; la inferencia real se verifica aparte."""
    model = Mock()
    model.dense.dimension = 1024
    model.sparse.metadata = {"model": "test"}
    verifier = Mock()
    verifier.check_hypothesis.return_value = None
    verifier.score_pairs.return_value = []
    monkeypatch.setattr("ragmur.main.load_models", Mock(return_value=model))
    monkeypatch.setattr("ragmur.main.load_verifier", Mock(return_value=verifier))
    monkeypatch.setattr("ragmur.main.first_tenant", AsyncMock(return_value=None))


async def _cliente() -> AsyncIterator[AsyncClient]:
    """Levanta la aplicación en memoria, sin abrir ningún puerto.

    `lifespan_context` es lo que ejecuta el arranque y el apagado. El transporte de
    httpx no lo hace por su cuenta, y sin él `app.state.resources` no existiría: el
    endpoint fallaría por un motivo que no es el que se está probando.
    """
    from ragmur.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    """Cliente contra PostgreSQL y Qdrant reales, levantados con Docker."""
    monkeypatch.setattr("ragmur.ingestion.pipeline.IngestionCoordinator.reconcile", AsyncMock())
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
    lock = AsyncMock()
    monkeypatch.setattr("ragmur.main.acquire_database_lock", AsyncMock(return_value=lock))
    monkeypatch.setattr("ragmur.main.ping", AsyncMock(return_value="1.19.0"))
    monkeypatch.setattr("ragmur.ingestion.pipeline.IngestionCoordinator.reconcile", AsyncMock())
    get_settings.cache_clear()

    async for c in _cliente():
        yield c
