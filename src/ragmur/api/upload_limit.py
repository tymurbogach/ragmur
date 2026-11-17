"""Limita el cuerpo multipart antes de que Starlette lo analice."""

import asyncio
import tempfile
from collections.abc import Callable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ragmur.api.error_response import send_error


async def _file_call[T](operation: Callable[..., T], *args: object) -> T:
    task = asyncio.create_task(asyncio.to_thread(operation, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        await task
        raise


class UploadLimitMiddleware:
    """Almacena temporalmente un cuerpo acotado antes de procesarlo."""

    def __init__(
        self,
        app: ASGIApp,
        max_bytes: int,
        overhead_bytes: int,
        max_concurrent: int = 8,
        timeout_seconds: float = 120,
    ) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.overhead_bytes = overhead_bytes
        self.max_concurrent = max_concurrent
        self.timeout_seconds = timeout_seconds
        self.active = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] != "/v1/documents":
            await self.app(scope, receive, send)
            return
        if self.active >= self.max_concurrent:
            await send_error(send, 503, "Upload capacity exhausted", retry_after=True)
            return
        self.active += 1
        try:
            await self._receive_upload(scope, receive, send)
        finally:
            self.active -= 1

    async def _receive_upload(self, scope: Scope, receive: Receive, send: Send) -> None:
        # El margen incluye cabeceras y campos del multipart, no bytes adicionales de fichero.
        limit = self.max_bytes + self.overhead_bytes
        deadline = asyncio.get_running_loop().time() + self.timeout_seconds
        with tempfile.TemporaryFile() as buffer:
            size = 0
            while True:
                try:
                    async with asyncio.timeout_at(deadline):
                        message = await receive()
                except TimeoutError:
                    await send_error(send, 408, "Upload timed out")
                    return
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                size += len(chunk)
                if size > limit:
                    await send_error(send, 413, "File too large")
                    return
                await _file_call(buffer.write, chunk)
                if asyncio.get_running_loop().time() >= deadline:
                    await send_error(send, 408, "Upload timed out")
                    return
                if not message.get("more_body", False):
                    break
            await _file_call(buffer.seek, 0)

            complete = False

            async def replay() -> Message:
                nonlocal complete
                if complete:
                    return await receive()
                chunk = await _file_call(buffer.read, 65536)
                if chunk:
                    return {"type": "http.request", "body": chunk, "more_body": True}
                complete = True
                return {"type": "http.request", "body": b"", "more_body": False}

            await self.app(scope, replay, send)
