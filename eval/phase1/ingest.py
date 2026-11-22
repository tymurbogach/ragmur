"""Etapa ingest C02: rompe la ingesta a gran escala con semilla fija.

Genera documentos sintéticos y los pasa por el troceador real
(``split_document``) y por los extractores reales (``extract_text``,
``extract_docx``, ``extract_pdf``). Cada documento lleva semilla fija, así que
una ejecución repetida produce los mismos ficheros y el mismo resumen.

Detectores (fallos que la etapa sabe cazar):
- ``text_loss``: el texto reconstruido desde los chunks no coincide.
- ``span``: un chunk no coincide con ``text[start:end]`` o su rango es inválido.
- ``owner``: un chunk no conserva tenant, dueño o documento de entrada.
- ``hang``: una extracción no responde antes del plazo (cuelgue).
- ``crash``: una extracción lanza una excepción no controlada.

Un fallo real se publica como fallo duro (salida 1) con su semilla y no
impide terminar la etapa: el resumen lista cada problema encontrado.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections.abc import Callable
from concurrent import futures
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_OID, UUID, uuid5

SEED = 20261122
DOCS = 100_000
PER_FORMAT_VALID = 1_000
PER_FORMAT_BAD = 1_000
FORMATS = ("txt", "md", "docx", "pdf")

WORDS = [
    "plazo",
    "entrega",
    "contrato",
    "transporte",
    "factura",
    "cliente",
    "servicio",
    "garantia",
    "informe",
    "pago",
    "cuenta",
    "documento",
    "texto",
    "pagina",
    "seccion",
    "titulo",
    "anexo",
    "firma",
    "fecha",
]

Issue = dict[str, Any]


def scoped_id(seed: int, name: str) -> UUID:
    """Genera un UUID determinista a partir de la semilla y un nombre."""
    return uuid5(NAMESPACE_OID, f"ragmur-c02:{seed}:{name}")


def make_text(rng: random.Random, min_words: int = 5, max_words: int = 400) -> str:
    """Genera texto sintético con párrafos ocasionales."""
    parts: list[str] = []
    remaining = rng.randint(min_words, max_words)
    while remaining > 0:
        block = min(remaining, rng.randint(3, 40))
        parts.append(" ".join(rng.choice(WORDS) for _ in range(block)))
        remaining -= block
    return "\n\n".join(parts)


def check_text_preserved(text: str, chunks: list[Any]) -> list[Issue]:
    """Reconstruye el texto desde los chunks quitando el solape por spans."""
    ordered = sorted(chunks, key=lambda chunk: (chunk.start, chunk.end))
    if not ordered:
        return [{"kind": "text_loss", "detail": "sin chunks para un texto no vacío"}]
    rebuilt = ordered[0].text
    previous_end = ordered[0].end
    for chunk in ordered[1:]:
        skip = max(0, previous_end - chunk.start)
        if skip > len(chunk.text):
            return [{"kind": "text_loss", "detail": f"solape incoherente en {chunk.start}"}]
        if skip and not rebuilt.endswith(chunk.text[:skip]):
            return [{"kind": "text_loss", "detail": f"solape distinto en {chunk.start}"}]
        rebuilt += chunk.text[skip:]
        previous_end = max(previous_end, chunk.end)
    if rebuilt != text:
        return [{"kind": "text_loss", "detail": f"reconstruido {len(rebuilt)} de {len(text)}"}]
    return []


def check_spans(text: str, chunks: list[Any]) -> list[Issue]:
    """Comprueba que cada chunk coincide con su rango sobre el texto."""
    issues: list[Issue] = []
    for chunk in chunks:
        if not (0 <= chunk.start < chunk.end <= len(text)):
            issues.append({"kind": "span", "detail": f"rango inválido {chunk.start}:{chunk.end}"})
        elif chunk.text != text[chunk.start : chunk.end]:
            issues.append({"kind": "span", "detail": f"texto distinto en {chunk.start}"})
    return issues


def check_owners(
    chunks: list[Any], tenant_id: UUID, owner_id: str | None, document_id: UUID
) -> list[Issue]:
    """Comprueba que cada chunk conserva su espacio (tenant, dueño, documento)."""
    issues: list[Issue] = []
    for chunk in chunks:
        if chunk.tenant_id != tenant_id:
            issues.append({"kind": "owner", "detail": "tenant distinto"})
        if chunk.owner_id != owner_id:
            issues.append(
                {"kind": "owner", "detail": f"dueño {chunk.owner_id!r} en vez de {owner_id!r}"}
            )
        if chunk.document_id != document_id:
            issues.append({"kind": "owner", "detail": "documento distinto"})
    return issues


def run_with_timeout(func: Callable[[], Any], deadline_s: float) -> tuple[str, Any]:
    """Ejecuta una función con plazo; un cuelgue se registra, no se cuelga.

    Devuelve (``ok`` | ``hang``, resultado o detalle). El hilo de un cuelgue
    real sigue hasta terminar por sí solo; lo que no se hace es esperar por él.
    """
    pool = futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(func)
    try:
        result = future.result(timeout=deadline_s)
    except futures.TimeoutError:
        pool.shutdown(wait=False, cancel_futures=True)
        return "hang", f"sin respuesta en {deadline_s:g} s"
    except Exception as exc:
        pool.shutdown(wait=True)
        return "raised", exc
    pool.shutdown(wait=True)
    return "ok", result


def minimal_pdf_bytes(body_text: str) -> bytes:
    """Construye un PDF mínimo de una página solo con la stdlib."""
    safe = body_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    contents = f"BT /F1 12 Tf 20 50 Td ({safe}) Tj ET".encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(contents)).encode() + b" >>\nstream\n" + contents + b"\nendstream",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(data)


def write_docx(path: Path, rng: random.Random) -> None:
    """Genera un DOCX válido con python-docx: párrafos y encabezados."""
    from docx import Document

    document = Document()
    document.add_heading(f"Tema {rng.randint(1, 50)}", level=1)
    for _ in range(rng.randint(1, 4)):
        document.add_paragraph(make_text(rng, 5, 40))
        if rng.random() < 0.4:
            document.add_heading(f"Detalle {rng.randint(1, 50)}", level=2)
    document.save(str(path))


def write_valid_file(kind: str, path: Path, rng: random.Random) -> None:
    """Escribe un fichero válido del formato indicado."""
    if kind in ("txt", "md"):
        text = make_text(rng, 10, 120)
        if kind == "md":
            text = f"# Informe {rng.randint(1, 50)}\n\n{text}\n\n## Detalle\n\n{text[:200]}\n"
        path.write_text(text, encoding="utf-8")
    elif kind == "docx":
        write_docx(path, rng)
    else:
        path.write_bytes(minimal_pdf_bytes(make_text(rng, 5, 30)[:200]))


def write_bad_file(kind: str, path: Path, rng: random.Random, variant: int) -> None:
    """Escribe un fichero vacío, truncado o corrupto del formato indicado."""
    if variant == 0:
        if kind == "docx":
            from docx import Document

            Document().save(str(path))
        elif kind == "pdf":
            path.write_bytes(b"%PDF-1.4\n")
        else:
            path.write_text("   \n  ", encoding="utf-8")
        return
    if kind in ("txt", "md"):
        path.write_bytes(b"\xff\xfe\x00binario")
        return
    if kind == "docx":
        path.write_bytes(b"esto no es un zip ni un docx")
        return
    full = minimal_pdf_bytes(make_text(rng, 5, 30)[:200])
    if variant == 1:
        path.write_bytes(full[: len(full) // 3])
    else:
        path.write_bytes(b"not a PDF at all")


def classify_outcome(status: str, outcome: Any) -> tuple[str, str]:
    """Traduce el resultado vigilado a clase de extracción.

    ``ok``: texto extraído. ``invalid``: rechazo esperado de los extractores.
    ``hang``: cuelgue. ``crashed``: excepción no controlada: fallo real.
    """
    from ragmur.ingestion.extractors.core import ExtractionError, UnsupportedDocumentError

    if status == "hang":
        return "hang", str(outcome)
    if status == "raised":
        if isinstance(outcome, (UnsupportedDocumentError, ExtractionError)):
            return "invalid", type(outcome).__name__
        return "crashed", f"{type(outcome).__name__}: {outcome}"
    return "ok", "extraído"


def classify_extraction(kind: str, path: Path, deadline_s: float) -> tuple[str, str]:
    """Extrae un fichero y clasifica el resultado sin dejar escapar fallos.

    ``ok``: texto extraído. ``unsupported`` / ``invalid``: rechazo esperado
    (sin texto útil o contenido inválido). ``hang``: cuelgue. ``crashed``:
    excepción no controlada por los extractores: fallo real.
    """
    from ragmur.ingestion.extractors.core import extract_docx, extract_pdf, extract_text

    def work() -> str:
        if kind in ("txt", "md"):
            mime = "text/markdown" if kind == "md" else "text/plain"
            extract_text(path, mime, 100_000)
        elif kind == "docx":
            extract_docx(path, 100_000, 10_000_000)
        else:
            extract_pdf(path, 100_000, 10, 1)
        return "ok"

    status, outcome = run_with_timeout(work, deadline_s)
    return classify_outcome(status, outcome)


def sweep_chunker(seed: int, n_docs: int) -> dict[str, Any]:
    """Pasa documentos sintéticos por el troceador real y caza defectos."""
    from ragmur.ingestion.chunker import split_document
    from ragmur.ingestion.extractors.core import ExtractionResult, Fragment

    rng = random.Random(seed)
    issues: list[Issue] = []
    total_chunks = 0
    for index in range(n_docs):
        text = make_text(rng)
        size = rng.choice([160, 400, 900])
        overlap = rng.choice([0, 40, 120])
        if overlap >= size:
            overlap = 0
        owner = None if index % 3 == 0 else f"u-{index % 7}"
        tenant_id = scoped_id(seed, f"tenant-{index % 5}")
        document_id = scoped_id(seed, f"doc-{index}")
        extraction = ExtractionResult(
            [Fragment(text, {"type": "offset", "start": 0, "end": len(text)})]
        )
        chunked = split_document(
            extraction, document_id, tenant_id, owner, size=size, overlap=overlap
        )
        total_chunks += len(chunked.chunks)
        for check in (
            check_text_preserved(text, chunked.chunks),
            check_spans(text, chunked.chunks),
            check_owners(chunked.chunks, tenant_id, owner, document_id),
        ):
            for issue in check:
                issues.append({"seed": seed, "doc": index, **issue})
                if len(issues) >= 20:
                    return {"docs": n_docs, "chunks": total_chunks, "issues": issues}
    return {"docs": n_docs, "chunks": total_chunks, "issues": issues}


def sweep_extractors(
    seed: int, valid_each: int, bad_each: int, workdir: Path, deadline_s: float
) -> dict[str, Any]:
    """Pasa ficheros válidos y rotos por los extractores reales."""
    rng = random.Random(seed + 1)
    files_dir = workdir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"formats": {}, "issues": []}
    for kind in FORMATS:
        counts = {"ok": 0, "rejected": 0, "hang": 0, "crashed": 0}
        for index in range(valid_each):
            path = files_dir / f"valid-{kind}-{index}.{kind if kind != 'md' else 'md'}"
            write_valid_file(kind, path, rng)
            status, detail = classify_extraction(kind, path, deadline_s)
            if status == "ok":
                counts["ok"] += 1
            elif status in ("hang", "crashed"):
                counts[status] += 1
                report["issues"].append(
                    {"seed": seed, "file": path.name, "kind": status, "detail": detail}
                )
            else:
                counts["rejected"] += 1
                report["issues"].append(
                    {"seed": seed, "file": path.name, "kind": "valid_failed", "detail": detail}
                )
        for index in range(bad_each):
            path = files_dir / f"bad-{kind}-{index}.bin"
            write_bad_file(kind, path, rng, index % 3)
            status, detail = classify_extraction(kind, path, deadline_s)
            if status in ("hang", "crashed"):
                counts[status] += 1
                report["issues"].append(
                    {"seed": seed, "file": path.name, "kind": status, "detail": detail}
                )
            elif status == "ok":
                counts["ok"] += 1
            else:
                counts["rejected"] += 1
        report["formats"][kind] = counts
    return report


def run_stage(
    seed: int, n_docs: int, valid_each: int, bad_each: int, out: Path, deadline_s: float
) -> dict[str, Any]:
    """Ejecuta la etapa completa y escribe el resumen con su semilla."""
    started = time.time()
    out.mkdir(parents=True, exist_ok=True)
    chunk_report = sweep_chunker(seed, n_docs)
    extraction_report = sweep_extractors(seed, valid_each, bad_each, out, deadline_s)
    issues = list(chunk_report["issues"]) + list(extraction_report["issues"])
    summary = {
        "seed": seed,
        "docs": chunk_report["docs"],
        "chunks": chunk_report["chunks"],
        "extraction": extraction_report["formats"],
        "issues": issues[:50],
        "issue_count": len(issues),
        "elapsed_s": round(time.time() - started, 1),
    }
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    """Define la línea de órdenes de la etapa ingest."""
    parser = argparse.ArgumentParser(prog="python -m eval.phase1.ingest")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--docs", type=int, default=DOCS)
    parser.add_argument("--per-format-valid", type=int, default=PER_FORMAT_VALID)
    parser.add_argument("--per-format-bad", type=int, default=PER_FORMAT_BAD)
    parser.add_argument("--deadline", type=float, default=60.0)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Genera, mide y publica fallos reales con su semilla; 0 bien, 1 fallo."""
    args = build_parser().parse_args(argv)
    summary = run_stage(
        args.seed, args.docs, args.per_format_valid, args.per_format_bad, args.out, args.deadline
    )
    line = (
        f"docs={summary['docs']} chunks={summary['chunks']} "
        f"issues={summary['issue_count']} elapsed_s={summary['elapsed_s']} seed={summary['seed']}\n"
    )
    sys.stdout.write(line)
    return 1 if summary["issues"] else 0


if __name__ == "__main__":
    sys.exit(main())
