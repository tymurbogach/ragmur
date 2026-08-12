"""Comprobaciones mecánicas de las salidas de la eval de learn-while-building.

Uso:
    python3 check.py <directorio-iteracion>

Recorre <iteracion>/eval-*/<config>/outputs/ y emite un JSON por run con lo que se
puede verificar sin criterio humano: formato de LEARNING.md, duplicados, longitud
de las notas, línea de concepto clave, presencia de analogía y ausencia de gates de
comprensión. Lo subjetivo —si la analogía es correcta, si la nota aporta— lo juzga
el grader.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

DASH = r"[—–]"
LEARNING_LINE = re.compile(rf"^-\s+(.+?)\s+{DASH}\s+(.+?)\s+{DASH}\s+(.+)$")
CONCEPTO_CLAVE = re.compile(r"^\s*[*_> ]*Concepto clave de esta tarea:\s*\S.*$", re.MULTILINE)
NOTA_CABECERA = re.compile(rf"^\s*[-*]?\s*\*\*(.+?)\*\*\s*{DASH}\s*(.*)$")

ANALOGIA = re.compile(
    r"\b(laravel|angular|php|php-fpm|javascript|typescript|composer|eloquent|doctrine|"
    r"phpunit|artisan|formrequest|service provider|contenedor de servicios|blade|astro)\b",
    re.IGNORECASE,
)
ALTERNATIVA = re.compile(
    r"\b(descartad\w+|alternativa|en vez de|en lugar de|frente a|se podría haber)\b",
    re.IGNORECASE,
)
GATE = re.compile(
    r"(¿has entendido|¿te queda claro|¿lo has pillado|¿sabrías|ejercicio\b|ejercicios\b|"
    r"cuestionario|pregunta de repaso|comprueba que has entendido|para practicar|"
    r"tu turno|progreso de aprendizaje|plan de estudio)",
    re.IGNORECASE,
)
RELLENO = re.compile(
    r"(¡genial|¡perfecto|buen trabajo|enhorabuena|sigue así|no te preocupes|"
    r"¡muy bien|excelente trabajo|vas por buen camino)",
    re.IGNORECASE,
)
FUERA_ALCANCE = re.compile(
    r"\b(docker|docker[- ]compose|contenedor(es)?|volumen(es)?|healthcheck de docker|"
    r"sql\b|índice de base de datos|clave foránea|foreign key|git\b|http\b|rest\b)",
    re.IGNORECASE,
)


def normaliza(texto: str) -> str:
    """Minúsculas sin tildes ni puntuación, para comparar conceptos entre sí."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", "", sin_tildes)


def zona_de_notas(respuesta: str) -> str:
    """Las notas van al cierre, separadas del resumen de trabajo por una regla horizontal.

    Sin este recorte, el resumen de «qué he creado» —que usa el mismo formato
    **algo** — descripción— se contaría como nota, y un fichero como docker-compose.yml
    aparecería como concepto explicado sin serlo.
    """
    partes = re.split(r"^\s*---+\s*$", respuesta, flags=re.MULTILINE)
    return partes[-1] if len(partes) > 1 else respuesta


def bloques_de_nota(respuesta: str) -> list[dict[str, object]]:
    """Un bloque es una cabecera **concepto** — ... y las líneas hasta la línea en blanco."""
    bloques: list[dict[str, object]] = []
    lineas = zona_de_notas(respuesta).splitlines()
    i = 0
    while i < len(lineas):
        m = NOTA_CABECERA.match(lineas[i])
        if not m:
            i += 1
            continue
        cuerpo = [lineas[i]]
        j = i + 1
        while j < len(lineas) and lineas[j].strip() and not NOTA_CABECERA.match(lineas[j]):
            cuerpo.append(lineas[j])
            j += 1
        texto = "\n".join(cuerpo)
        bloques.append(
            {
                "concepto": m.group(1).strip(),
                "lineas": len(cuerpo),
                "palabras": len(texto.split()),
                "texto": texto,
            }
        )
        i = j
    return bloques


def revisa_learning(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"existe": False}
    entradas, malformadas = [], []
    for linea in path.read_text(encoding="utf-8").splitlines():
        if not linea.startswith("- "):
            continue
        m = LEARNING_LINE.match(linea.rstrip())
        if m:
            entradas.append({"concepto": m.group(1), "frase": m.group(2), "fichero": m.group(3)})
        else:
            malformadas.append(linea)
    vistos: dict[str, str] = {}
    duplicados = []
    for e in entradas:
        clave = normaliza(str(e["concepto"]))
        if clave in vistos:
            duplicados.append([vistos[clave], e["concepto"]])
        else:
            vistos[clave] = str(e["concepto"])
    return {
        "existe": True,
        "n_entradas": len(entradas),
        "conceptos": [e["concepto"] for e in entradas],
        "lineas_malformadas": malformadas,
        "formato_ok": not malformadas and bool(entradas),
        "duplicados": duplicados,
        "sin_duplicados": not duplicados,
    }


def revisa_run(run: Path) -> dict[str, object]:
    outputs = run / "outputs"
    respuesta_path = outputs / "respuesta.md"
    respuesta = respuesta_path.read_text(encoding="utf-8") if respuesta_path.exists() else ""
    bloques = bloques_de_nota(respuesta)
    largos = [b for b in bloques if int(b["palabras"]) > 80]  # type: ignore[arg-type]
    claves = CONCEPTO_CLAVE.findall(respuesta)
    # Docker, SQL, git y HTTP son prioridad baja, no terreno prohibido: se listan para
    # que quien gradúe decida si la nota destapa algo no evidente o repasa lo obvio.
    baja = [b["concepto"] for b in bloques if FUERA_ALCANCE.search(str(b["concepto"]))]
    py = sorted(str(p.relative_to(outputs)) for p in outputs.rglob("*.py"))

    return {
        "run": run.name,
        "respuesta_existe": respuesta_path.exists(),
        "respuesta_chars": len(respuesta),
        "ficheros_py": py,
        "n_notas": len(bloques),
        "notas": [
            {"concepto": b["concepto"], "lineas": b["lineas"], "palabras": b["palabras"]}
            for b in bloques
        ],
        "notas_max_80_palabras": not largos,
        "notas_demasiado_largas": [(b["concepto"], b["palabras"]) for b in largos],
        "concepto_clave_unico": len(claves) == 1,
        "n_concepto_clave": len(claves),
        "analogia_presente": bool(ANALOGIA.search(respuesta)),
        "alternativa_descartada": bool(ALTERNATIVA.search(respuesta)),
        "sin_gates": not GATE.search(respuesta),
        "sin_relleno": not RELLENO.search(respuesta),
        "notas_de_prioridad_baja": baja,
        "learning": revisa_learning(outputs / "repo" / "LEARNING.md"),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    iteracion = Path(sys.argv[1])
    informe = []
    for eval_dir in sorted(iteracion.glob("eval-*")):
        for config in ("with_skill", "without_skill", "old_skill"):
            run = eval_dir / config
            if not run.is_dir():
                continue
            r = revisa_run(run)
            r["eval"] = eval_dir.name
            informe.append(r)
            (run / "checks.json").write_text(
                json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    print(json.dumps(informe, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
