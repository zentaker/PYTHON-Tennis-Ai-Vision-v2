# Nivel A2 - `nivel_a2_01`

**Estado:** Stage 1 cerrada; Stage 2 ejecutada técnicamente y Stage 3 implementada,
ambas pendientes de gate visual humano
**Fecha de actualización:** 2026-07-15

## Clip seleccionado

- Candidato: `data/candidates/a2_candidate_01.mp4`
- Ruta canonica: `data/clips/nivel_a2_01/source.mp4`
- Extension preservada: `.mp4`
- SHA-256: `e2a05a8eda9be4d821ae1acc60355c7c0403e450ac0febd6bb3c6a62e0aa5774`
- Clasificacion: B, utilizable con riesgos de orientacion/cadence.

La fuente canonica es una copia byte a byte; no se movio, convirtio ni recomprimio el
candidato original.

## Metadata

- Codec: HEVC; audio AAC estereo.
- Frames: `527`.
- Duracion: `10.48833333333333 s`.
- FPS nominal/promedio: `50.24630541871921`.
- FPS calculado por timestamps: `50.17488076311605`.
- Cadence variable: pasos de 1/60 y 1/30 s.
- Resolucion canonica: `2746x1536`.
- OpenCV entrega `1536x2746` por una rotacion de contenedor de 270°.
- Errores de decodificacion: `0`.

## Razon de seleccion

El clip contiene un rally continuo con camara fija, sin replay ni cambio de plano. Se ve
la cancha completa, incluidas lineas de doubles, baselines, service lines y red. Los
overlays no cubren los ocho puntos principales de calibracion.

Se mantiene en clase B porque las coordenadas solo seran coherentes si todas las etapas
aplican la misma orientacion. Los PNG de Stage 1 fueron rotados 90° en sentido antihorario
sin modificar el MP4.

## Estado por stage

| Stage | Estado Nivel A2 |
| --- | --- |
| 0 | Heredada y cerrada |
| 1 | Cerrada exitosa; gates numerico y visual aprobados |
| 2 | Ejecutada técnicamente; pendiente de gate visual humano |
| 3 | Baseline implementada; pendiente de gate visual humano |
| 4 | No iniciada para A2 |
| 5-7 | Pendientes |

## Frames para revision humana

- Seleccion automatica/canonica, frame `180`:
  `data/clips/nivel_a2_01/reference_frame.png`
- Opcion 01, frame `180`:
  `outputs/nivel_a2_01/stage_1/reference_frame_option_01.png`
- Opcion 02, frame `241`:
  `outputs/nivel_a2_01/stage_1/reference_frame_option_02.png`
- Opcion 03, frame `372`:
  `outputs/nivel_a2_01/stage_1/reference_frame_option_03.png`

La opcion 01 fue aprobada como frame oficial. La calibracion se ejecuto sobre esta copia
canonica horizontal.

## Resultado de calibracion

La captura humana ya se ejecuto con:

```bash
uv run python -m src.court.calibrate_web \
  --image data/clips/nivel_a2_01/reference_frame.png \
  --output data/clips/nivel_a2_01/court_corners_pixel.json \
  --layout doubles
```

La UI no uso calibration guide y escribio exclusivamente en la ruta A2 indicada. La
homografia y el reporte completo estan en:

- `data/clips/nivel_a2_01/homography.json`;
- `docs/levels/level_a2/stage_1_report.md`;
- `docs/levels/level_a2/stage_1_orientation_validation.md`.

## Cierre Stage 1

El usuario reviso
`outputs/nivel_a2_01/stage_1/reference_frame_with_reprojected_court.png` y confirmo que
las lineas reproyectadas coinciden con la cancha. El gate numerico paso con media
`4.705469 px` y maximo `8.598912 px`. Ver
`docs/levels/level_a2/stage_1_exit_report.md`.

## Stage 2 A2

- Plan: `docs/levels/level_a2/stage_2_plan.md`.
- Preflight aprobado: `docs/levels/level_a2/stage_2_preflight_report.md`.
- Ejecucion externa: `docs/levels/level_a2/STAGE_2_EXECUTION.md`.
- Inventario de handoff: `docs/levels/level_a2/STAGE_2_EXTERNAL_HANDOFF.md`.
- Preflight local: `scripts/stage2_a2_preflight.py`.
- Runner: `src/tracker/wasb_runner.py`.
- Ejecución técnica final: `docs/levels/level_a2/stage_2_runpod_execution_report.md`.
- Exit report provisional: `docs/levels/level_a2/stage_2_exit_report.md`.

La ejecución CUDA procesó `527/527` frames y generó `527` registros y un overlay
canónico `2746x1536` de `527` frames. Este resultado no equivale a aprobación visual.

## Stage 3 A2

- Plan y diferencias frente a Madrid: `docs/levels/level_a2/stage_3_plan.md`.
- Baseline real: `docs/levels/level_a2/stage_3_baseline_report.md`.
- CSV local: `outputs/nivel_a2_01/stage_3/smoothed_trajectory.csv`.
- Overlays locales: `outputs/nivel_a2_01/stage_3/smoothed_trajectory_overlay.mp4` y
  `outputs/nivel_a2_01/stage_3/trajectory_debug_overlay.mp4`.
- Hoja de contacto local:
  `outputs/nivel_a2_01/stage_3/stage_3_review_contact_sheet.png`.

Stage 3 preserva los `527` timestamps VFR y la orientación canónica `2746x1536`. La
baseline es material para revisión; no está visualmente aprobada.

WASB no se ejecutó en macOS durante esta pasada. Stage 4 y Stage 5 no se iniciaron.
