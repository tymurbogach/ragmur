"""Coordinación de extracción y recuperación tras un reinicio."""

import asyncio
import logging
import time
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ragmur.core.config import Settings
from ragmur.db.models import Document
from ragmur.ingestion.extractors.core import ExtractionResult, Fragment
from ragmur.ingestion.extractors.runner import extract_in_process
from ragmur.ingestion.indexer import IncompleteCleanupError, Indexer

logger = logging.getLogger(__name__)


class IngestionCoordinator:
    """Limita trabajos aceptados y activos en una instancia."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        settings: Settings,
        indexer: Indexer | None = None,
    ) -> None:
        self.sessions = sessions
        self.settings = settings
        self.indexer = indexer
        self.accepted: set[UUID] = set()
        self.semaphore = asyncio.Semaphore(settings.ingestion_max_active)

    def reserve(self, document_id: UUID) -> bool:
        """Reserva capacidad antes de aceptar una subida."""
        if len(self.accepted) >= self.settings.ingestion_max_jobs:
            return False
        self.accepted.add(document_id)
        return True

    def release(self, document_id: UUID) -> None:
        """Libera una reserva tras finalizar o fallar."""
        self.accepted.discard(document_id)

    async def run(self, tenant_id: UUID, document_id: UUID) -> None:
        """Extrae un documento con una sesión propia."""
        try:
            async with self.semaphore, self.sessions() as session:
                doc = await session.scalar(
                    select(Document).where(
                        Document.id == document_id, Document.tenant_id == tenant_id
                    )
                )
                if doc is None or doc.status != "pending":
                    return
                doc.status = "processing"
                await session.commit()
                try:
                    result = await extract_in_process(
                        Path(doc.storage_path),
                        doc.mime_type,
                        max_chars=self.settings.max_extracted_chars,
                        max_pages=self.settings.max_pdf_pages,
                        min_chars=self.settings.pdf_min_chars_per_page,
                        max_expanded_bytes=self.settings.max_docx_expanded_bytes,
                        deadline_seconds=self.settings.extraction_timeout_seconds,
                    )
                    if result.get("status") == "ok":
                        extracted = result["result"]
                        doc.page_count = extracted["page_count"]
                        doc.diagnostic = "; ".join(extracted["warnings"]) or None
                        doc.error = None
                        if self.indexer is None:
                            doc.status = "extracted"
                        else:
                            extraction = ExtractionResult(
                                fragments=[
                                    Fragment(text=part["text"], locator=part["locator"])
                                    for part in extracted["fragments"]
                                ],
                                page_count=extracted["page_count"],
                                warnings=extracted["warnings"],
                            )
                            doc.chunk_count = await self.indexer.index(
                                tenant_id, document_id, doc.owner_id, doc.filename, extraction
                            )
                            doc.status = "indexed"
                    elif result.get("status") == "unsupported":
                        doc.status = "unsupported"
                        doc.error = result.get("error", "Contenido no admitido")
                    else:
                        doc.status = "failed"
                        doc.error = result.get("error", "Error de extracción")
                except IncompleteCleanupError:
                    logger.warning(
                        "limpieza de puntos pendiente", extra={"document_id": str(document_id)}
                    )
                    doc.status = "processing"
                    doc.error = "No se pudo completar la limpieza del índice"
                except Exception:
                    logger.warning("fallo de extracción", extra={"document_id": str(document_id)})
                    doc.status = "failed"
                    doc.error = "No se pudo completar la extracción"
                await session.commit()
        except Exception:
            logger.warning(
                "trabajo de ingesta interrumpido", extra={"document_id": str(document_id)}
            )
            if self.indexer is not None:
                try:
                    await self.indexer.cleanup(tenant_id, document_id)
                except Exception:
                    logger.warning("limpieza de puntos pendiente")
                    return
            try:
                async with self.sessions() as session:
                    await session.execute(
                        update(Document)
                        .where(
                            Document.id == document_id,
                            Document.tenant_id == tenant_id,
                            Document.status.in_(("pending", "processing")),
                        )
                        .values(status="failed", error="No se pudo completar la extracción")
                    )
                    await session.commit()
            except Exception:
                logger.warning("no se pudo registrar el fallo de ingesta")
        finally:
            self.release(document_id)

    async def reconcile(self) -> None:
        """Marca trabajos interrumpidos y termina borrados antes de servir tráfico."""
        root = self.settings.storage_dir.resolve()
        await asyncio.to_thread(root.mkdir, parents=True, exist_ok=True)
        async with self.sessions() as session:
            interrupted = (
                await session.scalars(
                    select(Document).where(Document.status.in_(("pending", "processing")))
                )
            ).all()
            for document in interrupted:
                if self.indexer is not None:
                    await self.indexer.cleanup(document.tenant_id, document.id)
                document.status = "failed"
                document.error = "La ingesta se interrumpió durante el reinicio"
            deleting = (
                await session.scalars(select(Document).where(Document.status == "deleting"))
            ).all()
            for document in deleting:
                if self.indexer is not None:
                    await self.indexer.cleanup(document.tenant_id, document.id)
                path = Path(document.storage_path)
                if path.parent != root or path.name != str(document.id):
                    raise RuntimeError("Ruta de documento inválida")
                await asyncio.to_thread(path.unlink, missing_ok=True)
                await session.execute(delete(Document).where(Document.id == document.id))
            await session.commit()
            referenced = set((await session.scalars(select(Document.storage_path))).all())
        now = time.time()
        for entry in await asyncio.to_thread(lambda: list(root.iterdir())):
            try:
                generated_name = str(UUID(entry.name)) == entry.name
            except ValueError:
                generated_name = entry.name.startswith(".upload-")
            if (
                generated_name
                and str(entry) not in referenced
                and not entry.is_symlink()
                and entry.is_file()
                and now - entry.stat().st_mtime >= self.settings.orphan_min_age_seconds
            ):
                await asyncio.to_thread(entry.unlink, missing_ok=True)
