# Trampas de PHP a Python

Patrones que se escriben de forma natural viniendo de otro lenguaje y que en Python
son incorrectos, no idiomáticos o directamente peligrosos.

Uso: no recites esta lista. Consúltala cuando el código que acabas de escribir toque
uno de estos puntos, y menciónalo en la nota con el ejemplo concreto del fichero.

**Al explicarlos, no des por sabido el lado de PHP.** El valor de cada entrada está en
el comportamiento de Python, no en la comparación: cuenta qué hace Python y qué pasa
si se escribe de la otra forma. La referencia a PHP es un apunte opcional, no la
explicación.

## Índice

1. [Bloquear el bucle de eventos](#1-bloquear-el-bucle-de-eventos) — el más caro
2. [Argumentos por defecto mutables](#2-argumentos-por-defecto-mutables)
3. [Comprensiones](#3-comprensiones)
4. [Gestores de contexto](#4-gestores-de-contexto)
5. [Corrutina sin await](#5-corrutina-sin-await)
6. [dict para todo](#6-dict-para-todo)
7. [Tipado decorativo](#7-tipado-decorativo)
8. [EAFP frente a comprobarlo todo antes](#8-eafp-frente-a-comprobarlo-todo-antes)
9. [Verdad, falsedad e identidad](#9-verdad-falsedad-e-identidad)
10. [Código a nivel de módulo](#10-código-a-nivel-de-módulo)
11. [Detalles menores](#11-detalles-menores)

---

## 1. Bloquear el bucle de eventos

El error más caro del proyecto, y el más fácil de cometer viniendo de PHP.

```python
@app.post("/v1/search")
async def search(q: str) -> SearchResponse:
    vector = model.encode(q)          # ← 200 ms de CPU dentro de una corrutina
    return await store.query(vector)
```

En PHP-FPM cada petición vive en su proceso: bloquear solo se perjudica a uno mismo.
Aquí hay **un hilo y un bucle de eventos**. Esos 200 ms congelan todas las peticiones
en vuelo, incluido `/health`.

```python
vector = await asyncio.to_thread(model.encode, q)
```

Sospechosos habituales: `time.sleep`, `requests`, cualquier cliente de base de datos
síncrono, y en Ragmur los tres modelos —embeddings, reranker y NLI— que son síncronos
y pesados por naturaleza.

Regla práctica: dentro de un `async def`, cualquier línea que tarde y no lleve
`await` delante es sospechosa.

## 2. Argumentos por defecto mutables

```python
def add_chunk(chunk: str, acc: list[str] = []) -> list[str]:   # ← bug
    acc.append(chunk)
    return acc
```

El valor por defecto se evalúa **una vez al definir la función**, no en cada llamada.
Esa lista es la misma en todas las llamadas y se va llenando entre peticiones. En PHP
un array por defecto se copia y esto no ocurre.

```python
def add_chunk(chunk: str, acc: list[str] | None = None) -> list[str]:
    acc = [] if acc is None else acc
```

## 3. Comprensiones

```python
result = []
for c in chunks:
    if c.text:
        result.append(c.text.strip())
```

```python
result = [c.text.strip() for c in chunks if c.text]
```

Es `array_map` + `array_filter` en una expresión. Existen también para diccionarios
(`{k: v for ...}`) y conjuntos.

Límite: si la lógica no cabe cómoda en una línea, el bucle es más legible. Una
comprensión con dos `for` anidados y un condicional ya no lo es.

## 4. Gestores de contexto

Todo lo que hay que cerrar sí o sí va en un `with`, que es un `try/finally`
empaquetado: se cierra aunque salte una excepción.

```python
f = open(path)
data = f.read()
f.close()          # ← no se ejecuta si read() lanza
```

```python
with open(path) as f:
    data = f.read()
```

Aplica a ficheros, `AsyncSession` de SQLAlchemy (`async with`), locks y semáforos. Una
sesión olvidada abierta retiene una conexión del pool hasta que el recolector pasa por
ahí, que puede ser nunca.

## 5. Corrutina sin await

```python
store.upsert(points)          # ← no hace nada
await store.upsert(points)
```

Distinto de JavaScript: allí la promesa ya está corriendo cuando la recibes y olvidar
el `await` solo pierde el resultado. En Python la corrutina **no empieza** hasta que se
espera o se programa. Sin `await`, la línea no se ejecuta y no salta ningún error;
como mucho un aviso en el log.

## 6. dict para todo

En PHP el array asociativo sirve para todo, así que la traducción directa es usar
`dict` en todas partes. En Python eso tira el tipado y el autocompletado, y mueve los
errores a runtime.

```python
def index(chunk: dict) -> None:
    text = chunk["txt"]        # KeyError en producción
```

Con datos que entran o salen de la API, un modelo Pydantic. Con datos internos, una
`dataclass`. `dict` queda para lo que de verdad es un mapa de claves dinámicas.

## 7. Tipado decorativo

Las anotaciones no se comprueban al ejecutar. Sin `mypy` en CI son un comentario.

Dos hábitos que las vacían de contenido: usar `Any` como escape cuando el tipo
incomoda, y anotar solo los argumentos y no el retorno. `mypy` no se queja de una
función sin anotar; simplemente deja de comprobarla.

Excepción importante: Pydantic y FastAPI **sí** leen las anotaciones en tiempo de
ejecución para validar. En el mismo fichero conviven un tipado que solo existe para
`mypy` y otro que decide si una petición devuelve 422.

## 8. EAFP frente a comprobarlo todo antes

Python prefiere intentar y capturar antes que comprobar de antemano.

```python
if "locator" in payload and payload["locator"] is not None:
    loc = payload["locator"]
else:
    loc = default
```

```python
try:
    loc = payload["locator"]
except KeyError:
    loc = default
```

Las excepciones en Python son baratas y se usan para flujo esperado, no solo para
errores graves. Un `StopIteration` o un `KeyError` capturado es idiomático.

Límite: no envuelvas un bloque grande en `try` para atrapar una sola línea, y captura
la excepción concreta, nunca `except Exception` a secas.

## 9. Verdad, falsedad e identidad

```python
if not results:        # vacío o None
if len(results) == 0:  # innecesario
```

Cuidado con el mismo hábito sobre números: `if not score` es cierto cuando `score` es
`0.0`, que suele ser un valor legítimo. Ahí toca `if score is None`.

`==` compara valor, `is` compara identidad. Con `None` siempre `is None`.

## 10. Código a nivel de módulo

Importar un módulo ejecuta su fichero entero la primera vez. Lo que esté al margen de
una función corre al importar: al arrancar el servidor, al lanzar los tests, al abrir
una shell.

```python
model = SentenceTransformer("BAAI/bge-m3")   # ← 30 s cada vez que algo importe esto
```

Por eso los modelos van con carga perezosa detrás de una función, y las conexiones se
abren en el `lifespan`.

## 11. Detalles menores

- **`snake_case`** en funciones y variables, `PascalCase` en clases. No `camelCase`.
- **Sin getters ni setters.** El atributo es público; si hace falta lógica, `@property`.
- **f-strings** (`f"{a} y {b}"`) en lugar de concatenar con `+`.
- **`self` explícito** como primer argumento de todo método. No hay `$this` implícito.
- **`private` no existe.** Solo la convención `_nombre` para «esto es interno».
- **`is None`, no `== None`.**
- **Rutas con `pathlib.Path`**, no cadenas concatenadas.
