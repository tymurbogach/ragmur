"""Ejecución aislada y terminable de extractores."""

import asyncio
import json
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any


async def extract_in_process(
    path: Path,
    mime_type: str,
    *,
    max_chars: int,
    max_pages: int,
    min_chars: int,
    max_expanded_bytes: int,
    deadline_seconds: float,
) -> dict[str, Any]:
    """Ejecuta un trabajo en un proceso propio con tiempo de espera acotado."""
    payload = json.dumps(
        {
            "path": str(path),
            "mime_type": mime_type,
            "max_chars": max_chars,
            "max_pages": max_pages,
            "min_chars": min_chars,
            "max_expanded_bytes": max_expanded_bytes,
        }
    ).encode()
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "ragmur.ingestion.extractors.worker",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        async with asyncio.timeout(deadline_seconds):
            output, _ = await process.communicate(payload)
    except BaseException:
        if process.returncode is None:
            with suppress(ProcessLookupError):
                process.kill()
            await process.wait()
        raise
    if process.returncode != 0:
        return {"status": "failed", "error": "El proceso de extracción falló"}
    result: dict[str, Any] = json.loads(output)
    return result
