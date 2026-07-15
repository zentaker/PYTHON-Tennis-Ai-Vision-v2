# Handoff externo Stage 2 — Nivel A2

El bundle local ignorado está en `transfer/stage2_a2/`. Contiene el MP4 y JSON A2 con
checksums, pero no `.venv`, checkpoint, WASB-SBDT ni resultados inventados. El código se
transfiere mediante Git.

## Requisitos comunes

- Python 3.11 y uv.
- FFmpeg/FFprobe.
- GPU NVIDIA, driver y CUDA compatibles con PyTorch.
- `models/wasb/wasb_tennis_best.pth.tar`.
- `third_party/WASB-SBDT/src`.

El checkpoint y WASB-SBDT están ausentes en Mac. Recuperarlos del entorno Windows/WSL RTX
usado previamente, de su backup autorizado o de la fuente upstream autorizada. No
descargarlos desde una fuente no verificada.

## Ruta A — Windows + WSL2 + NVIDIA

1. Abrir Ubuntu bajo WSL2 y comprobar `nvidia-smi` dentro de WSL.
2. Clonar o actualizar el repo dentro del filesystem Linux:

   ```bash
   git clone <URL_DEL_REPOSITORIO>
   cd PYTHON-Tennis-Ai-Vision-v2
   git pull --ff-only
   uv sync --frozen --extra tracker --extra dev
   ```

3. Copiar `transfer/stage2_a2/data/` desde Windows al repo WSL conservando rutas.
4. Colocar checkpoint y WASB-SBDT en las rutas comunes.
5. Ejecutar `/ruta/al/bundle/verify_inputs.sh "$PWD"`.
6. Solo si pasa, ejecutar `/ruta/al/bundle/run_stage2_a2.sh "$PWD"`.
7. Copiar los tres resultados de vuelta al Mac sin commitearlos.

## Ruta B — Linux + NVIDIA GPU

1. Clonar o actualizar el repo y verificar `nvidia-smi`, `ffmpeg` y `ffprobe`.
2. Instalar el entorno:

   ```bash
   uv sync --frozen --extra tracker --extra dev
   ```

3. Copiar `transfer/stage2_a2/data/` al repo con `rsync -a`.
4. Colocar checkpoint y WASB-SBDT en las rutas comunes.
5. Ejecutar `verify_inputs.sh` y luego `run_stage2_a2.sh` desde el bundle.
6. Devolver los resultados al Mac.

## CLI exacto

```bash
uv run python -m src.tracker.wasb_runner \
  --video data/clips/nivel_a2_01/source.mp4 \
  --manifest data/clips/nivel_a2_01/clip_manifest.json \
  --checkpoint models/wasb/wasb_tennis_best.pth.tar \
  --wasb-root third_party/WASB-SBDT \
  --output-csv data/clips/nivel_a2_01/wasb_detections.csv \
  --output-overlay outputs/nivel_a2_01/stage_2/wasb_detections_overlay.mp4 \
  --output-report outputs/nivel_a2_01/stage_2/inference_report.json \
  --confidence-threshold 0.5 \
  --device cuda
```

## Archivos que regresan al Mac

1. `data/clips/nivel_a2_01/wasb_detections.csv`.
2. `outputs/nivel_a2_01/stage_2/wasb_detections_overlay.mp4`.
3. `outputs/nivel_a2_01/stage_2/inference_report.json`.

El reporte JSON incluye frames esperados/procesados, detecciones, confidence
media/mediana, tiempo de inferencia y total, dispositivo, versiones PyTorch/CUDA,
dimensiones canónicas, bounds y verificación de timestamps.

## Gate de regreso

- CSV: 527 filas, IDs `0–526`, PTS monotónicos y coordenadas canónicas.
- Overlay: horizontal, 527 frames, sin doble rotación ni CFR forzado.
- Reporte JSON: estado `COMPLETED_PENDING_HUMAN_GATE` y validaciones verdaderas.
- Veredicto humano: A viable, B no viable o C viable con ajustes.

Stage 3 A2 permanece bloqueada hasta completar este gate.
