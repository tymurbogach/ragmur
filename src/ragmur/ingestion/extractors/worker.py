"""Proceso de extracción que puede terminarse cuando supera el plazo."""

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ragmur.ingestion.extractors.core import (
    ExtractionError,
    UnsupportedDocumentError,
    extract_docx,
    extract_pdf,
    extract_text,
)


def process(request: dict[str, Any]) -> dict[str, Any]:
    """Extrae un único documento y devuelve un resultado serializable."""
    path = Path(request["path"])
    mime = request["mime_type"]
    try:
        if mime == "application/pdf":
            result = extract_pdf(
                path, request["max_chars"], request["max_pages"], request["min_chars"]
            )
        elif mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            result = extract_docx(path, request["max_chars"], request["max_expanded_bytes"])
        elif mime in ("text/plain", "text/markdown"):
            result = extract_text(path, mime, request["max_chars"])
        else:
            raise UnsupportedDocumentError("El formato no está admitido")
        return {"status": "ok", "result": asdict(result)}
    except UnsupportedDocumentError as exc:
        return {"status": "unsupported", "error": str(exc)}
    except ExtractionError as exc:
        return {"status": "failed", "error": str(exc)}


def main() -> None:
    """Lee un trabajo desde stdin y escribe el resultado en stdout."""
    try:
        result = process(json.load(sys.stdin))
    except Exception:
        result = {"status": "failed", "error": "No se pudo extraer el documento"}
    json.dump(result, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
