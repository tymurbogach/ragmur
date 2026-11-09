from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from ragmur.core.config import Settings
from ragmur.main import lifespan
from ragmur.retrieval import store


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan")])
def test_invalid_timeout(value: float) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="postgresql+asyncpg://localhost/db", health_timeout_seconds=value)


def test_fractional_timeout_is_rounded_up(monkeypatch: pytest.MonkeyPatch) -> None:
    client = Mock()
    monkeypatch.setattr(store, "AsyncQdrantClient", client)
    store.create_client("http://localhost:6333", 0.5)
    client.assert_called_once_with(url="http://localhost:6333", timeout=1)


async def test_engine_disposed_when_client_creation_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = Mock()
    engine.dispose = AsyncMock()
    monkeypatch.setattr("ragmur.main.create_engine", lambda _: engine)
    monkeypatch.setattr("ragmur.main.create_client", Mock(side_effect=RuntimeError("failure")))
    with pytest.raises(RuntimeError, match="failure"):
        async with lifespan(FastAPI()):
            pass
    engine.dispose.assert_awaited_once()


async def test_engine_disposed_when_client_close_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = Mock()
    engine.dispose = AsyncMock()
    client = Mock()
    client.close = AsyncMock(side_effect=RuntimeError("failure"))
    monkeypatch.setattr("ragmur.main.create_engine", lambda _: engine)
    monkeypatch.setattr("ragmur.main.create_client", lambda *_: client)
    monkeypatch.setattr("ragmur.main.create_session_factory", lambda _: Mock())
    with pytest.raises(RuntimeError, match="failure"):
        async with lifespan(FastAPI()):
            pass
    engine.dispose.assert_awaited_once()
