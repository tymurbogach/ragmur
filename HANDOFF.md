# Estado para continuar

## Despliegue de prueba en Skynet

La información siguiente describe las comprobaciones del 11 de noviembre de 2026.
Comprueba el estado actual antes de administrar el despliegue.

- La API, PostgreSQL 17 y Qdrant 1.19 se ejecutaban con Docker Desktop sobre WSL 2.
- La API escuchaba en `127.0.0.1:8000`; PostgreSQL y Qdrant no publicaban puertos.
- El proyecto remoto estaba en `C:\Users\Timur\ragmur-deploy` y se llamaba `ragmur_deploy`.
- El archivo remoto `.env` contiene secretos; no lo muestres ni lo copies al repositorio.
- La revisión `c409b39` se construyó y desplegó en Skynet con CUDA.
- `/ready` respondió correctamente y PyTorch `2.12.0+cu130` detectó la RTX 5080.
- Las pruebas HTTP con datos sintéticos cubrieron ingesta, búsqueda, `/verify` y aislamiento entre tenants y usuarios.
- Antes de actualizar se copiaron PostgreSQL y los originales a `C:\Users\Timur\ragmur-backup-final-c409b39`.
- La restauración se probó con una copia de la instancia local, en volúmenes separados y con reconstrucción de Qdrant.
- No se ha probado la restauración de la copia de Skynet.
- Docker Desktop requirió una configuración independiente para evitar el gestor de credenciales durante SSH.

El repositorio ofrece `docker-compose.deploy.yml` para CPU y `docker-compose.cuda.yml` como overlay para CUDA.
Antes de usar esos archivos con datos existentes, comprueba el nombre de proyecto, la configuración y los volúmenes.
En Skynet, el nombre de proyecto observado fue `ragmur_deploy`.

## Estado de la revisión del 12 de noviembre de 2026

- El árbol está limpio tras los commits de documentación y evaluación.
- SciFact exige una revisión Git completa y registra si se detectó o declaró.
- Falta repetir SciFact con GPU tras ese cambio de trazabilidad.
- La [evaluación exploratoria del verificador](eval/NLI.md) usa ocho textos públicos y 24 afirmaciones.
- La muestra no permite calibrar umbrales ni proporciona una prueba reservada independiente.
- En desarrollo se observó un falso rechazo sobre el texto del descubrimiento del oxígeno.
- Tras la evaluación adicional, la suite pasó con 135 pruebas correctas y cuatro omitidas.
  Usó PostgreSQL y Qdrant temporales aislados; se detuvieron al terminar.
- Las pruebas de modelos reales de la muestra exploratoria se ejecutaron en CPU.
- Se mantuvieron los umbrales y el comportamiento del reindexado.

## Evaluación adicional del verificador

- [InferES y SciFact](eval/NLI.md) aportan muestras públicas de desarrollo en español e inglés.
- InferES: 240 parejas cortas; 15 de 160 negativas recibieron `supported` según las etiquetas originales.
- SciFact: 269 fragmentos; seis de 86 contradicciones recibieron `supported` según las etiquetas originales.
- Se observaron etiquetas discutibles. Ambas muestras requieren más revisión y no representan uso real.
- Las particiones reservadas, de 180 y 59 parejas, no se han evaluado.
- Los umbrales siguen sin calibrar. La exploración de límites y sus compromisos está en `eval/NLI.md`.
- Falta acordar el compromiso aceptable entre respaldo falso y respaldo perdido antes de seleccionar umbrales.
- Revisa las etiquetas dudosas y reúne fragmentos representativos en español antes de calibrar.
- No evalúes las particiones reservadas hasta fijar el procedimiento y los criterios de elección.
- Los datos descargados y detalles por consulta están en `/tmp`; pueden desaparecer.
  Sigue las instrucciones de `eval/NLI.md` para regenerarlos sin guardar volcados por consulta en Git.
- No se han cambiado los umbrales. La fase 1 sigue abierta.


## Pendiente antes de cerrar la fase 1

- Revisar y ampliar la evaluación NLI con fragmentos reales. Los umbrales siguen provisionales.
- La muestra reservada inicial contiene nueve afirmaciones. Detectó dos de tres contradicciones.
- Repetir las pruebas HTTP si cambia la revisión o el entorno de Skynet.
- Usar un corpus real y preparar una demo pública segura, sin exponer claves ni bases de datos.
- Probar la restauración aislada de una copia de Skynet, incluidos los originales y la reconstrucción de Qdrant.
- Revisar la configuración y permisos de los secretos en Windows antes de publicar el servicio.
- `EMBEDDING_DEVICE=auto` selecciona CPU o CUDA al arrancar; `cpu` y `cuda` fuerzan la elección.
- No abrir la fase 2 hasta cumplir todos los criterios de cierre del roadmap.
