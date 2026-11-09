"""Modelos de entrada y salida de la API."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DependencyHealth(BaseModel):
    """Estado de una dependencia externa."""

    status: Literal["ok", "error"]
    detail: str | None = Field(
        default=None,
        description="Versión del servicio si responde, o el motivo del fallo si no.",
    )


class HealthResponse(BaseModel):
    """Respuesta de `GET /health`."""

    status: Literal["ok", "degraded"]
    dependencies: dict[str, DependencyHealth]


class DocumentAccepted(BaseModel):
    """Resultado de una subida."""

    document_id: UUID
    status: str
    duplicate: bool = False


class DocumentView(BaseModel):
    """Metadatos visibles de un documento."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: str | None
    filename: str
    mime_type: str
    status: str
    page_count: int | None
    chunk_count: int | None
    error: str | None
    diagnostic: str | None
    created_at: datetime
    updated_at: datetime


class DocumentList(BaseModel):
    """Página de documentos."""

    items: list[DocumentView]
    next_cursor: str | None
