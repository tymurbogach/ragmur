"""Medición opcional y reproducible de /search con modelos reales en CPU."""

import asyncio
import logging
import math
import os
import platform
import resource
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ragmur.auth.service import create_tenant, issue_key
from ragmur.core.config import get_settings
from ragmur.db.models import Base, Document
from ragmur.ingestion.extractors.core import ExtractionResult, Fragment
from ragmur.retrieval.models import load_models


@pytest.mark.skipif(os.environ.get("RAGMUR_REAL_MODEL_TESTS") != "1", reason="Requires real models")
async def test_search_p95_with_real_cpu_models(
    isolated_qdrant: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = make_url(get_settings().database_url)
    database = "test_" + uuid4().hex
    admin = create_async_engine(original, isolation_level="AUTOCOMMIT")
    async with admin.connect() as connection:
        await connection.execute(text(f'CREATE DATABASE "{database}"'))
    url = original.set(database=database).render_as_string(hide_password=False)
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        monkeypatch.setenv("DATABASE_URL", url)
        monkeypatch.setenv("QDRANT_URL", isolated_qdrant)
        monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
        monkeypatch.setenv("QDRANT_COLLECTION", "benchmark_test")
        monkeypatch.setenv("EMBEDDING_DEVICE", "cpu")
        get_settings.cache_clear()
        monkeypatch.setattr("ragmur.main.load_models", load_models)
        from ragmur.main import create_app
        from ragmur.retrieval import store

        probe = store.create_client(isolated_qdrant, 5)
        try:
            for attempt in range(50):
                try:
                    await store.ping(probe)
                    break
                except Exception:
                    if attempt == 49:
                        raise
                    await asyncio.sleep(0.1)
        finally:
            await probe.close()
        app = create_app()
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("ragmur.api.routes.search").setLevel(logging.WARNING)
        async with (
            app.router.lifespan_context(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
        ):
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                tenant_a = await create_tenant(session, "benchmark-a")
                tenant_b = await create_tenant(session, "benchmark-b")
                key = await issue_key(
                    session,
                    tenant_a.id,
                    None,
                    get_settings().api_key_hmac_secret.get_secret_value(),
                )
            indexer = app.state.resources.ingestion.indexer
            assert indexer is not None
            for index in range(32):
                tenant_id = tenant_a.id if index < 31 else tenant_b.id
                owner = "alice" if index < 30 else "bob"
                document_id = uuid4()
                body = (
                    f"Documento sintético {index}. "
                    + "El suministro debe seguir las condiciones y plazos del contrato. " * 6
                )
                path = tmp_path / str(document_id)
                path.write_text(body, encoding="utf-8")
                async with factory() as session:
                    session.add(
                        Document(
                            id=document_id,
                            tenant_id=tenant_id,
                            owner_id=owner,
                            filename="sample.txt",
                            mime_type="text/plain",
                            content_sha256=str(document_id),
                            storage_path=str(path),
                            status="processing",
                        )
                    )
                    await session.commit()
                source = ExtractionResult(
                    [Fragment(body, {"type": "offset", "start": 0, "end": len(body)})]
                )
                count = await indexer.index(tenant_id, document_id, owner, "sample.txt", source)
                async with factory() as session:
                    document = await session.get(Document, document_id)
                    assert document is not None
                    document.status = "indexed"
                    document.chunk_count = count
                    await session.commit()
            headers = {"X-API-Key": key}
            query = {
                "query": "¿Cuáles son las condiciones de suministro?",
                "owner_id": "alice",
                "top_k": 5,
                "candidates": 30,
                "rerank": True,
            }
            for _ in range(2):
                response = await client.post("/v1/search", headers=headers, json=query)
                assert response.status_code == 200 and len(response.json()["results"]) == 5
            durations = []
            for _ in range(20):
                start = time.perf_counter()
                response = await client.post("/v1/search", headers=headers, json=query)
                durations.append((time.perf_counter() - start) * 1000)
                assert response.status_code == 200 and len(response.json()["results"]) == 5
                assert all(item["score_type"] == "reranker" for item in response.json()["results"])
            p95 = sorted(durations)[math.ceil(0.95 * len(durations)) - 1]
            cpu_info = await asyncio.to_thread(Path("/proc/cpuinfo").read_text)
            cpu_line = next(
                (
                    line.split(":", 1)[1].strip()
                    for line in cpu_info.splitlines()
                    if line.startswith("model name")
                ),
                "unknown",
            )
            peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            sys.stdout.write(
                f"BENCHMARK p95_ms={p95:.2f} cpu={cpu_line} machine={platform.machine()} "
                f"threads={os.environ.get('OMP_NUM_THREADS')} candidates=30 samples=20 "
                f"warmup=2 concurrency=1 peak_rss_mib={peak_mb:.1f}\n"
            )
    finally:
        await engine.dispose()
        async with admin.connect() as connection:
            await connection.execute(text(f'DROP DATABASE "{database}" WITH (FORCE)'))
        await admin.dispose()
