"""Configuración del servicio, leída del entorno al arrancar."""

from functools import lru_cache

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
    qdrant_url: str = "http://localhost:6333"

    # Un chequeo de salud que tarda más que esto es un fallo a efectos prácticos:
    # quien lo consulta (un balanceador, un orquestador) no va a esperar más.
    health_timeout_seconds: float = 5.0

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Instancia única por proceso.

    `lru_cache` sin argumentos hace que la primera llamada construya el objeto y las
    siguientes devuelvan el mismo, de modo que el fichero `.env` se lee una vez.
    """
    return Settings()
