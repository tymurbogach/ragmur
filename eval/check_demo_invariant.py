"""Genera y comprueba las consultas del invariante del tenant de demo.

Fuente normativa: `docs/demo-design.md` §5. Solo biblioteca estándar.

Entradas:

- `eval/eu_manifest.yaml`: origen de los `sha256` (no se copian a mano).
- `eval/skynet_public_corpus_2026-11-13.md:58-71`: cuadro con exactamente
  los 10 `document_id` del corpus público (hallazgo 3 de F05a: la regla de
  selección en prosa da 14 documentos; solo valen los 10 listados).

Salida: las tres consultas SQL del invariante con los hashes ya rellenos
(hallazgo 4 de F05a: son tres, no dos), con `status = 'indexed'` en los
conteos (hallazgo 5 de F05a: solo los documentos indexados son visibles
para búsqueda y verificación).

El script falla (código 2) salvo que emita exactamente 10 hashes distintos
de 64 caracteres hexadecimales. Con `--check` ejecuta además las consultas
contra la base indicada y falla (código 1) si el invariante no se cumple:
0 documentos infractores, 10 documentos en total, 1 clave activa.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "eval" / "eu_manifest.yaml"
DEFAULT_CORPUS_REPORT = REPO_ROOT / "eval" / "skynet_public_corpus_2026-11-13.md"

# Tenant del corpus público en Skynet
# (`eval/skynet_public_corpus_2026-11-13.md`, apartado 5).
DEFAULT_TENANT_ID = "cbc8c3fe-1cdb-4e0d-9a7d-a3296884e08a"
OWNER_ID = "ue-publico"

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
HEX64_RE = re.compile(r"[0-9a-f]{64}")
DOCUMENT_ID_RE = re.compile(r"^-\s+document_id:\s+(\S+)\s*$")
SHA256_RE = re.compile(r"^\s+sha256:\s+(\S+)\s*$")


def read_document_ids(report: Path, first_line: int, last_line: int) -> list[str]:
    """Extrae los UUID del cuadro del informe, en orden de aparición."""
    lines = report.read_text(encoding="utf-8").splitlines()
    if last_line > len(lines):
        raise ValueError(f"{report} tiene {len(lines)} líneas; no llega a {last_line}")
    found: list[str] = []
    for line in lines[first_line - 1 : last_line]:
        found.extend(UUID_RE.findall(line.lower()))
    return found


def read_manifest_hashes(manifest: Path) -> dict[str, str]:
    """Lee pares document_id -> sha256 del manifiesto sin dependencias YAML."""
    hashes: dict[str, str] = {}
    current: str | None = None
    for line in manifest.read_text(encoding="utf-8").splitlines():
        match_id = DOCUMENT_ID_RE.match(line)
        if match_id is not None:
            current = match_id.group(1)
            continue
        match_sha = SHA256_RE.match(line)
        if match_sha is not None and current is not None:
            hashes[current] = match_sha.group(1)
            current = None
    return hashes


def resolve_hashes(
    manifest: Path, report: Path, first_line: int, last_line: int
) -> tuple[list[str], list[str]]:
    """Devuelve (document_ids, hashes) tras la autocomprobación."""
    document_ids = read_document_ids(report, first_line, last_line)
    if len(document_ids) != 10:
        raise ValueError(
            f"se esperaban exactamente 10 document_id en {report}:{first_line}-{last_line}, "
            f"hallados {len(document_ids)}"
        )
    if len(set(document_ids)) != 10:
        raise ValueError("los 10 document_id no son distintos")
    hashes = read_manifest_hashes(manifest)
    missing = [doc for doc in document_ids if doc not in hashes]
    if missing:
        raise ValueError(f"document_id sin entrada en {manifest}: {missing}")
    resolved = [hashes[doc] for doc in document_ids]
    for doc, sha in zip(document_ids, resolved, strict=True):
        if HEX64_RE.fullmatch(sha) is None:
            raise ValueError(f"sha256 inválido para {doc}: {sha!r}")
    if len(set(resolved)) != 10:
        raise ValueError("los 10 sha256 no son distintos")
    return document_ids, resolved


def render_sql(tenant_id: str, key_id: str, hashes: list[str]) -> str:
    """Genera las tres consultas del invariante con los hashes rellenos."""
    in_list = ",\n    ".join(f"'{sha}'" for sha in hashes)
    return f"""-- 1. Documentos infractores del tenant público (esperado: 0).
-- Detecta otro propietario u otro contenido. Solo cuentan los indexados:
-- son los únicos visibles para búsqueda y verificación.
SELECT count(*)
FROM documents
WHERE tenant_id = '{tenant_id}'
  AND status = 'indexed'
  AND (
    owner_id IS DISTINCT FROM '{OWNER_ID}'
    OR content_sha256 NOT IN (
    {in_list}
    )
  );

-- 2. Total de documentos indexados del tenant (esperado: 10).
-- Detecta un documento extra aunque su hash esté en el manifiesto.
SELECT count(*)
FROM documents
WHERE tenant_id = '{tenant_id}'
  AND status = 'indexed';

-- 3. Clave de demo activa en el tenant público (esperado: 1).
SELECT count(*)
FROM api_keys
WHERE key_id = '{key_id}'
  AND tenant_id = '{tenant_id}'
  AND revoked_at IS NULL;
"""


def run_psql(db_url: str, sql: str) -> str:
    """Ejecuta una consulta con `psql` y devuelve su salida tabular."""
    parsed = urllib.parse.urlsplit(db_url)
    if parsed.scheme not in ("postgresql", "postgresql+asyncpg"):
        raise ValueError(f"esquema no admitido: {parsed.scheme}")
    env = dict(os.environ)
    if parsed.password:
        env["PGPASSWORD"] = urllib.parse.unquote(parsed.password)
    host = parsed.hostname or "localhost"
    port = str(parsed.port or 5432)
    user = urllib.parse.unquote(parsed.username or "")
    dbname = parsed.path.lstrip("/") or "ragmur"
    command = ["psql", "-h", host, "-p", port, "-U", user, "-d", dbname, "-tA", "-c", sql]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
    except FileNotFoundError as exc:
        raise ValueError("`psql` no está instalado") from exc
    if completed.returncode != 0:
        raise ValueError(f"psql falló: {completed.stderr.strip()}")
    return completed.stdout.strip()


def check_invariant(db_url: str, tenant_id: str, key_id: str, hashes: list[str]) -> int:
    """Ejecuta las tres consultas y devuelve 0 si el invariante se cumple."""
    in_list = ", ".join(f"'{sha}'" for sha in hashes)
    bad = run_psql(
        db_url,
        f"SELECT count(*) FROM documents WHERE tenant_id = '{tenant_id}' "
        f"AND status = 'indexed' AND (owner_id IS DISTINCT FROM '{OWNER_ID}' "
        f"OR content_sha256 NOT IN ({in_list}));",
    )
    total = run_psql(
        db_url,
        f"SELECT count(*) FROM documents WHERE tenant_id = '{tenant_id}' AND status = 'indexed';",
    )
    key = run_psql(
        db_url,
        f"SELECT count(*) FROM api_keys WHERE key_id = '{key_id}' "
        f"AND tenant_id = '{tenant_id}' AND revoked_at IS NULL;",
    )
    sys.stdout.write(f"infractores={bad} total={total} clave={key}\n")
    if bad != "0" or total != "10" or key != "1":
        rows = run_psql(
            db_url,
            "SELECT id, owner_id, status, left(content_sha256, 12) FROM documents "
            f"WHERE tenant_id = '{tenant_id}' ORDER BY created_at, id;",
        )
        sys.stdout.write(f"filas del tenant:\n{rows}\n")
        return 1
    return 0


def main() -> int:
    """Punto de entrada de la CLI."""
    parser = argparse.ArgumentParser(description="Invariante del tenant de demo.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report", type=Path, default=DEFAULT_CORPUS_REPORT)
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT_ID)
    parser.add_argument("--demo-key-id", required=True)
    parser.add_argument(
        "--check",
        action="store_true",
        help="ejecuta las consultas contra --db-url o $DATABASE_URL",
    )
    parser.add_argument("--db-url", default=os.environ.get("DATABASE_URL", ""))
    args = parser.parse_args()
    try:
        _, hashes = resolve_hashes(args.manifest, args.report, 58, 71)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    if args.check:
        if not args.db_url:
            sys.stderr.write("error: --check exige --db-url o $DATABASE_URL\n")
            return 2
        try:
            return check_invariant(args.db_url, args.tenant_id, args.demo_key_id, hashes)
        except ValueError as exc:
            sys.stderr.write(f"error: {exc}\n")
            return 2
    sys.stdout.write(render_sql(args.tenant_id, args.demo_key_id, hashes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
