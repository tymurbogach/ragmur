"""Límite por clave con 429 y `Retry-After`."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from ragmur.api.deps import CurrentTenant
from ragmur.auth.service import create_tenant, issue_key
from ragmur.core.config import get_settings
from ragmur.db.models import Tenant
from ragmur.db.session import create_engine, create_session_factory
from ragmur.main import create_app


@pytest.fixture
async def rate_setup(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[tuple[FastAPI, str, str]]:
    monkeypatch.setattr("ragmur.ingestion.pipeline.IngestionCoordinator.reconcile", AsyncMock())
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "2")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    ids: list[UUID] = []
    try:
        async with factory() as session:
            tenant = await create_tenant(session, "rate-test")
            ids = [tenant.id]
            secret = settings.api_key_hmac_secret.get_secret_value()
            first = await issue_key(session, tenant.id, None, secret)
            second = await issue_key(session, tenant.id, None, secret)
        app = create_app()

        @app.get("/protected")
        async def protected(tenant_id: CurrentTenant) -> dict[str, str]:
            return {"tenant_id": str(tenant_id)}

        yield app, first, second
    finally:
        async with factory() as session:
            await session.execute(delete(Tenant).where(Tenant.id.in_(ids)))
            await session.commit()
        await engine.dispose()


async def test_rate_limit_returns_429_with_retry_after(
    rate_setup: tuple[FastAPI, str, str],
) -> None:
    app, first, second = rate_setup
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        assert (await client.get("/protected", headers={"X-API-Key": first})).status_code == 200
        assert (await client.get("/protected", headers={"X-API-Key": first})).status_code == 200
        limited = await client.get("/protected", headers={"X-API-Key": first})
        assert limited.status_code == 429
        assert limited.headers.get("Retry-After") is not None
        assert (await client.get("/protected", headers={"X-API-Key": second})).status_code == 200
