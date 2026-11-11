# Estado para continuar

## Despliegue de prueba en Skynet

- La API, PostgreSQL 17 y Qdrant 1.19 están en contenedores Docker Desktop sobre WSL 2.
- La API escucha en `127.0.0.1:8000` del equipo Skynet. No está publicada en Internet.
- PostgreSQL y Qdrant solo son accesibles en la red de Docker.
- El proyecto remoto está en `C:\Users\Timur\ragmur-deploy`.
- Su configuración es `compose.deploy.yml`. El archivo `.env` contiene secretos: no mostrarlo ni copiarlo al repositorio.
- El nombre del proyecto Compose es `ragmur_deploy`. Sus volúmenes conservan base de datos, índice, originales y modelos.
- En la conexión SSH se usó una configuración Docker independiente: `C:/Users/Timur/AppData/Local/Temp/ragmur-docker-test`.
  Evita el error del gestor de credenciales de Windows en sesiones SSH. No eliminarla mientras se use para administrar el despliegue.
- `/ready` devolvió `ok` para PostgreSQL, Qdrant y modelos. PyTorch `2.12.0+cu130` detectó la RTX 5080.
- Una prueba subió un documento TXT, lo indexó y lo encontró mediante búsqueda. Otro `owner_id` no pudo recuperarlo.
- La prueba dejó un tenant y un documento de ejemplo. La clave temporal utilizada fue revocada.
- Esta prueba no verificó `/verify` por HTTP, aislamiento entre dos tenants ni restauración de una copia.
- La imagen se construyó a partir de `fa4d20e`, con el Dockerfile corregido en `55d2c75`.
  El archivo Compose equivalente está versionado como `docker-compose.deploy.yml`.

## Pendiente antes de cerrar la fase 1

- Revisar y ampliar la evaluación NLI con fragmentos reales. Los umbrales siguen provisionales.
- La muestra reservada inicial contiene nueve afirmaciones. Detectó dos de tres contradicciones.
- Verificar `/verify` en el despliegue y repetir el aislamiento entre tenants con servicios reales.
- Usar un corpus real y preparar una demo pública segura, sin exponer claves ni bases de datos.
- Comprobar copia y restauración de PostgreSQL y originales, con reconstrucción de Qdrant.
- Revisar la configuración y permisos de los secretos en Windows antes de publicar el servicio.
- `EMBEDDING_DEVICE=auto` selecciona CPU o CUDA al arrancar; `cpu` y `cuda` fuerzan la elección.
  El despliegue existente en Skynet aún usa la versión anterior y fuerza CUDA; no se ha actualizado.
- No abrir la fase 2 hasta cumplir todos los criterios de cierre del roadmap.
