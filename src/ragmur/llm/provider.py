"""Puerta única de acceso a cualquier LLM (regla 7 de `AGENTS.md`).

Ningún otro módulo del servicio importa un SDK de proveedor: toda llamada a
un modelo de lenguaje pasa por `complete()`. La implementación usa LiteLLM,
que expone una sola función (`acompletion`) para proveedores locales
(Ollama, LM Studio) y remotos (OpenAI, Anthropic, Gemini).

Conceptos para quien lee esto por primera vez:

- *Proveedor*: servicio que ejecuta el modelo (Ollama en local, OpenAI por
  API, etc.). LiteLLM traduce una sola llamada al formato de cada uno.
- *`seed`*: número que fija el muestreo aleatorio del modelo para que la
  misma petición devuelva la misma respuesta.
- *`retry_after`*: segundos que pide esperar el proveedor tras un `429`
  (cuota de peticiones agotada) antes de reintentar.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from ragmur.core.config import Settings

# El mapa local de costes debe fijarse antes de importar litellm, o el import
# descarga el mapa remoto (ver DECISIONS.md 3.34). Sin `noqa E402`: ruff 0.16.2
# exime `os.environ.setdefault` antes de imports; añadirlo rompería `RUF100`.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import litellm
from litellm.exceptions import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    BadGatewayError,
    InternalServerError,
    PaymentRequiredError,
    PermissionDeniedError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)

if hasattr(litellm, "telemetry"):  # pragma: no cover
    litellm.telemetry = False
litellm.suppress_debug_info = True

logger = logging.getLogger(__name__)

# Espera máxima ante un `retry-after` del proveedor: se respeta su petición
# pero acotada para no bloquear una petición más de lo razonable.
MAX_RETRY_AFTER_WAIT_SECONDS = 10.0

# Espera base entre reintentos sin indicación del proveedor: crece como
# `0.5 * 2**intento` y queda acotada por `MAX_RETRY_AFTER_WAIT_SECONDS`.
BASE_BACKOFF_SECONDS = 0.5


def _backoff_seconds(attempt: int) -> float:
    """Espera ante un reintento sin `retry-after`, en segundos."""
    return float(min(BASE_BACKOFF_SECONDS * 2**attempt, MAX_RETRY_AFTER_WAIT_SECONDS))


class LLMError(Exception):
    """Fallo genérico de la llamada al LLM; base de los demás errores."""


class LLMConfigError(LLMError):
    """Falta configuración (`llm_model`) antes de llamar a la red."""


class LLMTimeout(LLMError):  # noqa: N818 - nombre fijado por el brief G02
    """El proveedor no respondió dentro de `llm_timeout_seconds`."""


class LLMRateLimited(LLMError):  # noqa: N818 - nombre fijado por el brief G02
    """Cuota de peticiones agotada (`429`); no se reintentó con éxito."""

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMAuthError(LLMError):
    """Credenciales inválidas o sin permiso (`401`/`403`); no se reintenta."""


class LLMQuotaExceeded(LLMError):  # noqa: N818 - nombre fijado por el brief G02
    """Crédito agotado (`402`); no se reintenta."""


@dataclass(frozen=True)
class ChatMessage:
    """Un mensaje del historial: quién habla y qué dice."""

    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class Completion:
    """Respuesta del modelo con coste y latencia para el registro.

    `attempts` es el intento que tuvo éxito, contado desde 1: vale 1 si la
    primera llamada funcionó y `llm_max_retries + 1` como mucho.
    `latency_ms` mide solo ese intento con éxito, no los reintentos previos.
    """

    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    attempts: int


def _retry_after_seconds(exc: BaseException) -> float | None:
    """Extrae los segundos de `retry-after` del error, si los trae."""
    candidates: list[Any] = [getattr(exc, "headers", None)]
    response = getattr(exc, "response", None)
    if response is not None:
        candidates.append(getattr(response, "headers", None))
    for headers in candidates:
        if not headers:
            continue
        items = headers.items() if hasattr(headers, "items") else headers
        try:
            pairs = list(items() if callable(items) else items)
        except Exception:  # pragma: no cover
            continue
        for key, value in pairs:
            if str(key).lower().replace("_", "-") != "retry-after":
                continue
            try:
                seconds = float(str(value))
            except (TypeError, ValueError):
                return None
            return seconds if seconds >= 0 else None
    return None


def _status_code(exc: BaseException) -> int | None:
    """Código HTTP del error de LiteLLM, si lo expone."""
    code = getattr(exc, "status_code", None)
    if isinstance(code, int):
        return code
    response = getattr(exc, "response", None)
    code = getattr(response, "status_code", None)
    return code if isinstance(code, int) else None


async def complete(
    messages: Sequence[ChatMessage],
    *,
    settings: Settings,
    temperature: float = 0.0,
    seed: int | None = None,
    max_tokens: int | None = None,
) -> Completion:
    """Completa un historial de chat con un solo modelo, sin `fallback`.

    Reintenta como máximo `settings.llm_max_retries` veces solo ante
    timeouts, `429` y errores de conexión o `5xx` sin código conocido;
    nunca ante `401`/`403`/`402` ni otros `4xx`. Ante un `429` con
    `retry-after`, espera esos segundos (acotados a 10 s) antes de
    reintentar; sin indicación del proveedor, la espera crece como
    `0.5 * 2**intento`, también acotada a 10 s. Nunca registra el
    contenido de los mensajes, la clave ni los valores de
    `llm_extra_headers`; solo modelo, tokens, latencia e intento.
    """
    model = settings.llm_model
    if not model:
        raise LLMConfigError("llm_model is not configured; set LLM_MODEL")
    limit = settings.llm_max_tokens if max_tokens is None else max_tokens
    if limit <= 0:
        raise LLMConfigError("max_tokens must be positive")
    api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key is not None else None
    # Copia defensiva: las cabeceras viajan a LiteLLM, nunca a logs ni errores.
    # Sin clave configurada no se envía `api_key`: la ruta `lm_studio/` de
    # LiteLLM 1.108.2 ya sustituye un valor interno (`fake-api-key`), así que
    # este módulo no inventa ninguna clave. Verificado en
    # `litellm/llms/lm_studio/chat/transformation.py` (`LMStudioChatConfig`).
    extra_headers = dict(settings.llm_extra_headers)

    payload = [{"role": message.role, "content": message.content} for message in messages]
    attempts = settings.llm_max_retries + 1
    for attempt in range(1, attempts + 1):
        # El reloj arranca en cada intento: la latencia publicada mide solo
        # el intento con éxito, no los reintentos previos.
        attempt_started = time.monotonic()
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": payload,
                "temperature": temperature,
                "max_tokens": limit,
                "timeout": settings.llm_timeout_seconds,
                "num_retries": 0,
            }
            if seed is not None:
                kwargs["seed"] = seed
            if api_key is not None:
                kwargs["api_key"] = api_key
            if settings.llm_api_base is not None:
                kwargs["api_base"] = settings.llm_api_base
            if extra_headers:
                kwargs["extra_headers"] = extra_headers
            response: Any = await litellm.acompletion(**kwargs)
            return _to_completion(response, model, attempt_started, attempt)
        except (
            AuthenticationError,
            PermissionDeniedError,
        ) as exc:
            logger.warning("llm auth failure", extra={"model": model, "attempt": attempt})
            raise LLMAuthError(f"LLM authentication failed for model {model}") from exc
        except PaymentRequiredError as exc:
            logger.warning("llm quota exceeded", extra={"model": model, "attempt": attempt})
            raise LLMQuotaExceeded(f"LLM quota exceeded for model {model}") from exc
        except RateLimitError as exc:
            retry_after = _retry_after_seconds(exc)
            if attempt >= attempts:
                logger.warning(
                    "llm rate limited",
                    extra={"model": model, "attempts": attempts, "retry_after": retry_after},
                )
                raise LLMRateLimited(
                    f"LLM rate limit exceeded for model {model}", retry_after=retry_after
                ) from exc
            wait = (
                min(retry_after, MAX_RETRY_AFTER_WAIT_SECONDS)
                if retry_after
                else _backoff_seconds(attempt)
            )
            logger.warning(
                "llm rate limited",
                extra={"model": model, "attempt": attempt, "retry_after": retry_after},
            )
            if wait > 0:
                await asyncio.sleep(wait)
        except Timeout as exc:
            if attempt >= attempts:
                logger.warning("llm timeout", extra={"model": model, "attempts": attempts})
                raise LLMTimeout(f"LLM request timed out for model {model}") from exc
            logger.warning("llm timeout", extra={"model": model, "attempt": attempt})
            await asyncio.sleep(_backoff_seconds(attempt))
        except (
            APIConnectionError,
            InternalServerError,
            ServiceUnavailableError,
            BadGatewayError,
        ) as exc:
            if attempt >= attempts:
                logger.warning(
                    "llm unavailable",
                    extra={
                        "model": model,
                        "attempts": attempts,
                        "error": type(exc).__name__,
                    },
                )
                raise LLMError(f"LLM request failed for model {model}") from exc
            logger.warning(
                "llm transient failure",
                extra={"model": model, "attempt": attempt, "error": type(exc).__name__},
            )
            await asyncio.sleep(_backoff_seconds(attempt))
        except APIError as exc:
            code = _status_code(exc)
            if code in (401, 403):
                logger.warning(
                    "llm auth failure",
                    extra={"model": model, "attempt": attempt, "status_code": code},
                )
                raise LLMAuthError(f"LLM authentication failed for model {model}") from exc
            if code == 402:
                logger.warning(
                    "llm quota exceeded",
                    extra={"model": model, "attempt": attempt, "status_code": code},
                )
                raise LLMQuotaExceeded(f"LLM quota exceeded for model {model}") from exc
            if code == 429:
                retry_after = _retry_after_seconds(exc)
                if attempt >= attempts:
                    logger.warning(
                        "llm rate limited",
                        extra={
                            "model": model,
                            "attempts": attempts,
                            "retry_after": retry_after,
                        },
                    )
                    raise LLMRateLimited(
                        f"LLM rate limit exceeded for model {model}", retry_after=retry_after
                    ) from exc
                wait = (
                    min(retry_after, MAX_RETRY_AFTER_WAIT_SECONDS)
                    if retry_after
                    else _backoff_seconds(attempt)
                )
                logger.warning(
                    "llm rate limited",
                    extra={"model": model, "attempt": attempt, "retry_after": retry_after},
                )
                if wait > 0:
                    await asyncio.sleep(wait)
            elif code is None or code >= 500:
                if attempt >= attempts:
                    logger.warning(
                        "llm unavailable",
                        extra={
                            "model": model,
                            "attempts": attempts,
                            "error": type(exc).__name__,
                        },
                    )
                    raise LLMError(f"LLM request failed for model {model}") from exc
                logger.warning(
                    "llm transient failure",
                    extra={
                        "model": model,
                        "attempt": attempt,
                        "error": type(exc).__name__,
                        "status_code": code,
                    },
                )
                await asyncio.sleep(_backoff_seconds(attempt))
            else:
                logger.warning(
                    "llm request failed",
                    extra={
                        "model": model,
                        "attempt": attempt,
                        "error": type(exc).__name__,
                        "status_code": code,
                    },
                )
                raise LLMError(f"LLM request failed for model {model}") from exc
        except Exception as exc:
            # Red final: excepciones que no heredan de `APIError`
            # (`BadRequestError`, `NotFoundError`, etc. de `litellm`) u otros
            # fallos inesperados. Nunca incluye el secreto en el mensaje.
            logger.warning(
                "llm request failed",
                extra={"model": model, "attempt": attempt, "error": type(exc).__name__},
            )
            raise LLMError(f"LLM request failed for model {model}") from exc
    raise LLMError(f"LLM request failed for model {model}")  # pragma: no cover


def _to_completion(response: Any, model: str, started: float, attempts: int) -> Completion:
    """Convierte la respuesta de LiteLLM en un `Completion` propio."""
    reported_model = getattr(response, "model", None) or model
    usage = getattr(response, "usage", None)
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    choices = getattr(response, "choices", None) or []
    text = ""
    if choices:
        message = getattr(choices[0], "message", None)
        text = getattr(message, "content", None) or ""
    completion = Completion(
        text=str(text),
        model=str(reported_model),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=(time.monotonic() - started) * 1000.0,
        attempts=attempts,
    )
    logger.info(
        "llm completion",
        extra={
            "model": completion.model,
            "prompt_tokens": completion.prompt_tokens,
            "completion_tokens": completion.completion_tokens,
            "latency_ms": round(completion.latency_ms, 1),
            "attempts": completion.attempts,
        },
    )
    return completion
