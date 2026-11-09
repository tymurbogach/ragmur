"""Configuración del servicio, leída del entorno al arrancar."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Valores de configuración validados.

    `database_url` no tiene valor por defecto a propósito: sin base de datos el
    servicio no puede hacer nada, y es preferible que falle al arrancar y lo diga a
    que arranque apuntando a un sitio equivocado.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    api_key_hmac_secret: SecretStr = Field(min_length=1)
    qdrant_url: str = "http://localhost:6333"

    # Un chequeo de salud que tarda más que esto es un fallo a efectos prácticos:
    # quien lo consulta (un balanceador, un orquestador) no va a esperar más.
    health_timeout_seconds: float = Field(default=5.0, gt=0, allow_inf_nan=False)

    storage_dir: Path = Path("./storage")
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    multipart_overhead_bytes: int = Field(default=65536, gt=0)
    max_extracted_chars: int = Field(default=5_000_000, gt=0)
    max_docx_expanded_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    max_pdf_pages: int = Field(default=500, gt=0)
    pdf_min_chars_per_page: int = Field(default=10, gt=0)
    extraction_timeout_seconds: float = Field(default=120, gt=0, allow_inf_nan=False)
    ingestion_max_jobs: int = Field(default=8, gt=0)
    ingestion_max_active: int = Field(default=2, gt=0)
    orphan_min_age_seconds: int = Field(default=3600, gt=0)
    document_list_max_limit: int = Field(default=100, gt=0)
    chunk_size: int = Field(default=800, gt=0)
    chunk_overlap: int = Field(default=120, ge=0)

    log_level: str = "INFO"

    @model_validator(mode="after")
    def validate_chunk_overlap(self) -> "Settings":
        """Comprueba que el solape permita avanzar."""
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


@lru_cache
def get_settings() -> Settings:
    """Instancia única por proceso.

    `lru_cache` sin argumentos hace que la primera llamada construya el objeto y las
    siguientes devuelvan el mismo, de modo que el fichero `.env` se lee una vez.
    """
    return Settings()
