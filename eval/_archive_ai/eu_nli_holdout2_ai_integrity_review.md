# Revisión de integridad — `eu_nli_holdout2_ai_draft.yaml` + `eu_nli_holdout2_ai_trace.yaml`

- Estado: propuesta IA sin revisión humana; **NO es gold**. Esta nota tampoco es adjudicación ni revisión humana: es un informe automático de integridad.
- Alcance: se cotejan manifiesto (`eval/eu_nli_holdout2_manifest_draft.yaml`), los 11 PDF usados en el draft bajo `/tmp/opencode/eu_holdout2/`, y los dos YAML del dataset. No se modifica el dataset ni ningún otro archivo.
- Límites explícitos: no se ejecuta NLI, no se consultan puntuaciones NLI ni resultados de evaluaciones para emitir los juicios. No se afirma revisión humana.

## Método reproducible

1. Conteo y distribución con `yaml.safe_load` sobre el draft (300 registros) y el trace (300 ítems).
2. Hash SHA-256 de cada PDF de `/tmp/opencode/eu_holdout2/*.pdf` comparado con `sha256` del manifiesto y con `source.sha256` del draft.
3. Reproducción mecánica de cada premisa con el código real del proyecto: `extract_pdf(path, max_chars, max_pages, min_chars)` (`src/ragmur/ingestion/extractors/core.py`) + `split_document(..., size=800, overlap=120)` (`src/ragmur/ingestion/chunker.py`). Comparación exacta de `premise` contra `chunk.text`, de `span` contra `(chunk.start, chunk.end)` y de `locator` página contra `chunk.locator`.
4. Búsqueda literal de `U+FFFE`, `U+FFFD`, `NUL` en premisas y en el texto normalizado de cada documento; inspección de `evidence_quote` normalizando espacios/saltos; lectura de `doubts` del trace solo como señal de riesgo declarado por el generador, no como veredicto.
5. Cotejo de `document_id`, `ordinal`, `locator`, `source.title/attribution/license/rights_page`, `chunking.size/overlap` entre draft, trace y manifiesto.

## Hechos verificados

### Cobertura mecánica: 100/100 fragmentos exactos

- 300 registros = **100 fragmentos distintos × 3 afirmaciones** (1 `supported` + 1 `contradicted` + 1 `unsupported` por fragmento). Balance de etiquetas exacto: **100/100/100**.
- Los 100 pares `(premise, span, locator, ordinal)` reproducidos con extractor + troceador reales coinciden al carácter: **0 discrepancias** en texto, span y localizador de página.
- Recuento de chunks reproducido por documento (size 800 / overlap 120): `009305e8`: 293; `0f15700a`: 239; `9a6a89dc`: 187; `d1d3df9b`: 178; `834e4a84`: 118; `68170c3d`: 34; `1f107d76`: 16; `93de16a0`: 16; `fe4eb1b7`: 16; `27473ee8`: 15; `605317ff`: 15. Los ordinales usados están dentro de rango en todos los casos.
- `evidence_quote`: los 300 aparecen en su premisa tras normalizar espacios/saltos de línea (la comprobación ingenua por subcadena falla por los `\n` del chunk, p. ej. `procedimiento de \nconciliación` en `euh2-016`; normalizado, 0 ausencias).
- Consistencia draft↔trace: los 300 `id`/`label`/`evidence_quote` coinciden; ninguna divergencia.

### Manifiesto, hashes y fuentes

- Los 12 PDF del manifiesto existen en `/tmp/opencode/eu_holdout2/` y sus 12 SHA-256 verificados coinciden (`OK` en los 12, incluidos los 11 usados más `af9be9f9`).
- `source.sha256`, `source.title`, `source.license` y `source.rights_page` del draft coinciden con el manifiesto en los registros comprobados (muestra `euh2-001/002/003`; el resto comparte bloque `source` por documento).
- Fuentes: las 12 son publicaciones oficiales de la Unión Europea vía `op.europa.eu` (Oficina de Publicaciones). Licencias declaradas: `CC BY 4.0` (3 docs: `0f15700a`, `834e4a84`, `d1d3df9b`); `Reproducción autorizada` (2: `68170c3d`, `9a6a89dc`); `Reproducción/Reutilización autorizada con indicación [de la fuente]` (6 + `009305e8` con variante `si se indica la fuente`); `af9be9f9` añade `(fines no comerciales)`. Todas incluyen cláusula de excluir elementos de terceros.
- `rights_page` y avisos de extracción del manifiesto son coherentes con lo observado (p. ej. `009305e8` 116 pp / 1 página pobre; `0f15700a` 96 pp / 2 pobres; `834e4a84` 57 pp / 2 pobres).

### Hueco de cobertura: un documento del manifiesto sin items

- **Hecho**: el manifiesto lista 12 documentos; el draft solo usa **11**. `af9be9f9` (*Guía de publicaciones gratuitas de la UE*, 60 pp, 111 407 caracteres extraídos, 168 chunks potenciales) tiene **0 items** en draft y trace.
- Distribución resultante por documento (fragmentos; cada uno ×3): `9a6a89dc` 12, `0f15700a` 12, `009305e8` 12, `d1d3df9b` 11, `834e4a84` 10, `68170c3d` 9, `fe4eb1b7` 8, `1f107d76` 7, `93de16a0` 7, `27473ee8` 6, `605317ff` 6. Total 100.
- **Inferencia**: el muestreo no es proporcional al tamaño (p. ej. `fe4eb1b7` usa 8/16 chunks potenciales ≈ 50 %, mientras `009305e8` usa 12/293 ≈ 4 %). No hay justificación registrada del muestreo ni de la exclusión de `af9be9f9`. Riesgo de sesgo temático: la guía ausente es la única de metacatálogo de publicaciones.

### Distribución temática y de fenómenos

- **Hecho**: el dataset cubre funcionamiento institucional UE (`9a6a89dc`), ICE (`68170c3d`), CultureEU (`0f15700a`), comunicación/visibilidad (`d1d3df9b`), Erasmus (`fe4eb1b7`), manual docente PE (`834e4a84`), 12 lecciones UE (`009305e8`) y 4 fichas Horizonte (`1f107d76`, `93de16a0`, `27473ee8`, `605317ff`).
- **Hecho**: el campo `phenomenon` del draft marca `numeric: true` casi exclusivamente en `unsupported` (≈ 1 por fragmento) y `negation: true` casi exclusivamente en `contradicted`; el trace usa etiquetas `paraphrase / negation / numeric / modality`. Es un diseño 1-fenómeno-por-rol, no una medición.
- No hay preguntas en el artefacto (son pares premisa–afirmación, no QA). Si "preguntas" se refiere a variedad interrogativa, el dataset no la evalúa por construcción.

### Fuga (hechos vs inferencias)

- **Hecho**: los 11 `document_id` del draft son disjuntos de los 24 de `eval/eu_manifest.yaml` (sin solape de ID). El manifiesto holdout2 declara similitud máxima 5-gramas nuevo-vs-previo 0,0183; no se re-ejecutó esa comparación contra los 24 previos en esta revisión.
- **Hecho**: dentro de holdout2, `_pairwise_sim_b2.json` muestra los máximos entre las fichas Horizonte: `1f107d76–93de16a0` 0,073; `27473ee8–93de16a0` 0,0595; `1f107d76–27473ee8` 0,0525. Son valores bajos en 5-gramas pero materialmente superiores al umbral citado contra previos; además las 4 fichas comparten plantilla (Decisión 2011/833/UE, `#HorizonEU`, estructura de ficha) y reutilización literal de párrafos legales.
- **Inferencia**: el riesgo de fuga cruzada previa es bajo por ID y por temática declarada, pero el riesgo de **contaminación intra-holdout** entre fichas Horizonte es real a nivel de plantilla/fraseo (ver `euh2-241` y `euh2-280`: ambas invocan la Decisión 2011/833/UE desde documentos distintos).

### Dependencia: 3 afirmaciones por fragmento

- **Hecho**: cada premisa aparece 3 veces idéntica (una por etiqueta). Las 300 filas no son 300 evidencias independientes sino 100.
- **Inferencia**: cualquier métrica agregada por fila sobreestima el tamaño efectivo; el modelo puede apoyarse en estilo/longitud del fragmento en vez de en la relación premisa–afirmación. El diseño 1-1-1 por fragmento además hace predecible la distribución de etiquetas a nivel de fragmento.

### Riesgos de construcción 100/100/100 y simplicidad (casos concretos)

Patrón general observado (inferencia a partir de los textos, sin NLI):

- `supported` ≈ paráfrasis/copia cercana con el mismo vocabulario del fragmento.
- `contradicted` ≈ negación mínima, cuantificador universal o cifra/lugar cambiado dentro del mismo eje del fragmento.
- `unsupported` ≈ dato externo plausible ausente del fragmento, con frecuencia numérico, fecha, sede o cifra de participantes.

Casos con evidencia:

1. Copia casi literal (`supported` trivial): `euh2-022` — la afirmación reproduce palabra por palabra dos frases del fragmento ("El Parlamento Europeo solo aprueba la gestión… si está satisfecho con el informe anual del Tribunal de Cuentas"). `euh2-001`, `euh2-025` y `euh2-109` siguen el mismo patrón (en `euh2-109` la premisa contiene literalmente "las publicaciones no son responsabilidad de la Comisión").
2. Contradicción por cuantificador universal: `euh2-005` ("Toda la legislación… exige la unanimidad") frente a un fragmento que distingue unanimidad de mayoría cualificada y describe el procedimiento ordinario. Etiqueta defendible, pero la señal es el cuantificador, no el contenido.
3. Contradicción por sustitución mínima en la misma línea: `euh2-029` — el fragmento lista "Lugar: Fráncfort del Meno, Alemania"; la afirmación cambia a "Fráncfort del Meno, Países Bajos". Detección por una sola palabra.
4. `unsupported` world-true pero ausente del fragmento (riesgo de que un revisor con conocimiento externo dude): `euh2-024` ("sede en Luxemburgo") con premisa que no menciona sede — el propio trace lo marca ("afirmación cierta en el mundo real pero ausente del fragmento"); igual `euh2-195` (Croacia 28.º miembro en julio de 2013), `euh2-228`, `euh2-231`, `euh2-261`. El criterio "solo vale lo visible" está declarado, pero estos casos son los más propensos a error de adjudicación humana.
5. Referencia anafórica que exige contexto previo del fragmento: `euh2-169` ("Para este método…") — el referente ("3, 2, 1, conexión") está 15+ líneas antes dentro del mismo chunk; el trace lo reconoce ("el referente… está en el contexto previo"). Los hermanos `euh2-170/171` heredan el riesgo.
6. Cortes que truncan la afirmación vecina: `euh2-250` — el fragmento termina en "hasta 11 euros en" (corte a mitad de frase; el trace lo declara); la afirmación supported usa solo la parte completa ("Normas más sencillas…"), pero el chunk contiene unacola incompleta que un evaluador descuidado podría usar. Igual `euh2-292` ("el concepto… se desplegará en los tres niveles siguientes" con solo 2 visibles; la afirmación usa solo el nivel POLÍTICA) y `euh2-043/044/045` (inicio truncado "ir todas las declaraciones…").

### Fragmentos truncados, tablas, terceros y `U+FFFE`

- Truncamiento por ventana (hecho): por el troceado 800/120 casi todos los chunks empiezan y/o terminan a mitad de frase (p. ej. `euh2-001` "der \ntomar…", `euh2-004` "o se \nrequiere…", `euh2-007` "i la UE no adopta…", `euh2-040` "a \npersona jurídica…", `euh2-133` "cio \npara la acción…"). Es el comportamiento esperado del troceador, no un error de extracción, pero deja afirmaciones apoyadas en oraciones parciales en los bordes. El trace solo declara el truncamiento en `euh2-043/044/045`, `061/062/063`, `094/095/096`, `250/251/252`, `292/293/294`, `298/299/300`; el fenómeno es general.
- Tablas/listas linealizadas (hechos): `euh2-067/068/069` (sectores CultureEU con iconos/colores: "Arquitectura / Oficios artísticos / Patrimonio cultural…" + "© Shutterstock, 2021"); `euh2-079` (ficha HAP4MARBLE con campos "Países participantes / Sector(es) / Fechas / Presupuesto 244 269 EUR" + "Right: HAP4MARBLE © Enrico Sassoni 2016"); `euh2-094` (lista de componentes MRR + URLs); `euh2-223/235` (listas con "•" y cifras "1 400", "3,3 %", "7,5 %/10 %"). Las afirmaciones evitan citar celdas, pero el ruido tabular rodea la evidencia.
- Texto de terceros (hechos): `euh2-031/032/033` incluyen "Las marcas auriculares de las vacas… © ImageGlobe" dentro del chunk sin usarlo en las afirmaciones (el trace lo declara); `euh2-241/242/243`, `262/263/264`, `280/281/282` incluyen créditos de imágenes; `euh2-067` incluye "© Shutterstock, 2021". Cumple la cláusula de exclusión solo porque las afirmaciones no usan ese contenido, pero el chunk lo transporta.
- `U+FFFE` (hecho): el carácter aparece en el texto normalizado de 8/12 documentos (conteo doc-level: `009305e8` 302, `0f15700a` 73, `af9be9f9` 35, resto ≤ 3 salvo los limpios `fe4eb1b7`, `1f107d76`, `93de16a0` con 0). En el draft, 42 premisas contienen `U+FFFE`, concentradas en `0f15700a` (`euh2-091`–`099`: URLs partidas como `cross\ufffeborder-cooperation…`, `recovery\ufffeand-resilience…`) y `009305e8` (`euh2-187`–`213`). No hay `U+FFFD` ni NUL en premisas. Es artefacto del extractor (ligaduras/saltos del PDF), no corrupción del dataset: la premisa reproduce fielmente el chunk. Riesgo menor pero real para evaluación automática ingenua por subcadena (una búsqueda de la URL sin `U+FFFE` no casa).

## Juicio de integridad (inferencias separadas de los hechos)

1. Integridad mecánica **alta**: premisas, spans, ordinales, páginas, hashes, títulos, licencias y `rights_page` verificados son correctos; no se detecta manipulación ni deriva del extractor/troceador.
2. Integridad de diseño **media-baja para NLI exigente**: el triplete 1-1-1 por fragmento con balance 100/100/100, paráfrasis cercanas, negaciones mínimas y `unsupported` externos-ausentes produce un test predecible y con señales léxicas triviales (cuantificadores, cifras, topónimos). Mide más "lectura literal del chunk" que inferencia.
3. Riesgos que piden decisión del orquestador antes de aceptar (no se corrigen en esta nota):
   - ausencia total de `af9be9f9` (12,5 % del manifiesto por documentos; 168 chunks potenciales desperdiciados);
   - dependencia total intra-fragmento (100 evidencias efectivas, no 300);
   - `unsupported` world-true (`euh2-024`, `195`, `228`, `231`, `261`) que tensionan la consigna "solo vale lo visible";
   - anáfora lejana (`euh2-169/170/171`), colas cortadas (`euh2-250`, `292`) y ruido de terceros/tablas/`U+FFFE` documentados arriba.
4. La revisión ciega independiente existe (`eval/eu_nli_holdout2_ai_blind_review.yaml`, 300 entradas con hash de fuente declarado en cabecera); no se ha usado su contenido para este juicio, solo se constata su existencia. La adjudicación final sigue pendiente del orquestador.
