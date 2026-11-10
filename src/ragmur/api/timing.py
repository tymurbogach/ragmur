"""Marca el inicio de las peticiones con un reloj monotónico."""

import time

from starlette.types import ASGIApp, Receive, Scope, Send


class RequestTimingMiddleware:
    """Registra el comienzo de la petición en su estado ASGI."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            scope.setdefault("state", {})["request_started"] = time.perf_counter()
        await self.app(scope, receive, send)
