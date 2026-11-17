"""Admisión acotada de peticiones que usan modelos."""

from starlette.types import ASGIApp, Receive, Scope, Send

from ragmur.api.error_response import send_error


class InferenceLimitMiddleware:
    """Limita las peticiones de búsqueda y verificación en una instancia."""

    def __init__(self, app: ASGIApp, max_requests: int) -> None:
        self.app = app
        self.max_requests = max_requests
        self.active = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"] not in ("/v1/search", "/v1/verify")
        ):
            await self.app(scope, receive, send)
            return
        if self.active >= self.max_requests:
            await send_error(send, 503, "Inference capacity exhausted", retry_after=True)
            return
        self.active += 1
        try:
            await self.app(scope, receive, send)
        finally:
            self.active -= 1
