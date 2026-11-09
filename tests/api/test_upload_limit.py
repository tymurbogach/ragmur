"""Límites del cuerpo HTTP antes del análisis multipart."""

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
    assert not called
