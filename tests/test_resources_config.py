from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from ragmur.core.config import Settings
from ragmur.main import lifespan
from ragmur.retrieval import store


def _base_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "database_url": "postgresql+asyncpg://localhost/db",
        "api_key_hmac_secret": "test-secret",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_env_example_loads() -> None:
    """`.env.example` debe arrancar `Settings` sin error de JSON (B1)."""
    env_example = Path(__file__).resolve().parents[1] / ".env.example"
    settings = Settings(
        _env_file=env_example,
        database_url="postgresql+asyncpg://localhost/db",
        api_key_hmac_secret="test-only-hmac-secret",
    )
    assert settings.llm_model is None
    assert settings.llm_extra_headers == {}


def test_extra_headers_hidden_from_repr_and_str() -> None:
    session_secret = "session-secret-that-must-not-leak"
    settings = _base_settings(llm_extra_headers={"x-opencode-session": session_secret})
    assert session_secret not in repr(settings)
    assert session_secret not in str(settings)


def test_empty_llm_strings_become_none() -> None:
    settings = _base_settings(llm_model="", llm_api_key="", llm_api_base="")
    assert settings.llm_model is None
    assert settings.llm_api_key is None
    assert settings.llm_api_base is None


def test_llm_max_retries_capped_at_five() -> None:
    with pytest.raises(ValidationError):
        _base_settings(llm_max_retries=6)
    assert _base_settings(llm_max_retries=5).llm_max_retries == 5


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
    lock = Mock()
    lock.close = AsyncMock()
    monkeypatch.setattr("ragmur.main.acquire_database_lock", AsyncMock(return_value=lock))
    monkeypatch.setattr("ragmur.main.ping", AsyncMock(return_value="1.19.0"))
    monkeypatch.setattr("ragmur.main.IngestionCoordinator.reconcile", AsyncMock())
    with pytest.raises(RuntimeError, match="failure"):
        async with lifespan(FastAPI()):
            pass
    engine.dispose.assert_awaited_once()
