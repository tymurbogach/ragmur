"""Calculo search sobre los preparados (corre en el contenedor ``$P-api``).

Lee ``prepared/search.json`` (seleccion ya congelada en el portatil), crea el
indice en Qdrant con los modelos reales del servicio y puntua las 15.944
preguntas en cuatro etapas (densa, BM25, hibrida RRF y reordenador), mas las
sondas de aislamiento por pregunta. No importa ningun cargador de conjuntos:
solo ``eval.phase1.search_data`` (seleccion pura y metricas) y el servicio.

Se ejecuta con ``PYTHONPATH=/tmp/code/src:/tmp/code`` y el Python del contenedor.
Progresa cada 500 preguntas y acepta ``--resume`` con filas ya puntuadas y
su iso: restaura los contadores y solo sondea el resto. Sin iso en el
parcial (formato anterior), re-sondea lo ya puntuado antes de seguir.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Final
from uuid import uuid4

logger = logging.getLogger(__name__)

ISO_KEYS: Final[tuple[str, ...]] = (
    "tenant_results",
    "tenant_leaks",
    "owner_results",
    "owner_leaks",
    "cross_tenant_reads",
    "cross_tenant_read_leaks",
    "cross_owner_reads",
    "cross_owner_read_leaks",
    "control_read",
)


def zero_iso() -> dict[str, int]:
    """Contadores de aislamiento a cero para un calculo desde cero."""
    return {key: 0 for key in ISO_KEYS}


def extract_resume(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int] | None]:
    """Separa filas e iso de un fichero de reanudacion.

    Devuelve las filas y una copia de los contadores, o ``None`` si el
    parcial no trae iso (formato anterior): entonces hay que re-sondear lo
    ya puntuado, nunca dar por bueno un iso a cero.
    """
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("reanudacion ilegible: sin filas")
    raw_iso = payload.get("iso")
    if not isinstance(raw_iso, dict):
        return list(rows), None
    try:
        iso = {key: int(raw_iso[key]) for key in ISO_KEYS}
    except (KeyError, TypeError, ValueError):
        return list(rows), None
    if any(value < 0 for value in iso.values()):
        return list(rows), None
    return list(rows), iso


def build_parser() -> argparse.ArgumentParser:
    """Define la linea de ordenes del calculo."""
    parser = argparse.ArgumentParser(prog="python -m eval.phase1.search_compute")
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--log", type=Path, default=None)
    parser.add_argument("--resume", type=Path, default=None)
    parser.add_argument("--collection", type=str, default="p1search")
    parser.add_argument(
        "--depths",
        type=str,
        default="",
        help="profundidades extra de candidatos (p. ej. 50,100) para medir su cobertura",
    )
    parser.add_argument(
        "--rerank-every",
        type=int,
        default=0,
        help="con --depths, reordena cada n-esima pregunta con cada profundidad extra",
    )
    return parser


def parse_depths(raw: str, limit: int) -> list[int]:
    """Convierte "50,100" en profundidades validas, distintas de 30 y sin pasar del limite."""
    depths: list[int] = []
    for piece in raw.split(","):
        if not piece.strip():
            continue
        depth = int(piece)
        if depth <= 30 or depth > limit:
            raise ValueError(f"profundidad {depth} fuera de (30, {limit}]")
        if depth not in depths:
            depths.append(depth)
    return depths


def rank_of(ids: list[str], wanted: set[str]) -> int | None:
    """Primera posicion (desde 1) de un identificador buscado, si aparece."""
    for position, value in enumerate(ids, 1):
        if value in wanted:
            return position
    return None


async def main(argv: list[str] | None = None) -> int:
    """Crea el indice, puntua las preguntas y escribe filas con rangos."""
    from eval.phase1 import search_data
    from ragmur.core.config import get_settings
    from ragmur.ingestion.chunker import split_document
    from ragmur.ingestion.extractors.core import ExtractionResult, Fragment
    from ragmur.retrieval import store
    from ragmur.retrieval.models import load_models

    args = build_parser().parse_args(argv)
    started_all = time.time()
    logging.basicConfig(
        level=logging.INFO,
        filename=str(args.log) if args.log else None,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    prepared = json.loads(args.prepared.read_text(encoding="utf-8"))
    docs = [search_data.Doc.from_dict(item) for item in prepared["docs"]]
    cases = [search_data.Case.from_dict(item) for item in prepared["cases"]]
    resumed_rows: list[dict[str, Any]] = []
    resumed_iso: dict[str, int] | None = None
    if args.resume is not None and args.resume.is_file():
        resumed_rows, resumed_iso = extract_resume(
            json.loads(args.resume.read_text(encoding="utf-8"))
        )
    scored = {str(row["id"]) for row in resumed_rows}
    pending = [case for case in cases if case.id not in scored]

    settings = get_settings()
    if (settings.chunk_size, settings.chunk_overlap) != (
        search_data.CHUNK_SIZE,
        search_data.CHUNK_OVERLAP,
    ):
        raise ValueError("el troceado del contenedor no es 800/120")
    if settings.search_max_candidates < search_data.CANDIDATES:
        raise ValueError("el contenedor no admite 30 candidatos")
    if settings.rrf_k != search_data.RRF_K:
        raise ValueError(f"rrf_k del contenedor es {settings.rrf_k}, se exige {search_data.RRF_K}")
    logger.warning("search_compute: rrf_k efectivo %s", settings.rrf_k)
    depths = parse_depths(args.depths, settings.search_max_candidates)
    if args.rerank_every < 0:
        raise ValueError("--rerank-every no puede ser negativo")
    index_of = {case.id: position for position, case in enumerate(cases)}
    models = await asyncio.to_thread(load_models, settings)
    if models.reranker is None:
        raise ValueError("el contenedor no trae reordenador")
    logger.warning(
        "search_compute: %d docs, %d preguntas (%d ya puntuadas), dispositivo %s",
        len(docs),
        len(cases),
        len(resumed_rows),
        settings.resolved_device,
    )

    client = store.create_client(settings.qdrant_url, 60)
    try:
        await store.ping(client)
        tenant_main, tenant_decoy = uuid4(), uuid4()
        meta: dict[str, object] = {"model": "p1search"}
        await store.ensure_collection(
            tenant_main, client, args.collection, models.dense.dimension, meta
        )
        doc_id: dict[str, Any] = {}
        doc_owner: dict[str, str] = {}
        by_doc: dict[str, list[Any]] = {}
        for entry in docs:
            point_id = uuid4()
            doc_id[entry.key] = point_id
            owner = search_data.owner_for(entry.key)
            doc_owner[str(point_id)] = owner
            extraction = ExtractionResult(
                [Fragment(entry.text, {"type": "offset", "start": 0, "end": len(entry.text)})]
            )
            chunks = split_document(
                extraction,
                point_id,
                tenant_main,
                owner,
                size=settings.chunk_size,
                overlap=settings.chunk_overlap,
            ).chunks
            by_doc[str(point_id)] = chunks
        n_chunks = sum(len(part) for part in by_doc.values())
        continued = sum(1 for part in by_doc.values() for chunk in part if chunk.start)
        logger.warning("search_compute: fragmentos %d, continuados %d", n_chunks, continued)

        index_started = time.time()
        decoy_chunk: dict[Any, Any] = {}
        decoy_doc: dict[Any, Any] = {}
        mine = {str(chunk.id) for part in by_doc.values() for chunk in part}
        for position, entry in enumerate(docs):
            point_id = doc_id[entry.key]
            chunks = by_doc[str(point_id)]
            texts = [chunk.text for chunk in chunks]
            dense_vectors = models.dense.embed(texts, settings.embedding_batch_size)
            sparse_vectors = models.sparse.embed(texts, settings.embedding_batch_size)
            for tenant in (tenant_main, tenant_decoy):
                points = []
                for chunk, dense, sparse in zip(chunks, dense_vectors, sparse_vectors, strict=True):
                    use_id, use_doc = chunk.id, point_id
                    if tenant == tenant_decoy:
                        use_id = decoy_chunk[chunk.id] = uuid4()
                        use_doc = decoy_doc.setdefault(str(point_id), uuid4())
                    points.append(
                        store.VectorPoint(
                            id=use_id,
                            document_id=use_doc,
                            owner_id=chunk.owner_id,
                            filename="bench.txt",
                            text=chunk.text,
                            ordinal=chunk.ordinal,
                            start=chunk.start,
                            end=chunk.end,
                            locator=chunk.locator,
                            dense=dense,
                            sparse_indices=sparse.indices,
                            sparse_values=sparse.values,
                        )
                    )
                await store.upsert_points(tenant, client, args.collection, points)
            if position % 500 == 0:
                logger.warning("search_compute: indexados %d", position)
        index_s = time.time() - index_started
        logger.warning("search_compute: indice en %.0f s", index_s)

        own_of = {case.id: search_data.owner_for(case.doc) for case in cases}
        case_by_id = {case.id: case for case in cases}
        rows: list[dict[str, Any]] = []
        iso: dict[str, int] = dict(resumed_iso) if resumed_iso is not None else zero_iso()

        async def accumulate_probes(
            own: str,
            chunks: list[Any],
            fused: list[Any],
            other: list[Any],
            control: bool,
        ) -> None:
            """Suma las sondas de un caso al iso restaurado, sin reiniciarlo."""
            iso["tenant_results"] += len(fused)
            iso["tenant_leaks"] += sum(
                1
                for point in fused
                if str(point.id) not in mine or point.payload.get("owner_id") != own
            )
            iso["owner_results"] += len(other)
            iso["owner_leaks"] += sum(
                1
                for point in other
                if str(point.id) not in mine
                or point.payload.get("owner_id") != ("bob" if own == "alice" else "alice")
            )
            sample = [decoy_chunk[chunk.id] for chunk in chunks[:5]]
            iso["cross_tenant_reads"] += 1
            iso["cross_tenant_read_leaks"] += len(
                await store.retrieve_points(tenant_main, client, args.collection, sample, None)
            )
            iso["cross_owner_reads"] += 1
            iso["cross_owner_read_leaks"] += len(
                await store.retrieve_points(
                    tenant_main,
                    client,
                    args.collection,
                    [chunk.id for chunk in chunks[:5]],
                    "bob" if own == "alice" else "alice",
                )
            )
            if control:
                iso["control_read"] = len(
                    await store.retrieve_points(
                        tenant_main,
                        client,
                        args.collection,
                        [chunk.id for chunk in chunks[:5]],
                        None,
                    )
                )

        if resumed_rows and resumed_iso is None:
            logger.warning(
                "search_compute: parcial sin iso, re-sondeando %d casos ya puntuados",
                len(resumed_rows),
            )
            for position, old_row in enumerate(resumed_rows):
                old_case = case_by_id[str(old_row["id"])]
                old_own = own_of[old_case.id]
                old_dense = models.dense.embed([old_case.question], settings.embedding_batch_size)[
                    0
                ]
                old_sparse = models.sparse.query_embed(old_case.question)
                old_chunks = by_doc[str(doc_id[old_case.doc])]
                old_fused = await store.hybrid_search(
                    tenant_main,
                    client,
                    args.collection,
                    old_dense,
                    old_sparse.indices,
                    old_sparse.values,
                    owner_id=old_own,
                    document_ids=None,
                    candidates=search_data.CANDIDATES,
                    rrf_k=settings.rrf_k,
                )
                old_other = await store.hybrid_search(
                    tenant_main,
                    client,
                    args.collection,
                    old_dense,
                    old_sparse.indices,
                    old_sparse.values,
                    owner_id="bob" if old_own == "alice" else "alice",
                    document_ids=None,
                    candidates=search_data.CANDIDATES,
                    rrf_k=settings.rrf_k,
                )
                await accumulate_probes(old_own, old_chunks, old_fused, old_other, position == 0)
        search_started = time.time()
        for number, case in enumerate(pending):
            question_started = time.perf_counter()
            own = own_of[case.id]
            wrong = "bob" if own == "alice" else "alice"
            dense_query = models.dense.embed([case.question], settings.embedding_batch_size)[0]
            sparse_query = models.sparse.query_embed(case.question)
            expected_doc = str(doc_id[case.doc])
            chunks = by_doc[expected_doc]
            good = {
                str(chunk.id)
                for chunk in chunks
                for start, end, _ in case.answers
                if chunk.start <= start and end <= chunk.end
            }
            dense_hits = await store.branch_search(
                tenant_main,
                client,
                args.collection,
                branch="dense",
                dense=dense_query,
                sparse_indices=sparse_query.indices,
                sparse_values=sparse_query.values,
                owner_id=own,
                document_ids=None,
                limit=search_data.CANDIDATES,
            )
            sparse_hits = await store.branch_search(
                tenant_main,
                client,
                args.collection,
                branch="sparse",
                dense=dense_query,
                sparse_indices=sparse_query.indices,
                sparse_values=sparse_query.values,
                owner_id=own,
                document_ids=None,
                limit=search_data.CANDIDATES,
            )
            fused = await store.hybrid_search(
                tenant_main,
                client,
                args.collection,
                dense_query,
                sparse_query.indices,
                sparse_query.values,
                owner_id=own,
                document_ids=None,
                candidates=search_data.CANDIDATES,
                rrf_k=settings.rrf_k,
            )
            ranked = [str(point.id) for point in fused]
            reranked: list[str] = []
            reranked_docs: list[str] = []
            rerank_ms = 0.0
            if fused:
                rerank_started = time.perf_counter()
                scores = models.reranker.score(
                    case.question,
                    [str(point.payload["text"]) for point in fused],
                    settings.reranker_batch_size,
                )
                rerank_ms = round((time.perf_counter() - rerank_started) * 1000, 1)
                ordered = sorted(
                    zip(fused, scores, strict=True), key=lambda pair: pair[1], reverse=True
                )
                top = [point for point, _ in ordered[: search_data.TOP_K]]
                reranked = [str(point.id) for point in top]
                reranked_docs = [str(point.payload["document_id"]) for point in top]
            dense_ids = [str(point.id) for point in dense_hits]
            sparse_ids = [str(point.id) for point in sparse_hits]
            doc_ids = [str(point.payload["document_id"]) for point in fused]
            dense_docs = [str(point.payload["document_id"]) for point in dense_hits]
            sparse_docs = [str(point.payload["document_id"]) for point in sparse_hits]
            row = {
                "id": case.id,
                "src": case.src,
                "covered": bool(good),
                "d_doc": rank_of(dense_docs, {expected_doc}),
                "d_ans": rank_of(dense_ids, good) if good else None,
                "s_doc": rank_of(sparse_docs, {expected_doc}),
                "s_ans": rank_of(sparse_ids, good) if good else None,
                "h_doc": rank_of(doc_ids, {expected_doc}),
                "h_ans": rank_of(ranked, good) if good else None,
                "r_doc": rank_of(reranked_docs, {expected_doc}) if reranked else None,
                "r_ans": rank_of(reranked, good) if good and reranked else None,
                "ms": round((time.perf_counter() - question_started) * 1000, 1),
            }
            sampled = args.rerank_every > 0 and index_of[case.id] % args.rerank_every == 0
            if sampled:
                row["sample"] = True
                row["r30_ms"] = rerank_ms
            for depth in depths:
                wide = await store.hybrid_search(
                    tenant_main,
                    client,
                    args.collection,
                    dense_query,
                    sparse_query.indices,
                    sparse_query.values,
                    owner_id=own,
                    document_ids=None,
                    candidates=depth,
                    rrf_k=settings.rrf_k,
                )
                row[f"h{depth}_doc"] = rank_of(
                    [str(point.payload["document_id"]) for point in wide], {expected_doc}
                )
                if sampled and wide:
                    wide_started = time.perf_counter()
                    wide_scores = models.reranker.score(
                        case.question,
                        [str(point.payload["text"]) for point in wide],
                        settings.reranker_batch_size,
                    )
                    row[f"r{depth}_ms"] = round((time.perf_counter() - wide_started) * 1000, 1)
                    wide_top = [
                        point
                        for point, _ in sorted(
                            zip(wide, wide_scores, strict=True),
                            key=lambda pair: pair[1],
                            reverse=True,
                        )[: search_data.TOP_K]
                    ]
                    row[f"r{depth}_doc"] = rank_of(
                        [str(point.payload["document_id"]) for point in wide_top], {expected_doc}
                    )
                    row[f"r{depth}_ans"] = (
                        rank_of([str(point.id) for point in wide_top], good) if good else None
                    )
            rows.append(row)

            other = await store.hybrid_search(
                tenant_main,
                client,
                args.collection,
                dense_query,
                sparse_query.indices,
                sparse_query.values,
                owner_id=wrong,
                document_ids=None,
                candidates=search_data.CANDIDATES,
                rrf_k=settings.rrf_k,
            )
            await accumulate_probes(
                own, chunks, fused, other, number == 0 and iso["control_read"] < 1
            )
            done = len(resumed_rows) + len(rows)
            if done % search_data.PROGRESS_EVERY == 0 or done == len(cases):
                logger.warning("search_compute: puntuadas %d %s", done, dict(iso))
                write_out(
                    args.out,
                    settings,
                    docs,
                    n_chunks,
                    index_s,
                    time.time() - search_started,
                    iso,
                    resumed_rows + rows,
                )
        search_s = time.time() - search_started
        merged, _overlap = search_data.merge_rows(resumed_rows, rows)
        if _overlap:
            logger.warning("search_compute: %d filas repetidas entre parcial y resto", _overlap)
        positions = {case.id: position for position, case in enumerate(cases)}
        merged.sort(key=lambda row: positions[str(row["id"])])
        write_out(args.out, settings, docs, n_chunks, index_s, search_s, iso, merged)
    finally:
        await client.close()
    (args.out.parent / "search-done").write_text("ok\n", encoding="utf-8")
    sys.stdout.write(f"search_compute: {len(cases)} casos en {time.time() - started_all:.0f} s\n")
    return 0


def write_out(
    path: Path,
    settings: Any,
    docs: list[Any],
    chunks: int,
    index_s: float,
    search_s: float,
    iso: dict[str, int],
    rows: list[dict[str, Any]],
) -> None:
    """Escribe el avance (cada 500) o el resultado final con sus rangos."""
    gpu: str | None = None
    if settings.resolved_device == "cuda":
        import torch

        try:
            gpu = torch.cuda.get_device_name(0)
        except RuntimeError:
            gpu = "cuda sin nombre"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "device": settings.resolved_device,
                "gpu": gpu,
                "models": {
                    "dense": [settings.embedding_model, settings.embedding_revision],
                    "sparse": [settings.bm25_model, settings.bm25_revision],
                    "reranker": [settings.reranker_model, settings.reranker_revision],
                },
                "meta": {
                    "n_docs": len(docs),
                    "chunks": chunks,
                    "index_s": round(index_s, 1),
                    "search_s": round(search_s, 1),
                    "rrf_k": settings.rrf_k,
                },
                "iso": dict(iso),
                "rows": rows,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
