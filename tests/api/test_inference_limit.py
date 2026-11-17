"""Límite de peticiones y cancelación de inferencia."""

import asyncio
import threading
from contextlib import suppress

from starlette.types import Message, Receive, Scope, Send

from ragmur.api.inference_limit import InferenceLimitMiddleware
from ragmur.retrieval.models import run_inference


async def test_capacity_released_after_cancellation() -> None:
    started = threading.Event()
    release = threading.Event()
    messages: list[Message] = []

    def work() -> None:
        started.set()
        release.wait(timeout=5)

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        await run_inference(work)

    async def receive() -> Message:
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        messages.append(message)

    middleware = InferenceLimitMiddleware(app, 1)
    scope: Scope = {"type": "http", "method": "POST", "path": "/v1/search"}
    first = asyncio.create_task(middleware(scope, receive, send))
    try:
        assert await asyncio.to_thread(started.wait, 2)
        first.cancel()
        await asyncio.sleep(0)
        await asyncio.wait_for(middleware(scope, receive, send), timeout=2)
        assert messages[0]["status"] == 503
        assert messages[0]["headers"] == [
            (b"content-type", b"application/json"),
            (b"content-length", b"62"),
            (b"retry-after", b"1"),
        ]
        assert messages[1] == {
            "type": "http.response.body",
            "body": b'{"code": "http_503", "detail": "Inference capacity exhausted"}',
        }
        assert middleware.active == 1
    finally:
        release.set()
    with suppress(asyncio.CancelledError):
        await asyncio.wait_for(first, timeout=2)
    assert middleware.active == 0
