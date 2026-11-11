"""Admisión acotada de peticiones que usan modelos."""

import json

from starlette.types import ASGIApp, Receive, Scope, Send


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
            body = json.dumps(
                {"code": "http_503", "detail": "Inference capacity exhausted"}
            ).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 503,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                        (b"retry-after", b"1"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        self.active += 1
        try:
            await self.app(scope, receive, send)
        finally:
            self.active -= 1
