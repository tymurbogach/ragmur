"""Límite de peticiones por clave de API."""

import asyncio
import time
from collections import deque


class RateLimiter:
    """Ventana deslizante en memoria para una sola instancia.

    La fase 1 mantiene una única instancia escritora; un contador en memoria
    basta y evita añadir una dependencia externa. Con varias réplicas haría
    falta un contador compartido.
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def check(
        self, key: str, limit: int, window_seconds: float, max_keys: int = 10000
    ) -> float | None:
        """Devuelve segundos de espera si se supera el límite, o `None`."""
        now = time.monotonic()
        async with self._lock:
            expired = [key for key, hits in self._hits.items() if hits[-1] <= now - window_seconds]
            for expired_key in expired:
                del self._hits[expired_key]
            if key not in self._hits and len(self._hits) >= max_keys:
                return max(
                    0.0, min(hits[-1] for hits in self._hits.values()) + window_seconds - now
                )
            queue = self._hits.setdefault(key, deque())
            while queue and queue[0] <= now - window_seconds:
                queue.popleft()
            if not queue:
                # Evita que las claves inactivas crezcan sin cota.
                del self._hits[key]
                queue = self._hits.setdefault(key, deque())
            if len(queue) >= limit:
                return max(0.0, queue[0] + window_seconds - now)
            queue.append(now)
            return None

    async def reset(self) -> None:
        """Vacía el estado; solo para tests."""
        async with self._lock:
            self._hits.clear()

    def clear(self) -> None:
        """Vacía el estado sin bloqueo; solo para fixtures de test."""
        self._hits.clear()


limiter = RateLimiter()
auth_limiter = RateLimiter()
