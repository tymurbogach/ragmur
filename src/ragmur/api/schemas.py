"""Modelos de entrada y salida de la API."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class SearchRequest(BaseModel):
    """Consulta de recuperación híbrida."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1)
    candidates: int = Field(default=30, ge=1)
    rerank: bool = True
    owner_id: str | None = None
    document_ids: list[UUID] | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_search(self) -> "SearchRequest":
        """Comprueba las relaciones entre los parámetros de búsqueda."""
        if not self.query.strip():
            raise ValueError("query must not be blank")
        if self.owner_id is not None and not self.owner_id.strip():
            raise ValueError("owner_id must not be blank")
        if self.top_k > self.candidates:
            raise ValueError("top_k must not exceed candidates")
        return self


class SearchHit(BaseModel):
    """Fragmento recuperado con su procedencia."""

    chunk_id: UUID
    document_id: UUID
    filename: str
    locator: dict[str, str | int | list[str]]
    text: str
    score: float
    score_type: Literal["rrf", "reranker"] = "rrf"
    dense_rank: int | None
    sparse_rank: int | None


class SearchResponse(BaseModel):
    """Resultados, configuración de fusión y tiempos en milisegundos."""

    results: list[SearchHit]
    timings_ms: dict[str, float]
    rrf_k: int
    branch_limit: int


class VerifyRequest(BaseModel):
    """Texto redactado y evidencias citadas para verificar."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)
    chunk_ids: list[UUID] = Field(min_length=1)
    owner_id: str | None = None

    @model_validator(mode="after")
    def validate_verify(self) -> "VerifyRequest":
        """Comprueba los límites de la petición de verificación."""
        if not self.answer.strip():
            raise ValueError("answer must not be blank")
        if self.owner_id is not None and not self.owner_id.strip():
            raise ValueError("owner_id must not be blank")
        return self


class VerifyClaim(BaseModel):
    """Veredicto por frase con su evidencia."""

    text: str
    verdict: Literal["supported", "weak", "unsupported", "contradicted"]
    score: float
    best_chunk_id: UUID | None


class VerifySummary(BaseModel):
    """Recuento de veredictos."""

    supported: int = Field(ge=0)
    weak: int = Field(ge=0)
    unsupported: int = Field(ge=0)
    contradicted: int = Field(ge=0)


class VerifyResponse(BaseModel):
    """Frases verificadas y resumen."""

    claims: list[VerifyClaim]
    summary: VerifySummary
