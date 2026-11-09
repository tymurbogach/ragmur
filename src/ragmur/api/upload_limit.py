"""Limita el cuerpo multipart antes de que Starlette lo analice."""

import asyncio
import json
import tempfile

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class UploadLimitMiddleware:
    """Almacena temporalmente un cuerpo acotado antes de procesarlo."""

    def __init__(self, app: ASGIApp, max_bytes: int, overhead_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.overhead_bytes = overhead_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] != "/v1/documents":
            await self.app(scope, receive, send)
            return
        # El margen incluye cabeceras y campos del multipart, no bytes adicionales de fichero.
        limit = self.max_bytes + self.overhead_bytes
        with tempfile.TemporaryFile() as buffer:
            size = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                size += len(chunk)
                if size > limit:
                    body = json.dumps({"code": "http_413", "detail": "File too large"}).encode()
                    await send(
                        {
                            "type": "http.response.start",
                            "status": 413,
                            "headers": [
                                (b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode()),
                            ],
                        }
                    )
                    await send({"type": "http.response.body", "body": body})
                    return
                await asyncio.to_thread(buffer.write, chunk)
                if not message.get("more_body", False):
                    break
            await asyncio.to_thread(buffer.seek, 0)

            complete = False

            async def replay() -> Message:
                nonlocal complete
                if complete:
                    return await receive()
                chunk = await asyncio.to_thread(buffer.read, 65536)
                if chunk:
                    return {"type": "http.request", "body": chunk, "more_body": True}
                complete = True
                return {"type": "http.request", "body": b"", "more_body": False}

            await self.app(scope, replay, send)
