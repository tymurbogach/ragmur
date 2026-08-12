# Catálogo de analogías

> **Aviso: no uses este fichero como fuente de analogías para las notas.**
>
> Está escrito suponiendo soltura con Laravel y Angular, y el usuario no la tiene.
> Comparar `Depends()` con el contenedor de servicios de Laravel no explica nada a
> quien ha tocado Laravel dos tardes: cambia una palabra desconocida por otra.
>
> Sirve para una sola cosa: **saber dónde se rompe una equivalencia** si estás a punto
> de usarla, y qué explicar en su lugar. La opción por defecto es la explicación
> directa, sin analogía. Ver la sección «Analogías: úsalas poco y con red» de
> `SKILL.md`.

Cada entrada tiene el mismo esquema: equivalencia, y el límite. El límite importa
tanto como la equivalencia: una analogía sin frontera enseña algo falso que hay que
desaprender después.

Cada entrada tiene el mismo esquema: equivalencia, y el límite. El límite importa
tanto como la equivalencia: una analogía sin frontera enseña algo falso que hay que
desaprender después.

## Índice

1. [FastAPI y el ciclo de petición](#1-fastapi-y-el-ciclo-de-petición)
2. [Pydantic y validación](#2-pydantic-y-validación)
3. [SQLAlchemy, Alembic y la base de datos](#3-sqlalchemy-alembic-y-la-base-de-datos)
4. [Async y concurrencia](#4-async-y-concurrencia)
5. [Tipado](#5-tipado)
6. [Herramientas y empaquetado](#6-herramientas-y-empaquetado)
7. [Tests](#7-tests)
8. [Estructura del lenguaje](#8-estructura-del-lenguaje)
9. [Conceptos sin equivalente](#9-conceptos-sin-equivalente)

---

## 1. FastAPI y el ciclo de petición

**`Depends()`** — El contenedor de servicios de Laravel, o los providers de Angular.
Declaras qué necesitas en la firma y el framework lo construye.
*Límite:* no hay contenedor global ni registro previo. La dependencia es la propia
función, resuelta por petición, y se cachea dentro de esa petición pero no entre
peticiones. No existe el equivalente a un singleton `bind()` salvo que lo montes tú.

**`lifespan`** — El `boot()` de un Service Provider: código que corre una vez al
arrancar el proceso y una vez al pararlo.
*Límite:* es el único sitio correcto para cargar modelos de ML. En Laravel cada
petición arranca el framework entero; aquí el proceso vive entre peticiones, así que
lo que cargues en `lifespan` se reutiliza. Esa es toda la razón por la que un modelo
de 2 GB es viable.

**`APIRouter`** — `Route::prefix()` con sus grupos y su middleware.
*Límite:* el router es un objeto que se importa y se monta, no un fichero de rutas
declarativo que el framework descubre solo.

**Middleware** — Idéntico a Laravel: envuelve la petición, puede cortarla.
*Sin límite relevante.* No merece nota propia salvo por la sintaxis async.

**`BackgroundTasks`** — Se parece a `dispatch()` de una cola de Laravel.
*Límite, y es grande:* la tarea corre **en el mismo proceso**, después de enviar la
respuesta. No hay worker, no hay reintentos, no hay persistencia. Un reinicio pierde
lo que estuviera en vuelo — de ahí que el roadmap marque como `failed` los documentos
colgados en `processing` al arrancar. Una cola real (Redis + arq) es otra cosa.

**`HTTPException`** — `abort(404)` de Laravel.
*Límite:* se lanza como excepción normal y FastAPI la traduce; no hay manejador
global que renderice vistas.

**`response_model`** — API Resource de Laravel: define la forma de la salida y filtra
lo que no está declarado.
*Límite:* además valida la salida en tiempo de ejecución. Un campo que no cuadre con
el modelo revienta en tu servidor, no en el cliente. Es deliberado.

---

## 2. Pydantic y validación

**Modelo Pydantic en la firma del endpoint** — `FormRequest`: valida antes de que el
código de negocio se ejecute, y devuelve 422 con el detalle si falla.
*Límite:* el modelo no es solo validación, es **el tipo** del objeto que recibes.
Después de validar tienes una instancia tipada, no un array asociativo. Es más
parecido a un DTO de TypeScript que a un `Request` de Laravel.

**`pydantic-settings`** — `config/*.php` leyendo de `.env`.
*Límite:* la validación ocurre al instanciar la configuración, es decir al arrancar.
Una variable que falta tumba el proceso en el arranque en vez de devolver `null` a
mitad de una petición tres semanas después.

**`Field(...)`** — Las reglas de validación de Laravel (`required|max:255`), pero
como argumentos tipados en lugar de una cadena.

**`model_validate` / `model_dump`** — Hidratar y serializar. Equivale a `fill()` y
`toArray()` de Eloquent.
*Límite:* Pydantic v2 renombró estos métodos respecto a v1 (`parse_obj`, `dict`).
Casi todo lo que hay escrito por internet es de la v1 y no aplica.

---

## 3. SQLAlchemy, Alembic y la base de datos

**Modelo declarativo de SQLAlchemy 2.0** — Se escribe como un modelo de Eloquent.
*Límite, y es el que más cuesta:* no es Active Record. El objeto no sabe guardarse.
No hay `$user->save()`. Los cambios se acumulan en una sesión y se escriben cuando
esa sesión hace `commit()`. Conceptualmente es Doctrine, no Eloquent.

**`AsyncSession`** — La unidad de trabajo. Abre, opera, confirma o revierte.
*Límite:* es también un gestor de contexto (`async with`), y esa es la forma
correcta de usarla. Una sesión que se olvida abierta retiene una conexión del pool.

**Relaciones y carga perezosa** — `hasMany` / `belongsTo` existen igual.
*Límite crítico en async:* la carga perezosa clásica no funciona con `AsyncSession`;
acceder a una relación no cargada intenta ir a la base de datos fuera de contexto y
falla. Hay que pedirla explícitamente (`selectinload`). En Laravel el N+1 es un
problema de rendimiento; aquí es un error en tiempo de ejecución.

**Alembic** — Las migraciones de Laravel.
*Límite:* `upgrade()` y `downgrade()` en vez de `up()` y `down()`, y la cadena de
revisiones es un grafo con `down_revision`, no un orden por nombre de fichero.
Autogenera el diff comparando los modelos con la base de datos real, cosa que
`php artisan` no hace.

---

## 4. Async y concurrencia

**`async` / `await`** — Exactamente el de JavaScript, incluido el modelo mental. Un
solo hilo, un bucle de eventos, y `await` cede el control mientras espera.
*Este es el anclaje correcto: Angular, no Laravel.* PHP-FPM da un proceso por
petición, así que bloquear solo se perjudica a uno mismo. Aquí bloquear congela a
todos.

**Corrutina** — La `Promise` de JS.
*Límite:* una corrutina no empieza a ejecutarse al crearla. En JS la promesa ya está
corriendo cuando la recibes; en Python no pasa nada hasta que la esperas o la
programas. Una corrutina sin `await` es un bug silencioso.

**`asyncio.gather`** — `Promise.all`.

**`asyncio.to_thread` / `run_in_executor`** — No hay equivalente en el mundo PHP.
Es la vía para meter código bloqueante (un modelo de ML, una librería síncrona) en
un servidor async sin congelar el bucle. En Ragmur importa: embeddings, reranker y
NLI son todos síncronos y pesados.

**`asyncio.Semaphore`** — Un límite de concurrencia, como el número de workers de una
cola. Es lo que el roadmap pide para que N subidas simultáneas no compitan por la GPU.

---

## 5. Tipado

**Anotaciones + mypy** — TypeScript. Se comprueban antes de ejecutar, no existen en
tiempo de ejecución.
*Límite:* Python es todavía más laxo que TS. Nadie comprueba nada al ejecutar; si
`mypy` no pasa por CI, el tipado es decorativo. Excepción: Pydantic y FastAPI **sí**
leen las anotaciones en runtime para validar. Son los dos regímenes conviviendo en el
mismo fichero.

**`str | None`** — El `?string` de PHP 8 y el `string | null` de TS.
*Límite:* en Python 3.12 se escribe con `|`. `Optional[str]` es la forma antigua y
significa lo mismo.

**`list[str]`, `dict[str, int]`** — Genéricos, como en TS.
*Límite:* en versiones antiguas se escribían `List[str]` importando de `typing`. En
3.12 sobra.

**`Protocol`** — Una interfaz de PHP, pero estructural: no hay que declarar que la
implementas, basta con tener los métodos. Es el tipado de TS, no el de Java.

---

## 6. Herramientas y empaquetado

**`uv`** — composer, y además el gestor de versiones de Python.
*Límite:* `uv run <cmd>` ejecuta dentro del entorno del proyecto sin activarlo, que
es la razón por la que todos los comandos de `CLAUDE.md` empiezan por `uv run`.

**`pyproject.toml`** — `composer.json`, más la configuración de las herramientas
(ruff, mypy, pytest) que en JS estaría repartida en cinco ficheros de configuración.

**`uv.lock`** — `composer.lock`. Se commitea.

**`.venv`** — El `vendor/` del proyecto: dependencias aisladas por proyecto en lugar
de instaladas en el sistema.

**`ruff`** — ESLint y Prettier fusionados: `ruff check` es el linter, `ruff format`
el formateador.

**Import** — `use` de PHP, o `import` de JS.
*Límite:* importar un módulo **ejecuta** el fichero entero la primera vez. Por eso el
código a nivel de módulo (cargar un modelo, abrir una conexión) es un problema, y por
eso los modelos van con carga perezosa.

---

## 7. Tests

**pytest** — PHPUnit, con menos ceremonia: funciones sueltas con `assert`, sin clase
que herede de nada.

**Fixtures** — `setUp()` y las factories, pero por inyección: declaras el nombre de la
fixture como argumento de la función de test y pytest la construye.
*Límite:* el alcance es explícito (`function`, `module`, `session`), y ahí está la
diferencia de coste entre levantar un contenedor por test o por suite.

**`conftest.py`** — El fichero de fixtures compartidas del directorio. No se importa;
pytest lo descubre por convención, y aplica a todo lo que cuelgue de esa carpeta.

**`monkeypatch` / `unittest.mock`** — Los mocks de PHPUnit. En Ragmur se usan para los
modelos de ML; Qdrant y PostgreSQL van con contenedor real.

---

## 8. Estructura del lenguaje

**Comprensión de lista** — `array_map` y `array_filter` en una sola expresión, con la
legibilidad de un `foreach`. Es la forma por defecto de transformar una colección.

**Gestor de contexto (`with`)** — `try/finally` empaquetado y reutilizable. Ficheros,
sesiones, locks, semáforos: todo lo que hay que cerrar sí o sí.

**Decorador** — Atributo de PHP 8 en la sintaxis, decorador de Angular en el uso, pero
más potente: es una función que envuelve a otra y puede cambiar su comportamiento.

**`dataclass`** — Una clase de datos sin escribir constructor ni getters. Cuando
además hace falta validación, se usa Pydantic en su lugar.

**Generador (`yield`)** — Devuelve elementos de uno en uno sin construir la lista
entera. No tiene equivalente cómodo en PHP, y es lo que permite procesar un documento
grande sin cargarlo entero en memoria.

**No hay `$this` implícito ni visibilidad real.** `self` es explícito y siempre el
primer argumento; `private` no existe, solo la convención del guion bajo inicial.

---

## 9. Conceptos sin equivalente

Aquí no hay analogía que valga. Explícalos directos, con la misma brevedad de
siempre; forzar un paralelismo con Laravel enseña algo falso.

- **Embedding**: un vector que representa el significado de un texto; textos parecidos
  quedan cerca en el espacio.
- **Vector denso frente a disperso**: el denso captura significado, el disperso captura
  qué palabras exactas aparecen. Son complementarios, y por eso Ragmur guarda los dos.
- **BM25 e IDF**: puntuación léxica que premia los términos raros del corpus.
- **Fusión RRF**: combina dos rankings por posición en lugar de por puntuación,
  porque las puntuaciones de coseno y BM25 no son comparables entre sí.
- **Cross-encoder / reranking**: un modelo que lee consulta y fragmento juntos y los
  puntúa. Mucho más preciso y mucho más lento, por eso solo se aplica a los finalistas.
- **Modelo NLI**: clasifica un par (premisa, hipótesis) como entailment, neutral o
  contradiction. Es el mecanismo de `/verify`.
- **recall@k, MRR, nDCG**: recall@k mide si el fragmento correcto entra en la lista;
  MRR y nDCG miden en qué posición queda. Por eso el reranking no mueve recall@k.
- **Carga perezosa de modelos**: cargar un modelo cuesta decenas de segundos y cientos
  de MB; se carga una vez y se reutiliza entre peticiones.
