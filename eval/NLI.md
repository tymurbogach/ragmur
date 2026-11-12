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
