# Plan Stage 2 — Nivel A2

**Estado:** preparada para ejecución externa

**Inferencia:** no ejecutada

## Input y contrato

- Video: `data/clips/nivel_a2_01/source.mp4` (MP4 HEVC, 527 frames).
- Manifest: `data/clips/nivel_a2_01/clip_manifest.json`.
- Timing: VFR; intervalos observados de `0.016667` y `0.033333 s`.
- Decodificación esperada: `1536x2746` lateral.
- Transformación: `rotate_90_ccw`.
- Espacio canónico e inferencia: `2746x1536` horizontal.
- Homografía: `data/clips/nivel_a2_01/homography.json`.

Cada frame decodificado debe producir exactamente una fila, conservando `frame_id` de
`0` a `526` y su timestamp real normalizado al inicio del clip. No se admite resampling a
60 FPS, duplicación ni eliminación de frames.

## Auditoría del Stage 2 histórico

Antes de esta preparación, `src/tracker/wasb_runner.py` contenía defaults para
`data/reference_clip/madrid_R1.mov`, el checkpoint histórico y outputs globales. También
importaba PyTorch y WASB al cargar el módulo, y el overlay usaba FPS nominal de OpenCV.

El runner A2 ahora exige rutas explícitas y separa:

- orientación y timestamps en `src/video/canonical_frames.py`;
- CSV, bounds y render VFR en lógica ligera;
- carga real de PyTorch/WASB dentro de `load_wasb_predictor`.

Las menciones `1920x1080`, `60 FPS` y `949 frames` que permanecen en
`docs/stages/stage_2/` describen exclusivamente la pasada histórica Madrid R1. Los
defaults Madrid R1 que aún existen en utilidades de Stage 3 no se modificaron porque
Stage 3 A2 no comenzó. `trajectory_io.py` conserva compatibilidad con las cuatro columnas
históricas y tolera las columnas adicionales del nuevo CSV.

## Outputs y gate futuro

- CSV: `data/clips/nivel_a2_01/wasb_detections.csv`.
- Overlay: `outputs/nivel_a2_01/stage_2/wasb_detections_overlay.mp4`.

El CSV incluirá `frame_id`, `timestamp_seconds`, `x_pixel`, `y_pixel`, `confidence`,
`detected`, `canonical_width` y `canonical_height`. El overlay se codificará como VFR a
partir de los timestamps, en `2746x1536`, sin forzar 60 FPS.

Stage 2 solo podrá cerrarse tras recuperar ambos artefactos y recibir un veredicto humano:

- A — viable;
- B — no viable;
- C — viable con ajustes.

## Entorno y riesgos

La ejecución requiere Linux/WSL, GPU/CUDA compatible, extra `tracker`, checkpoint WASB,
árbol `third_party/WASB-SBDT`, `ffprobe` y `ffmpeg`. Los riesgos principales son HEVC,
metadata de rotación, resolución alta, VFR, disponibilidad del codec H.264 y compatibilidad
entre CUDA, PyTorch y el checkpoint.
