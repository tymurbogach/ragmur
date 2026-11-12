# Evaluación del verificador

`nli_cases.yaml` contiene ejemplos funcionales breves.
`nli_public_cases.yaml` contiene una muestra exploratoria basada en ocho textos públicos de `eval/corpus`.
Cada texto aparece en una sola partición. Las afirmaciones y etiquetas se redactaron manualmente.
Ninguna de las muestras es representativa ni permite calibrar los umbrales.
Una afirmación de prueba se aclaró después de observar el primer resultado.
Por eso, esta partición de prueba tampoco es una reserva independiente.

Para ejecutar la muestra pública con los umbrales actuales:

```bash
uv run python -m eval.nli_run --dataset eval/nli_public_cases.yaml --split dev --output /tmp/nli-public-dev.json
uv run python -m eval.nli_run --dataset eval/nli_public_cases.yaml --split test --output /tmp/nli-public-test.json
```

La muestra tiene cuatro textos y doce afirmaciones por partición.
No incluye ejemplos de referencia para `weak` ni ha tenido revisión independiente.
Las premisas son extractos completos, no fragmentos generados por la ingesta.
Los dos resúmenes de 2026-11-12 registran que se ejecutaron con cambios sin commit.

La tasa de respaldo falso cuenta contradicciones o afirmaciones sin respaldo clasificadas como respaldadas.
El intervalo de Wilson muestra la incertidumbre estadística de esa tasa bajo sus supuestos.
Una muestra pequeña o sesgada no representa necesariamente el uso real.
Con cero errores en ocho ejemplos, el intervalo del 95 % llega aproximadamente al 32,4 %.

Para calibrar hacen falta más documentos y etiquetas revisadas, con particiones por documento.
Incluye negaciones, cifras, fechas, referencias entre frases y ejemplos difíciles.
Mantén los umbrales actuales hasta evaluar cambios con una partición reservada.

## Observación exploratoria

En desarrollo, la premisa sobre el oxígeno sitúa el descubrimiento de Priestley en 1774.
El verificador clasificó la afirmación correspondiente como contradictoria.
La puntuación de contradicción fue 0,975 y la de respaldo 0,021 en CPU.
Este caso muestra un falso rechazo en la muestra; no identifica por sí solo su causa.

## InferES: comparación complementaria en español

[InferES](https://aclanthology.org/2022.coling-1.340/) es un corpus de inferencia en español.
Sus autores, Venelin Kovatchev y Mariona Taulé, publican los datos bajo CC BY 4.0.
La [ficha del conjunto](https://huggingface.co/datasets/venelin/inferes) describe sus anotaciones y límites.
El modelo usado por Ragmur se entrenó con XNLI; no se ha demostrado que InferES sea independiente de todos sus datos de entrenamiento.

La selección usa la revisión `c371a1915e6902b40182b2ae83c5ec7fe5e6cbd2` de InferES.
Descarga `train.csv` y `test.csv` de esa revisión fuera del repositorio.
`eval.inferes` comprueba las huellas SHA-256 antes de leerlos.

```bash
uv run python -m eval.inferes --input /ruta/inferes --output /tmp/inferes-cases.yaml
uv run python -m eval.nli_run --dataset /tmp/inferes-cases.yaml --split dev --output /tmp/inferes-dev.json
```

La selección usa 240 pares de desarrollo y reserva 180 pares de prueba.
Reparte cada partición en tercios entre respaldo, contradicción y neutralidad.
Selecciona como máximo una hipótesis por premisa y excluye la categoría `Automated`.
Desarrollo usa los temas 1–5 del entrenamiento; prueba usa los temas 6 y 10 del test original.
Los temas son disjuntos y se comprueba que las premisas seleccionadas no coincidan exactamente.
El corpus no identifica documentos de origen de forma suficiente para garantizar separación por documento.

Las etiquetas originales identifican tres relaciones. `weak` es un veredicto de Ragmur, no una cuarta etiqueta de InferES.
La matriz conserva esa columna y no inventa ejemplos de referencia `weak`.
Las premisas son generalmente frases, no fragmentos de 800 caracteres de la ingesta.
La revisión manual preliminar detectó una etiqueta discutible en `inferes-2650`.
Se conserva el ejemplo para no seleccionar resultados según su dificultad.
Esta muestra no representa por sí sola el uso real ni justifica calibrar umbrales.

### Primera medición de desarrollo

El 12 de noviembre de 2026 se evaluaron los 240 pares de desarrollo con los umbrales vigentes.
En CPU Intel Core Ultra 9 285H, 15 de 160 pares etiquetados como contradicción o neutral recibieron `supported`.
El resultado y su matriz están en `eval/results/nli-inferes-dev-2026-11-12.json`.
La muestra está equilibrada por diseño; sus proporciones no describen la frecuencia real de esos casos.
El intervalo de Wilson presupone independencia, que compartir temas puede afectar.
El test de 180 pares no se ha evaluado y sigue reservado para una decisión posterior.

La revisión preliminar de nueve ejemplos identificó una etiqueta discutible.
La premisa de `inferes-2650` menciona seis países y la hipótesis una ampliación posterior a nueve.
La premisa no niega necesariamente la hipótesis. No se ha revisado toda la muestra.

## SciFact: evidencia anotada en fragmentos reales

[SciFact](https://github.com/allenai/scifact) incluye afirmaciones y frases de evidencia anotadas.
Sus autores publican las anotaciones bajo CC BY 4.0 y los resúmenes bajo ODC-By 1.0.
Descarga [los datos originales](https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz) fuera del repositorio.
El SHA-256 del archivo descargado es `11c621288d41ac144d29b13b0f8503b3820b7d6e8b1f6ff24dff335c196d76be`.
El adaptador también comprueba las huellas de los archivos utilizados tras extraerlos.

```bash
uv run python -m eval.scifact_nli --input /ruta/data --output /tmp/scifact-nli-cases.yaml
uv run python -m eval.nli_run --dataset /tmp/scifact-nli-cases.yaml --split dev --output /tmp/scifact-nli-dev.json
```

El adaptador aplica el troceador de Ragmur con tamaño 800 y solape 120.
Conserva solo fragmentos que contienen todas las frases de una evidencia anotada.
Agrupa las afirmaciones conectadas por documentos antes de separar desarrollo y prueba.
Selecciona como máximo una afirmación por documento y un documento por afirmación.
La selección tiene 269 pares de desarrollo y 59 de prueba, de 277 a 800 caracteres.

Solo hay etiquetas de respaldo y contradicción. No se generan etiquetas de neutralidad ni `weak`.
La etiqueta original describe la evidencia anotada; el texto adicional del fragmento puede afectar a su interpretación.
Las afirmaciones y documentos ya se usaron para estudiar recuperación, aunque no se evaluaron estas etiquetas del verificador.
El corpus es científico y en inglés; no representa por sí solo documentos generales en español.
La partición de prueba no se ha ejecutado para esta evaluación del verificador.

### Primera medición de fragmentos de desarrollo

El 12 de noviembre de 2026 se evaluaron 269 fragmentos con los umbrales existentes.
En CPU Intel Core Ultra 9 285H se clasificaron como respaldados 6 de 86 casos etiquetados como contradictorios.
De 183 casos etiquetados como respaldados, 93 recibieron `supported`.
El [resumen](results/nli-scifact-chunks-dev-2026-11-12.json) incluye la matriz completa.
Son resultados de desarrollo sobre textos científicos en inglés; no permiten generalizar al español ni a documentos propios.
No se revisó de forma independiente el efecto del contexto adicional en cada etiqueta.

Para revisar errores concretos, añade `--details /tmp/nli-details.json`.
El archivo contiene identificadores, etiquetas, veredictos y puntuaciones, pero no textos.
Guarda los detalles fuera de Git; los resúmenes por ejecución sí se versionan.

En una revisión manual posterior se encontró un desacuerdo claro en `inferes-2633`.
La premisa dice que los reglamentos europeos prevalecen sobre el derecho nacional.
La hipótesis afirma que tienen carácter secundario; el verificador la clasificó como respaldada.
En otros ejemplos, como `inferes-329` y `inferes-6167`, la etiqueta original admite dudas.
Estos ejemplos requieren revisión independiente; no se excluyen de la matriz inicial.

Para explorar el compromiso entre respaldos correctos y falsos sin cambiar Ragmur:

```bash
uv run python -m eval.nli_thresholds --details /tmp/nli-details.json --support 0.75 --support 0.85 --support 0.90 --support 0.95 --support 0.99 --contradiction 0.75 --output /tmp/nli-thresholds.json
```

La comparación conserva la precedencia del umbral de contradicción.
No selecciona un umbral ni sustituye la evaluación de una partición reservada.
