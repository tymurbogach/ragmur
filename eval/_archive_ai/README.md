# Archivo de borradores IA (F04 triage)

Contiene borradores con etiquetas propuestas por IA, sin revisión humana.
Ningún archivo aquí es `gold`, ni calibra umbrales, ni cierra 1.8.

- `eu_nli_dev_ai_*`, `eu_nli_test_ai_*`, `eu_nli_holdout2_ai_*`: borradores
  quemados como reserva (`eut-*`, `euh2-*`); no reutilizar sus IDs.
- `eu_numeric_stress_dev_ai*`, `eu_pilot_*ai*`, `eu_pilot_revised*`: estrés
  y piloto IA, pendientes de revisión humana.
- `NLI_AI_EVALUATION_PROTOCOL*.md`, `nli_changed_ai_blind_review.yaml`: notas
  provisionales, no aceptadas.
- `results/`: resúmenes de ejecuciones sobre etiquetas IA; solo diagnóstico,
  no validan umbrales. Detalles por consulta en `/tmp`, fuera de Git.

Umbrales vigentes intactos: 0.75/0.5/0.75. Fase 1 sin LLM.
