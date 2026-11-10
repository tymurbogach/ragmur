# Medición de búsqueda con reranking en CPU

Fecha: 2026-11-10. Esta prueba mide tiempo, no calidad de recuperación.

La prueba usó un Intel Core Ultra 9 285H, con 16 núcleos y 62 GiB de RAM.
No usó GPU. PyTorch ejecutó la inferencia con dos hilos de CPU.

El corpus contenía 30 documentos sintéticos autorizados y dos documentos de otros espacios.
Cada consulta solicitó 30 candidatos y devolvió cinco resultados con reranking.
El cliente ASGI y la API compartieron proceso. PostgreSQL y Qdrant usaron contenedores locales.

Tras dos consultas de calentamiento, se ejecutaron 20 consultas secuenciales.
El p95 observado de `/search` fue **9359,62 ms** por el método de rango más cercano.
El objetivo inicial era un p95 de hasta 10 000 ms en este hardware.
El pico de memoria residente del proceso fue **3621,5 MiB**.

Es una medición preliminar con datos sintéticos y una muestra pequeña.
Había otros procesos en el equipo y se realizaron comprobaciones breves durante la ejecución.
No representa la latencia de producción, una GPU ni un corpus real.

Para repetirla con las revisiones de modelos configuradas y Docker disponible:

```bash
RAGMUR_REAL_MODEL_TESTS=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  uv run pytest -s tests/retrieval/test_benchmark_cpu.py
```
