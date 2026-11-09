"""Pruebas del almacenamiento de originales."""

from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest

from ragmur.ingestion.storage import UploadTooLargeError, store_original


def test_store_original_persists_content_and_hash(tmp_path: Path) -> None:
    original = store_original(tmp_path, uuid4(), BytesIO(b"abc"), 3)
    assert original.path.read_bytes() == b"abc"
    assert original.sha256 == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert original.size == 3
    assert list(tmp_path.iterdir()) == [original.path]


def test_upload_limit_removes_temporary_file(tmp_path: Path) -> None:
    with pytest.raises(UploadTooLargeError):
        store_original(tmp_path, uuid4(), BytesIO(b"abcd"), 3)
    assert list(tmp_path.iterdir()) == []


def test_existing_original_is_not_overwritten(tmp_path: Path) -> None:
    document_id = uuid4()
    original = store_original(tmp_path, document_id, BytesIO(b"old"), 5)
    with pytest.raises(FileExistsError):
        store_original(tmp_path, document_id, BytesIO(b"new"), 5)
    assert original.path.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [original.path]


def test_instance_lock_rejects_second_writer(tmp_path: Path) -> None:
    from ragmur.ingestion.storage import acquire_instance_lock

    with acquire_instance_lock(tmp_path), pytest.raises(BlockingIOError):
        acquire_instance_lock(tmp_path)
    with acquire_instance_lock(tmp_path):
        pass
