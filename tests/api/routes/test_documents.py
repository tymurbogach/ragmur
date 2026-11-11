"""Pruebas de las rutas de documentos con PostgreSQL real."""

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from ragmur.auth.service import create_tenant, issue_key
from ragmur.core.config import get_settings
from ragmur.db.models import Tenant
from ragmur.db.session import create_engine, create_session_factory
from ragmur.main import create_app


@pytest.fixture
async def document_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> AsyncIterator[tuple[AsyncClient, str, str]]:
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr("ragmur.ingestion.pipeline.IngestionCoordinator.reconcile", AsyncMock())
    monkeypatch.setattr("ragmur.ingestion.indexer.Indexer.index", AsyncMock(return_value=1))
    monkeypatch.setattr("ragmur.ingestion.indexer.Indexer.cleanup", AsyncMock())
    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    ids: list[UUID] = []
    try:
        async with factory() as session:
            a = await create_tenant(session, "documents-a")
            b = await create_tenant(session, "documents-b")
            ids = [a.id, b.id]
            secret = settings.api_key_hmac_secret.get_secret_value()
            first = await issue_key(session, a.id, None, secret)
            second = await issue_key(session, b.id, None, secret)
        app: FastAPI = create_app()
        async with (
            app.router.lifespan_context(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
        ):
            yield client, first, second
    finally:
        async with factory() as session:
            await session.execute(delete(Tenant).where(Tenant.id.in_(ids)))
            await session.commit()
        await engine.dispose()


async def test_upload_deduplicate_and_isolate(
    document_client: tuple[AsyncClient, str, str],
) -> None:
    client, first, second = document_client
    headers = {"X-API-Key": first}
    response = await client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("hello.txt", b"hello", "text/plain")},
        data={"owner_id": "alice"},
    )
    assert response.status_code == 202
    document_id = response.json()["document_id"]
    assert response.headers["location"] == f"/v1/documents/{document_id}"
    detail = await client.get(
        f"/v1/documents/{document_id}", headers=headers, params={"owner_id": "alice"}
    )
    assert detail.status_code == 200 and detail.json()["status"] == "indexed"
    assert (
        await client.get(
            f"/v1/documents/{document_id}", headers=headers, params={"owner_id": "bob"}
        )
    ).status_code == 404
    assert (
        await client.get(f"/v1/documents/{document_id}", headers={"X-API-Key": second})
    ).status_code == 404
    duplicate = await client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("again.txt", b"hello", "text/plain")},
        data={"owner_id": "alice"},
    )
    assert duplicate.status_code == 200 and duplicate.json()["document_id"] == document_id
    assert duplicate.json()["status"] == "indexed"
    assert (
        await client.delete(
            f"/v1/documents/{document_id}", headers=headers, params={"owner_id": "alice"}
        )
    ).status_code == 204
    assert (await client.get(f"/v1/documents/{document_id}", headers=headers)).status_code == 404


async def test_owner_id_length_on_document_routes(
    document_client: tuple[AsyncClient, str, str],
) -> None:
    client, first, _ = document_client
    headers = {"X-API-Key": first}
    owner = "x" * 256
    response = await client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("hello.txt", b"hello", "text/plain")},
        data={"owner_id": owner},
    )
    assert response.status_code == 202
    document_id = response.json()["document_id"]
    too_long = owner + "x"
    for method, path in [
        ("GET", "/v1/documents"),
        ("GET", f"/v1/documents/{document_id}"),
        ("DELETE", f"/v1/documents/{document_id}"),
    ]:
        assert (
            await client.request(method, path, headers=headers, params={"owner_id": too_long})
        ).status_code == 422
    assert (
        await client.post(
            "/v1/documents",
            headers=headers,
            files={"file": ("other.txt", b"other", "text/plain")},
            data={"owner_id": too_long},
        )
    ).status_code == 422
    assert (
        await client.get(
            f"/v1/documents/{document_id}", headers=headers, params={"owner_id": owner}
        )
    ).status_code == 200


async def test_upload_rejects_wrong_format_and_missing_key(
    document_client: tuple[AsyncClient, str, str],
) -> None:
    client, first, _ = document_client
    files = {"file": ("bad.pdf", b"not a pdf", "application/pdf")}
    assert (await client.post("/v1/documents", files=files)).status_code == 401
    response = await client.post("/v1/documents", headers={"X-API-Key": first}, files=files)
    assert response.status_code == 415


async def test_concurrent_duplicates_have_one_identity(
    document_client: tuple[AsyncClient, str, str],
) -> None:
    import asyncio

    client, first, _ = document_client

    async def upload() -> tuple[int, dict[str, object]]:
        result = await client.post(
            "/v1/documents",
            headers={"X-API-Key": first},
            files={"file": ("same.txt", b"the same document", "text/plain")},
        )
        return result.status_code, result.json()

    first_result, second_result = await asyncio.gather(upload(), upload())
    assert sorted([first_result[0], second_result[0]]) == [200, 202]
    assert first_result[1]["document_id"] == second_result[1]["document_id"]


async def test_rejects_unexpected_form_fields(
    document_client: tuple[AsyncClient, str, str],
) -> None:
    client, key, _ = document_client
    response = await client.post(
        "/v1/documents",
        headers={"X-API-Key": key},
        files={"file": ("a.txt", b"abc", "text/plain")},
        data={"tenant_id": "foreign"},
    )
    assert response.status_code == 422


async def test_disk_failure_and_upload_size_are_safe(
    document_client: tuple[AsyncClient, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, key, _ = document_client
    headers = {"X-API-Key": key}
    get_settings().max_upload_bytes = 3
    response = await client.post(
        "/v1/documents", headers=headers, files={"file": ("a.txt", b"1234", "text/plain")}
    )
    assert response.status_code == 413
    get_settings().max_upload_bytes = 100

    def failing_store(*args: object) -> None:
        raise OSError("sensitive internal path")

    monkeypatch.setattr("ragmur.api.routes.documents.store_original", failing_store)
    response = await client.post(
        "/v1/documents", headers=headers, files={"file": ("a.txt", b"abc", "text/plain")}
    )
    assert response.status_code == 503
    assert "sensitive" not in response.text
    assert (await client.get("/v1/documents", headers=headers)).json()["items"] == []


async def test_validation_does_not_echo_sensitive_input(
    document_client: tuple[AsyncClient, str, str],
) -> None:
    client, key, _ = document_client
    response = await client.get(
        "/v1/documents", headers={"X-API-Key": key}, params={"limit": "secret-value"}
    )
    assert response.status_code == 422
    assert "secret-value" not in response.text


async def test_owner_and_tenant_cannot_delete_each_others_documents(
    document_client: tuple[AsyncClient, str, str],
) -> None:
    client, first, second = document_client
    alice_headers = {"X-API-Key": first}
    upload = await client.post(
        "/v1/documents",
        headers=alice_headers,
        files={"file": ("private.txt", b"private document", "text/plain")},
        data={"owner_id": "alice"},
    )
    document_id = upload.json()["document_id"]
    assert upload.status_code == 202
    bob_delete = await client.delete(
        f"/v1/documents/{document_id}", headers=alice_headers, params={"owner_id": "bob"}
    )
    tenant_delete = await client.delete(
        f"/v1/documents/{document_id}", headers={"X-API-Key": second}
    )
    assert bob_delete.status_code == tenant_delete.status_code == 404
    listing = await client.get("/v1/documents", headers=alice_headers, params={"owner_id": "bob"})
    assert listing.json()["items"] == []
    assert (
        await client.get(f"/v1/documents/{document_id}", headers=alice_headers)
    ).status_code == 200


async def test_listing_cursor_and_invalid_cursor(
    document_client: tuple[AsyncClient, str, str],
) -> None:
    client, key, _ = document_client
    headers = {"X-API-Key": key}
    ids = []
    for text in (b"first", b"second"):
        response = await client.post(
            "/v1/documents", headers=headers, files={"file": ("a.txt", text, "text/plain")}
        )
        assert response.status_code == 202
        ids.append(response.json()["document_id"])
    first = await client.get("/v1/documents", headers=headers, params={"limit": 1})
    assert first.status_code == 200 and first.json()["next_cursor"]
    second = await client.get(
        "/v1/documents",
        headers=headers,
        params={"limit": 1, "cursor": first.json()["next_cursor"]},
    )
    assert second.status_code == 200 and second.json()["next_cursor"] is None
    assert {first.json()["items"][0]["id"], second.json()["items"][0]["id"]} == set(ids)
    invalid = await client.get("/v1/documents", headers=headers, params={"cursor": "not-a-cursor"})
    assert invalid.status_code == 422


async def test_empty_owner_does_not_expand_scope(
    document_client: tuple[AsyncClient, str, str],
) -> None:
    client, key, _ = document_client
    result = await client.post(
        "/v1/documents",
        headers={"X-API-Key": key},
        files={"file": ("a.txt", b"abc", "text/plain")},
        data={"owner_id": ""},
    )
    assert result.status_code == 422


async def test_delete_failure_can_be_retried(
    document_client: tuple[AsyncClient, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, key, _ = document_client
    headers = {"X-API-Key": key}
    upload = await client.post(
        "/v1/documents", headers=headers, files={"file": ("a.txt", b"delete me", "text/plain")}
    )
    document_id = upload.json()["document_id"]
    original_unlink = Path.unlink

    def broken_unlink(path: Path, *args: object, **kwargs: object) -> None:
        if path.name == document_id:
            raise OSError("private path")
        original_unlink(path, *args, **kwargs)  # type: ignore[arg-type]

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", broken_unlink)
        failed = await client.delete(f"/v1/documents/{document_id}", headers=headers)
    assert failed.status_code == 503 and "private path" not in failed.text
    detail = await client.get(f"/v1/documents/{document_id}", headers=headers)
    assert detail.json()["status"] == "deleting"
    assert (await client.delete(f"/v1/documents/{document_id}", headers=headers)).status_code == 204


async def test_active_document_cannot_be_deleted_or_disclosed(
    document_client: tuple[AsyncClient, str, str],
) -> None:
    from typing import cast

    client, first, second = document_client
    headers = {"X-API-Key": first}
    upload = await client.post(
        "/v1/documents", headers=headers, files={"file": ("a.txt", b"active", "text/plain")}
    )
    document_id = upload.json()["document_id"]
    transport = cast(ASGITransport, client._transport)
    app = cast(FastAPI, transport.app)
    app.state.resources.ingestion.accepted.add(UUID(document_id))
    try:
        assert (
            await client.delete(f"/v1/documents/{document_id}", headers=headers)
        ).status_code == 409
        foreign = await client.delete(f"/v1/documents/{document_id}", headers={"X-API-Key": second})
        assert foreign.status_code == 404
    finally:
        app.state.resources.ingestion.accepted.discard(UUID(document_id))
