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
