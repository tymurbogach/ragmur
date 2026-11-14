# Trazabilidad: conjunto de estrés numérico dev con etiquetas propuestas por IA

`eval/eu_numeric_stress_dev_ai.yaml` — 68 casos adversariales de desarrollo.

## Avisos visibles (leer antes de usar)

- **Etiquetas propuestas por IA, NO gold.** Cada caso lleva
  `label_source: ai-proposal (pending-human-review, no gold)` y
  `review_status: pending-human-review`.
- **NO representativo** del dominio ni del uso real. Muestra diseñada a mano
  para revisar la utilidad y los errores de la señal, no para medir calidad.
- **NO sirve para aceptación ni para calibrar o cambiar umbrales.**
- **Solo desarrollo.** Los 68 casos son `split: dev`; ningún `document_id` es
  de test. La partición reservada no se ha tocado.
- **La señal numérica NO se ha ejecutado sobre este conjunto.**
  Queda pendiente de revisión humana previa, como pidió el orquestador.
- **Sin modelo NLI, sin datos de test, sin adaptar ejemplos a resultados del
  prototipo.** Este conjunto se construyó sin leer detalles de NLI y sin
  puntuar nada con modelos.

## Contexto

`eval/numeric_signal.py` es un experimento offline que solo sugiere revisión,
NO decide veredicto. En 300 ejemplos dev post hoc con etiquetas de IA marca
16 de 99 contradicciones y cubre solo 41/300; ese resultado está contaminado
(selección posterior a observar salidas). El orquestador corrigió el manejo de
`1.234,50` y aclaró que la coincidencia de número no verifica entidad
(27 pruebas pasan). Este conjunto NUEVO existe para revisar la señal con casos
distintos a los usados para crear la regla, sin afirmar validación
independiente humana.

## Método (sin LLM en ejecución, sin dependencias nuevas, sin tocar `src/`)

1. Premisas extraídas **literalmente** de la extracción del proyecto
   (`/tmp/opencode/eu_300/shortlist/*.json`, una sentencia por registro con su
   `loc` de página), sin reescribirlas: se conservan incluso erratas de
   extracción (ver ambigüedades).
2. Fuente verificada: los 18 PDF dev de `/tmp/opencode/eu_300` coinciden por
   SHA-256 con `eval/eu_manifest.yaml` (comprobado caso por caso, tabla
   inferior) y tienen permiso de reutilización con atribución comprobado en la
   `rights_page` indicada. Elementos de terceros excluidos (solo se usa texto
   extraído; el documento con fotografía de terceros es de test y no se toca).
3. Deduplicación contra `eval/eu_nli_dev_ai_posthoc.yaml` (300 casos):
   ninguna premisa repite una premisa exacta anterior y ninguna hipótesis
   repite una hipótesis exacta anterior (comprobación por igualdad tras
   normalizar espacios, en el guion de construcción).
4. Hipótesis redactadas para los 8 fenómenos pedidos, decidibles solo con el
   fragmento visible, sin terceros y sin inventar texto de fuente.
5. Congelación: SHA-256 del YAML al final de este informe.

## Verificación de fuentes dev (SHA-256 coincide con el manifiesto)

| document_id (8) | título | rights_p. | licencia | sha256 (16) | bytes |
|---|---|---|---|---|---|
| 736395fe | Breve guía de la UE | 2 | CC BY 4.0 | 784f856adce4c096 | 5043882 |
| a43004fd | La UE en 2025 | 4 | CC BY 4.0 | d736f4f51d17e89d | 14376466 |
| a0d2cd8c | La estrategia Global Gateway | 2 | CC BY 4.0 | 4fe9557df7c8a3ac | 3073249 |
| aaf2a1b7 | La etiqueta ecológica de la UE | 2 | CC BY 4.0 | 0fe7291fc19b5895 | 6631216 |
| 1fa0183b | Opciones de contenido educativo digital | 2 | CC BY 4.0 | 831584fc204df9d5 | 11912712 |
| f692aa0b | IA ética en la enseñanza | 2 | CC BY 4.0 | ab6a2720ed22ba04 | 8552892 |
| 7eee7159 | Europa, mejor juntos | 2 | CC BY 4.0 | 8ae48a1c8387cf7b | 13563542 |
| bc11dbbe | Monitor de la educación y la formación de 2023 | 2 | CC BY 4.0 | 8a34cee6a36447f0 | 1926986 |
| 2acad822 | El presupuesto de Europa | 8 | CC BY 4.0 | 4afc822dea51a1f0 | 1399620 |
| 9af3bbaf | Ficha informativa sanitaria | 5 | reutilización con atribución | 638a33f31f2a1006 | 294817 |
| b4e46873 | Energía limpia para todos los europeos | 2 | reutilización con atribución | 83e77d3b7bc29d2f | 1440560 |
| a18b60ce | Premios a la inspiración rural 2021 | 2 | reutilización con atribución | fe58e88954eb526f | 4748262 |
| 6e83d2c4 | Breve guía de la UE, edición 2024 | 2 | CC BY 4.0 | c259c961bd78e66f | 6970964 |
| 33740183 | El Reglamento de Servicios Digitales explicado | 24 | CC BY 4.0 | a46b03f851a76355 | 12289903 |
| f12b6c43 | Panel europeo de ciudadanos sobre equidad intergeneracional | 2 | CC BY 4.0 | a544f83b0dcebacc | 7808362 |
| 43a17056 | Una Unión que se esfuerza por lograr más resultados | 2 | reutilización con atribución | b1890477003a65a6 | 1311527 |
| 186d5adb | El presupuesto europeo | 2 | CC BY 4.0 | 883cb0084f27bb9c | 157803 |
| 06b9b2a8 | Misión de la UE: restaurar nuestro océano y nuestras aguas | 3 | CC BY 4.0 | 61885815ef16f9c6 | 297781 |

18/18 documentos dev cubiertos, al menos un caso por documento.

## Distribución (diseño adversarial, no equilibrio poblacional)

Etiquetas propuestas por IA: supported 26, contradicted 31, unsupported 11.

| stress_type | n | ids |
|---|---|---|
| equivalente-formato-es | 8 | euns-001–008 |
| distinta-cantidad | 10 | euns-009–018 |
| cota-inclusiva | 8 | euns-019–026 |
| aproximacion | 8 | euns-027–034 |
| ano-rango | 10 | euns-035–042, 066–067 |
| unidad-distinta | 8 | euns-043–050 |
| entidad-cruzada | 9 | euns-051–057, 065, 068 |
| independiente-significado | 7 | euns-058–064 |

Casos por documento: a43004fd 14, a18b60ce 9, 2acad822 9, bc11dbbe 6,
a0d2cd8c 6, b4e46873 5, 6e83d2c4 3, 7eee7159 3, 43a17056 3, 9af3bbaf 2,
186d5adb 2, f12b6c43 1, f692aa0b 1, 1fa0183b 1, 736395fe 1, aaf2a1b7 1,
33740183 1, 06b9b2a8 1.

## Controles previos al congelado (todos pasan)

- 68 ids únicos; 68 premisas literales de sentencias de extracción dev.
- `split: dev` en los 68; `document_id` existe en el manifiesto y es dev.
- `premise_locator` tipo `page` con inicio/fin en los 68.
- 0 premisas idénticas a las 300 de `eu_nli_dev_ai_posthoc.yaml`;
  0 hipótesis idénticas a sus 300 hipótesis.
- 0 documentos de test; 0 lecturas de datos de test; 0 ejecuciones de la
  señal o del modelo NLI sobre este conjunto.
- No se modificó `src/`, ni umbrales, ni configuración, ni código de señal.
  No se añadieron dependencias. No se creó `TASKS.md` ni commits.

## Faltantes y ambigüedades (sin inventar)

1. **Erratas de extracción conservadas literalmente.** Las premisas copian la
   extracción tal cual: `fja` (por «fija», euns-004), `fnanciar`
   (euns-003/008), `proteaginosos`, `as limpias…`. La revisión humana debe
   decidir si se mantienen (fidelidad) o se normalizan.
2. **Premisa truncada euns-068** (06b9b2a8, p3): la extracción termina en
   «…y el». La hipótesis solo usa la primera parte (ODS 14 ↔ regeneración),
   que está completa; se deja constancia del corte.
3. **Premisas compuestas largas** (p. ej. euns-008 con cuatro importes,
   euns-044/056 con varias cifras): la etiqueta se decide por la cifra citada
   en la justificación; otras cifras del mismo fragmento quedan fuera del
   alcance declarado.
4. **Margen de «alrededor/casi/unos» sin definir** (euns-027–034, 031, 033):
   la frontera supported/contradicted/unsupported de una aproximación la debe
   fijar la revisión humana; las etiquetas propuestas son criterio del agente.
5. **Casos límite unsupported/contradicted** (euns-022, 024, 028, 031, 033,
   058–059, 061–064): la distinción entre «compatible pero no fijado»
   y «incompatible» requiere criterio humano, sobre todo con identificadores
   (teléfono 00 800…, reglamentos 2017/745 y 2024/1689, 150 participantes).
6. **Conversiones de unidad** (euns-044: 30 000 km ↔ 30 000 000 m;
   euns-045: casi 60 km ↔ casi 60 000 m): aritmética exacta asumida por el
   agente; validar en revisión.
7. **Doble uso de premisa**: euns-001/021/037 comparten premisa (16-17 de
   Global Gateway) y euns-019/020, 023/024, 027/028/029 también; es
   intencionado (sensibilidad de etiqueta ante la misma evidencia).
8. **«De aquí a 2032» (euns-040)** se lee como inclusivo de 2032; si la
   revisión lo considera ambiguo, el caso debe descartarse o reescribirse.
9. Sin terceros: no se usa contenido atribuido a terceros; el documento con
   fotografía de terceros (rape, test) queda fuera del conjunto.

## Congelado

- Archivo: `eval/eu_numeric_stress_dev_ai.yaml`
- SHA-256: `1e04021963e3112b48a9dec3e972e22622cd7e2d25e850c7ff3dd3141dbd2062`
- 68 casos, 18/18 documentos dev, 26 supported / 31 contradicted /
  11 unsupported propuestos por IA, pendientes de revisión humana.
- La señal numérica NO se ha ejecutado sobre este conjunto.
