"""Conservación acotada de originales bajo rutas generadas por el servidor."""

import fcntl
import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import IO, BinaryIO
from uuid import UUID


class UploadTooLargeError(Exception):
    """El original excede el límite de bytes."""


class InvalidDocumentPathError(Exception):
    """La ruta conservada no corresponde al documento."""


def resolve_document_path(root: Path, document_id: UUID, storage_path: str) -> Path:
    """Comprueba que la ruta conservada viva bajo `root` con el nombre del documento."""
    resolved_root = root.resolve()
    path = Path(storage_path)
    if path.parent != resolved_root or path.name != str(document_id):
        raise InvalidDocumentPathError("La ruta del documento no pertenece a su espacio")
    return path


def acquire_instance_lock(root: Path) -> IO[bytes]:
    """Impide ejecutar dos instancias escritoras sobre el mismo almacenamiento."""
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / ".ragmur.lock").open("a+b")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        lock.close()
        raise
    return lock


@dataclass(frozen=True, slots=True)
class StoredOriginal:
    """Ruta y huella de un original persistido."""

    path: Path
    sha256: str
    size: int


def store_original(
    root: Path, document_id: UUID, source: BinaryIO, max_bytes: int
) -> StoredOriginal:
    """Escribe un original mediante un temporal y lo mueve al finalizar."""
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    target = root / str(document_id)
    digest = hashlib.sha256()
    size = 0
    descriptor, temporary_name = tempfile.mkstemp(prefix=".upload-", dir=root)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            while block := source.read(1024 * 1024):
                size += len(block)
                if size > max_bytes:
                    raise UploadTooLargeError("El fichero supera el límite de bytes")
                digest.update(block)
                output.write(block)
            output.flush()
            os.fsync(output.fileno())
        # El identificador es generado por el servidor y nunca proviene del nombre del fichero.
        # Un enlace duro no sobrescribe un original si el identificador ya existe.
        os.link(temporary, target)
        temporary.unlink()
        directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return StoredOriginal(target, digest.hexdigest(), size)
    finally:
        temporary.unlink(missing_ok=True)
