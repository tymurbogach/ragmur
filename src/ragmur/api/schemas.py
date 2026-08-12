"""Modelos de entrada y salida de la API."""

from typing import Literal

from pydantic import BaseModel, Field


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
