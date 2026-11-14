# Protocolo V2 de evaluación por IA para NLI (segunda reserva disjunta)

Estado: **preregistrado, no ejecutado, no aceptado, no cambia la configuración de Ragmur**.
Alcance: fase 1.8. Prepara la revisión humana final; no la sustituye.
Fecha de preregistro (UTC): 2026-11-13. Este documento se escribió
**antes de explorar o descargar nuevas fuentes** para la segunda reserva.
El manifiesto en borrador `eval/eu_nli_holdout2_manifest_draft.yaml`
documenta su propio orden temporal y el SHA-256 de este protocolo.

Vigentes en `src/ragmur/core/config.py`: `verify_supported_threshold=0.75`,
`verify_weak_threshold=0.5`, `verify_contradiction_threshold=0.75`.
Troceado vigente: `chunk_size=800`, `chunk_overlap=120`.
Modelo NLI vigente: `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`,
revisión `b5113eb38ab63efdd7f280f8c144ea8b13f978ce`.

## 1. Contexto que motiva esta segunda reserva (no es validación de la anterior)

1. Una hipótesis previa con `support=0.97` falló en una reserva provisional
   de seis documentos. Esa reserva está **consumida**: no debe reutilizarse
   para ajustar ni para aceptar umbrales. Reutilizarla tras ver sus
   resultados la convertiría en desarrollo.
2. Volver a evaluar el verificador **vigente** en documentos nuevos es una
   hipótesis motivada después de ver fallar la reserva previa, no una
   validación de esa reserva ni una recuperación de la hipótesis `0.97`.
3. La variante experimental de ventanas de frases elevó contradicciones
   aparentemente falsas y se descarta para producto: **no forma parte**
   de este protocolo.
4. La señal numérica (`eval/numeric_signal.py` y variantes de estrés) es
   solo un experimento offline: **no se integra**, no cambia veredictos
   y **no forma parte** de esta evaluación.
5. Las etiquetas anteriores son propuestas por IA y aún no tienen revisión
   humana. Este protocolo tampoco produce etiquetas humanas.
6. Hay 24 documentos ya usados en `eval/eu_manifest.yaml` (18 dev + 6 de la
   reserva anterior). Ninguno puede repetirse en la segunda reserva,
   ni por identificador, ni por URL canónica, ni por SHA-256, ni como
   reedición o copia sustancial detectada por comparación de texto o
   n-gramas.

## 2. Configuración bajo prueba (única configuración primaria)

La **única** configuración primaria de esta evaluación es el verificador
actual tal como está en producto:

- Premisa: chunk completo (`full-chunk`) según el troceador vigente
  (`800/120`), sin variante de ventanas de frases.
- Umbrales: `supported=0.75`, `weak=0.5`, `contradiction=0.75`.
- Precedencia vigente: `contradiction >= C → contradicted`; si no,
  `entailment >= S → supported`; si no, `entailment >= W → weak`;
  si no, `unsupported`.
- `false_supported` cuenta `expected != supported` con veredicto
  `supported`. `weak` nunca cuenta como respaldo.
- Sin cambios de código, sin cambio de modelo o revisión, sin cambio
  de troceado, sin dependencias nuevas, sin señal numérica.

No hay configuración candidata secundaria. No se compara `0.97` ni
ningún otro umbral en esta reserva. Si el informe sugiriera otro umbral,
se documenta como hipótesis para una **tercera** evaluación con
documentos nuevos, nunca como cambio.

## 3. Criterios existentes (ROADMAP / NLI)

Se aplican los criterios ya fijados, sin redefinirlos aquí:

- Tasa de falso respaldo `<= 0.05`.
- Límite superior del intervalo de Wilson al 95 % para la tasa de
  falso respaldo `<= 0.10`.
- Recall de respaldo `>= 0.5`.
- Matriz de confusión por veredicto (`supported / weak / unsupported /
  contradicted`) frente a etiqueta de referencia
  (`supported / contradicted / unsupported`). La fila de referencia
  `weak` está vacía por diseño: `weak` es un veredicto de Ragmur,
  no una etiqueta de referencia.
- Registro explícito de posibles falsas contradicciones
  (`expected != contradicted` con veredicto `contradicted`).
- Métricas y conteos por documento y por fragmento, además de los
  agregados.
- Limitación por correlación: afirmaciones que comparten fragmento o
  documento no son independientes. El intervalo de Wilson es solo
  **descriptivo** si hay dependencia; no sostiene inferencia a
  producción.

Ninguna cifra de este protocolo autoriza producción, declara aceptación
humana ni cierra 1.8/1.9. Solo etiquetas revisadas por humanos pueden
sostener el cierre. Este protocolo y sus métricas IA solo preparan esa
revisión.

## 4. Procedimiento obligatorio (orden temporal)

1. **Prerregistro.** Este documento existe y su SHA-256 queda registrado
   en el manifiesto en borrador antes de descargar fuentes nuevas.
2. **Fuentes disjuntas.** Solo publicaciones oficiales de la UE en español,
   descargadas de URL oficiales, con licencia CC BY o permiso explícito
   de reutilización verificado en el PDF o ficha oficial, atribución y
   página de derechos. Excluidos imágenes, fotografías o texto de terceros.
   Disjunción por ID, URL canónica y SHA contra `eval/eu_manifest.yaml`;
   exclusión de reediciones o copias sustanciales detectadas por texto
   o n-gramas (o anotación de la duda).
3. **Referencias por IA sin acceso a scores.** Quien redacta afirmaciones
   y etiquetas no ve `entailment`/`contradiction`, veredictos ni matrices.
   Cada referencia lleva justificación de evidencia (documento,
   localizador, cita corta). No se leen ni se producen puntuaciones,
   predicciones NLI ni señal numérica en esta fase.
4. **Segunda revisión y adjudicación por el orquestador antes de congelar.**
   Una segunda pasada IA revisa cada propuesta con orden aleatorio e IDs
   opacos; los desacuerdos van a adjudicación con traza
   (`propuesta / revisión / decisión / motivo`). Solo lo adjudicado entra
   al dataset congelado. Esta doble pasada es provisional y no es
   revisión humana ni gold.
5. **Congelación y hashes.** Se fijan el YAML reservado, la política de
   decisión y la configuración primaria por escrito. Se registran SHA-256
   del dataset, del código (`nli_run.py`, `nli_thresholds.py`,
   `verification/nli.py`, `core/config.py`), modelo y revisión, hardware,
   commit y estado del árbol. Sin congelación no hay ejecución válida.
6. **Un único pase test tras congelar.** Se ejecuta `eval.nli_run` una sola
   vez sobre la reserva. No se eligen umbrales usando esta reserva.
   Se publican matrices, tasa de falso respaldo con intervalo descriptivo
   y recalls. Resúmenes versionados en `eval/results/`; detalles por
   consulta fuera de Git.
7. **Si falla, no iterar sobre la misma reserva.** Un resultado adverso se
   documenta y se cierra esa reserva. La siguiente hipótesis requiere
   documentos nuevos y disjuntos, nuevas referencias y nuevos hashes.
8. **Revisión humana posterior y ciega.** La revisión humana se hace
   después y es ciega a predicciones individuales por caso: el revisor
   no ve veredictos ni scores al juzgar cada referencia. Si tras ver
   resultados se cambian referencias, se deja constancia (qué cambió,
   por qué, hash antes/después) y **no se afirma aceptación
   independiente** sobre el conjunto modificado.

## 5. Prohibiciones explícitas

- No cambiar `src/`, modelo, troceado ni umbrales en esta tarea.
- No añadir dependencias.
- No usar la variante de ventanas de frases.
- No integrar ni ejecutar la señal numérica.
- No leer el contenido de los documentos nuevos para etiquetar fuera
  del procedimiento, y no producir etiquetas, puntuaciones o
  predicciones de casos test en la fase de manifiesto.
- No ejecutar el verificador NLI en esta tarea.
- No reutilizar la reserva anterior para ajustar ni aceptar.
- No declarar aceptación humana ni de producción con etiquetas IA.

## 6. Trazabilidad de este preregistro

- Este fichero se creó antes de descargar ninguna fuente de la segunda
  reserva. La hora de creación del fichero y el orden documentado en el
  manifiesto en borrador lo acreditan.
- El manifiesto en borrador registra el SHA-256 de este protocolo una vez
  escrito, además del SHA-256, URL oficial, URL del PDF, licencia,
  atribución, página de derechos, tamaño, páginas, caracteres extraídos,
  avisos, UUID estable de documento y número de chunks potenciales
  (`800/120`) por documento.
- No se modificó ningún fichero previo, ni roadmap, ni resultados,
  ni datasets.
