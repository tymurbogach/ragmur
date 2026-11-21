"""Unitarios del proveedor LLM con LiteLLM simulado (sin red)."""

import asyncio
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from ragmur.core.config import Settings
from ragmur.llm.provider import (
    ChatMessage,
    LLMAuthError,
    LLMConfigError,
    LLMError,
    LLMQuotaExceeded,
    LLMRateLimited,
    LLMTimeout,
    complete,
)

# Acceso al módulo LiteLLM sin importarlo aquí: `import litellm` en un test
# rompería el test de confinamiento (regla 7). Importar `provider` ya lo
# carga en `sys.modules`.
_litellm: Any = sys.modules["litellm"]


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "database_url": "postgresql+asyncpg://localhost/db",
        "api_key_hmac_secret": "test-secret",
        "llm_model": "test-provider/test-model",
        "llm_timeout_seconds": 5,
        "llm_max_tokens": 16,
        "llm_max_retries": 2,
    }
    values.update(overrides)
    return Settings(**values)


def _response(
    text: str = "hola",
    model: str = "test-provider/test-model",
    prompt_tokens: int = 3,
    completion_tokens: int = 2,
) -> SimpleNamespace:
    return SimpleNamespace(
        model=model,
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


def _fake_success(calls: dict[str, Any], **kwargs: Any) -> Any:
    async def _call(**call_kwargs: Any) -> SimpleNamespace:
        calls["count"] += 1
        calls["kwargs"] = call_kwargs
        return _response(**kwargs)

    return _call


def _messages() -> list[ChatMessage]:
    return [ChatMessage(role="user", content="di hola")]


async def test_success_returns_completion_with_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {"count": 0, "kwargs": {}}
    monkeypatch.setattr(
        "ragmur.llm.provider.litellm.acompletion", _fake_success(calls, text="hola")
    )
    settings = _settings(llm_api_key="live-key", llm_api_base="http://localhost:11434")

    result = await complete(_messages(), settings=settings, temperature=0.0, seed=7)

    assert result.text == "hola"
    assert result.model == "test-provider/test-model"
    assert result.prompt_tokens == 3
    assert result.completion_tokens == 2
    assert result.latency_ms >= 0
    assert calls["count"] == 1
    assert calls["kwargs"]["model"] == "test-provider/test-model"
    assert calls["kwargs"]["temperature"] == 0.0
    assert calls["kwargs"]["seed"] == 7
    assert calls["kwargs"]["max_tokens"] == 16
    assert calls["kwargs"]["timeout"] == 5
    assert calls["kwargs"]["num_retries"] == 0
    assert calls["kwargs"]["api_key"] == "live-key"
    assert calls["kwargs"]["api_base"] == "http://localhost:11434"


async def test_timeout_retries_then_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}
    slept: list[float] = []

    async def _sleep(delay: float) -> None:
        slept.append(delay)

    async def _call(**kwargs: Any) -> Any:
        calls["count"] += 1
        raise _litellm.Timeout("timed out", "test-model", "test-provider")

    monkeypatch.setattr(asyncio, "sleep", _sleep)
    monkeypatch.setattr("ragmur.llm.provider.litellm.acompletion", _call)

    with pytest.raises(LLMTimeout):
        await complete(_messages(), settings=_settings())
    assert calls["count"] == 3
    assert slept == [1.0, 2.0]


async def test_rate_limited_retry_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    async def _call(**kwargs: Any) -> Any:
        calls["count"] += 1
        if calls["count"] == 1:
            raise _litellm.RateLimitError(
                "limited", "test-provider", "test-model", headers={"retry-after": "0"}
            )
        return _response(text="al segundo intento")

    monkeypatch.setattr("ragmur.llm.provider.litellm.acompletion", _call)

    result = await complete(_messages(), settings=_settings())
    assert result.text == "al segundo intento"
    assert calls["count"] == 2


async def test_rate_limited_exhausted_carries_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slept: list[float] = []
    calls = {"count": 0}

    async def _sleep(delay: float) -> None:
        slept.append(delay)

    async def _call(**kwargs: Any) -> Any:
        calls["count"] += 1
        raise _litellm.RateLimitError(
            "limited", "test-provider", "test-model", headers={"retry-after": "2"}
        )

    monkeypatch.setattr(asyncio, "sleep", _sleep)
    monkeypatch.setattr("ragmur.llm.provider.litellm.acompletion", _call)

    with pytest.raises(LLMRateLimited) as excinfo:
        await complete(_messages(), settings=_settings())
    assert excinfo.value.retry_after == 2.0
    assert calls["count"] == 3
    assert slept == [2.0, 2.0]


async def test_auth_error_does_not_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    async def _call(**kwargs: Any) -> Any:
        calls["count"] += 1
        raise _litellm.AuthenticationError("denied", "test-provider", "test-model")

    monkeypatch.setattr("ragmur.llm.provider.litellm.acompletion", _call)

    with pytest.raises(LLMAuthError):
        await complete(_messages(), settings=_settings())
    assert calls["count"] == 1


async def test_quota_error_does_not_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    async def _call(**kwargs: Any) -> Any:
        calls["count"] += 1
        raise _litellm.PaymentRequiredError("quota", "test-model", "test-provider")

    monkeypatch.setattr("ragmur.llm.provider.litellm.acompletion", _call)

    with pytest.raises(LLMQuotaExceeded):
        await complete(_messages(), settings=_settings())
    assert calls["count"] == 1


async def test_missing_model_raises_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    called = AsyncMock(side_effect=AssertionError("no debe llamar a la red"))
    monkeypatch.setattr("ragmur.llm.provider.litellm.acompletion", called)

    with pytest.raises(LLMConfigError):
        await complete(_messages(), settings=_settings(llm_model=None))
    called.assert_not_awaited()


async def test_secret_never_leaks(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "super-secret-key-that-must-not-leak"

    async def _call(**kwargs: Any) -> Any:
        raise _litellm.Timeout("timed out", "test-model", "test-provider")

    monkeypatch.setattr("ragmur.llm.provider.litellm.acompletion", _call)
    settings = _settings(llm_api_key=secret, llm_max_retries=0)

    with caplog.at_level("INFO"), pytest.raises(LLMTimeout) as excinfo:
        await complete(_messages(), settings=settings)

    assert secret not in caplog.text
    assert secret not in str(excinfo.value)
    assert secret not in repr(settings)


async def test_extra_headers_passed_through_and_never_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    session_secret = "session-secret-that-must-not-leak"
    calls: dict[str, Any] = {"count": 0, "kwargs": {}}
    monkeypatch.setattr(
        "ragmur.llm.provider.litellm.acompletion", _fake_success(calls, text="hola")
    )
    settings = _settings(
        llm_extra_headers={"x-opencode-session": session_secret, "User-Agent": "ragmur/0.1"}
    )

    with caplog.at_level("INFO"):
        result = await complete(_messages(), settings=settings)

    assert result.text == "hola"
    assert calls["kwargs"]["extra_headers"] == {
        "x-opencode-session": session_secret,
        "User-Agent": "ragmur/0.1",
    }
    # Copia defensiva: mutar lo enviado no cambia la configuración.
    assert calls["kwargs"]["extra_headers"] is not settings.llm_extra_headers
    assert session_secret not in caplog.text


async def test_no_extra_headers_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {"count": 0, "kwargs": {}}
    monkeypatch.setattr(
        "ragmur.llm.provider.litellm.acompletion", _fake_success(calls, text="hola")
    )

    await complete(_messages(), settings=_settings())

    assert "extra_headers" not in calls["kwargs"]


async def test_success_reports_single_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {"count": 0, "kwargs": {}}
    monkeypatch.setattr(
        "ragmur.llm.provider.litellm.acompletion", _fake_success(calls, text="hola")
    )

    result = await complete(_messages(), settings=_settings())

    assert result.attempts == 1
    assert result.latency_ms >= 0


async def test_retry_then_success_reports_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}

    async def _call(**kwargs: Any) -> Any:
        calls["count"] += 1
        if calls["count"] == 1:
            raise _litellm.Timeout("timed out", "test-model", "test-provider")
        return _response(text="al segundo intento")

    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    monkeypatch.setattr("ragmur.llm.provider.litellm.acompletion", _call)

    result = await complete(_messages(), settings=_settings())

    assert result.text == "al segundo intento"
    assert result.attempts == 2
    assert calls["count"] == 2


async def test_retry_after_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []
    calls = {"count": 0}

    async def _sleep(delay: float) -> None:
        slept.append(delay)

    async def _call(**kwargs: Any) -> Any:
        calls["count"] += 1
        raise _litellm.RateLimitError(
            "limited", "test-provider", "test-model", headers={"retry-after": "30"}
        )

    monkeypatch.setattr(asyncio, "sleep", _sleep)
    monkeypatch.setattr("ragmur.llm.provider.litellm.acompletion", _call)

    with pytest.raises(LLMRateLimited):
        await complete(_messages(), settings=_settings())
    assert calls["count"] == 3
    assert slept == [10.0, 10.0]


async def test_403_does_not_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    async def _call(**kwargs: Any) -> Any:
        calls["count"] += 1
        raise _litellm.APIError(
            status_code=403,
            message="forbidden",
            llm_provider="test-provider",
            model="test-model",
        )

    monkeypatch.setattr("ragmur.llm.provider.litellm.acompletion", _call)

    with pytest.raises(LLMAuthError):
        await complete(_messages(), settings=_settings())
    assert calls["count"] == 1


async def test_generic_5xx_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    async def _call(**kwargs: Any) -> Any:
        calls["count"] += 1
        if calls["count"] == 1:
            raise _litellm.APIError(
                status_code=500,
                message="server broke",
                llm_provider="test-provider",
                model="test-model",
            )
        return _response(text="recuperado")

    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    monkeypatch.setattr("ragmur.llm.provider.litellm.acompletion", _call)

    result = await complete(_messages(), settings=_settings())

    assert result.text == "recuperado"
    assert result.attempts == 2
    assert calls["count"] == 2


async def test_connection_error_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    async def _call(**kwargs: Any) -> Any:
        calls["count"] += 1
        if calls["count"] == 1:
            raise _litellm.APIConnectionError("conn broke", "test-provider", "test-model")
        return _response(text="recuperado")

    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    monkeypatch.setattr("ragmur.llm.provider.litellm.acompletion", _call)

    result = await complete(_messages(), settings=_settings())

    assert result.text == "recuperado"
    assert calls["count"] == 2


async def test_generic_4xx_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    async def _call(**kwargs: Any) -> Any:
        calls["count"] += 1
        raise _litellm.APIError(
            status_code=400,
            message="bad request",
            llm_provider="test-provider",
            model="test-model",
        )

    monkeypatch.setattr("ragmur.llm.provider.litellm.acompletion", _call)

    with pytest.raises(LLMError):
        await complete(_messages(), settings=_settings())
    assert calls["count"] == 1


async def test_not_found_error_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    async def _call(**kwargs: Any) -> Any:
        calls["count"] += 1
        raise _litellm.NotFoundError(
            message="no such model", model="test-model", llm_provider="test-provider"
        )

    monkeypatch.setattr("ragmur.llm.provider.litellm.acompletion", _call)

    with pytest.raises(LLMError):
        await complete(_messages(), settings=_settings())
    assert calls["count"] == 1


async def test_bad_request_error_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    async def _call(**kwargs: Any) -> Any:
        calls["count"] += 1
        raise _litellm.BadRequestError(
            message="bad request", model="test-model", llm_provider="test-provider"
        )

    monkeypatch.setattr("ragmur.llm.provider.litellm.acompletion", _call)

    with pytest.raises(LLMError):
        await complete(_messages(), settings=_settings())
    assert calls["count"] == 1


async def test_unmapped_exception_is_wrapped_without_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "super-secret-key-that-must-not-leak"
    calls = {"count": 0}

    async def _call(**kwargs: Any) -> Any:
        calls["count"] += 1
        raise ValueError("unexpected boom")

    monkeypatch.setattr("ragmur.llm.provider.litellm.acompletion", _call)
    settings = _settings(llm_api_key=secret)

    with pytest.raises(LLMError) as excinfo:
        await complete(_messages(), settings=settings)

    assert calls["count"] == 1
    assert secret not in str(excinfo.value)


async def test_lm_studio_without_api_key_sends_no_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin clave no se inventa ninguna: `LMStudioChatConfig` de LiteLLM 1.108.2
    ya sustituye `fake-api-key` (verificado en el paquete instalado)."""
    calls: dict[str, Any] = {"count": 0, "kwargs": {}}
    monkeypatch.setattr(
        "ragmur.llm.provider.litellm.acompletion", _fake_success(calls, text="hola")
    )
    settings = _settings(
        llm_model="lm_studio/test-model",
        llm_api_key=None,
        llm_api_base="http://127.0.0.1:1234/v1",
    )

    result = await complete(_messages(), settings=settings)

    assert result.text == "hola"
    assert "api_key" not in calls["kwargs"]
    assert calls["kwargs"]["api_base"] == "http://127.0.0.1:1234/v1"
