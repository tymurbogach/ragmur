# Guía mínima — revisión humana ciega de la segunda reserva (1.8)

Estado: las referencias son propuestas sin revisión humana. Esto **no es gold**,
no cierra nada y una sola revisión **no equivale a dos revisores independientes**.

## Qué hacer

1. Lea cada fragmento una sola vez y juzgue sus 3 afirmaciones por separado.
2. En cada `juicio` escriba UNA palabra exacta: `apoyada` | `contradicha` |
   `no dice` | `ambigua`. Deje `comentario` vacío o con una duda breve.
3. Regla única: **solo vale lo que dice el fragmento visible**. No use
   conocimiento externo ni complete datos que el fragmento no da.
4. No cambie `premisa`, `text`, `fragment_id` ni `item_id`. No busque el
   reparto de respuestas: no hay pistas en el formulario.

## Significado (con ejemplos inventados, ajenos a la reserva)

Fragmento inventado: «La biblioteca abre de lunes a viernes de 9 a 18 horas.»

- `apoyada`: el fragmento la respalda.
  Afirmación: «La biblioteca abre entre semana por la mañana.» → `apoyada`.
- `contradicha`: el fragmento la niega o es incompatible con ella.
  Afirmación: «La biblioteca abre los domingos.» → `contradicha`.
- `no dice`: el fragmento no da información para decidir.
  Afirmación: «La biblioteca se fundó en 1962.» → `no dice`.
- `ambigua`: el fragmento admite dos lecturas razonables y no puede decidir.
  Afirmación: «La biblioteca cierra al mediodía.» (el horario 9–18 no dice si
  cierra a mediodía) → si de verdad no puede decidir, `ambigua`. Úsela poco:
  solo ante ambigüedad genuina del fragmento, no ante duda de conocimiento.

## Validar antes de entregar

```bash
uv run python -m eval.holdout2_human_review validar \
  --formulario eval/eu_nli_holdout2_human_review_form.yaml \
  --mapeo eval/eu_nli_holdout2_human_review_mapping.yaml
```

La entrega es válida solo con 279 juicios, vocabulario exacto y textos
intactos. La comparación con las etiquetas IA la ejecuta otra persona con el
subcomando `comparar`, solo después de validar los 279 juicios, y su salida
es únicamente agregada (sin detalle por caso).
