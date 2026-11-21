"""Único punto de acceso a Qdrant.

Ningún otro módulo importa `qdrant_client`. La razón es que una consulta que olvide
filtrar por `tenant_id` devuelve datos de otro cliente sin dar ningún error, así que
el filtro no puede quedar repartido por el código: se aplica aquí y solo aquí.

De ahí la regla de que toda función pública reciba `tenant_id` como primer argumento
obligatorio. Las dos de este fichero son la excepción: abrir la conexión y comprobar
que el servidor responde no leen ni escriben puntos de ninguna colección, así que no
hay espacio de tenant que aislar. Cualquier función que sí toque datos la cumple.
"""

import asyncio
import math
import re
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from qdrant_client import AsyncQdrantClient, models

# El tipo se reexporta a propósito: quien necesite anotar un cliente de Qdrant lo
# importa de aquí y no de `qdrant_client`, de modo que la regla «solo este módulo
# importa la biblioteca» siga siendo cierta sin excepciones y comprobable con un
# simple test de imports.
__all__ = [
    "AsyncQdrantClient",
    "BranchPoint",
    "HybridPoint",
    "StoredPoint",
    "VectorPoint",
    "branch_search",
    "count_document_points",
    "create_client",
    "delete_document_points",
    "delete_tenant_points",
    "ensure_collection",
    "hybrid_search",
    "list_document_point_ids",
    "ping",
    "retrieve_points",
    "set_reindex_metadata",
    "upsert_points",
]


# Página del scroll de Qdrant; sin relación con `owner_id` ni con BM25.
SCROLL_PAGE_SIZE = 256


def create_client(url: str, timeout_seconds: float) -> AsyncQdrantClient:
    """Abre el cliente asíncrono contra el Qdrant configurado."""
    return AsyncQdrantClient(url=url, timeout=math.ceil(timeout_seconds))


async def ping(client: AsyncQdrantClient) -> str:
    """Comprueba que el servidor responde y devuelve su versión.

    Lanza la excepción del cliente si no hay servidor al otro lado; quien llama
    decide qué hacer con ella.
    """
    info = await client.info()
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", info.version)
    if not match or tuple(map(int, match.groups())) < (1, 19, 0):
        raise RuntimeError("Qdrant server does not support scoped IDF")
    if "idf" not in models.SearchParams.model_fields:
        raise RuntimeError("Qdrant client does not support scoped IDF")
    return info.version


@dataclass(frozen=True, slots=True)
class VectorPoint:
    """Fragmento y vectores que se escriben en Qdrant."""

    id: UUID
    document_id: UUID
    owner_id: str | None
    filename: str
    text: str
    ordinal: int
    start: int
    end: int
    locator: dict[str, str | int | list[str]]
    dense: list[float]
    sparse_indices: list[int]
    sparse_values: list[float]


def _require_completed(result: models.UpdateResult) -> None:
    if result.status != models.UpdateStatus.COMPLETED:
        raise RuntimeError("Qdrant did not confirm completion of the operation")


def _tenant_filter(
    tenant_id: UUID, *, document_id: UUID | None = None, owner_id: str | None = None
) -> models.Filter:
    conditions = [
        models.FieldCondition(key="tenant_id", match=models.MatchValue(value=str(tenant_id)))
    ]
    if document_id is not None:
        conditions.append(
            models.FieldCondition(
                key="document_id", match=models.MatchValue(value=str(document_id))
            )
        )
    if owner_id is not None:
        conditions.append(
            models.FieldCondition(key="owner_id", match=models.MatchValue(value=owner_id))
        )
    return models.Filter(must=conditions)


async def count_document_points(
    tenant_id: UUID,
    client: AsyncQdrantClient,
    collection: str,
    document_id: UUID,
    owner_id: str | None = None,
) -> int:
    """Cuenta puntos de un documento dentro del espacio autorizado."""
    result = await client.count(
        collection_name=collection,
        count_filter=_tenant_filter(tenant_id, document_id=document_id, owner_id=owner_id),
        exact=True,
    )
    return result.count


async def list_document_point_ids(
    tenant_id: UUID,
    client: AsyncQdrantClient,
    collection: str,
    document_id: UUID,
    owner_id: str | None = None,
) -> set[UUID]:
    """Devuelve identificadores del documento dentro del espacio autorizado."""
    result: set[UUID] = set()
    offset: int | str | UUID | None = None
    while True:
        points, next_offset = await client.scroll(
            collection_name=collection,
            scroll_filter=_tenant_filter(tenant_id, document_id=document_id, owner_id=owner_id),
            limit=SCROLL_PAGE_SIZE,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        result.update(UUID(str(point.id)) for point in points)
        if next_offset is None:
            return result
        if not isinstance(next_offset, (int, str, UUID)):
            raise RuntimeError("Unsupported Qdrant cursor")
        offset = next_offset


async def ensure_collection(
    tenant_id: UUID,
    client: AsyncQdrantClient,
    collection: str,
    dense_size: int,
    metadata: dict[str, object],
) -> None:
    """Prepara la colección compartida y comprueba su configuración."""
    await ping(client)
    if not await client.collection_exists(collection):
        created = await client.create_collection(
            collection_name=collection,
            vectors_config={
                "dense": models.VectorParams(size=dense_size, distance=models.Distance.COSINE)
            },
            sparse_vectors_config={
                "sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)
            },
            metadata=metadata,
        )
        if not created:
            raise RuntimeError("Qdrant did not create the collection")
    info = await client.get_collection(collection)
    if info.config.metadata != metadata:
        raise RuntimeError("Qdrant collection metadata does not match the configured models")
    vectors = info.config.params.vectors
    sparse = info.config.params.sparse_vectors
    if not isinstance(vectors, dict) or "dense" not in vectors:
        raise RuntimeError("Qdrant collection has no named dense vector")
    dense = vectors["dense"]
    if dense.size != dense_size or dense.distance != models.Distance.COSINE:
        raise RuntimeError("Qdrant dense vector configuration is incompatible")
    if sparse is None or "sparse" not in sparse or sparse["sparse"].modifier != models.Modifier.IDF:
        raise RuntimeError("Qdrant sparse vector requires IDF")
    for field_name in ("tenant_id", "owner_id", "document_id"):
        result = await client.create_payload_index(
            collection_name=collection,
            field_name=field_name,
            field_schema=models.KeywordIndexParams(
                type=models.KeywordIndexType.KEYWORD, is_tenant=(field_name == "tenant_id")
            ),
            wait=True,
        )
        _require_completed(result)
    # Relee la colección tras crear los índices para comprobar su estado real.
    indexes = (await client.get_collection(collection)).payload_schema
    for field_name in ("tenant_id", "owner_id", "document_id"):
        index = indexes.get(field_name)
        if index is None or index.data_type != models.PayloadSchemaType.KEYWORD:
            raise RuntimeError(f"Missing Qdrant keyword index: {field_name}")
        if field_name == "tenant_id" and (
            not isinstance(index.params, models.KeywordIndexParams)
            or index.params.is_tenant is not True
        ):
            raise RuntimeError("Qdrant tenant index does not enable tenant optimization")


async def upsert_points(
    tenant_id: UUID, client: AsyncQdrantClient, collection: str, points: list[VectorPoint]
) -> None:
    """Escribe vectores y fija el tenant desde el argumento autorizado."""
    if not points:
        return
    batch_document = points[0]
    if any(
        point.document_id != batch_document.document_id or point.owner_id != batch_document.owner_id
        for point in points
    ):
        raise ValueError("All points in a batch must belong to the same document and owner")
    if len({point.id for point in points}) != len(points):
        raise ValueError("Point IDs must be unique within a batch")
    records = [
        models.PointStruct(
            id=point.id,
            vector={
                "dense": point.dense,
                "sparse": models.SparseVector(
                    indices=point.sparse_indices, values=point.sparse_values
                ),
            },
            payload={
                "tenant_id": str(tenant_id),
                "document_id": str(point.document_id),
                "owner_id": point.owner_id,
                "filename": point.filename,
                "text": point.text,
                "ordinal": point.ordinal,
                "start": point.start,
                "end": point.end,
                "locator": point.locator,
            },
        )
        for point in points
    ]
    condition = _tenant_filter(tenant_id, document_id=batch_document.document_id)
    assert isinstance(condition.must, list)
    if batch_document.owner_id is None:
        condition.must.append(models.IsNullCondition(is_null=models.PayloadField(key="owner_id")))
    else:
        condition.must.append(
            models.FieldCondition(
                key="owner_id", match=models.MatchValue(value=batch_document.owner_id)
            )
        )
    update_result = await client.upsert(
        collection_name=collection,
        points=records,
        update_filter=condition,
        wait=True,
        ordering=models.WriteOrdering.STRONG,
    )
    _require_completed(update_result)
    condition.must.append(models.HasIdCondition(has_id=[point.id for point in points]))
    verified = await client.count(collection_name=collection, count_filter=condition, exact=True)
    if verified.count != len(points):
        raise RuntimeError(
            "One or more vector points could not be written to their authorized space"
        )


async def delete_document_points(
    tenant_id: UUID,
    client: AsyncQdrantClient,
    collection: str,
    document_id: UUID,
    owner_id: str | None = None,
) -> None:
    """Borra solo los puntos del documento y tenant indicados."""
    if not await client.collection_exists(collection):
        return
    result = await client.delete(
        collection_name=collection,
        points_selector=_tenant_filter(tenant_id, document_id=document_id, owner_id=owner_id),
        wait=True,
        ordering=models.WriteOrdering.STRONG,
    )
    _require_completed(result)


async def delete_tenant_points(tenant_id: UUID, client: AsyncQdrantClient, collection: str) -> None:
    """Elimina los puntos de un tenant durante mantenimiento."""
    if await client.collection_exists(collection):
        result = await client.delete(
            collection_name=collection,
            points_selector=_tenant_filter(tenant_id),
            wait=True,
            ordering=models.WriteOrdering.STRONG,
        )
        _require_completed(result)


async def set_reindex_metadata(
    tenant_id: UUID,
    client: AsyncQdrantClient,
    collection: str,
    dense_size: int,
    metadata: dict[str, object],
) -> None:
    """Actualiza metadatos solo durante un reindexado completo con la API detenida."""
    if await client.collection_exists(collection):
        updated = await client.update_collection(collection_name=collection, metadata=metadata)
        if not updated:
            raise RuntimeError("Qdrant did not update the collection metadata")
    await ensure_collection(tenant_id, client, collection, dense_size, metadata)


@dataclass(frozen=True, slots=True)
class HybridPoint:
    """Resultado de RRF con rangos diagnósticos por rama."""

    id: UUID
    payload: dict[str, Any]
    score: float
    dense_rank: int | None
    sparse_rank: int | None
    sparse_score: float | None


@dataclass(frozen=True, slots=True)
class BranchPoint:
    """Resultado de una rama, usado para evaluación independiente."""

    id: UUID
    payload: dict[str, Any]
    score: float


@dataclass(frozen=True, slots=True)
class StoredPoint:
    """Punto recuperado por identificador para verificación."""

    id: UUID
    payload: dict[str, Any]


def _result_filter(
    tenant_id: UUID, owner_id: str | None, document_ids: list[UUID] | None
) -> models.Filter:
    result = _tenant_filter(tenant_id, owner_id=owner_id)
    assert isinstance(result.must, list)
    if document_ids is not None:
        result.must.append(
            models.FieldCondition(
                key="document_id", match=models.MatchAny(any=[str(value) for value in document_ids])
            )
        )
    return result


def _checked_payload(
    point: models.ScoredPoint,
    tenant_id: UUID,
    owner_id: str | None,
    document_ids: list[UUID] | None,
) -> dict[str, Any]:
    payload = point.payload or {}
    if payload.get("tenant_id") != str(tenant_id):
        raise RuntimeError("Qdrant returned a point outside the authorized tenant")
    if owner_id is not None and payload.get("owner_id") != owner_id:
        raise RuntimeError("Qdrant returned a point outside the authorized owner")
    if document_ids is not None and payload.get("document_id") not in {
        str(value) for value in document_ids
    }:
        raise RuntimeError("Qdrant returned a point outside the document filter")
    return payload


def _require_document_ids(document_ids: list[UUID] | None) -> None:
    """Rechaza la lista vacía: no restringir no equivale a buscar en todo."""
    if document_ids is not None and not document_ids:
        raise ValueError("Invalid search parameters")


def _sparse_vector(indices: list[int], values: list[float]) -> models.SparseVector:
    """Construye el vector disperso de consulta con un solo formato."""
    return models.SparseVector(indices=indices, values=values)


def _idf_search_params(corpus: models.Filter) -> models.SearchParams:
    """Envuelve el filtro autorizado como corpus de estadísticas IDF."""
    return models.SearchParams(idf=models.IdfCorpusParams(corpus=corpus))


async def branch_search(
    tenant_id: UUID,
    client: AsyncQdrantClient,
    collection: str,
    *,
    branch: Literal["dense", "sparse"],
    dense: list[float],
    sparse_indices: list[int],
    sparse_values: list[float],
    owner_id: str | None,
    document_ids: list[UUID] | None,
    limit: int,
) -> list[BranchPoint]:
    """Consulta una rama con los mismos filtros que la búsqueda híbrida."""
    if branch not in ("dense", "sparse") or limit < 1:
        raise ValueError("Invalid search parameters")
    _require_document_ids(document_ids)
    if not await client.collection_exists(collection) or (
        branch == "sparse" and not sparse_indices
    ):
        return []
    query: list[float] | models.SparseVector = dense
    params = None
    if branch == "sparse":
        query = _sparse_vector(sparse_indices, sparse_values)
        params = _idf_search_params(_tenant_filter(tenant_id, owner_id=owner_id))
    response = await client.query_points(
        collection_name=collection,
        query=query,
        using=branch,
        query_filter=_result_filter(tenant_id, owner_id, document_ids),
        search_params=params,
        limit=limit,
        with_payload=True,
    )
    return [
        BranchPoint(
            id=UUID(str(point.id)),
            score=point.score,
            payload=_checked_payload(point, tenant_id, owner_id, document_ids),
        )
        for point in response.points
    ]


async def hybrid_search(
    tenant_id: UUID,
    client: AsyncQdrantClient,
    collection: str,
    dense: list[float],
    sparse_indices: list[int],
    sparse_values: list[float],
    *,
    owner_id: str | None,
    document_ids: list[UUID] | None,
    candidates: int,
    rrf_k: int,
) -> list[HybridPoint]:
    """Fusiona las ramas con filtros de autorización y corpus IDF acotado."""
    if candidates < 1 or rrf_k < 1:
        raise ValueError("Invalid search parameters")
    _require_document_ids(document_ids)
    if not await client.collection_exists(collection):
        return []
    corpus_filter = _tenant_filter(tenant_id, owner_id=owner_id)
    result_filter = _result_filter(tenant_id, owner_id, document_ids)
    sparse_query = _sparse_vector(sparse_indices, sparse_values)
    sparse_params = _idf_search_params(corpus_filter)
    prefetch = [models.Prefetch(query=dense, using="dense", filter=result_filter, limit=candidates)]
    if sparse_indices:
        prefetch.append(
            models.Prefetch(
                query=sparse_query,
                using="sparse",
                filter=result_filter,
                params=sparse_params,
                limit=candidates,
            )
        )

    async def dense_branch() -> list[models.ScoredPoint]:
        response = await client.query_points(
            collection_name=collection,
            query=dense,
            using="dense",
            query_filter=result_filter,
            limit=candidates,
            with_payload=False,
        )
        return response.points

    async def sparse_branch() -> list[models.ScoredPoint]:
        if not sparse_indices:
            return []
        response = await client.query_points(
            collection_name=collection,
            query=sparse_query,
            using="sparse",
            query_filter=result_filter,
            search_params=sparse_params,
            limit=candidates,
            with_payload=False,
        )
        return response.points

    async def fused_branch() -> list[models.ScoredPoint]:
        response = await client.query_points(
            collection_name=collection,
            prefetch=prefetch,
            query=models.RrfQuery(rrf=models.Rrf(k=rrf_k)),
            query_filter=result_filter,
            limit=candidates,
            with_payload=True,
        )
        return response.points

    dense_points, sparse_points, fused_points = await asyncio.gather(
        dense_branch(), sparse_branch(), fused_branch()
    )
    dense_ranks = {str(point.id): index for index, point in enumerate(dense_points, 1)}
    sparse_ranks = {str(point.id): index for index, point in enumerate(sparse_points, 1)}
    sparse_scores = {str(point.id): point.score for point in sparse_points}
    output = []
    for point in fused_points:
        payload = _checked_payload(point, tenant_id, owner_id, document_ids)
        output.append(
            HybridPoint(
                id=UUID(str(point.id)),
                payload=payload,
                score=point.score,
                dense_rank=dense_ranks.get(str(point.id)),
                sparse_rank=sparse_ranks.get(str(point.id)),
                sparse_score=sparse_scores.get(str(point.id)),
            )
        )
    return output


async def retrieve_points(
    tenant_id: UUID,
    client: AsyncQdrantClient,
    collection: str,
    chunk_ids: list[UUID],
    owner_id: str | None,
) -> list[StoredPoint]:
    """Recupera puntos por identificador dentro del espacio autorizado.

    Los identificadores fuera del espacio del solicitante se ignoran en lugar de
    puntuarse: así `/verify` no se convierte en un oráculo para sondear
    fragmentos ajenos.
    """
    if not chunk_ids or not await client.collection_exists(collection):
        return []
    records = await client.retrieve(collection_name=collection, ids=chunk_ids, with_payload=True)
    output: list[StoredPoint] = []
    seen: set[UUID] = set()
    for record in records:
        point_id = UUID(str(record.id))
        if point_id in seen:
            continue
        seen.add(point_id)
        payload = record.payload or {}
        if payload.get("tenant_id") != str(tenant_id):
            continue
        if owner_id is not None and payload.get("owner_id") != owner_id:
            continue
        output.append(StoredPoint(id=point_id, payload=payload))
    return output
