# Revisión previa al desarrollo

Fecha: 2026-10-19. Base revisada: `58cd7ee`, con cambios locales previos en `AGENTS.md` y `CLAUDE.md`.

## Resultado

El diseño mantiene las fases, los proveedores elegidos y los dos niveles de aislamiento.
La documentación concreta los contratos necesarios para implementar la fase 1 y corrige afirmaciones que carecían de evidencia.
La siguiente tarea funcional sigue siendo 1.1; antes hay correcciones acotadas del esqueleto.
La regla 8 queda unificada con la arquitectura y el comportamiento actual del código.

Esta revisión modifica documentación. No incorpora dependencias, endpoints, modelos ni migraciones.
El estado `deleting` pertenece al esquema objetivo de 1.2; todavía no existe una tabla `documents` que migrar.

## Refinamientos aplicados

| Área | Corrección | Validación prevista |
|---|---|---|
| Autorización | El alcance también se aplica a detalle, borrado, PostgreSQL y citas | Matriz con dos tenants, dos owners y documentos compartidos |
| API keys | Entropía, parser, revocación y efecto de rotar la clave HMAC explícitos | Tests de 1.1 |
| Ingesta | `202` tras persistencia; deduplicación concurrente y estado real del duplicado | Tests de 1.2 |
| Fallos | Recuperar `pending` y `processing`; borrar mediante `deleting` sin perder la fila | Fallos entre cada paso, en 1.2 y 1.4 |
| Concurrencia | Una instancia, capacidad acotada y PDFium fuera de hilos concurrentes | Timeout efectivo y pruebas de saturación |
| Búsqueda | Límites, `score_type`, autorización en ramas y coste de obtener rangos | Tests de 1.5 y mediciones de 1.6 |
| BM25 | Embedding documental y de consulta distintos; corpus IDF por espacio autorizado | Prueba de interferencia entre espacios |
| Localizadores | Spans normalizados, convenciones de índices y reconstrucción sin repetir solape | Tests de 1.3 |
| Evaluación | Recall distinto de hit-rate; métricas antes y después del corte; prueba reservada | Ejecución reproducible de 1.7 |
| NLI | Precedencia de contradicción, ventanas, límites y calibración separada | Matriz de confusión en 1.8 |
| Operación | Compatibilidad GPU comprobada, claves fuera del navegador y restauración | Cierre de 1.9 |
| Fase 2 | Presupuesto concurrente, privacidad del fallback y citas autorizadas | Definir contratos al abrir esa fase |

## Regla 8 unificada

[`AGENTS.md`](AGENTS.md) exige `tenant_id` como primer argumento de las funciones públicas de `store.py`, excepto `create_client()` y `ping()`.
Estas dos funciones solo gestionan la conexión y comprueban el servidor; no pueden leer ni escribir documentos o fragmentos.
El roadmap incluye ambas excepciones en el test de arquitectura previsto para 1.5.

## Pendientes antes de continuar

### Corregir el esqueleto

Estos puntos proceden de lectura del código; los tres tests actuales no cubren sus condiciones de fallo.

1. **Liberación de recursos.** En [`main.py`](src/ragmur/main.py), la creación de recursos ocurre antes del `try/finally`.
   Si falla la preparación posterior al motor, la limpieza no se ejecuta; si falla `qdrant.close()`, no se alcanza `engine.dispose()`.
   Registrar cada limpieza al adquirir el recurso y garantizar que las demás se ejecutan si una falla.
   Aplicar el mismo criterio al motor de [`env.py`](src/ragmur/db/migrations/env.py), cuyo `dispose()` queda después de la migración.
2. **Timeouts.** [`Settings`](src/ragmur/core/config.py) acepta valores cero, negativos o no finitos.
   [`store.create_client`](src/ragmur/retrieval/store.py) convierte el valor a entero y pierde fracciones, incluido `0.5 → 0`.
   Validar valores finitos positivos y definir una conversión compatible con el cliente, sin reducir silenciosamente el plazo.

Cada corrección requiere un test que reproduzca el fallo y mantenga la suite de integración existente.

### Preparación local

Los ejecutables `pytest` y `mypy` de `.venv` conservan el intérprete de `/home/cyberdyne/dev/ragmur`, que ya no existe.
La verificación usa `.venv/bin/python -m pytest` y `.venv/bin/python -m mypy`.
Antes de retomar el flujo habitual de comandos, crea un entorno virtual nuevo e instala con `uv sync --locked`.

El repositorio anuncia MIT, pero no contiene `LICENSE`. El roadmap exige añadirlo con titular confirmado antes de publicar.
El Compose actual publica puertos y usa credenciales de desarrollo; el cierre de fase exige una configuración de despliegue privada.

## Verificación realizada

| Comprobación | Resultado |
|---|---|
| Ruff | Sin errores |
| Formato Ruff | 34 ficheros conformes |
| Mypy | Sin errores en 27 ficheros |
| Alembic | `upgrade head` aplica `0001` sobre PostgreSQL temporal |
| Pytest | 3 tests aprobados contra PostgreSQL 17 y Qdrant 1.19 reales |
| Repositorio | Sin cambios de aplicación ni esquema; cambios locales previos conservados |

Los contenedores de comprobación usan puertos locales dinámicos y almacenamiento temporal, sin volúmenes del proyecto.
Los dos contenedores y su red se retiraron después de las pruebas; sus datos temporales se descartaron.
La suite prueba salud y fallo de dependencias. No demuestra aislamiento, calidad de recuperación, NLI ni compatibilidad GPU.

La revisión usa el índice `home-cyberdyne-Projects-ragmur`, generación `2026-10-07T19:05:06Z`, con verificación dirigida de símbolos y llamadas.
La comprobación de cobertura no registra problemas en los 14 ficheros de código consultados; los huecos de alcance son cachés `__pycache__`.
Los ficheros relevantes se contrastan con el código local. La cobertura del grafo es orientativa y no prueba ausencia de errores.

## Fuentes y límites

Context7 no está disponible en esta sesión; las comprobaciones de bibliotecas usan documentación oficial y la instalación local.

- [Qdrant 1.19](https://qdrant.tech/blog/qdrant-1.19.x/#per-tenant-idf-statistics): corpus IDF filtrado, confirmado también en los modelos del cliente local 1.19.0.
- [Query API de Qdrant](https://qdrant.tech/documentation/search/hybrid-queries/): prefetch y fusión nativa.
- [FastEmbed BM25](https://github.com/qdrant/fastembed/blob/main/fastembed/sparse/bm25.py): diferencias entre `embed` y `query_embed` y configuración léxica.
- [PDFium](https://pypdfium2.readthedocs.io/en/stable/python_api.html#incompatibility-with-threading): restricción de concurrencia entre hilos.
- [FastAPI](https://fastapi.tiangolo.com/tutorial/background-tasks/#caveat): alcance de las tareas de fondo.
- [PyTorch 2.12](https://pytorch.org/blog/pytorch-2-12-release-blog/): retirada de la rueda CUDA 12.8 y alternativas para Blackwell.
- [Modelo NLI](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7): evaluación publicada y limitaciones.
- [PyMuPDF](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright): opciones AGPL y comercial.

La revisión no descarga modelos ni mide rendimiento. No atribuye mejoras a una capa sin la evaluación prevista.
