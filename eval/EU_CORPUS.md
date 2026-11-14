# Corpus español de publicaciones de la UE

[`eu_manifest.yaml`](eu_manifest.yaml) registra 24 PDF distintos de la Oficina de Publicaciones de la UE.
Cada entrada conserva la ficha oficial, URL del PDF español, atribución, versión descargada, permiso, página de derechos,
SHA-256, tamaño y resultado de extracción de Ragmur.
Los PDF originales permanecen fuera de Git. Sus hashes permiten verificar la versión exacta.

La selección quedó dividida por documento el 12 de noviembre de 2026: 18 publicaciones de desarrollo y seis reservadas.
La partición reservada no se ha evaluado con NLI.
Los 24 archivos son PDF válidos, distintos por hash y menores que el límite de subida de 20 MiB.
Ragmur extrajo texto de todos; cada documento tiene entre 2 y 119 páginas y entre 4 619 y 277 091 caracteres extraídos.
Las advertencias de páginas con poco texto se registran en el manifiesto.

El permiso se comprobó en el texto de cada PDF, en la página indicada por `rights_page`.
Dieciocho indican CC BY 4.0; seis permiten reutilización o reproducción con atribución en términos anteriores.
La atribución identifica a la Unión Europea, la publicación y la Oficina de Publicaciones.
Los elementos con derechos de terceros, especialmente imágenes y fotografías, quedan excluidos de la evaluación y de la demo.
Ragmur solo extrae texto; las futuras anotaciones deben omitir cualquier pasaje atribuido a terceros.
El documento [*El rape en la UE*](https://op.europa.eu/es/publication-detail/-/publication/06d73220-b88a-11f1-81de-01aa75ed71a1/language-es) identifica expresamente una fotografía de EUROFISH.

La [ficha de *Breve guía de la UE*](https://op.europa.eu/es/publication-detail/-/publication/736395fe-fbf9-11f0-8da5-01aa75ed71a1)
sirvió para comprobar el flujo de descarga.
Ragmur extrajo 36 páginas, 41 268 caracteres y 61 fragmentos con tamaño 800 y solape 120.
La huella del PDF consta en el manifiesto.

## Estado de la evaluación

Faltan 300 pares de fragmento y afirmación revisados antes de ejecutar el modelo: 100 respaldados,
100 contradictorios y 100 sin respaldo.
La revisión debe incluir cifras, fechas, negaciones y referencias entre frases; debe registrar desacuerdos.
Solo después se puntúa desarrollo, se fijan los tres umbrales y se abre una vez la reserva.
La selección de fuentes no prueba la calidad del verificador ni la recuperación.

## Protocolo de anotación (pendiente de revisión humana)

Objetivo: producir 300 pares revisados (100 respaldados, 100 contradictorios, 100 sin respaldo)
sin ejecutar aún el modelo sobre el split reservado ni fijar umbrales.

### Cobertura por fenómeno

Cada etiqueta (respaldo, contradicción, neutralidad) debe incluir casos de:

- **Negación:** la afirmación niega o invierte lo que dice el fragmento (p. ej. «no», «nunca», «sin»).
- **Cifras y fechas:** cantidades, porcentajes, plazos, años o fechas que solo cambian en el número.
- **Correferencia:** la afirmación usa un pronombre o descripción («este plazo», «dicha ayuda»)
  cuyo referente solo se resuelve con la frase anterior del documento.

La planilla de anotación registra por par una casilla por fenómeno (sí/no).
Antes de puntuar se comprueba que cada combinación etiqueta × fenómeno tenga ejemplos en desarrollo.

### Definiciones operativas de etiqueta

Se anota la relación entre **un fragmento concreto** (premisa) y **una afirmación** (hipótesis),
no lo que el anotador sepa por otro documento:

- `supported` — el fragmento afirma lo mismo que la hipótesis, con sus cifras y fechas incluidas.
  Un cambio de número o fecha invalida el respaldo.
- `contradicted` — el fragmento afirma algo incompatible con la hipótesis.
  La contradicción prevalece aunque otra frase del mismo fragmento parezca respaldarla.
- `unsupported` — el fragmento no dice nada suficiente sobre la hipótesis.
  La falta de información no es contradicción.

`weak` no se anota: es un veredicto de Ragmur para respaldo bajo umbral, no una cuarta etiqueta humana.
No se anotan pares ambiguos sin resolución (ver desacuerdos).

### Procedimiento y desacuerdos

1. Dos anotadores etiquetan por separado cada par, con el fragmento y la afirmación a la vista.
2. Todo desacuerdo queda registrado con ambas etiquetas y el motivo (cifra, fecha, negación, correferencia, alcance).
3. Un tercer revisor decide la etiqueta final o descarta el par como ambiguo y lo sustituye por otro del mismo fenómeno.
4. No se revisa ni se edita ningún par después de conocer la salida del modelo sobre él.
5. El informe final publica el número de desacuerdos por etiqueta y fenómeno, sin ocultar los descartes.

### Separación por documento

- Todo par lleva `document_id` obligatorio, igual a la clave del documento en `eu_manifest.yaml`.
- Ningún documento aparece en más de una partición (desarrollo o reservada).
- La comprobación anti-fuga exige `document_id` presente: un registro sin `document_id`
  (como ocurre en datos heredados) no es válido para esta evaluación y se rechaza antes de puntuar.
- Afirmaciones casi duplicadas van al mismo documento y, por tanto, a la misma partición.
- La partición reservada (seis documentos) no se anota consultando salidas del modelo.

### Formato estricto de cada par

```yaml
- id: eu-001
  document_id: <clave exacta de eu_manifest.yaml>  # obligatorio, nunca vacío
  split: dev            # dev | test, fijado por documento antes de anotar
  premise_locator: { type: page, start: 4, end: 4 }  # localizador del fragmento
  phenomenon: { negation: false, numeric: true, coreference: false }
  label: supported      # supported | contradicted | unsupported
  note: "qué cifra o fecha decide la etiqueta"
```

Reglas de validación: `document_id` existe en el manifiesto; `split` coincide con la partición
del documento; `label` es una de las tres etiquetas; `phenomenon` lleva las tres casillas.
Este documento solo define el protocolo; no contiene pares ni etiquetas gold.
