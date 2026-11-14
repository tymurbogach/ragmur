"""Tests del evaluador de estrés numérico sin IDs fijos ni tasas artificiales."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_dataset(path: Path, cases: list[dict[str, object]]) -> None:
    path.write_text(yaml.safe_dump(cases, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _run_eval(dataset: Path, output: Path, details: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "eval.numeric_signal_stress_eval",
            "--dataset",
            str(dataset),
            "--output",
            str(output),
            "--details",
            str(details),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def _two_dev_cases() -> list[dict[str, object]]:
    return [
        {
            "id": "stress-001",
            "document_id": "doc-a",
            "split": "dev",
            "premise": "La ayuda es de hasta 10 euros.",
            "claims": [{"text": "La ayuda es de hasta 20 euros.", "label": "supported"}],
            "stress_type": "cota-inclusiva",
        },
        {
            "id": "stress-002",
            "document_id": "doc-a",
            "split": "dev",
            "premise": "La ayuda es de 10 euros.",
            "claims": [{"text": "La ayuda es de 50 euros.", "label": "contradicted"}],
            "stress_type": "distinta-cantidad",
        },
    ]


def test_eval_accepts_dataset_without_eu_dev_223(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.yaml"
    output = tmp_path / "summary.json"
    details = tmp_path / "details.json"
    _write_dataset(dataset, _two_dev_cases())
    proc = _run_eval(dataset, output, details)
    assert proc.returncode == 0, proc.stderr
    summary = json.loads(output.read_text(encoding="utf-8"))
    assert "eu_dev_223" not in summary
    assert "eu-dev-223" not in json.dumps(summary)
    assert summary["dataset"]["n_cases"] == 2
    assert summary["counts"]["claims"] == 2
    assert summary["dataset"]["sha256"]
    assert summary["code"]["sha256"]
    assert summary["script"]["sha256"]


def test_missing_class_yields_null_rates(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.yaml"
    output = tmp_path / "summary.json"
    details = tmp_path / "details.json"
    _write_dataset(
        dataset,
        [
            {
                "id": "only-supported-1",
                "document_id": "doc-a",
                "split": "dev",
                "premise": "La ayuda es de hasta 10 euros.",
                "claims": [{"text": "La ayuda es de hasta 20 euros.", "label": "supported"}],
            }
        ],
    )
    proc = _run_eval(dataset, output, details)
    assert proc.returncode == 0, proc.stderr
    summary = json.loads(output.read_text(encoding="utf-8"))
    assert summary["counts"]["contradicted"] == 0
    assert summary["counts"]["unsupported"] == 0
    assert summary["signal_flag_rate"]["contradicted"] is None
    assert summary["signal_flag_rate"]["unsupported"] is None
    assert summary["signal_flag_counts"]["contradicted"] == {"flagged": 0, "total": 0}
    # La clase presente sí tiene tasa numérica, no null artificial distinto.
    assert summary["signal_flag_rate"]["supported"] in (0.0, 1.0)


def test_non_dev_split_rejected(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.yaml"
    output = tmp_path / "summary.json"
    details = tmp_path / "details.json"
    _write_dataset(
        dataset,
        [
            {
                "id": "reserved-001",
                "document_id": "doc-test",
                "split": "test",
                "premise": "La ayuda es de 10 euros.",
                "claims": [{"text": "La ayuda es de 50 euros.", "label": "contradicted"}],
            }
        ],
    )
    proc = _run_eval(dataset, output, details)
    assert proc.returncode != 0
    assert "Solo split dev" in proc.stderr


def test_summary_does_not_equate_alert_with_error(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.yaml"
    output = tmp_path / "summary.json"
    details = tmp_path / "details.json"
    _write_dataset(dataset, _two_dev_cases())
    proc = _run_eval(dataset, output, details)
    assert proc.returncode == 0, proc.stderr
    summary = json.loads(output.read_text(encoding="utf-8"))
    text = json.dumps(summary, ensure_ascii=False).lower()
    assert "no error ni veredicto" in text
    assert "no verifica entidad" in text
    assert "no es necesariamente falsa" in text
    assert "alerta equivale a error" not in text
    assert "falso respaldo" not in text or "tasa de respaldo falso" not in text
