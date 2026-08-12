"""Logging estructurado en JSON, una línea por evento.

Un fichero de log en JSON se consulta con herramientas (`jq`, Loki, Grafana) en vez
de leerse a ojo. Cuando en la fase 1 cada petición lleve `tenant_id`, poder filtrar
por ese campo es la diferencia entre encontrar un fallo y no encontrarlo.
"""

import json
import logging
import sys
from typing import Any

# Atributos que `logging.LogRecord` trae de serie. Todo lo que no esté aquí lo ha
# añadido quien llamó al logger con `extra=...`, y por tanto va al JSON de salida.
_ATRIBUTOS_ESTANDAR = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()) | {
    "message",
    "asctime",
    "taskName",
    # Uvicorn adjunta una copia del mensaje con códigos de color de terminal. En un
    # log en JSON es basura: el mismo texto otra vez, lleno de secuencias de escape.
    "color_message",
}


class JsonFormatter(logging.Formatter):
    """Convierte un registro de log en una línea de JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for clave, valor in record.__dict__.items():
            if clave not in _ATRIBUTOS_ESTANDAR:
                payload[clave] = valor
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Deja un único manejador en la raíz que escribe JSON por stdout.

    Uvicorn instala sus propios manejadores al arrancar. Vaciar los suyos y dejar que
    propaguen a la raíz evita la línea duplicada: una en texto plano y otra en JSON.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    for nombre in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(nombre)
        logger.handlers = []
        logger.propagate = True
