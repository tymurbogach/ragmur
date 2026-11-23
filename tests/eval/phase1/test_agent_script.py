"""Contrato de scripts/phase1-agent.sh: propaga el código y aísla al explicador."""

import os
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "phase1-agent.sh"


def _write_stub(path: Path, body: str) -> Path:
    """Escribe un falso ejecutable y lo hace ejecutable."""
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def _quick_stub(path: Path) -> Path:
    """Falso quick: escribe quick.json y sale con FAKE_QUICK_EXIT."""
    return _write_stub(
        path,
        "#!/bin/sh\n"
        'out=""\n'
        'for arg in "$@"; do\n'
        '  if [ "$prev" = "--out" ]; then out="$arg"; fi\n'
        '  prev="$arg"\n'
        "done\n"
        'echo "{\\"mode\\": \\"quick\\", \\"exit_code\\": $FAKE_QUICK_EXIT}" > "$out/quick.json"\n'
        'echo "exit=$FAKE_QUICK_EXIT"\n'
        "exit $FAKE_QUICK_EXIT\n",
    )


def _delivery_stub(path: Path) -> Path:
    """Falso delivery: final escribe informe y paquete; explain delega al real."""
    return _write_stub(
        path,
        "#!/bin/sh\n"
        'if [ "$1" = "quick" ]; then\n'
        '  dir="$3"\n'
        '  echo "informe" > "$dir/informe.md"\n'
        '  echo "{\\"failures\\": []}" > "$dir/fallos-publicos.json"\n'
        '  echo "$dir/informe.md $dir/fallos-publicos.json"\n'
        "  exit 0\n"
        "fi\n"
        'if [ "$1" = "final" ]; then\n'
        '  run="$3"\n'
        '  dir="eval/results/phase1/per_query/$run"\n'
        '  mkdir -p "$dir"\n'
        '  echo "informe final" > "$dir/informe.md"\n'
        '  echo "{\\"mode\\": \\"full\\", \\"exit_code\\": 3,'
        ' \\"seed\\": 20261123, \\"failures\\": [], \\"note\\": \\"x\\"}"'
        ' > "$dir/fallos-publicos.json"\n'
        '  echo "$dir/informe.md $dir/fallos-publicos.json"\n'
        "  exit 0\n"
        "fi\n"
        'exec uv run python -m eval.phase1.delivery "$@"\n',
    )


def _runner_stub(path: Path) -> Path:
    """Falso runner: start/status/report enlatados con FAKE_REPORT_EXIT."""
    return _write_stub(
        path,
        "#!/bin/sh\n"
        'if [ "$1" = "start" ]; then echo "falso1234"; exit 0; fi\n'
        'if [ "$1" = "status" ]; then\n'
        '  echo "run_id: falso1234"\n'
        '  echo "estado: done salida=$FAKE_REPORT_EXIT"\n'
        "  exit 0\n"
        "fi\n"
        'if [ "$1" = "report" ]; then\n'
        '  echo "{\\"run_id\\": \\"falso1234\\"}"\n'
        "  exit $FAKE_REPORT_EXIT\n"
        "fi\n"
        'echo "orden desconocida: $1" >&2\n'
        "exit 2\n",
    )


def _opencode_stub(path: Path, record: Path) -> Path:
    """Falso opencode: anota la llamada y sale con FAKE_EXPLAINER_EXIT."""
    return _write_stub(
        path,
        f'#!/bin/sh\necho "llamado: $@" >> "{record}"\nexit $FAKE_EXPLAINER_EXIT\n',
    )


def _env(extra: dict[str, str]) -> dict[str, str]:
    """Entorno base: sin inhibit, sin espera y con stubs en el PATH."""
    env = dict(os.environ)
    env["PHASE1_AGENT_NO_INHIBIT"] = "1"
    env["PHASE1_AGENT_POLL_SLEEP"] = "0"
    env.update(extra)
    return env


def test_uso_sin_modo_falla() -> None:
    """Sin [quick|full] el script explica el uso y sale con 2."""
    done = subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, cwd=REPO, timeout=60.0
    )
    assert done.returncode == 2
    assert "quick|full" in done.stderr


def test_quick_propaga_el_codigo_y_no_llama_al_explicador(tmp_path: Path) -> None:
    """El quick sale con el código del quick y jamás invoca a opencode."""
    record = tmp_path / "opencode-llamadas.txt"
    outdir = tmp_path / "quick-salida"
    env = _env(
        {
            "PHASE1_AGENT_QUICK_CMD": str(_quick_stub(tmp_path / "quick-falso")),
            "PHASE1_AGENT_DELIVERY_CMD": str(_delivery_stub(tmp_path / "delivery-falso")),
            "PHASE1_AGENT_EXPLAINER_CMD": str(_opencode_stub(tmp_path / "opencode", record)),
            "PHASE1_AGENT_QUICK_OUTDIR": str(outdir),
            "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
            "FAKE_QUICK_EXIT": "3",
        },
    )
    done = subprocess.run(
        ["bash", str(SCRIPT), "quick"],
        capture_output=True,
        text=True,
        cwd=REPO,
        env=env,
        timeout=120.0,
    )
    assert done.returncode == 3
    assert not record.exists()
    assert "informe:" in done.stdout
    assert (outdir / "informe.md").exists()
    assert (outdir / "fallos-publicos.json").exists()


def test_full_llama_al_explicador_y_mantiene_el_codigo(tmp_path: Path) -> None:
    """El full explica con plazo y sale con el código del report aunque caiga."""
    record = tmp_path / "opencode-llamadas.txt"
    env = _env(
        {
            "PHASE1_AGENT_RUNNER_CMD": str(_runner_stub(tmp_path / "runner-falso")),
            "PHASE1_AGENT_DELIVERY_CMD": str(_delivery_stub(tmp_path / "delivery-falso")),
            "PHASE1_AGENT_EXPLAINER_CMD": str(_opencode_stub(tmp_path / "opencode", record)),
            "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
            "PHASE1_AGENT_EXPLAINER_TIMEOUT": "30",
            "FAKE_REPORT_EXIT": "3",
            "FAKE_EXPLAINER_EXIT": "1",
        },
    )
    done = subprocess.run(
        ["bash", str(SCRIPT), "full"],
        capture_output=True,
        text=True,
        cwd=REPO,
        env=env,
        timeout=180.0,
    )
    run_dir = REPO / "eval" / "results" / "phase1" / "per_query" / "falso1234"
    try:
        assert done.returncode == 3
        assert record.exists()
        explanation = run_dir / "explicacion.md"
        assert explanation.exists()
        text = explanation.read_text(encoding="utf-8")
        assert "no cambia la nota" in text
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
