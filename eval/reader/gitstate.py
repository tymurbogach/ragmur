"""Estado del árbol Git para los bancos de evaluación (sin importaciones ML).

Este módulo no importa modelos ni clientes: solo interroga a Git para saber
si `src` o `eval` tienen cambios sin commitear. Lo usan tanto la preparación
de la caché (`prepare`) como el ejecutor del lector (`run`) para negarse a
correr sobre un árbol sucio salvo `--allow-dirty`.
"""

from __future__ import annotations

import subprocess

IGNORED_DIRTY_PREFIXES = ("eval/results", "eval/.datasets")


def is_dirty_tree() -> bool:
    """Indica si `src` o `eval` tienen cambios sin commitear.

    Ignora `eval/results` y `eval/.datasets` (cachés y descargas locales).
    Si Git no responde, se considera sucio por prudencia.
    """
    try:
        proc = subprocess.run(
            [
                "git",
                "status",
                "--porcelain",
                "--",
                ":/src",
                ":/eval",
                ":/pyproject.toml",
                ":/uv.lock",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return True
    for line in proc.stdout.splitlines():
        path = line[3:] if len(line) > 3 else ""
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip().strip('"')
        if not path:
            continue
        if path.startswith(IGNORED_DIRTY_PREFIXES):
            continue
        return True
    return False
