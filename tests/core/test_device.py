"""Selección del dispositivo para todos los modelos."""

from unittest.mock import Mock

import pytest

from ragmur.core.config import Settings


@pytest.mark.parametrize(("available", "expected"), [(True, "cuda"), (False, "cpu")])
def test_auto_selects_available_device(
    monkeypatch: pytest.MonkeyPatch, available: bool, expected: str
) -> None:
    probe = Mock(return_value=available)
    monkeypatch.setattr("torch.cuda.is_available", probe)
    settings = Settings(_env_file=None, database_url="postgresql://unused", api_key_hmac_secret="x")
    assert settings.resolved_device == expected
    assert settings.resolved_device == expected
    probe.assert_called_once()


def test_explicit_cpu_does_not_probe_cuda(monkeypatch: pytest.MonkeyPatch) -> None:
    probe = Mock(side_effect=AssertionError("CPU must not probe CUDA"))
    monkeypatch.setattr("torch.cuda.is_available", probe)
    settings = Settings(
        _env_file=None,
        database_url="postgresql://unused",
        api_key_hmac_secret="x",
        embedding_device="cpu",
    )
    assert settings.resolved_device == "cpu"


def test_explicit_cuda_requires_available_gpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("torch.cuda.is_available", lambda: False)
    settings = Settings(
        _env_file=None,
        database_url="postgresql://unused",
        api_key_hmac_secret="x",
        embedding_device="cuda",
    )
    with pytest.raises(RuntimeError, match="CUDA requested but unavailable"):
        _ = settings.resolved_device


def test_explicit_cuda_selects_gpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("torch.cuda.is_available", lambda: True)
    settings = Settings(
        _env_file=None,
        database_url="postgresql://unused",
        api_key_hmac_secret="x",
        embedding_device="cuda",
    )
    assert settings.resolved_device == "cuda"
