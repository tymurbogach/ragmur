"""Pruebas de autenticación con PostgreSQL real."""

from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from ragmur.api.deps import CurrentTenant
from ragmur.auth.service import create_tenant, issue_key, revoke_key
from ragmur.core.config import Settings, get_settings
from ragmur.db.models import ApiKey, Tenant
from ragmur.db.session import create_engine, create_session_factory
from ragmur.main import create_app


@pytest.fixture
async def auth_setup() -> AsyncIterator[tuple[FastAPI, str, str]]:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    ids = []
    try:
        async with factory() as session:
            a = await create_tenant(session, "test-a")
            b = await create_tenant(session, "test-b")
            ids = [a.id, b.id]
            secret = settings.api_key_hmac_secret.get_secret_value()
            first = await issue_key(session, a.id, None, secret)
            second = await issue_key(session, b.id, None, secret)
        app = create_app()

        @app.get("/protected")
        async def protected(tenant: CurrentTenant) -> dict[str, str]:
            return {"tenant_id": str(tenant)}

        yield app, first, second
    finally:
        async with factory() as session:
            await session.execute(delete(Tenant).where(Tenant.id.in_(ids)))
            await session.commit()
        await engine.dispose()


async def test_authentication_and_revocation(auth_setup: tuple[FastAPI, str, str]) -> None:
    app, first, second = auth_setup
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        assert (await client.get("/protected")).status_code == 401
        assert (await client.get("/protected", headers={"X-API-Key": "bad"})).status_code == 401
        invalid = first.rsplit("_", 1)[0] + "_wrong"
        assert (await client.get("/protected", headers={"X-API-Key": invalid})).status_code == 401
        a = await client.get("/protected", headers={"X-API-Key": first})
        b = await client.get("/protected", headers={"X-API-Key": second})
        assert a.status_code == b.status_code == 200
        assert UUID(a.json()["tenant_id"]) != UUID(b.json()["tenant_id"])
        factory = app.state.resources.sessions
        async with factory() as session:
            key = await session.scalar(
                select(ApiKey).where(ApiKey.key_id == first.split("_", 2)[1])
            )
            assert key is not None and key.last_used_at is not None
            assert str(key.tenant_id) == a.json()["tenant_id"]
            before = key.last_used_at
        await client.get("/protected", headers={"X-API-Key": first})
        async with factory() as session:
            key = await session.scalar(
                select(ApiKey).where(ApiKey.key_id == first.split("_", 2)[1])
            )
            assert key is not None and key.last_used_at == before
            assert await revoke_key(session, key.key_id)
        assert (await client.get("/protected", headers={"X-API-Key": first})).status_code == 401
        assert (await client.get("/protected", headers={"X-API-Key": second})).status_code == 200


def test_hmac_secret_is_required_and_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("API_KEY_HMAC_SECRET", raising=False)
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="postgresql+asyncpg://localhost/db")
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://localhost/db",
        api_key_hmac_secret="private-value",
    )
    assert "private-value" not in repr(settings)


async def test_cli_lifecycle() -> None:
    import asyncio
    import sys

    async def command(*args: str) -> tuple[int | None, str]:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "ragmur.cli",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()
        return process.returncode, stdout.decode().strip()

    code, tenant = await command("create-tenant", "cli-test")
    assert code == 0
    engine = create_engine(get_settings().database_url)
    try:
        code, raw_key = await command("issue-key", tenant, "--name", "test")
        assert code == 0 and raw_key.startswith("rgm_")
        key_id = raw_key.split("_", 2)[1]
        code, message = await command("revoke-key", key_id)
        assert code == 0 and raw_key not in message
        code, _ = await command("revoke-key", key_id)
        assert code != 0
    finally:
        async with create_session_factory(engine)() as session:
            await session.execute(delete(Tenant).where(Tenant.id == UUID(tenant)))
            await session.commit()
        await engine.dispose()
