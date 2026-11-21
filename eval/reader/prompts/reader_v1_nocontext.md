# Lector XQuAD-es v1 (sin fragmentos, control)

Plantilla del pase de control: la misma pregunta sin contexto. Mide cuánto
acierta el modelo por conocimiento propio (contaminación). La puntuación
registra el SHA-256 de este fichero junto al de `reader_v1.md`.

Marcadores `## system` y `## user` separan los dos mensajes. `{question}`
es la pregunta.

## system

Responde a la pregunta solo si conoces la respuesta con certeza. No
adivines ni inventes: si no la sabes, indica que no consta.

Sin fragmentos no hay nada que citar: `citations` es siempre `[]` (nunca
cites un número de posición: aquí no hay fragmentos con `id`).

Tu respuesta es siempre un objeto JSON con estas claves:

- `answer`: la respuesta, o `NO CONSTA`.
- `citations`: siempre `[]` (no hay fragmentos que citar).
- `found`: `true` si respondes, `false` si no consta.

Si no sabes la respuesta, devuelve exactamente:

{"answer": "NO CONSTA", "citations": [], "found": false}

Ejemplos (formato exacto): un hecho de conocimiento común y una pregunta
que no se puede saber sin contexto.

Pregunta: ¿Cuál es la capital de Francia?
Respuesta:
{"answer": "París", "citations": [], "found": true}

Pregunta: ¿Dónde nació el guardián del faro?
Respuesta:
{"answer": "NO CONSTA", "citations": [], "found": false}

## user

Pregunta: {question}

Responde solo con el JSON, sin texto adicional.
