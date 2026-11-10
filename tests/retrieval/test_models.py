"""Interfaz de modelos con inferencia simulada en tests unitarios."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from ragmur.retrieval.embedder import DenseEmbedder
from ragmur.retrieval.sparse import SparseEmbedder


def test_dense_loads_revision_and_reuses_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model = Mock()
    model.get_embedding_dimension.return_value = 1024
    model.encode.return_value = np.array([[0.5, 0.5]])
    factory = Mock(return_value=model)
    monkeypatch.setattr("ragmur.retrieval.embedder.SentenceTransformer", factory)
    embedder = DenseEmbedder("model", "revision", "cpu", tmp_path)
    assert embedder.embed(["example"], 2) == [[0.5, 0.5]]
    assert embedder.embed([], 2) == []
    factory.assert_called_once()
    assert factory.call_args.kwargs["revision"] == "revision"
    assert factory.call_args.kwargs["trust_remote_code"] is False
    model.encode.assert_called_once()


def test_sparse_uses_different_document_and_query_operations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    vector = SimpleNamespace(indices=np.array([3]), values=np.array([0.5]))
    model = Mock()
    model.model = SimpleNamespace(stopwords={"el", "la"}, stemmer=None, token_max_length=40)
    model.embed.return_value = iter([vector])
    model.query_embed.return_value = iter([vector])
    factory = Mock(return_value=model)
    monkeypatch.setattr("ragmur.retrieval.sparse.SparseTextEmbedding", factory)
    monkeypatch.setattr(
        "ragmur.retrieval.sparse.snapshot_download", Mock(return_value=str(tmp_path))
    )
    embedder = SparseEmbedder("Qdrant/bm25", "revision", tmp_path, "spanish", False, 1.2, 0.75, 256)
    assert embedder.embed(["texto"], 8)[0].indices == [3]
    assert embedder.query_embed("consulta").values == [0.5]
    assert embedder.metadata["language"] == "spanish"
    assert factory.call_args.kwargs["specific_model_path"] == str(tmp_path)
    model.embed.assert_called_once()
    model.query_embed.assert_called_once()
