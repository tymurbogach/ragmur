"""Configuración del servicio, leída del entorno al arrancar."""

from functools import cached_property, lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
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
    qdrant_collection: str = Field(default="ragmur_chunks", min_length=1)

    # Un chequeo de salud que tarda más que esto es un fallo a efectos prácticos:
    # quien lo consulta (un balanceador, un orquestador) no va a esperar más.
    health_timeout_seconds: float = Field(default=5.0, gt=0, allow_inf_nan=False)

    storage_dir: Path = Path("./storage")
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    max_json_body_bytes: int = Field(default=65536, gt=0)
    multipart_overhead_bytes: int = Field(default=65536, gt=0)
    upload_max_concurrent: int = Field(default=8, gt=0)
    upload_timeout_seconds: float = Field(default=120, gt=0, allow_inf_nan=False)
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
    embedding_model: str = "BAAI/bge-m3"
    embedding_revision: str = "5617a9f61b028005a4858fdac845db406aefb181"
    embedding_device: Literal["auto", "cpu", "cuda"] = "auto"
    model_cache_dir: Path = Path("./models/huggingface")
    embedding_batch_size: int = Field(default=16, gt=0)
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_revision: str = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
    reranker_batch_size: int = Field(default=8, gt=0)
    index_batch_size: int = Field(default=64, gt=0)
    bm25_model: str = "Qdrant/bm25"
    bm25_revision: str = "22b8d2af71a76161e18dd432d2cee0eefa66e412"
    bm25_language: str = "spanish"
    bm25_disable_stemmer: bool = False
    bm25_k: float = Field(default=1.2, gt=0, allow_inf_nan=False)
    bm25_b: float = Field(default=0.75, ge=0, le=1, allow_inf_nan=False)
    # 256 de BM25 sin relación con owner_id ni con el paginado de scroll.
    bm25_avg_len: float = Field(default=256, gt=0, allow_inf_nan=False)
    search_max_query_chars: int = Field(default=4096, gt=0)
    search_max_candidates: int = Field(default=100, ge=30)
    search_max_document_ids: int = Field(default=100, gt=0)
    rrf_k: int = Field(default=2, gt=0)
    rate_limit_requests: int = Field(default=60, gt=0)
    rate_limit_window_seconds: float = Field(default=60.0, gt=0, allow_inf_nan=False)
    auth_rate_limit_requests: int = Field(default=120, gt=0)
    auth_rate_limit_window_seconds: float = Field(default=60.0, gt=0, allow_inf_nan=False)
    rate_limit_max_keys: int = Field(default=10000, gt=0)
    inference_max_requests: int = Field(default=16, gt=0)
    nli_model: str = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
    nli_revision: str = "b5113eb38ab63efdd7f280f8c144ea8b13f978ce"
    nli_batch_size: int = Field(default=8, gt=0)
    verify_max_answer_chars: int = Field(default=4096, gt=0)
    verify_max_claims: int = Field(default=20, gt=0)
    verify_max_chunks: int = Field(default=20, gt=0)
    verify_max_pairs: int = Field(default=400, gt=0)
    verify_max_windows: int = Field(default=2000, gt=0)
    verify_supported_threshold: float = Field(default=0.9, ge=0, le=1)
    verify_weak_threshold: float = Field(default=0.5, ge=0, le=1)
    verify_contradiction_threshold: float = Field(default=0.75, ge=0, le=1)
    # D7: apoyo que supera su umbral y aventaja a la contradicción en este margen.
    verify_conflict_margin: float = Field(default=0.15, ge=0, le=1)

    # Puerta única al LLM (fase 2, regla 7): ningún valor de proveedor
    # hardcodeado; el modelo y la clave llegan por entorno.
    llm_model: str | None = None
    llm_api_key: SecretStr | None = None
    llm_api_base: str | None = None
    # Cabeceras extra por petición (p. ej. sesión de OpenCode Go).
    # En entorno llega como JSON: LLM_EXTRA_HEADERS='{"X":"y"}'.
    # Los valores pueden ser secretos: nunca se registran ni van en errores.
    # `repr=False` los oculta también de `repr()` y `str()`.
    llm_extra_headers: dict[str, str] = Field(default_factory=dict, repr=False)
    llm_timeout_seconds: float = Field(default=60, gt=0, allow_inf_nan=False)
    llm_max_tokens: int = Field(default=512, gt=0)
    # `le=5` acota el peor caso: 6 intentos de como mucho
    # (`timeout` + 10 s) cada uno (ver `ARCHITECTURE.md`).
    llm_max_retries: int = Field(default=2, ge=0, le=5)

    log_level: str = "INFO"

    @field_validator("llm_model", "llm_api_key", "llm_api_base", mode="before")
    @classmethod
    def empty_llm_string_is_none(cls, value: object) -> object:
        """Convierte `""` en `None` para las opciones del LLM.

        En un fichero de entorno una variable sin valor (`LLM_MODEL=`) llega
        como cadena vacía, no como ausencia; sin este validador el servicio
        intentaría usar `""` como modelo, clave o URL base.
        """
        return None if value == "" else value

    @cached_property
    def resolved_device(self) -> Literal["cpu", "cuda"]:
        """Selecciona el dispositivo una vez para todos los modelos del proceso."""
        if self.embedding_device == "cpu":
            return "cpu"
        # Importación diferida: torch solo se carga al resolver el dispositivo.
        import torch

        available = torch.cuda.is_available()
        if self.embedding_device == "cuda" and not available:
            raise RuntimeError(
                "CUDA requested but unavailable; check PyTorch, drivers and GPU access"
            )
        return "cuda" if available else "cpu"

    @model_validator(mode="after")
    def validate_chunk_overlap(self) -> "Settings":
        """Comprueba que el solape permita avanzar."""
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self

    @model_validator(mode="after")
    def validate_verify_thresholds(self) -> "Settings":
        """Comprueba el orden de los umbrales de verificación."""
        if not (0 <= self.verify_weak_threshold < self.verify_supported_threshold <= 1) or not (
            0 <= self.verify_contradiction_threshold <= 1
        ):
            raise ValueError("Invalid verification thresholds")
        if not 0 <= self.verify_conflict_margin <= 1:
            raise ValueError("Invalid verification conflict margin")
        return self


@lru_cache
def get_settings() -> Settings:
    """Instancia única por proceso.

    `lru_cache` sin argumentos hace que la primera llamada construya el objeto y las
    siguientes devuelvan el mismo, de modo que el fichero `.env` se lee una vez.
    """
    return Settings()
