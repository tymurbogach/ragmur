"""Único punto de acceso a Qdrant.

Ningún otro módulo importa `qdrant_client`. La razón es que una consulta que olvide
filtrar por `tenant_id` devuelve datos de otro cliente sin dar ningún error, así que
el filtro no puede quedar repartido por el código: se aplica aquí y solo aquí.

De ahí la regla de que toda función pública reciba `tenant_id` como primer argumento
obligatorio. Las dos de este fichero son la excepción: abrir la conexión y comprobar
que el servidor responde no leen ni escriben puntos de ninguna colección, así que no
hay espacio de tenant que aislar. Cualquier función que sí toque datos la cumple.
"""

import math
import re
from dataclasses import dataclass
from uuid import UUID

from qdrant_client import AsyncQdrantClient, models

# El tipo se reexporta a propósito: quien necesite anotar un cliente de Qdrant lo
# importa de aquí y no de `qdrant_client`, de modo que la regla «solo este módulo
# importa la biblioteca» siga siendo cierta sin excepciones y comprobable con un
# simple test de imports.
__all__ = [
    "AsyncQdrantClient",
    "VectorPoint",
    "count_document_points",
    "create_client",
    "delete_document_points",
    "delete_tenant_points",
    "ensure_collection",
    "list_document_point_ids",
    "ping",
    "set_reindex_metadata",
    "upsert_points",
]


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
    tenant_id: UUID, document_id: UUID | None = None, owner_id: str | None = None
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
        count_filter=_tenant_filter(tenant_id, document_id, owner_id),
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
            scroll_filter=_tenant_filter(tenant_id, document_id, owner_id),
            limit=256,
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
    first = points[0]
    if any(
        point.document_id != first.document_id or point.owner_id != first.owner_id
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
    condition = _tenant_filter(tenant_id, first.document_id)
    assert isinstance(condition.must, list)
    if first.owner_id is None:
        condition.must.append(models.IsNullCondition(is_null=models.PayloadField(key="owner_id")))
    else:
        condition.must.append(
            models.FieldCondition(key="owner_id", match=models.MatchValue(value=first.owner_id))
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
        points_selector=_tenant_filter(tenant_id, document_id, owner_id),
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
