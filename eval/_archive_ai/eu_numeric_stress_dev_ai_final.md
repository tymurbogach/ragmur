# Conjunto final de estrés numérico dev — 62 casos, PENDIENTE de revisión humana

`eval/eu_numeric_stress_dev_ai_final.yaml` — 62 casos, solo `dev`, NO gold.

## Avisos visibles (leer antes de usar)

- **Etiquetas propuestas por IA de implementación, NO gold, NO revisadas por humanos.**
  Cada caso lleva `review_status: pending-human-review`.
- **NO representativo** del dominio ni del uso real. Muestra adversarial diseñada
  después de conocer defectos del prototipo de señal numérica; sobrerrepresenta
  errores conocidos.
- **NO sirve para aceptación, ni para calibrar o cambiar umbrales, ni para cerrar fase.**
  Tampoco es prueba independiente: el conjunto se construyó conociendo el prototipo.
- **Solo desarrollo.** Los 62 casos son `split: dev`; ningún `document_id` es de test.
  La partición reservada no se ha tocado.
- **Sin NLI.** El modelo NLI no se ha ejecutado sobre este conjunto para este informe.
- **Fuente inmutable.** `eval/eu_numeric_stress_dev_ai.yaml` y
  `eval/eu_numeric_stress_dev_ai_reviewed.yaml` no se modifican. Este YAML final
  y este informe son archivos NUEVOS.
- Sin cambios de código, umbrales, `src/`, API, modelo ni datasets previos.
  Sin `TASKS.md`, sin commits.

## Origen y exclusiones

Deriva de `eval/eu_numeric_stress_dev_ai_reviewed.yaml` (68 candidatos dev con
etiquetas IA, comprobados texto a texto contra las fuentes). Se conservan 62 casos
literales, sin reescribir ni alterar el resto. Se excluyen exactamente 6 por
ambigüedad, por decisión del orquestador: no son referencias suficientemente claras.

| ID excluido | Motivo registrado |
|---|---|
| euns-013 | Objetivo y cota inferior: «al menos 42,5 %» frente a «al menos 24,5 %»; la inferencia entre cotas no es referencia clara. |
| euns-029 | Aproximación sin margen: «unos 394 000» frente a 250 000 exactos; no hay margen definido para decidir. |
| euns-040 | Límite temporal ambiguo: «de aquí a 2032» con lectura inclusiva dudosa. |
| euns-049 | «Euros asisten» no tiene sentido: claim mal formado («1,6 millones de euros asisten»); los euros no asisten. |
| euns-060 | Diagrama sin relación clara de cantidades: 150 participantes frente a 150 millones en diagrama. |
| euns-066 | Actualización de servicio frente a guía: la fecha corresponde a la guía, el claim original la atribuía al servicio. |

Excluidos: 6. Conservados: 62. Ninguna otra exclusión, reescritura o reetiquetado.

## Verificación del conjunto final

- 62 `id` únicos; 62 `derives_from` idénticos a `id`.
- Los 62 son `split: dev`; 0 casos de test.
- Los 62 bloques son idénticos carácter a carácter a sus homólogos del revisado
  (comparación por igualdad de diccionarios tras la generación; 0 diferencias).
- Los 16 `document_id` existen en `eval/eu_manifest.yaml` con `split: dev`;
  0 documentos de test, 0 lecturas de test.
- Al excluir euns-060 y euns-066 desaparecen sus dos documentos de un solo caso
  (`f12b6c43-a8ce-11f1-b9e5-01aa75ed71a1` y `aaf2a1b7-466e-11f0-b9f2-01aa75ed71a1`);
  el final cubre 16 de los 18 PDF dev del revisado.
- Formato compatible con `eval/nli_run.py`: cada caso tiene `id`, `document_id`,
  `split`, `premise` y `claims[{text, label}]`; etiquetas solo
  `supported` / `unsupported` / `contradicted` (sin `weak`).
- Distribución final por etiqueta IA (sin revisión humana):
  **24 supported / 21 contradicted / 17 unsupported**.
- Por `stress_type`: equivalente-formato-es 8, distinta-cantidad 9,
  cota-inclusiva 8, aproximación 7, ano-rango 8, unidad-distinta 7,
  entidad-cruzada 9, independiente-significado 6.

## Fuentes y hashes (manifiesto, solo dev presentes en el final)

| document_id (8) | título | split | sha256 (16) |
|---|---|---|---|
| 06b9b2a8 | Misión de la UE: restaurar nuestro océano y nuestras aguas | dev | 61885815ef16f9c6 |
| 186d5adb | El presupuesto europeo | dev | 883cb0084f27bb9c |
| 1fa0183b | Opciones de contenido educativo digital | dev | 831584fc204df9d5 |
| 2acad822 | El presupuesto de Europa | dev | 4afc822dea51a1f0 |
| 33740183 | El Reglamento de Servicios Digitales explicado | dev | a46b03f851a76355 |
| 43a17056 | Una Unión que se esfuerza por lograr más resultados | dev | b1890477003a65a6 |
| 6e83d2c4 | Breve guía de la UE, edición 2024 | dev | c259c961bd78e66f |
| 736395fe | Breve guía de la UE | dev | 784f856adce4c096 |
| 7eee7159 | Europa, mejor juntos | dev | 8ae48a1c8387cf7b |
| 9af3bbaf | Ficha informativa sanitaria | dev | 638a33f31f2a1006 |
| a0d2cd8c | La estrategia Global Gateway | dev | 4fe9557df7c8a3ac |
| a18b60ce | Premios a la inspiración rural 2021 | dev | fe58e88954eb526f |
| a43004fd | La UE en 2025 | dev | d736f4f51d17e89d |
| b4e46873 | Energía limpia para todos los europeos | dev | 83e77d3b7bc29d2f |
| bc11dbbe | Monitor de la educación y la formación de 2023 | dev | 8a34cee6a36447f0 |
| f692aa0b | IA ética en la enseñanza | dev | ab6a2720ed22ba04 |

Los 62 textos y los 16 hashes se comprobaron contra las fuentes en la revisión
previa; aquí solo se filtró por ID, sin tocar texto, fuente ni etiqueta.

## Diseño adversarial posterior (límites)

- La muestra se construyó tras ver defectos del prototipo (formato español
  `1.234,50` / `300.000` frente a `300 000`; coincidencia de cifra sin verificar
  entidad). Sobrerrepresenta esos fenómenos a propósito.
- `eval/numeric_signal.py` es aviso offline solo, no veredicto. `reason="match"`
  indica solo coincidencia numérica; no verifica entidad ni significado.
- Una alerta (`needs_review=true`) no es necesariamente falsa porque la referencia
  sea `unsupported`: avisar ante una cifra incompatible con una referencia no
  respaldada puede ser el comportamiento esperado; la etiqueta describe la fuente,
  no la corrección del aviso.

## Archivos

- Nuevo: `eval/eu_numeric_stress_dev_ai_final.yaml` (62 casos).
  SHA-256: `bd803c2acb3de928b6168527d43e86bfce9ab22175de850c6cebbd2c4cae96e5`.
- Nuevo: este informe `eval/eu_numeric_stress_dev_ai_final.md`.
- Intactos: `eval/eu_numeric_stress_dev_ai.yaml` (SHA-256
  `1e04021963e3112b48a9dec3e972e22622cd7e2d25e850c7ff3dd3141dbd2062`),
  `eval/eu_numeric_stress_dev_ai_reviewed.yaml` (SHA-256
  `f469681fb307d99478fd7d6287f394e9f33997eb7dfbb9a4b53243e8edacfc55`),
  manifiesto, resultados, señal (`eval/numeric_signal.py`, SHA-256
  `52b123d05c27409e7f8f8382a38741e4363d9275eea2f7483fa8e58f8e96ff74`)
  y test reservado (no abierto ni puntuado).
