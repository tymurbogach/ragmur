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

## Pendiente antes de cerrar la fase 1

- Revisar y ampliar la evaluación NLI con fragmentos reales. Los umbrales siguen provisionales.
- La muestra reservada inicial contiene nueve afirmaciones. Detectó dos de tres contradicciones.
- Repetir las pruebas HTTP si cambia la revisión o el entorno de Skynet.
- Usar un corpus real y preparar una demo pública segura, sin exponer claves ni bases de datos.
- Probar la restauración aislada de una copia de Skynet, incluidos los originales y la reconstrucción de Qdrant.
- Revisar la configuración y permisos de los secretos en Windows antes de publicar el servicio.
- `EMBEDDING_DEVICE=auto` selecciona CPU o CUDA al arrancar; `cpu` y `cuda` fuerzan la elección.
- No abrir la fase 2 hasta cumplir todos los criterios de cierre del roadmap.
