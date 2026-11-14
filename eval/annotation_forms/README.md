# Formularios de anotación — piloto EU (20 pares, split dev)

Protocolo: `../EU_CORPUS.md`. Fuente intacta sin etiquetas: `../eu_pilot_candidates.yaml`.

## Archivos

- `annotator_a.yaml` — 20 pares, orden propio de A. Campos por par: `label` (null),
  `phenomenon` (tres null), `rationale` (""). Sin `note` de la fuente.
- `annotator_b.yaml` — mismos 20 pares, orden distinto al de A. Mismos campos vacíos.
- `adjudication.yaml` — una fila por id con `label_a`, `label_b`, `label_final`,
  `rationale_final` vacíos. Sin identidad de revisores ni etiquetas.

## Instrucciones

1. A trabaja solo sobre `annotator_a.yaml`; B solo sobre `annotator_b.yaml`.
   No abráis el formulario del otro ni comentéis pares hasta entregar ambos.
2. Etiqueta válida: `supported` | `contradicted` | `unsupported` (definiciones en `EU_CORPUS.md`).
   Marca los tres fenómenos (true/false) y escribe el motivo en `rationale`.
3. Tras entregar A y B, la coordinación transcribe `label_a`/`label_b` a
   `adjudication.yaml` y pasa a C SOLO los pares en desacuerdo (con ambas
   etiquetas y motivo). C fija `label_final` o `discarded-ambiguous` y lo justifica
   en `rationale_final`. Los pares ambiguos sin resolución se sustituyen por otro
   del mismo fenómeno.
4. Prohibido ejecutar el modelo NLI sobre estos pares hasta completar la anotación.
