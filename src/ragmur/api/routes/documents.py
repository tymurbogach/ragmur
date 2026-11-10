"""Operaciones HTTP sobre originales del tenant autenticado."""

import asyncio
import base64
import binascii
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from sqlalchemy import delete, select, true, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.elements import ColumnElement

from ragmur.api.deps import CurrentTenant, ResourcesDep
from ragmur.api.schemas import DocumentAccepted, DocumentList, DocumentView
from ragmur.core.config import get_settings
from ragmur.db.models import Document
from ragmur.ingestion.storage import UploadTooLargeError, store_original

router = APIRouter(prefix="/v1/documents", tags=["documents"])
MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


def owner_filter(owner_id: str | None) -> ColumnElement[bool]:
    """Filtra el usuario solicitado cuando está presente."""
    if owner_id is None:
        return true()
    if not owner_id.strip():
        raise HTTPException(422, detail="Invalid owner_id")
    return Document.owner_id == owner_id


@router.post("", response_model=DocumentAccepted, status_code=202)
async def upload(
    response: Response,
    background: BackgroundTasks,
    request: Request,
    tenant_id: CurrentTenant,
    resources: ResourcesDep,
    file: Annotated[UploadFile, File()],
    owner_id: Annotated[str | None, Form()] = None,
) -> DocumentAccepted:
    """Conserva el original y acepta su extracción."""
    owner_filter(owner_id)
    form = await request.form()
    if set(form.keys()) - {"file", "owner_id"} or len(form.getlist("file")) != 1:
        raise HTTPException(422, detail="Invalid form fields")
    if len(form.getlist("owner_id")) > 1:
        raise HTTPException(422, detail="Invalid form fields")
    supplied_owner = form.get("owner_id")
    if supplied_owner is not None and (
        not isinstance(supplied_owner, str) or not supplied_owner.strip()
    ):
        raise HTTPException(422, detail="Invalid owner_id")
    settings = get_settings()
    name = Path(file.filename or "").name
    mime = MIME_TYPES.get(Path(name).suffix.lower())
    if not name or mime is None:
        raise HTTPException(415, detail="Unsupported file format")
    signature = await file.read(5)
    await file.seek(0)
    if (mime == "application/pdf" and signature != b"%PDF-") or (
        mime.endswith("wordprocessingml.document") and not signature.startswith(b"PK\x03\x04")
    ):
        raise HTTPException(415, detail="Invalid file signature")
    doc_id = uuid.uuid4()
    coordinator = resources.ingestion
    if not coordinator.reserve(doc_id):
        raise HTTPException(
            503, detail="Ingestion capacity exhausted", headers={"Retry-After": "1"}
        )
    kept = False
    path: Path | None = None
    try:
        try:
            saved = await asyncio.to_thread(
                store_original, settings.storage_dir, doc_id, file.file, settings.max_upload_bytes
            )
        except UploadTooLargeError as exc:
            raise HTTPException(413, detail="File too large") from exc
        except OSError as exc:
            raise HTTPException(503, detail="Storage unavailable") from exc
        path = saved.path
        async with resources.sessions() as session:
            doc = Document(
                id=doc_id,
                tenant_id=tenant_id,
                owner_id=owner_id,
                filename=name,
                mime_type=mime,
                content_sha256=saved.sha256,
                storage_path=str(path),
                status="pending",
            )
            session.add(doc)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                existing = await session.scalar(
                    select(Document).where(
                        Document.tenant_id == tenant_id,
                        Document.owner_id == owner_id,
                        Document.content_sha256 == saved.sha256,
                    )
                )
                if existing is None:
                    raise
                if existing.status == "deleting":
                    raise HTTPException(409, detail="Document is being deleted") from None
                response.status_code = 200
                response.headers["Location"] = f"/v1/documents/{existing.id}"
                return DocumentAccepted(
                    document_id=existing.id, status=existing.status, duplicate=True
                )
        kept = True
        background.add_task(coordinator.run, tenant_id, doc_id)
        response.headers["Location"] = f"/v1/documents/{doc_id}"
        return DocumentAccepted(document_id=doc_id, status="pending")
    finally:
        if not kept:
            coordinator.release(doc_id)
            if path is not None:
                try:
                    await asyncio.to_thread(path.unlink, missing_ok=True)
                except OSError:
                    raise HTTPException(503, detail="Storage unavailable") from None


@router.get("", response_model=DocumentList)
async def list_documents(
    tenant_id: CurrentTenant,
    resources: ResourcesDep,
    owner_id: str | None = None,
    limit: Annotated[int | None, Query(ge=1)] = None,
    cursor: str | None = None,
) -> DocumentList:
    """Lista documentos con orden estable y cursor opaco."""
    max_limit = get_settings().document_list_max_limit
    if limit is None:
        limit = min(20, max_limit)
    if limit > max_limit:
        raise HTTPException(422, detail="Invalid limit")
    filters = [Document.tenant_id == tenant_id, owner_filter(owner_id)]
    if cursor:
        try:
            date, identifier = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
            timestamp = datetime.fromisoformat(date)
            if timestamp.tzinfo is None:
                raise ValueError
            filters.append(
                tuple_(Document.created_at, Document.id) > (timestamp, uuid.UUID(identifier))
            )
        except (ValueError, TypeError, binascii.Error, json.JSONDecodeError) as exc:
            raise HTTPException(422, detail="Invalid cursor") from exc
    async with resources.sessions() as session:
        rows = (
            await session.scalars(
                select(Document)
                .where(*filters)
                .order_by(Document.created_at, Document.id)
                .limit(limit + 1)
            )
        ).all()
        more = len(rows) > limit
        page = rows[:limit]
        next_cursor = None
        if more:
            next_cursor = base64.urlsafe_b64encode(
                json.dumps([page[-1].created_at.isoformat(), str(page[-1].id)]).encode()
            ).decode()
        return DocumentList(
            items=[DocumentView.model_validate(row) for row in page], next_cursor=next_cursor
        )


@router.get("/{document_id}", response_model=DocumentView)
async def document_detail(
    document_id: uuid.UUID,
    tenant_id: CurrentTenant,
    resources: ResourcesDep,
    owner_id: str | None = None,
) -> DocumentView:
    """Devuelve metadatos dentro del espacio autorizado."""
    async with resources.sessions() as session:
        doc = await session.scalar(
            select(Document).where(
                Document.id == document_id, Document.tenant_id == tenant_id, owner_filter(owner_id)
            )
        )
        if doc is None:
            raise HTTPException(404, detail="Document not found")
        return DocumentView.model_validate(doc)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    tenant_id: CurrentTenant,
    resources: ResourcesDep,
    owner_id: str | None = None,
) -> Response:
    """Borra el original y después la fila, con reintentos."""
    async with resources.sessions() as session:
        doc = await session.scalar(
            select(Document)
            .where(
                Document.id == document_id, Document.tenant_id == tenant_id, owner_filter(owner_id)
            )
            .with_for_update()
        )
        if doc is None:
            raise HTTPException(404, detail="Document not found")
        if document_id in resources.ingestion.accepted:
            raise HTTPException(409, detail="Document is processing")
        from ragmur.ingestion.storage import InvalidDocumentPathError, resolve_document_path

        root = get_settings().storage_dir.resolve()
        try:
            path = resolve_document_path(root, doc.id, doc.storage_path)
        except InvalidDocumentPathError as exc:
            raise HTTPException(503, detail="Storage unavailable") from exc
        doc.status = "deleting"
        await session.commit()
        try:
            if resources.ingestion.indexer is not None:
                await resources.ingestion.indexer.cleanup(tenant_id, document_id)
            await asyncio.to_thread(path.unlink, missing_ok=True)
        except Exception as exc:
            raise HTTPException(503, detail="Storage unavailable") from exc
        await session.execute(
            delete(Document).where(Document.id == doc.id, Document.tenant_id == tenant_id)
        )
        await session.commit()
    return Response(status_code=204)
