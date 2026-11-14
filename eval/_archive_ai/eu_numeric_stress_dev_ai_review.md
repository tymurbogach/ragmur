# Revisión IA (implementación) del conjunto de estrés numérico dev — PENDIENTE de revisión humana

`eval/eu_numeric_stress_dev_ai_reviewed.yaml` — 68 casos, solo `dev`, NO gold.

## Avisos visibles (leer antes de usar)

- **Etiquetas finales propuestas por IA de implementación, NO gold, NO revisadas por humanos.**
  Cada caso lleva `review_status: pending-human-review`.
- **NO representativo** del dominio ni del uso real. Muestra adversarial diseñada
  después de conocer defectos del prototipo de señal numérica; sobrerrepresenta
  errores conocidos.
- **NO sirve para aceptación ni para calibrar o cambiar umbrales.** Tampoco como
  prueba independiente: el conjunto se construyó conociendo el prototipo.
- **Solo desarrollo.** Los 68 casos son `split: dev`; ningún `document_id` es de test.
  La partición reservada no se ha tocado.
- **La señal numérica NO se ha ejecutado sobre este conjunto. El modelo NLI tampoco.**
- **Fuente inmutable.** `eval/eu_numeric_stress_dev_ai.yaml` y el manifiesto no se
  modifican. Este informe y el YAML revisado son archivos NUEVOS.
- Sin cambios de código, umbrales, roadmap, manifiesto, resultados ni archivos anteriores.
  Sin `TASKS.md`, sin commits, sin subagentes.

## Método

1. Lectura de `AGENTS.md`, `ROADMAP.md`, `ARCHITECTURE.md`, `DECISIONS.md` y `eval/NLI.md`.
2. Lectura completa de los 68 casos originales con premisa, claim, etiqueta y
   justificación propuestas por IA.
3. Revisión caso por caso **solo desde la premisa visible**, sin abrir PDFs de test,
   sin ejecutar la señal numérica ni el NLI, sin inventar fuente.
4. Reglas aplicadas a todos los casos:
   - Una cantidad mínima global no refuta que una parte sea menor (global frente a subconjunto).
   - Un objetivo no demuestra que el hecho ocurrió (objetivo frente a futuro real).
   - Distintos objetos o unidades pueden coexistir (porcentaje frente a euros,
     empleos frente a euros, beneficiarios frente a población total).
   - Un sujeto elíptico no identifica entidad (no nombrar el conflicto).
   - Una fecha límite temprana satisface una posterior con cautela; el límite
     inclusivo (`de aquí a 2032`) requiere lectura explícita.
   - Para `supported` se conserva la modalidad (hasta, al menos, más de, unos,
     alrededor, casi).
   - Para `unsupported` se usan hechos compatibles no inferibles (valor compatible
     no fijado, unidad distinta, entidad distinta, identificador frente a importe).
   - Para `contradicted` se formula la negación explícita de la misma relación de
     la premisa (mismo objeto, misma unidad, misma fecha, misma entidad).
5. Cada caso final conserva `id`, `document_id` dev, `premise_locator` y `premise`
   literales; `ai_proposal` guarda claim, etiqueta y justificación originales de la IA;
   `review_note` da la justificación individual de esta revisión.

## Verificación de fuentes y controles

- Los 68 `id` son únicos; las 68 premisas son idénticas carácter a carácter a las
  originales (comprobación por igualdad de cadenas tras la generación).
- Los 68 son `split: dev`; los 18 `document_id` existen en `eval/eu_manifest.yaml`
  con `split: dev`; **0 documentos de test**, 0 lecturas de test.
- Los 18 `document_id` cubren los 18 PDF dev; al menos un caso por documento.
- Prefijos SHA-256 del manifiesto coinciden con la tabla del informe de trazabilidad
  original (16 hex por documento; comprobados los 18 por programa):
  `736395fe…`, `a43004fd…`, `a0d2cd8c…`, `aaf2a1b7…`, `1fa0183b…`, `f692aa0b…`,
  `7eee7159…`, `bc11dbbe…`, `2acad822…`, `9af3bbaf…`, `b4e46873…`, `a18b60ce…`,
  `6e83d2c4…`, `33740183…`, `f12b6c43…`, `43a17056…`, `186d5adb…`, `06b9b2a8…`.
- Todo `premise_locator` es `{type: page, start, end}` con `1 <= start <= end <= pages`
  del documento según el manifiesto (comprobado por programa).
- Formato compatible con `eval/nli_run.py`: cada caso tiene `id`, `document_id`,
  `split`, `premise` y `claims[{text, label}]`; etiquetas solo
  `supported` / `unsupported` / `contradicted` (sin `weak`).
- Diversidad y origen preservados: mismos 8 `stress_type` y mismos conteos por tipo
  que el original; mismos 18 documentos.

## Adjudicaciones expresas pedidas

- **009** (`a0d2cd8c`, global >300.000 frente a 250.000 del subconjunto):
  `contradicted`→`unsupported`. El global para cinco ámbitos no contradice 250.000
  solo para energía y transporte. Claim compatible, cifra del subconjunto no inferible.
- **012** (`a0d2cd8c`, hospital de Bălți): claim reescrito, sigue `contradicted`.
  La premisa enuncia un **objetivo** (tiene como objetivo construir, 340 camas);
  «tendrá 430 camas» afirma un futuro real y no niega la misma relación.
  Final: «El proyecto tiene como objetivo construir y equipar un hospital regional
  de atención terciaria con una capacidad de 430 camas de hospital» (340 frente a 430).
- **013** (`6e83d2c4`, al menos 42,5 %): `contradicted`→`supported`.
  «Al menos 42,5 %» entails «al menos 24,5 %».
- **017** (`7eee7159`, guerra de seis años): claim reescrito, sigue `contradicted`.
  La premisa no nombra la Segunda Guerra Mundial; el sujeto elíptico no identifica
  entidad. Final: «Esa guerra, que duró seis años, dejó 2 millones de huérfanos»
  (20 frente a 2 millones, misma guerra sin nombrarla).
- **040** (`2acad822`, «de aquí a 2032»): se mantiene `supported` **con cautela**.
  Se adopta lectura inclusiva (en 2032 la exclusión ya rige) y se marca como dudosa;
  si el humano considera ambiguo el límite, descartar el caso.
- **046** (`186d5adb`, 35 % frente a 35 millones): `contradicted`→`unsupported`.
  Porcentaje del presupuesto y euros son unidades distintas que pueden coexistir;
  el fragmento no fija ningún importe de 35 millones.
- **047** (`a43004fd`, 65 millones de euros para 700 000 estudiantes):
  `contradicted`→`unsupported`. Los 700 000 destinatarios no excluyen otra población;
  el claim cruza importe (65 millones) con personas (65 millones de estudiantes)
  sin que el fragmento fije el total de estudiantes.
- **048** (`b4e46873`, 3,4 millones de empleos): `contradicted`→`unsupported`.
  La cifra de empleos no excluye un importe en euros; unidades distintas, el fragmento
  no fija ningún importe.
- **049** (`bc11dbbe`, 1,6 millones): `contradicted`→`unsupported`. El claim
  («1,6 millones de euros asisten a centros privados») está **mal formado**: los euros
  no asisten. La premisa cuenta niños, no euros; sin negación explícita de la misma
  relación.
- **054** (`a43004fd`, >50 millones cultura incluidos >11,5 patrimonio):
  `contradicted`→`unsupported`. Una financiación superior a 11,5 millones para
  patrimonio es compatible con 50 millones (50 > 11,5); el valor exacto no se deriva.
- **066** (`aaf2a1b7`, etiqueta ecológica): claim reescrito, sigue `supported`.
  La actualización corresponde a la **guía** (orientaciones sobre el logotipo), no al
  servicio. Final: «Las orientaciones sobre el logotipo de la etiqueta ecológica de
  la UE se actualizaron en abril de 2025».
- **068** (`06b9b2a8`, ODS 14 / ODS 6): `contradicted`→`unsupported`.
  El apoyo al ODS 14 mediante la regeneración de océanos no excluye que el ODS 6
  también contribuya por esa vía; la atribución exclusiva al ODS 6 no se deriva.

## Cambios aplicados

- `keep` (mismo claim, misma etiqueta): 57 casos.
- `relabel` (mismo claim, distinta etiqueta): 8 casos —
  009, 013, 046, 047, 048, 049, 054, 068.
- `rewrite-claim` (claim corregido sin inventar fuente): 3 casos — 012, 017, 066.
- Distribución final: **27 supported / 23 contradicted / 18 unsupported**
  (original IA: 26 / 31 / 11).
- Por `stress_type` (conteos de casos, sin cambiar el tipo):
  equivalente-formato-es 8, distinta-cantidad 10, cota-inclusiva 8, aproximación 8,
  año-rango 10, unidad-distinta 8, entidad-cruzada 9, independiente-significado 7.
- Etiquetas finales por tipo: equivalente-formato-es 8 supported; distinta-cantidad
  1 supported (013) + 9 contradicted; cota-inclusiva 4 supported + 2 contradicted +
  2 unsupported; aproximación 4 supported + 1 contradicted + 3 unsupported;
  año-rango 7 supported + 3 contradicted; unidad-distinta 3 supported + 1 contradicted
  + 4 unsupported; entidad-cruzada 5 contradicted + 3 unsupported + 1 supported (065
  se mantiene contradicted por negar la misma relación de usuarios del euro);
  independiente-significado 6 unsupported + 1 contradicted (060).

## Exclusiones

- **Excluidos: 0.** Todos los casos producen un par inequívoco tras la revisión sin
  inventar fuente. Criterio: se excluye lo que no pueda corregirse con la premisa
  visible (p. ej. premisa truncada que impida decidir, o claim irreparable sin datos
  externos). Ningún caso llega a ese punto: 049 se conserva como `unsupported` con
  nota de malformación en lugar de excluirse; 040 se conserva con duda explícita
  para decisión humana.

## Dudas que requieren criterio humano antes de medir

1. **040** (límite inclusivo «de aquí a 2032»): si se considera ambiguo, descartar.
2. **049** (claim mal formado): confirmar que `unsupported` con nota basta o
   preferir exclusión en la adjudicación humana.
3. **058** (número gratuito con «algunos operadores pueden cobrar»): se mantiene
   `unsupported`; un lector estricto podría ver contradicción entre «gratuito» y
   «cuesta 800 euros», pero el fragmento no fija precio y el número es un
   identificador, no un importe.
4. **029** («unos 394 000» frente a 250 000 exactos): se mantiene `contradicted`
   por quedar fuera de todo margen razonable de la aproximación; el umbral de
   «margen razonable» es criterio humano.
5. **060** (150 participantes frente a 150 millones): se mantiene `contradicted`
   como negación del tamaño del grupo; si el diagrama admite otra lectura,
   reetiquetar a `unsupported`.
6. Las erratas de extracción se conservan literalmente (`fja`, truncado de 068);
   normalizarlas o no es decisión humana posterior.

## Archivos

- Nuevo: `eval/eu_numeric_stress_dev_ai_reviewed.yaml` (68 casos, SHA pendiente de
  congelar por el orquestador tras su revisión).
- Nuevo: este informe `eval/eu_numeric_stress_dev_ai_review.md`.
- Intactos: `eval/eu_numeric_stress_dev_ai.yaml`,
  `eval/eu_numeric_stress_dev_ai_trace.md`, manifiesto, resultados y código.
