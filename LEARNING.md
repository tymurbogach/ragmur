# LEARNING.md

Índice de conceptos que han aparecido al construir Ragmur. Uno por línea, sin
duplicados. Cada línea se escribe para entenderse suelta, sin el contexto de la
conversación en que salió.

- uv — Programa que instala las librerías del proyecto y el propio Python, y las deja aisladas de las del sistema — pyproject.toml
- pyproject.toml — Fichero único donde se declara el proyecto: sus datos, sus librerías y la configuración de las herramientas — pyproject.toml
- uv.lock — Lista generada con la versión exacta de cada librería instalada, para que otra máquina instale lo mismo — uv.lock
- Layout `src/` — Poner el código en `src/ragmur/` en vez de en la raíz obliga a que los tests usen el paquete instalado y no los ficheros sueltos — src/ragmur/
- `[dependency-groups]` — Sección para las librerías que solo hacen falta al desarrollar (tests, revisores); quien use el proyecto no las recibe — pyproject.toml
- mypy — Revisor de tipos: comprueba antes de ejecutar que no se pasa un texto donde se espera un número. En modo `strict` obliga a declarar el tipo de todo — pyproject.toml
- ruff — Revisor de estilo y errores, y formateador automático del código — pyproject.toml
- Regla ASYNC de ruff — Avisa si dentro de una función `async` hay una llamada que se queda esperando y bloquea el servicio entero — pyproject.toml
