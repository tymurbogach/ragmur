"""Prueba el límite antes del análisis del cuerpo."""

from uuid import UUID

import pytest
from pydantic import ValidationError
from starlette.types import Message, Receive, Scope, Send

from ragmur.api.json_limit import JsonLimitMiddleware
from ragmur.api.schemas import SearchRequest, VerifyRequest


@pytest.mark.parametrize("chunks, expected", [([b"123", b"45"], 200), ([b"123", b"456"], 413)])
async def test_stream_limit(chunks: list[bytes], expected: int) -> None:
    messages = iter(
        {"type": "http.request", "body": chunk, "more_body": index < len(chunks) - 1}
        for index, chunk in enumerate(chunks)
    )
    sent: list[Message] = []
    received: list[bytes] = []

    async def receive() -> Message:
        return next(messages)

    async def send(message: Message) -> None:
        sent.append(message)

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        message = await receive()
        received.append(message["body"])
        await send({"type": "http.response.start", "status": 200, "headers": []})

    middleware = JsonLimitMiddleware(app, max_bytes=5)
    await middleware({"type": "http", "method": "POST", "path": "/v1/search"}, receive, send)
    assert sent[0]["status"] == expected
    assert received == ([b"12345"] if expected == 200 else [])


@pytest.mark.parametrize("owner", ["x" * 257, "   "])
def test_json_routes_reject_invalid_owner(owner: str) -> None:
    with pytest.raises(ValidationError):
        SearchRequest(query="test", owner_id=owner)
    with pytest.raises(ValidationError):
        VerifyRequest(answer="test", chunk_ids=[UUID(int=1)], owner_id=owner)
