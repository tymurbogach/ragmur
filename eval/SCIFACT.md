# Evaluación de SciFact

SciFact contiene resúmenes científicos y etiquetas de relevancia por documento.
El evaluador compara documentos etiquetados con los fragmentos que recupera Ragmur.
La ejecución mide los componentes internos. No mide HTTP, PostgreSQL ni originales.

## Preparar los datos

Descarga [SciFact de BEIR](https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip) fuera del repositorio.
El SHA-256 del archivo es `536e14446a0ba56ed1398ab1055f39fe852686ecad24a6306c80c490fa8e0165`.
Descomprime el archivo y pasa el directorio `scifact` al evaluador.
El evaluador comprueba las huellas de los archivos antes de cargar los modelos.
La ficha de [BeIR SciFact](https://huggingface.co/datasets/BeIR/scifact) indica la licencia CC BY-SA 4.0.

## Ejecutar

Configura las dependencias y los modelos como para `eval.run`.
El argumento `--output` define el directorio de salida.

```bash
uv run python -m eval.scifact --dataset /ruta/scifact --split train --partition dev --output eval/results/scifact-dev
uv run python -m eval.scifact --dataset /ruta/scifact --split train --partition holdout --output eval/results/scifact-holdout
```

Las consultas que comparten un documento relevante pertenecen a la misma partición.
El corpus completo está disponible para ambas particiones.
La partición `holdout` reserva consultas y fuentes etiquetadas, no documentos excluidos del índice.
El reparto depende de las identidades de los documentos y no de las puntuaciones.

El conjunto oficial `test` ya se inspeccionó durante el diagnóstico inicial.
Por tanto, no es una prueba reservada independiente para estas decisiones.
La partición `holdout` de entrenamiento comparte 40 documentos etiquetados con ese test ya evaluado.
Sus consultas no se han usado en la comparación de desarrollo; sus documentos no son totalmente inéditos.

```bash
uv run python -m eval.scifact --dataset /ruta/scifact --split test --partition all --output eval/results/scifact-test
```

La ejecución usa un tenant temporal en una colección de evaluación separada.
Comprueba el aislamiento entre tenants y usuarios antes de evaluar.
Al terminar, elimina los puntos temporales de ese tenant.
Si el proceso termina de forma abrupta, pueden quedar puntos temporales.
El resumen se guarda como JSON; los resultados por consulta van en `per_query/`.
Git ignora `per_query/`; conserva una copia externa si necesitas comparar consultas individuales.
El resumen registra la revisión completa y la configuración de hilos OMP y MKL.
En un contenedor sin Git, añade `--source-commit` con el SHA completo de la imagen.
El campo `commit_source` distingue una revisión declarada de la detectada por Git.
La revisión detectada no demuestra que el árbol estuviera limpio.
Los empates RRF pueden variar entre ejecuciones; compara varias ejecuciones antes de concluir.

## Interpretar los resultados

Las etiquetas identifican documentos completos, no fragmentos concretos.
El evaluador corta a diez fragmentos y después elimina los documentos repetidos.
Este orden reproduce el corte por fragmentos, pero difiere del ranking oficial por documento de BEIR.
No compares directamente sus cifras con la clasificación oficial de BEIR.

`missing_from_candidates` indica que ningún documento etiquetado apareció entre los 30 candidatos.
`outside_top_10_after_reranking` indica que hubo un candidato etiquetado fuera de los diez fragmentos finales.
Esta categoría no demuestra que el reordenamiento haya causado la pérdida.
Las etiquetas incompletas tampoco demuestran que un documento no etiquetado sea irrelevante.

## Comparación inicial

La comparación de desarrollo usa 627 consultas con modelos reales en la RTX 5080.
La configuración actual encuentra una fuente etiquetada en 547 consultas.
Sin reducción de palabras encuentra una más; gana una y empata en las otras 626.
Con el procesador inglés encuentra una menos; gana cinco y pierde seis frente a la referencia.
Estas diferencias son pequeñas y no justifican cambiar la configuración.
El resumen registra también la cobertura y el orden de los resultados.
No se usó la partición `holdout` para elegir una alternativa.

Antes del reordenamiento se encontró una fuente en 539 consultas; después, en 547.
El reordenamiento recuperó 18 consultas y perdió 10, respecto a los diez primeros fragmentos.
La puntuación media de orden bajó de 0,741 a 0,734 en esta muestra.
Estas cifras describen documentos etiquetados, no la calidad de una respuesta redactada.

## Variación observada

Tres ejecuciones exploratorias del test en la RTX 5080 obtuvieron un hit-rate entre 0,847 y 0,853.
La cifra mide consultas con al menos un documento etiquetado entre los diez fragmentos finales.
Una ejecución reutilizó el índice; las otras lo reconstruyeron.
Las primeras usaron un adaptador temporal y la última usó el evaluador del repositorio.
Por tanto, el intervalo describe estas ejecuciones y no una variabilidad estadística general.
