# Plan de adaptación Stage 3 — Nivel A2

**Estado histórico del plan:** `IMPLEMENTED_PENDING_HUMAN_VISUAL_GATE`
**Fecha baseline:** 2026-07-15

> Cierre posterior: el usuario aprobó Stage 3 con veredicto `A`. Estado final:
> `CLOSED_SUCCESSFULLY`; ver `docs/levels/level_a2/stage_3_exit_report.md`.

## Objetivo

Reutilizar el suavizado histórico de Madrid sin alterar sus resultados, ampliándolo
para clips con rutas explícitas, timestamps VFR y orientación canónica.

Stage 3 continúa trabajando en coordenadas de imagen 2D. No estima física 3D, golpes,
botes ni posiciones sobre la cancha.

## Supuestos históricos identificados

La implementación Madrid original dependía de:

- rutas por defecto bajo `data/reference_clip`;
- CSV de cuatro columnas sin `timestamp_seconds`;
- saltos medidos en píxeles/frame;
- interpolación por índice de frame;
- lectura y escritura OpenCV CFR;
- ausencia de `iter_canonical_frames`;
- outputs globales bajo `outputs/stage_3`;
- parámetros calibrados para `1920x1080` y aproximadamente 60 fps.

Estos defaults y el comportamiento por frame se conservan cuando no hay timestamps.
Los resultados históricos de Madrid no se borran ni sobrescriben.

## Adaptación A2

- `trajectory_io` acepta ambos esquemas y preserva timestamps, flag `detected` y
  dimensiones canónicas.
- Valida IDs consecutivos, timestamps estrictamente crecientes, confidence finita y
  bounds canónicos.
- Con timestamps, las discontinuidades se miden en px/s y los gaps por duración real.
- La interpolación A2 usa proporción temporal, no solo índice.
- Las ventanas temporales limitan vecindad y suavizado en una cadencia VFR.
- Los thresholds espaciales históricos se escalan con la diagonal canónica.
- El límite de velocidad puede expresarse en diagonales canónicas por segundo.
- Los overlays A2 decodifican con `iter_canonical_frames` y reutilizan el helper VFR
  compartido con Stage 2.
- La CLI admite rutas explícitas para detecciones, video, manifest, timestamps, CSV,
  reporte y ambos overlays.

## Parámetros de la primera baseline

- `threshold_min = 0.5`
- `max_gap_frames = 10`
- `max_gap_seconds = 0.22`
- `local_window = 7`
- `local_window_seconds = 0.14`
- `smoothing_window = 5`
- `smoothing_window_seconds = 0.10`
- `normalized_speed_per_diagonal_s = 1.5`
- Diagonal canónica: `3146.396669 px`.
- Límite efectivo: `4719.595004 px/s`.
- Escala espacial frente a `1920x1080`: `1.428293`.

Se hizo una sola ejecución. No se ajustaron parámetros después de observar sus métricas.

## Comando reproducible

```bash
uv run python -m src.tracker.trajectory_smoothing \
  --detections data/clips/nivel_a2_01/wasb_detections.csv \
  --video data/clips/nivel_a2_01/source.mp4 \
  --manifest data/clips/nivel_a2_01/clip_manifest.json \
  --frame-timestamps data/clips/nivel_a2_01/frame_timestamps.json \
  --output-csv outputs/nivel_a2_01/stage_3/smoothed_trajectory.csv \
  --report-json outputs/nivel_a2_01/stage_3/trajectory_quality_report.json \
  --overlay outputs/nivel_a2_01/stage_3/smoothed_trajectory_overlay.mp4 \
  --debug-overlay outputs/nivel_a2_01/stage_3/trajectory_debug_overlay.mp4 \
  --contact-sheet outputs/nivel_a2_01/stage_3/stage_3_review_contact_sheet.png \
  --threshold-min 0.5 --max-gap-frames 10 --max-gap-seconds 0.22 \
  --local-window 7 --local-window-seconds 0.14 \
  --smoothing-window 5 --smoothing-window-seconds 0.10 \
  --normalized-speed-per-diagonal-s 1.5
```

## Gate

La implementación y baseline son material de revisión. No cierran Stage 3 y no habilitan
Stage 4 hasta que una persona revise ambos overlays.
