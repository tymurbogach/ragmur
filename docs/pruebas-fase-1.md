# Pruebas de fase 1: cómo lanzarlas y entenderlas

Una sola orden ejecuta las pruebas de la fase 1, escribe un informe en
español sencillo y pide a un agente que explique los fallos. La nota la
pone siempre un programa; el agente solo explica y su salida nunca cambia
el resultado.

## Las dos órdenes

```sh
# Rápida: estática + puerta sin servicios + 10.000 documentos + defectos.
# Nunca usa Skynet, ni LLM, ni llama al explicador.
scripts/phase1-agent.sh quick

# Completa: todas las etapas (Skynet, GPU) y después el explicador.
scripts/phase1-agent.sh full
```

El código de salida es el de las pruebas (0, 1, 2 o 3), nunca el del
explicador. Si el explicador cae o dice «todo aprobado» con fallos, se
ignora y el código no cambia.

## Lanzar sin estar delante

El script ya impide que el equipo se suspenda mientras trabaja. Para
dejarlo de fondo y marcharse:

```sh
nohup scripts/phase1-agent.sh full > ~/.local/share/ragmur/fase1.log 2>&1 &
```

## Mirar cómo va

- `quick`: trabaja en `eval/results/phase1/per_query/quick-<fecha>/`. Al
  acabar deja `quick.json`, `informe.md` y `fallos-publicos.json`.
- `full`: primero imprime un `run_id`. Con ese identificador:
  - `uv run python -m eval.phase1 status <run_id>` — estado y latido.
  - `uv run python -m eval.phase1 report <run_id>` — resumen JSON y código.
  - Los logs de cada etapa están en el mismo directorio (`static.log`,
    `suite.log`, `nli.log`, `search.log`, `service.log`).
- Repetir `status` cada minuto es suficiente; la shell corta a los 120 s,
  así que conviene un `status` por llamada, sin prisas.

## Parar

```sh
uv run python -m eval.phase1 cancel <run_id>
```

`cancel` mata al trabajador, cierra túneles y retira solo los recursos de
esa ejecución (etiquetados con su `run_id`). Nunca toca el despliegue.

## Entender el resultado

`informe.md` tiene cinco partes, en español sencillo:

1. **Lo que está verde**: etapas que pasaron.
2. **Lo que está rojo**: etapas que fallaron, con el motivo.
3. **No probado**: etapas que no llegaron a ejecutarse.
4. **Fallos ya conocidos**: defectos D1-D8, reproducidos a propósito. Que
   salgan es lo esperado; no bloquean.
5. **Siguiente decisión**: qué hacer según el código.

Códigos: 0 es todo bien. 1 es fallo duro (hay que parar y mirar). 2 es
fallo de infraestructura (hay que reintentar; no dice nada de la
calidad). 3 es fallo de calidad publicado en rojo (se decide en U01).

`fallos-publicos.json` lleva hasta 50 fallos elegidos con semilla fija
(repetible). Solo contiene motivos y detalles sintéticos: nunca texto de
consultas, citas, sellados, secretos ni datos privados.

`explicacion.md` (solo en `full`) es la salida del agente `critica`,
llamado en solo lectura y con plazo. Empieza avisando de que **no cambia
la nota**. Si el agente no responde, el fichero lo dice y la nota sigue
igual.

## Reglas que no se rompen

- El Docker del portátil está prohibido: todo sale con
  `DOCKER_HOST=unix:///nonexistent`. Skynet solo crea recursos
  `ragmur-p1-<run_id>-*`.
- El `quick` nunca llama a `opencode`. El `full` sí, una vez, con plazo, y
  el runner no depende de su éxito.
- Los sellados (conjuntos reservados de evaluación) no se descargan ni se
  evalúan; el paquete público falla cerrado si aparece uno.
