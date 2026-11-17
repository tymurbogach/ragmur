"""Límites del cuerpo HTTP antes del análisis multipart."""

import asyncio

import pytest
from starlette.types import Message, Scope

from ragmur.api.upload_limit import UploadLimitMiddleware


@pytest.mark.parametrize("chunks", [[b"123456", b"7890"], [b"1234567890"]])
async def test_body_limit_rejects_stream_without_content_length(chunks: list[bytes]) -> None:
    messages: list[Message] = []
    received: list[Message] = [
        {"type": "http.request", "body": chunk, "more_body": index < len(chunks) - 1}
        for index, chunk in enumerate(chunks)
    ]
    called = False

    async def app(scope: Scope, receive: object, send: object) -> None:
        nonlocal called
        called = True

    async def receive() -> Message:
        return received.pop(0)

    async def send(message: Message) -> None:
        messages.append(message)

    middleware = UploadLimitMiddleware(app, max_bytes=5, overhead_bytes=2)
    scope: Scope = {"type": "http", "method": "POST", "path": "/v1/documents"}
    await middleware(scope, receive, send)
    assert messages[0]["status"] == 413
    assert messages[0]["headers"] == [
        (b"content-type", b"application/json"),
        (b"content-length", b"48"),
    ]
    assert messages[1] == {
        "type": "http.response.body",
        "body": b'{"code": "http_413", "detail": "File too large"}',
    }
    assert not called


async def test_timeout_and_capacity_release() -> None:
    entered = asyncio.Event()
    release = asyncio.Event()
    messages: list[Message] = []

    async def app(scope: Scope, receive: object, send: object) -> None:
        raise AssertionError("The upload must not reach the application")

    async def receive() -> Message:
        entered.set()
        await release.wait()
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        messages.append(message)

    middleware = UploadLimitMiddleware(app, 5, 2, max_concurrent=1, timeout_seconds=0.05)
    scope: Scope = {"type": "http", "method": "POST", "path": "/v1/documents"}
    first = asyncio.create_task(middleware(scope, receive, send))
    await entered.wait()
    await middleware(scope, receive, send)
    assert messages[0]["status"] == 503
    assert messages[0]["headers"] == [
        (b"content-type", b"application/json"),
        (b"content-length", b"59"),
        (b"retry-after", b"1"),
    ]
    assert messages[1] == {
        "type": "http.response.body",
        "body": b'{"code": "http_503", "detail": "Upload capacity exhausted"}',
    }
    await first
    assert messages[2]["status"] == 408
    assert messages[2]["headers"] == [
        (b"content-type", b"application/json"),
        (b"content-length", b"50"),
    ]
    assert messages[3] == {
        "type": "http.response.body",
        "body": b'{"code": "http_408", "detail": "Upload timed out"}',
    }
    assert middleware.active == 0
    release.set()
    await middleware(scope, receive, send)
    assert middleware.active == 0
