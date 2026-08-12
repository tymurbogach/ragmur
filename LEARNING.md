# LEARNING.md

Índice de conceptos que han aparecido al construir Ragmur. Uno por línea, sin
duplicados. Cada línea se escribe para entenderse suelta, sin el contexto de la
conversación en que salió.

## Proyecto y herramientas

- uv — Programa que instala las librerías del proyecto y el propio Python, y las deja aisladas de las del sistema — pyproject.toml
- pyproject.toml — Fichero único donde se declara el proyecto: sus datos, sus librerías y la configuración de las herramientas — pyproject.toml
- uv.lock — Lista generada con la versión exacta de cada librería instalada, para que otra máquina instale lo mismo — uv.lock
- Layout `src/` — Poner el código en `src/ragmur/` en vez de en la raíz obliga a que los tests usen el paquete instalado y no los ficheros sueltos — src/ragmur/
- `[dependency-groups]` — Sección para las librerías que solo hacen falta al desarrollar (tests, revisores); quien use el proyecto no las recibe — pyproject.toml
- mypy — Revisor de tipos: comprueba antes de ejecutar que no se pasa un texto donde se espera un número. En modo `strict` obliga a declarar el tipo de todo — pyproject.toml
- ruff — Revisor de estilo y errores, y formateador automático del código — pyproject.toml
- Regla ASYNC de ruff — Avisa si dentro de una función `async` hay una llamada que se queda esperando y bloquea el servicio entero — pyproject.toml

## Configuración y arranque

- pydantic-settings — Lee las variables de entorno al arrancar, comprueba que están y que tienen el tipo correcto, y falla ahí si falta alguna — src/ragmur/core/config.py
- `@lru_cache` — Guarda el resultado de una función; sin argumentos, convierte a `get_settings()` en un objeto único por proceso — src/ragmur/core/config.py
- `lifespan` — Bloque de FastAPI que se ejecuta una vez al arrancar y una vez al parar; el único sitio correcto para abrir conexiones y cargar modelos — src/ragmur/main.py
- Fábrica `create_app()` — Construir la aplicación en una función, en vez de dejarla suelta, permite a los tests levantar una instancia limpia por caso — src/ragmur/main.py
- Logging estructurado en JSON — Una línea de JSON por evento, para poder filtrar por campo (`tenant_id`, nivel) con herramientas en vez de leer a ojo — src/ragmur/core/logging.py

## Base de datos

- Motor de SQLAlchemy — Objeto que mantiene un grupo de conexiones abiertas y reutilizables; se crea una vez por proceso, no por petición — src/ragmur/db/session.py
- `expire_on_commit=False` — Evita que SQLAlchemy recargue los objetos tras un `commit()`, recarga que con un motor asíncrono ocurriría fuera del `await` y fallaría — src/ragmur/db/session.py
- `naming_convention` — Fija cómo se llaman índices y restricciones; sin ello PostgreSQL los inventa y Alembic detecta cambios que no existen — src/ragmur/db/models.py
- Alembic — Herramienta de migraciones: cada cambio del esquema es un fichero con `upgrade` y `downgrade`, encadenados por `down_revision` — src/ragmur/db/migrations/
- `run_sync` en env.py — Alembic es síncrono por dentro; abre la conexión con asyncpg y le pasa una vista síncrona de ella — src/ragmur/db/migrations/env.py

## API

- `Depends()` y `Annotated` — Manera de FastAPI de darle a una función lo que necesita, resuelto en cada petición — src/ragmur/api/deps.py
- `response_model` — Declara la forma de la respuesta: FastAPI la valida al salir y la documenta sola — src/ragmur/api/routes/health.py
- `asyncio.gather` — Lanza varias esperas a la vez en lugar de una detrás de otra; dos comprobaciones de 5s tardan 5s y no 10s — src/ragmur/api/routes/health.py
- `asyncio.timeout` — Corta una espera que se alarga demasiado, para que una dependencia colgada no cuelgue también al que pregunta — src/ragmur/api/routes/health.py
