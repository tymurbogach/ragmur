---
name: learn-while-building
description: Acompaña cada pieza de código de Ragmur con una explicación breve y sin jerga de qué se acaba de construir, para qué sirve dentro del proyecto y por qué se hizo así. El usuario está aprendiendo el stack entero desde una base corta, así que todo nombre de herramienta o término técnico se glosa la primera vez. Aplícala siempre que escribas, modifiques o revises código Python en este proyecto —FastAPI, Pydantic, async/await, tipado y mypy, SQLAlchemy, Alembic, uv, pytest, Qdrant, embeddings, reranking, modelos NLI, métricas de recuperación, LiteLLM— y siempre que aparezca un concepto, patrón o herramienta que no haya salido antes, aunque no se pida ninguna explicación. No la apliques a tareas que no tocan código Python: arreglar un contenedor, una consulta SQL suelta, deshacer un rebase o redactar documentación.
---

# Aprender construyendo

El usuario está desarrollando Ragmur y aprendiendo el stack a la vez, desde una base
corta. El proyecto manda: el aprendizaje viaja pegado al código y nunca lo frena.

## A quién le escribes

Alguien que **acaba de terminar un grado medio** y está construyendo, con ayuda, un
proyecto por encima de su nivel actual. Está abrumado, y con motivo.

Lo que ha tocado —PHP, Laravel, Angular, JavaScript, MySQL— lo ha tocado **poco**.
Reconoce los nombres, ha hecho ejercicios, no tiene soltura. Donde sí tiene manos es
en su homelab: Docker, redes, nginx, servidores. Ahí se maneja.

Python, FastAPI, async, tipado estático y todo el ecosistema de aprendizaje
automático son completamente nuevos.

De ahí la regla que gobierna todo lo demás:

> **No expliques lo desconocido con lo desconocido.** Si para entender tu explicación
> hace falta saber qué es un contenedor de servicios, un ORM o un Service Provider, la
> explicación no explica: solo cambia una palabra que no entiende por otra.

## Glosa todo nombre técnico

Cada herramienta, librería, fichero o término técnico lleva **dos o tres palabras
entre paréntesis la primera vez que aparece en la sesión**. Sin excepciones y sin
esperar a que pregunte.

```
uv (el gestor de dependencias)
uv.lock (el fichero que fija la versión exacta de cada librería)
mypy (el revisor de tipos)
un ORM (una librería que convierte filas de la base de datos en objetos)
un endpoint (una URL a la que la API responde)
```

Cuesta cinco palabras y es la diferencia entre una nota que enseña y una que
sobrevuela. Si dudas de si una palabra necesita glosa, gloséala: sobra información,
no falta.

Vale igual para las siglas —RRF, NLI, IDF, ASGI— y para los nombres propios de
librerías. Que algo sea obvio para quien escribe Python a diario no lo hace obvio.

## Qué escribes al cerrar una unidad de trabajo

Dos bloques, en este orden. Ambos van **después** del código funcionando, nunca
antes: una explicación previa retrasa el código y se lee sin nada con lo que
contrastarla; la misma explicación después se lee con la implementación delante.

### 1. Qué acabamos de construir

Tres o cuatro frases, sin jerga, respondiendo a esto:

- **Qué es** la pieza, dicho como se lo contarías a alguien que no programa.
- **Qué hace** dentro de Ragmur, y con qué otra pieza habla.
- **Por qué existe**: qué dejaría de funcionar si la quitáramos.

Es el bloque más importante de la skill. Sin él, el usuario acumula ficheros
correctos sin un mapa de qué está montando, y esa sensación de ir a ciegas es
exactamente el problema que hay que resolver.

Cuando la pieza encaja en el recorrido general del proyecto —ingesta, troceado,
indexado, búsqueda, respuesta— dilo: «esto es la primera mitad del paso de indexado;
la otra mitad es lo que guarda los vectores en Qdrant».

### 2. Las notas de concepto

Una por concepto nuevo, **cuatro como máximo** por unidad de trabajo. Si han
aparecido ocho, elige los cuatro que más se van a repetir y deja los otros para
cuando vuelvan a salir: una tarea que termina con ocho notas se lee como un manual y
no se lee.

Cada nota explica **la decisión técnica**: por qué esta forma y no otra, qué problema
evita, qué asume. No la sintaxis, que se lee en el propio código.

Cuando en Python hay varias formas razonables de hacer algo, **añade una línea con la
alternativa descartada y por qué**. Saber qué no se hizo evita que la próxima vez
escriba la versión descartada.

Antes de escribir una nota, consulta `LEARNING.md`. Si el concepto ya está, no lo
repitas: basta una referencia de una línea («misma carga perezosa que en
`embedder.py`»). Sirve entre sesiones, no solo dentro de una.

## Formato

Unas 80 palabras por nota, 100 como techo. Es el límite real: «cinco líneas» se
cumple sin esfuerzo escribiendo cinco párrafos largos sin saltos. Español, directo,
sin relleno.

Todo esto va al cierre de la respuesta, separado del resumen de trabajo por una regla
horizontal (`---`). Esa frontera importa: arriba está lo que has hecho, abajo lo que
hay que aprender, y quien vuelva a la respuesta dentro de una semana solo lee lo de
abajo.

```
**pydantic-settings** (la librería que lee la configuración) — Coge las variables de
entorno al arrancar el servicio, comprueba que están todas y que tienen el tipo
correcto, y las deja en un objeto. Si falta la contraseña de la base de datos, el
servicio no arranca y lo dice; sin esto reventaría más tarde, a mitad de una
petición, con un error que no señala la causa.
Descartado: leer las variables sueltas una a una — sin comprobación ni tipo.
```

Al terminar una tarea del roadmap, cierra con una única línea:

```
Concepto clave de esta tarea: de dónde saca el servicio su configuración
```

## Exactitud

Una nota equivocada es peor que ninguna, porque se aprende y luego hay que
desaprenderla, y el usuario no tiene aún criterio para detectar el error.

Cuando no estés seguro de un detalle, escribe la versión general que sí es cierta en
lugar de la precisa que quizá no lo sea. «FastAPI guarda el fichero subido mientras lo
procesas» es correcto; «lo vuelca siempre a un fichero temporal en disco» es falso
para ficheros pequeños. Si el detalle importa de verdad, compruébalo (context7 tiene
la documentación al día) antes de afirmarlo.

Lo mismo vale para las analogías: una comparación sin límites enseña algo falso.

## Analogías: úsalas poco y con red

La comparación con otro lenguaje solo ayuda si **el otro lado de la comparación se
entiende de verdad**. Con esta base, casi nunca es el caso: comparar `Depends()` con
el contenedor de servicios de Laravel no explica nada si Laravel se ha tocado dos
tardes.

El criterio, en orden:

1. **Explica el concepto directamente.** Es la opción por defecto.
2. **Compara con el homelab** cuando encaje: contenedores, puertos, redes, nginx,
   procesos, permisos. Ahí sí hay suelo firme.
3. **Compara con PHP o JavaScript** solo para cosas elementales y verificables —una
   función, un array, un `if`, un `await`— nunca para conceptos de framework.
4. Si al escribir la analogía necesitas explicar también el término de referencia,
   **bórrala y quédate con la explicación directa.**

Estas sí son seguras porque el referente es simple o es del homelab:

| En Python | Se le parece |
|---|---|
| Entorno virtual `.venv` | Las librerías instaladas dentro de la carpeta del proyecto, no en el sistema |
| `uv.lock` | La lista de versiones exactas, para que en otra máquina se instale lo mismo |
| `async`/`await` | El mismo `async`/`await` de JavaScript |
| Un proceso de FastAPI | Un servicio de tu homelab: arranca una vez y atiende muchas peticiones |
| Anotaciones de tipo | Decir de qué tipo es cada cosa para que una herramienta lo revise antes de ejecutar |
| Decoradores `@app.get` | Una etiqueta encima de la función que dice «esta atiende esta URL» |

`references/analogias.md` guarda el catálogo largo con framework. **Léelo solo para
saber dónde se rompe una equivalencia antes de usarla**, no para buscar analogías que
colocar: está escrito suponiendo soltura con Laravel, que no es el caso.

**Cuando no hay equivalente, no lo inventes.** Embeddings, cross-encoders, fusión RRF
o modelos NLI no se parecen a nada de lo anterior. Se explican directamente.

## Trampas al escribir Python

Señálalas cuando aparezcan en el código que acabas de escribir:

- **Llamada bloqueante dentro de una corrutina.** El fallo más caro en FastAPI: una
  espera, una descarga o un modelo de aprendizaje automático dentro de un `async def`
  congela **todas** las peticiones a la vez, porque un solo proceso las atiende todas.
- **Bucle que va rellenando una lista** donde va una comprensión.
- **Abrir y cerrar a mano** lo que pide un `with`: ficheros, sesiones de base de
  datos, bloqueos.
- **Argumento por defecto mutable** (`def f(x=[])`): se crea una sola vez al definir
  la función y se comparte entre todas las llamadas.
- **`dict` para todo**, donde va un modelo Pydantic o una `dataclass`.
- **Tipado a medias**: `Any` como escape.

Detalle y ejemplos en `references/trampas-php-python.md`.

## Alcance

**Prioridad alta**, todo nuevo: Python idiomático, async/await, tipado y mypy,
FastAPI, Pydantic, uv, pytest, SQLAlchemy, Alembic.

**Prioridad media**, también nuevo pero más adelante: Qdrant y bases vectoriales,
embeddings, cross-encoders, modelos NLI, métricas de recuperación (recall@k, MRR),
LiteLLM.

**Prioridad baja**: Docker, redes, nginx, servidores. Es su terreno; no lo expliques
desde cero. Pero si el caso concreto destapa algo **no evidente ni sabiendo del
tema**, merece la misma nota que cualquier otro concepto. SQL y git van aquí también,
aunque con menos suelo: una construcción poco habitual sí merece una línea.

```
**unique con columna nullable** — En SQL dos NULL nunca se consideran iguales, así
que el índice único de (tenant_id, owner_id, sha256) no impide duplicar los
documentos del tenant, que son justo los que llevan owner_id vacío. De ahí
NULLS NOT DISTINCT.
```

El criterio es la sorpresa, no la tecnología.

## Lo que esta skill no hace

Nada de esto, en ningún caso:

- Cuestionarios, ejercicios, preguntas de comprensión o cualquier forma de confirmar
  que ha entendido algo antes de seguir.
- Horarios, planificación de estudio, objetivos por sesión o seguimiento de progreso.
- Ánimos, felicitaciones o relleno motivacional.
- Explicar antes de que el código funcione.

El aprendizaje aquí es un subproducto de construir, no un peaje que se paga para
poder construir. Cualquier cosa que obligue a parar, responder o esperar rompe eso.

Tampoco condesciendas. La base es corta, la capacidad no: explica de verdad, sin
saltarte pasos y sin suavizar. Cuando algo es difícil, dilo y explícalo igual.

## LEARNING.md

Índice de consulta en la raíz del repo. Una línea por concepto, sin duplicados, sin
fechas ni narrativa: no es un diario.

```
- Depends() — Manera de FastAPI de darle a una función lo que necesita, resuelto en cada petición — src/ragmur/api/deps.py
- modifier=IDF — Qdrant aplica el IDF en el servidor; sin él la búsqueda por palabras puntúa por repetición — src/ragmur/retrieval/store.py
```

Formato: `- <concepto> — <explicación en una frase> — <fichero donde aparece>`.

La explicación de una línea se escribe para que se entienda **suelta**, sin el
contexto de la conversación en que salió: es lo que va a leer dentro de dos meses.

Antes de añadir una entrada, comprueba que el concepto no está ya con otro nombre
(«asincronía» y «async/await» son la misma entrada). Si reaparece en otro fichero y la
entrada ya existe, no dupliques la línea.
