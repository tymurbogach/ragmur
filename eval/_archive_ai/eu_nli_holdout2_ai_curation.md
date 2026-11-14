# Memoria de curaduría — `eval/eu_nli_holdout2_ai_curated.yaml`

- Estado: propuesta IA sin revisión humana; **NO es gold**. Esta nota no es adjudicación ni revisión humana.
- Base: `eval/eu_nli_holdout2_ai_draft.yaml` (300 registros = 100 fragmentos × 3) y `eval/eu_nli_holdout2_ai_integrity_review.md`.
- Protocolo aplicado: `eval/NLI_AI_EVALUATION_PROTOCOL_V2.md` (prerregistrado 2026-11-13, SHA-256 `9687d3ac…` según manifiesto en borrador).
  La curaduría se hace **antes** de puntuar, conforme al punto 4 del protocolo.
- Las dos revisiones de etiquetas coincidieron en 300, según el encargo; esa coincidencia no se usa para seleccionar ni para declarar calidad.
- **No se examinó ninguna evaluación, ni predicciones, ni puntuaciones, ni scores. No se ejecutó NLI** (`eval.nli_run`, verificador, señal numérica o variantes de ventanas). No se leyó `eval/results/`.
- Resultado: `eval/eu_nli_holdout2_ai_curated.yaml` con **279 registros = 93 fragmentos × 3** (93 `supported` / 93 `contradicted` / 93 `unsupported`). Cada registro es copia exacta del borrador: mismo `id`, `document_id`, `split`, `premise`, `claims`, `locator`, `ordinal`, `span`, `source`, `chunking`, `status`, `human_review`, `gold`, `phenomenon`, `note` y `evidence_quote`. No se reescribió ni cambió ninguna etiqueta, afirmación ni premisa.

## 1. Criterio uniforme de exclusión

1. Exclusión **a nivel de fragmento completo**: cada fragmento eliminado retira sus **tres casos** (1 `supported` + 1 `contradicted` + 1 `unsupported`). No se elimina por etiqueta ni por calidad de predicción; el balance de clases se conserva por construcción.
2. Se excluye todo fragmento cuya premisa incluya **créditos de imágenes o de terceros, texto de colofón editorial (ISBN, DOI, pie editorial, fuentes de imágenes) o texto de licencias/derechos de la publicación** (avisos de reutilización, exención de responsabilidad, reserva de derechos sobre imágenes). La afirmación puede evitar ese material y seguir contaminada por transportarlo en la premisa, por lo que el criterio mira la **premisa**, no la afirmación.
3. Se excluye el fragmento con **sujeto potencialmente fuera de fragmento** (`euh2-169/170`, y por uniformidad su hermano `euh2-171`).
4. Se examinan además todos los fragmentos con **ambigüedad genuina o cortes que afecten a la adjudicación del claim**; solo se excluyen los que la afectan. Los defectos de borde que no cambian el significado (truncamientos del troceador `800/120`, tablas linealizadas, `U+FFFE`) **se conservan** y se documentan.
5. No se fuerza ninguna distribución de clases: la resultante (93/93/93) es consecuencia mecánica del criterio por fragmento.

## 2. Decisiones por ID

| Fragmento (3 IDs) | Motivo | Evidencia en la premisa |
|---|---|---|
| `euh2-031/032/033` | Crédito de tercero dentro del cuerpo | `© ImageGlobe` + pie `30 CÓMO FUNCIONA LA UNIÓN EUROPEA` intercalado entre la explicación del TCE y la composición del órgano colegiado |
| `euh2-067/068/069` | Crédito de tercero | `© Shutterstock, 2021` entre la guía de navegación y la lista de sectores CultureEU |
| `euh2-079/080/081` | Crédito de tercero | `Right: HAP4MARBLE © Enrico Sassoni 2016` entre el texto del proyecto y la ficha `Países participantes / Sector(es) / Fechas / Presupuesto` |
| `euh2-241/242/243` | Colofón de licencias/derechos + créditos de terceros | `reutilización de esta publicación`, `Decisión 2011/833/UE`, `Todas las imágenes © Unión Europea, salvo que se indique lo contrario`, `Fuentes de las imágenes: © ivector … stock.adobe.com`, `Iconos © Flaticon — Todos los derechos reservados`, `Print ISBN … doi:10.2777/…` |
| `euh2-262/263/264` | Colofón de licencias/derechos | `Luxemburgo: Oficina de Publicaciones de la Unión Europea, 2021`, `© Unión Europea, 2021`, `Reutilización autorizada, con indicación de la fuente…`, `La Comisión Europea no es responsable de las consecuencias…`, `Decisión 2011/833/UE` |
| `euh2-280/281/282` | Colofón de licencias/derechos + créditos de terceros | `con indicación de la fuente… sin deformar…`, `no es responsable…`, `Decisión 2011/833/UE`, `Todas las imágenes © Unión Europea…`, `Fuentes de las imágenes: ©ivector … © shooarts` |
| `euh2-169/170/171` | Sujeto potencialmente fuera de fragmento | Afirmaciones `Para este método…` / `Este método requiere…` con referente ambiguo: `No se necesita ningún material` aparece bajo `MATERIALES Y RECURSOS NECESARIOS` del método descrito al inicio (`Este método se recomienda en el Itinerario 5…`), mientras el final del mismo chunk enumera `1. 3, 2, 1, conexión…` y repite la cabecera `3, 2, 1, CONEXIÓN`. El antecedente exigido (`169`: cuál es "este método"; `170`: qué método exigiría tabletas) puede estar fuera del fragmento. Se excluyen `169` y `170` según encargo y `171` por uniformidad de fragmento (misma premisa y mismo riesgo heredado). |

Excluidos: **7 fragmentos × 3 = 21 casos**. Retenidos: **93 fragmentos × 3 = 279 casos**.

## 3. Barrido completo de premisas (no solo los ejemplos del informe)

Búsqueda literal sobre las 300 premisas del borrador:

- `©`: 18 casos en 6 fragmentos — exactamente los seis de la tabla (`031`, `067`, `079`, `241`, `262`, `280` por triplicado). Sin otros positivos.
- `Flaticon`, `stock.adobe`, `Todas las imágenes`, `Print ISBN`, `doi:`, `Todos los derechos`: solo `241/242/243`. `shooarts`, `sin deformar`, `con indicación de la fuente`, `reutilización de esta publicación`, `reutilización de los documentos`, `las imágenes`, `no es responsable`: solo `241/242/243`, `262/263/264` y `280/281/282`. `ivector`: `241` + `280`. `Luxemburgo:` / `Oficina de Publicaciones`: solo `262/263/264`. `Right:` / `Enrico Sassoni`: solo `079/080/081`. `ImageGlobe`: solo `031/032/033`. `Shutterstock`: solo `067/068/069`.
- Falsos positivos verificados y **conservados** (vocabulario institucional ordinario, no colofón):
  - `derechos` en `euh2-043/044/045` (derechos de los firmantes), `euh2-184/185/186` (derechos fundamentales), `euh2-217/218/219` (derechos de aduana: `exime del pago de derechos…`, `exentas del pago de derechos`), `euh2-118/119/120` (contenido sustantivo sobre el `derecho de uso` del emblema UE, no colofón editorial). Ninguna de estas premisas contiene créditos, ISBN/DOI, pies editoriales ni avisos de reutilización de la publicación.
  - `licencia` en `euh2-211/212/213` es `Licencia￾tura` (grado académico partido por `U+FFFE`, ver §5), y en `euh2-118/119/120` es contenido sustantivo (licencias del material de comunicación del beneficiario). Se conservan.
  - `autor` en `euh2-055/056/057`, `115/116/117`, `118/119/120`, `205/206/207`, `262/263/264` corresponde a `autoridades nacionales`, `autorizada/autorizaciones` o `autoridades públicas`; solo `262` se excluye, y por su colofón (`§2`), no por esta subcadena.
  - `terceros` en `euh2-247/248/249` es `terceros países` (países no UE en Horizonte Europa), término sustantivo del programa, no texto de terceros. Se conserva.
  - `reproducción` fuera de los tres fragmentos de colofón no aparece como aviso editorial.

## 4. Ambigüedad y cortes: examinados, solo `169/170/171` se excluye

- `euh2-043/044/045` (inicio `ir todas las declaraciones…`), `euh2-061/062/063` (inicio `articipan estrechamente…`), `euh2-094/095/096` (inicio `nciación CultureEU…` + `U+FFFE` en URLs), `euh2-298/299/300` (inicio `ionales de la UE…` + `U+FFFE`): el corte deja oraciones parciales en los bordes, pero cada `evidence_quote` (`se suprimen una vez finalizado`, `respuestas de la Comisión`, `conectividad digital`, `plataforma de resultados`) está en una oración completa interior. El corte **no afecta** a la adjudicación. Se conservan.
- `euh2-250/251/252` (cola `hasta 11 euros en` cortada a mitad de frase) y `euh2-292/293/294` (`tres niveles siguientes` con solo `POLÍTICA` y `PROGRAMACIÓN` visibles): las afirmaciones usan la parte completa (`Normas más sencillas… seguridad jurídica…`; nivel `POLÍTICA…`). `euh2-294` (`El tercer nivel… proyectos…`) se califica `unsupported` precisamente porque el tercer nivel no es visible; el corte no invierte ninguna etiqueta bajo la consigna "solo vale lo visible". Se conservan con esta justificación explícita.
- `euh2-184/185/186` (`Estas actividades…`): el referente (debates, negociar, votar y adoptar resoluciones; familiarizarse con las instituciones) está completo dentro del chunk; no hay ambigüedad genuina. Se conserva.
- Solo `euh2-169/170/171` presenta anáfora lejana con antecedente potencialmente fuera de fragmento (ver tabla). Se excluye.

## 5. `U+FFFE` y caracteres de control

- `U+FFFE`: **42 premisas retenidas** (14 fragmentos × 3), concentradas en `0f15700a` y `009305e8`:
  `euh2-091–099` (fragmentos `091/092/093`, `094/095/096`, `097/098/099`: URLs `cross￾border`, `recovery￾and-resilience`, `business￾economy`),
  `euh2-187–219` salvo huecos (fragmentos `187–189`, `196–198`, `199–201`, `202–204`, `205–207` (`principa￾les`, `autori￾dades`), `208–210`, `211–213` (`millo￾nes`, `signi￾fica`, `Licencia￾tura`), `214–216`, `217–219` (`importa￾ciones`, `preferen￾cias`, `princi￾pales`)),
  `euh2-277/278/279` y `euh2-298/299/300` (`Horizonte￾Interreg`).
  Es artefacto del extractor (ligaduras/saltos del PDF); la premisa reproduce fielmente el chunk y el defecto **no cambia el significado** del contenido institucional. Se conserva y se enumera aquí. Ningún fragmento excluido contenía `U+FFFE`, por lo que el conteo es idéntico en borrador y curado.
- `U+FFFD`: 0 premisas. `NUL`: 0 premisas.

## 6. Verificación del subset

- IDs: 279 identificadores únicos, formato `euh2-NNN`, todos presentes en el borrador; 21 IDs excluidos listados en la cabecera del YAML y en `§2`. Subset estricto: cada registro curado es igual al objeto del borrador (comparación registro a registro, 0 diferencias).
- Etiquetas: 93 `supported` + 93 `contradicted` + 93 `unsupported`; una afirmación por registro; etiquetas válidas para `eval/nli_run.py --require-document-id`.
- `split`: 279 `test`, 0 `dev`. Sin mezcla de particiones dentro del fichero.
- Fuentes y hashes: los 11 `document_id` del curado existen en `eval/eu_nli_holdout2_manifest_draft.yaml` y cada `source.sha256` coincide con el manifiesto (0 discrepancias en los 279 registros; comprobación por `document_id`). Los 12 SHA-256 del manifiesto están verificados contra los PDF en el informe de integridad (12 `OK`).
- Disjunción dev/test: los 11 `document_id` del curado son disjuntos de los 24 de `eval/eu_manifest.yaml` (18 `dev` + 6 `test`): 0 solapes por ID, URL canónica o SHA-256. Similitud máxima de 5-gramas nuevo-vs-previo `0,0183` citada del manifiesto (no re-ejecutada en esta curaduría).
- Conteos de fragmentos y documentos:

| doc (`short`) | título abreviado | frags borrador | frags curado | casos curados |
|---|---|---|---|---|
| `9a6a89dc` | Cómo funciona la UE | 12 | 11 | 33 |
| `68170c3d` | Guía ICE | 9 | 9 | 27 |
| `0f15700a` | CultureEU | 12 | 10 | 30 |
| `d1d3df9b` | Comunicación/visibilidad | 11 | 11 | 33 |
| `fe4eb1b7` | Erasmus | 8 | 8 | 24 |
| `834e4a84` | Manual PE | 10 | 9 | 27 |
| `009305e8` | 12 lecciones UE | 12 | 12 | 36 |
| `1f107d76` | Horizonte presupuesto | 7 | 6 | 18 |
| `93de16a0` | Horizonte programa | 7 | 6 | 18 |
| `27473ee8` | Horizonte pilar I | 6 | 5 | 15 |
| `605317ff` | Horizonte sinergias | 6 | 6 | 18 |
| `af9be9f9` | Guía publicaciones gratuitas | 0 | 0 | 0 |
| **Total** | 11 docs con items (12 en manifiesto) | **100** | **93** | **279** |

- Validador strict: `validate_cases(…, require_document_id=True)` (misma lógica que `eval/nli_run.py`: IDs únicos, `split` en {`dev`,`test`}, `document_id` obligatorio, premisa no vacía, etiquetas en {`supported`,`unsupported`,`contradicted`}, ningún documento en dos particiones) **pasa** sobre el curado.

## 7. Riesgos y limitaciones que siguen vigentes

1. Cobertura reducida y artificial: 93 fragmentos / 11 documentos tras curar (100/11 en borrador; 12 en manifiesto por la ausencia total de `af9be9f9`, 168 chunks potenciales desperdiciados). Muestreo no proporcional al tamaño (p. ej. `fe4eb1b7` ≈ 50 % de sus chunks frente a `009305e8` ≈ 4 %); sin justificación registrada del muestreo.
2. Dependencia: 3 afirmaciones por fragmento; el tamaño efectivo son 93 evidencias, no 279. El diseño 1-1-1 por fragmento hace predecible la distribución de etiquetas a nivel de fragmento. El intervalo de Wilson es solo descriptivo si hay dependencia; no sostiene inferencia a producción.
3. Simplicidad del diseño 1-fenómeno-por-rol (`supported` ≈ paráfrasis cercana, `contradicted` ≈ negación mínima o sustitución en el mismo eje, `unsupported` ≈ dato externo ausente, a menudo numérico): mide más "lectura literal del chunk" que inferencia. Los `unsupported` world-true (`euh2-024` sede en Luxemburgo, `euh2-195`, `euh2-228/231/261`) siguen tensionando la consigna "solo vale lo visible" y son propensos a error de adjudicación humana.
4. Contaminación intra-holdout entre las 4 fichas Horizonte (plantilla compartida, Decisión 2011/833/UE, `#HorizonEU`, párrafos legales reutilizados; p. ej. `euh2-241` y `euh2-280` invocan la misma Decisión desde documentos distintos). Riesgo bajo de fuga cruzada con los 24 previos por ID y temática, pero real a nivel de fraseo entre fichas.
5. Etiquetas IA sin revisión humana: este curado limpia colofones y un caso anafórico, pero **no convierte el dataset en gold** ni autoriza cambios de configuración, umbrales, modelo, troceado o dependencias. No afirma aceptación humana ni de producción; no cierra 1.8/1.9.

## 8. Trazabilidad

- Solo se crean dos archivos nuevos: `eval/eu_nli_holdout2_ai_curated.yaml` (subset) y esta memoria. Sin cambios a `src/`, configuración, roadmap, manifiestos, borrador, trace, revisiones ni resultados; sin commits.
- Orden temporal del protocolo respetado: prerregistro → fuentes disjuntas → referencias IA sin scores → doble revisión (coincidencia 300/300 constatada, no usada para seleccionar) → esta curaduría documentada → congelación pendiente → un único pase test futuro con `eval.nli_run`.
