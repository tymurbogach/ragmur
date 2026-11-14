# Protocolo provisional de evaluación por IA para NLI (reserva disjunta)

Estado: **provisional, no aceptado, no cambia la configuración de Ragmur**.
Alcance: fase 1.8. Prepara la revisión humana final; no la sustituye.
Las etiquetas citadas son **propuestas por IA, no revisión humana ni gold**.

Vigentes en `src/ragmur/core/config.py`: `supported=0.75`, `weak=0.5`,
`contradiction=0.75`. El candidato de este documento **no los modifica**.

## 1. Revisión independiente realizada en esta tarea

Esta tarea no generó etiquetas de test, no usó el modelo NLI y no abrió,
descargó ni evaluó el contenido de los 6 documentos test.
Solo releyó puntuaciones dev ya existentes y código vigente.

Fuentes releídas:

- `AGENTS.md`, `ROADMAP.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `eval/NLI.md`.
- `eval/nli_thresholds.py` (política de selección).
- `eval/numeric_signal.py` (prototipo offline, cabecera y criterio exacto).
- `eval/results/nli-ai-294-dev-threshold-exploration-2026-11-13.json` (malla).
- `/tmp/nli-ai-300-dev-details-2026-11-13.json` (300 puntuaciones dev, no versionado).
- `eval/eu_nli_dev_ai_exploratory.yaml` (300 casos dev).

### 1.1 Hashes confirmados

Todos los hashes del informe de exploración coinciden con los ficheros
actuales (comprobación solo lectura con `sha256sum` / `hashlib`):

| Fichero | SHA-256 esperado en el informe | Comprobado |
|---|---|---|
| `/tmp/nli-ai-300-dev-details-2026-11-13.json` | `b55ce7b7416171f90474f8a7cdfc340f8d475586a7879cb453240de8a2638340` | coincide, `n=300` |
| `eval/eu_nli_dev_ai_exploratory.yaml` | `5b0481a91bbae5a46d5a6be016defc7b6f31977f03ac08d3bd28278705e5044d` | coincide |
| `eval/nli_thresholds.py` | `6413151dff59cbab8b5e5fb08713744fdbbda788c73c648bfb7bec21ca252264` | coincide |
| `eval/nli_run.py` | `cbebf5d7dd476bd3c3bd54483dc4c50e22211c4ab32cad91e4b3c27d623c5e6d` | coincide |
| `src/ragmur/verification/nli.py` | `fdae7fce5f322183261455fc5d019c11f7017e91991225295684524ce0096880` | coincide |
| `src/ragmur/core/config.py` | `76418354b5701b0cd0f2a4d15e84771ff354ce31c6b1a546504f74b739607cbc` | coincide |

El dataset dev contiene 300 filas con `split="dev"`, 18 `document_id`
distintos y reparto por etiqueta `100 supported / 99 contradicted /
101 unsupported` antes de exclusiones. Tras excluir los 6 IDs post hoc
restan 294: `98 supported / 95 contradicted / 101 unsupported`.
IDs excluidos: `eu-dev-097, eu-dev-108, eu-dev-109, eu-dev-115,
eu-dev-207, eu-dev-286`. La exclusión se hizo tras ver resultados;
por eso está contaminada y solo es exploratoria.

### 1.2 Política de selección confirmada en código

`eval/nli_thresholds.py::select_support_threshold` exige:

1. Solo filas con `split == "dev"`.
2. Todo candidato `S` cumple `S > weak`.
3. El conjunto dev contiene casos `supported` y no `supported`.
4. Descarta candidatos con `recall_supported < minimum_recall` (aquí `0.5`).
5. Entre los elegibles elige menor `false_support_rate =
   false_supported / expected_not_supported`.
6. En empate elige mayor `recall_supported`; en segundo empate, mayor `S`.

Precedencia aplicada en `summarize` y en `eval/nli_run.py`:
`contradiction >= C → contradicted`; si no,
`entailment >= S → supported`; si no,
`entailment >= W → weak`; si no, `unsupported`.
`false_supported` cuenta `expected != supported` con veredicto
`supported`; `weak` nunca cuenta como respaldo.

### 1.3 Cálculos reproducidos desde los 294 scores

Re cómputo puro con los detalles existentes, sin inferencia nueva,
para `C=0.75`, `W=0.5`:

| `S` | Verdaderos respaldos | Falsos respaldos | `recall` | `false_rate` |
|---|---|---|---|---|
| 0.75 | 92/98 | 1/196 | 0.9388 | 0.0051 |
| 0.85 | 91/98 | 1/196 | 0.9286 | 0.0051 |
| 0.90 | 90/98 | 1/196 | 0.9184 | 0.0051 |
| 0.95 | 78/98 | 1/196 | 0.7959 | 0.0051 |
| 0.97 | 74/98 | 0/196 | 0.7551 | 0.0000 |
| 0.99 | 56/98 | 0/196 | 0.5714 | 0.0000 |

La llamada a `select_support_threshold` con candidatos
`[0.75, 0.85, 0.90, 0.95, 0.97, 0.99]`, `C=0.75`, `W=0.5`,
`minimum_recall=0.5` devuelve `S=0.97` (`recall 74/98=0.7551`,
`false 0/196`). Coincide con `policy_comparison` del informe.
Para todo `C` en `{0.5, 0.6, 0.7, 0.75, 0.8, 0.9}` la política
elige el mismo `S=0.97` sobre estos datos.

La diferencia entre `S=0.75` y `S=0.97` es un único caso:
`eu-dev-223` (`expected=contradicted`, `entailment=0.9609375`,
`contradiction=0.03460693359375`). Para todo `S < 0.97` es el único
falso respaldo; con `S >= 0.97` pasa a `weak` porque `0.9609 < 0.97`
y la contradicción no supera `C`. Subir `S` de 0.75 a 0.97 elimina
ese falso respaldo (1→0) a costa de 18 respaldos verdaderos perdidos
(92→74, caída de recall 0.1837). Los intervalos de Wilson al 95 %
citados en el informe se solapan ampliamente
(p. ej. 1/196 `[0.0009, 0.0283]` frente a 0/196 `[0.0, 0.0192]`);
con etiqueta IA no revisada y exclusión post hoc no hay base para
declarar significación ni mejora validada.

Eje de contradicción con `S` fijo: `C=0.50` da 85/95 contradicciones
verdaderas; `C=0.60/0.70/0.75` dan 83/95; `C=0.80` da 81/95;
`C=0.90` da 75/95. Las falsas contradicciones son constantes en 1
(`eu-dev-090`, `unsupported` con contradicción 0.9424). Subir `C`
solo pierde verdaderas sin reducir falsas en esta malla.

Si estas cifras o el selector no coincidieran en una repetición,
no se fuerza el candidato: se documenta la diferencia (código,
hashes, detalle de entrada) y se detiene la propuesta.

### 1.4 Señal numérica: alcance verificado, sin integración

`eval/numeric_signal.py` declara en su cabecera que es un prototipo
aislado en `eval/`: no altera `src/`, API, veredictos ni umbrales;
solo biblioteca estándar; nunca afirma contradicción; como mucho
marca `needs_review=True`. La lógica de intervalos, unidades,
granularidad de fechas y no atribución número-entidad se leyó en el
fichero; no se reevaluó su corrección semántica caso por caso.

Evidencia de esta tarea (solo lectura y ejecución de tests
existentes, sin cambiar código):

- `tests/eval/test_numeric_signal.py` + `tests/eval/test_numeric_signal_stress_eval.py`:
  recolección 29 + 4 = 33 casos; `uv run pytest ... -q` en este árbol
  muestra 33 aprobados.
- Tras corregir defectos sobre la misma muestra de estrés no se puede
  afirmar validación independiente: medir de nuevo sobre los mismos
  casos no es una reserva nueva.

Por tanto: no se integra al producto, no cambia veredictos de Ragmur
y **no forma parte del protocolo NLI a evaluar** en la reserva.
Cualquier uso futuro requiere su propia evaluación independiente.

## 2. Candidato provisional (solo para evaluar, no vigente)

Si se confirma la revisión anterior, el candidato a contrastar en
reserva es:

- `S_candidato = 0.97`, `W = 0.5`, `C = 0.75`.

Se mantiene `W=0.5` y `C=0.75` por permanecer sin evidencia suficiente
para cambiarlos en estos datos (ver §1.3 y §3). No son una
recalibración: son los vigentes conservados por defecto.

Contraste obligatorio en el informe reservado:

| Configuración | Falso respaldo (dev 294) | Recall supported (dev 294) |
|---|---|---|
| Vigente `0.75/0.5/0.75` | 1/196 (0.0051) | 92/98 (0.9388) |
| Candidata `0.97/0.5/0.75` | 0/196 (0.0000) | 74/98 (0.7551) |
| Coste del cambio | −1 falso | −18/98 respaldos (−0.1837 recall) |

El candidato **NO cambia la configuración de Ragmur ni se declara
aceptado**. Es solo la hipótesis que la reserva debe poner a prueba
contra los vigentes. Aceptar `S=0.97` sobre estos datos sería
sobreajuste a un solo caso con etiqueta IA (`eu-dev-223`) tras una
exclusión post hoc. La incertidumbre es muy alta: datos sintéticos,
etiquetas sin revisión humana, equilibrio artificial y posible
compartición de temas/documentos entre filas.

## 3. Por qué `weak` no se calibra directamente aquí

El corpus dev solo usa etiquetas `supported / unsupported /
contradicted`. No hay clase de referencia para `weak`; la fila de
referencia `weak` de la matriz está vacía por diseño.

Consecuencia en el código vigente: mover `W` (mientras `W < S`) solo
redistribuye `unsupported ↔ weak`. No cambia `false_supported`,
`recall_supported` ni `recall_contradicted`, porque `summarize`
solo distingue `supported` frente a no `supported` y la precedencia
de contradicción va primero. Por eso `W` no es calibrable con estas
referencias y se conserva `W=0.5` sin evaluarlo. Calibrar `weak`
requeriría una definición de referencia propia y revisión humana,
fuera del alcance de este protocolo.

## 4. Protocolo reservado: reglas antes de crear o puntuar

Nada de esta sección se ejecutó en esta tarea. Es el contrato para el
siguiente paso. El orden es obligatorio.

### 4.1 Congelar antes de medir

1. **Documentos test disjuntos por `document_id`.** Ningún documento
   (ni sus fragmentos ni afirmaciones casi duplicadas) cruza entre
   desarrollo y reserva. Se comprueba por `document_id`, no por título
   ni por similitud informal. Los 6 documentos test no se abrieron en
   esta tarea; su contenido no se usa hasta la fase de ejecución.
2. **Referencias construidas y justificadas por IA sin acceso a
   scores NLI ni a resultados por consulta dev.** Quien redacta
   afirmaciones y etiquetas no ve `entailment`/`contradiction`,
   veredictos, matrices ni el caso `eu-dev-223`. Cada referencia lleva
   justificación de evidencia (documento, localizador, cita corta).
3. **Segunda revisión y adjudicación por orquestador antes de
   congelar.** Una segunda pasada IA revisa cada propuesta; los
   desacuerdos van a adjudicación del orquestador con traza
   (`propuesta / revisión / decisión / motivo`). Solo lo adjudicado
   entra al dataset congelado. Esta doble pasada es provisional y no
   es revisión humana ni gold.
4. **Congelar dataset y umbrales.** Fijar el YAML reservado, los dos
   juegos de umbrales a comparar (vigente `0.75/0.5/0.75` frente a
   candidato `0.97/0.5/0.75`) y la política de decisión por escrito.
   Registrar `SHA-256` del dataset, de los detalles de puntuación
   futuros, del código (`nli_run.py`, `nli_thresholds.py`,
   `verification/nli.py`, `core/config.py`), modelo y revisión,
   hardware, commit y estado del árbol. Sin congelación no hay
   ejecución válida.
5. **Una inferencia por par, solo después de congelar.** Ejecutar
   `eval.nli_run` una vez con el candidato como configuración principal
   y guardar las puntuaciones fuera de Git. Calcular la matriz vigente
   como comparación descriptiva a partir de esas mismas puntuaciones,
   sin una segunda inferencia ni selección de umbrales sobre la reserva.
   Publicar matrices, tasa de falso respaldo con intervalo y recalls.
6. **Ausencia de calibración en test.** La reserva no se usa para
   elegir `S`, `W` ni `C`. Si el informe reservado sugiere otro umbral,
   se documenta como hipótesis para una **nueva** evaluación
   independiente, no como cambio.
7. **Si falla, no iterar sobre la misma reserva.** Un resultado
   adverso (falso respaldo alto, recall bajo, o candidato peor que el
   vigente) se documenta y se cierra esa reserva. La siguiente
   hipótesis requiere documentos nuevos y disjuntos, nuevas
   referencias y nuevos hashes. Reutilizar la misma reserva tras ver
   sus resultados la convierte en desarrollo.
8. **Trazabilidad.** Versionar resúmenes por ejecución en
   `eval/results/`; guardar detalles por consulta fuera de Git.
   Conservar `details_sha256`, malla explorada y la lista de
   exclusiones (si las hubiera, con motivo previo, nunca post hoc).

### 4.1.1 Prerregistro de la reserva provisional

Antes de ejecutar el modelo, se fijó
`eval/eu_nli_test_ai_provisional_frozen.yaml` con SHA-256
`6c5559ac70dc556c584de9bcc1a2469515fd54ca6d699e72b1f76956826a1b11`.
Contiene 296 afirmaciones: 100 respaldadas, 100 contradichas y 96
sin respaldo, distribuidas en 100 fragmentos de seis documentos.
Las etiquetas son propuestas por IA y siguen pendientes de revisión humana.

El autor generó 300 propuestas. La primera revisión se descarta como
evidencia de independencia: el orden revelaba un patrón de etiquetas.
Otra sesión revisó los 300 casos con orden aleatorio e IDs opacos.
El orquestador revisó una muestra y los cuatro desacuerdos. Antes de
puntuar se excluyeron `eut-042`, `eut-181`, `eut-246` y `eut-285`
por ambigüedad de contexto, cuantificación u orden temporal.
La revisión ciega no equivale a revisión humana ni garantiza ausencia de errores.

La revisión mezclada tiene SHA-256
`dcd9f2ca3551e2b8058bb32f98c7b7c2a0a086485e3efa8ed77e2a22e75fed87`.
La correspondencia de IDs opacos está en
`eval/eu_nli_test_ai_blind_mapping.yaml`, SHA-256
`98160703c275d69e3ed4cb7bc18d9b9e3676a2fb7db5dd79ccd64bbb9ecbc909`.
El modelo, su revisión, código y umbrales son los de las secciones 1 y 2.
La configuración principal provisional es `0.97/0.5/0.75`; la vigente
`0.75/0.5/0.75` se calcula con los mismos scores como referencia descriptiva.
Los datos de reserva no elegirán entre configuraciones.

Las afirmaciones comparten fragmentos y proceden de solo seis documentos.
Los intervalos de Wilson suponen independencia y son solo descriptivos aquí.
El informe incluirá conteos por documento y por fragmento; no extrapolará
esas cifras a una tasa de producción. La revisión humana sigue pendiente.

### 4.2 Revisión humana final, ciega por caso

- La revisión humana final es ciega a predicciones por caso: el
  revisor no ve veredictos ni scores al juzgar cada referencia.
- Si tras ver resultados se cambian referencias, se deja constancia
  (qué cambió, por qué, con qué hash antes/después) y **no se afirma
  aceptación independiente** sobre el conjunto modificado.
- Solo etiquetas revisadas por humanos pueden sostener el cierre de
  1.8/1.9. Este protocolo y sus métricas IA solo preparan esa
  revisión.

## 5. Límites de inferencia (lectura obligatoria del informe)

- Etiquetas IA sin revisión humana; 6 exclusiones post hoc; análisis
  de 294 no independiente ni representativo.
- Muestra pequeña y equilibrada por diseño; las proporciones
  (98/95/101) no describen uso real. Sin independencia los intervalos
  de Wilson son descriptivos, no inferencia.
- Posible compartición de temas/documentos entre filas; la partición
  por `document_id` en reserva mitiga, no elimina, la dependencia.
- Premisas de ~800 caracteres fuera del régimen XNLI de una frase;
  troceado y dominio (español general) no generalizan a SciFact,
  InferES ni a documentos propios.
- Ninguna cifra de este documento autoriza producción ni cambio de
  configuración. La segunda medición de 1.7 y el cierre de 1.8/1.9
  exigen corpus real, demo y revisión humana según `ROADMAP.md`.

## 6. Reproducibilidad de esta revisión (sin reejecutar el modelo)

Comandos solo lectura usados (no modifican el árbol, no puntúan la
reserva, no generan etiquetas):

```bash
sha256sum /tmp/nli-ai-300-dev-details-2026-11-13.json
# b55ce7b7416171f90474f8a7cdfc340f8d475586a7879cb453240de8a2638340, n=300
uv run pytest tests/eval/test_numeric_signal.py tests/eval/test_numeric_signal_stress_eval.py -q
# 33 aprobados (29 + 4)
```

Re cómputo de la política con `eval/nli_thresholds.py` sobre los
detalles existentes ya puntuados (sin modelo nuevo) reproduce
`S=0.97` para `C=0.75`, `W=0.5`, `minimum_recall=0.5`, con
`0/196` falsos y `74/98` verdaderos frente a `1/196` y `92/98`
con `S=0.75`. Ver §1.3. El detalle del caso único es
`eu-dev-223` (`entailment 0.9609375`, `contradiction 0.03460693359375`).

No se modificaron configuración, código, documentación previa,
datasets ni resultados previos. No se crearon etiquetas de test.
No se usó el modelo NLI. No se abrió contenido test.
