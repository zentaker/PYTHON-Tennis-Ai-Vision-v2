# Ejecución externa Stage 2 — Nivel A2

WASB no debe ejecutarse en macOS Intel. Estos pasos están destinados a Linux/WSL con GPU
CUDA compatible.

## Preparar el entorno

```bash
git clone <URL_DEL_REPOSITORIO>
cd PYTHON-Tennis-Ai-Vision-v2
git pull --ff-only
uv sync --extra tracker --extra dev
nvidia-smi
ffprobe -version
ffmpeg -version
```

Colocar, sin commitear:

- el MP4 original en `data/clips/nivel_a2_01/source.mp4`;
- el checkpoint en `models/wasb/wasb_tennis_best.pth.tar`;
- WASB-SBDT en `third_party/WASB-SBDT`, con su carpeta `src`.

El SHA-256 esperado del MP4 es
`e2a05a8eda9be4d821ae1acc60355c7c0403e450ac0febd6bb3c6a62e0aa5774`.

## Preflight sin inferencia

```bash
uv run python scripts/stage2_a2_preflight.py \
  --video data/clips/nivel_a2_01/source.mp4 \
  --manifest data/clips/nivel_a2_01/clip_manifest.json \
  --checkpoint models/wasb/wasb_tennis_best.pth.tar \
  --wasb-root third_party/WASB-SBDT \
  --require-runtime
```

Debe confirmar 527 frames/timestamps, VFR, `rotate_90_ccw`, salida `2746x1536`, checkpoint,
WASB source y CUDA. Este comando no carga el modelo ni ejecuta inferencia.

## Ejecutar WASB

```bash
uv run python -m src.tracker.wasb_runner \
  --video data/clips/nivel_a2_01/source.mp4 \
  --manifest data/clips/nivel_a2_01/clip_manifest.json \
  --checkpoint models/wasb/wasb_tennis_best.pth.tar \
  --wasb-root third_party/WASB-SBDT \
  --output-csv data/clips/nivel_a2_01/wasb_detections.csv \
  --output-overlay outputs/nivel_a2_01/stage_2/wasb_detections_overlay.mp4 \
  --confidence-threshold 0.5 \
  --device cuda
```

El runner transforma cada frame antes de inferencia, conserva un registro por frame y
codifica el overlay con durations VFR derivadas de los timestamps. No aplica una segunda
rotación y no convierte automáticamente a 60 FPS.

## Recuperar y validar

Regresar a la máquina de trabajo únicamente:

- `data/clips/nivel_a2_01/wasb_detections.csv`;
- `outputs/nivel_a2_01/stage_2/wasb_detections_overlay.mp4`.

Comprobar que el CSV tenga 527 filas, IDs `0–526`, timestamps monotónicos y coordenadas
dentro de `2746x1536` cuando `detected=true`. Revisar visualmente el overlay y clasificar
el resultado como A, B o C. No iniciar Stage 3 antes de cerrar este gate.
