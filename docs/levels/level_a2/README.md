# Nivel A2 - `nivel_a2_01`

**Estado:** Stage 1–4 `CLOSED_SUCCESSFULLY`; Stage 5A y 5A.1 cerradas;
Stage 5B `IN_PROGRESS` (`BALLISTIC_BASELINE_MARGINAL`); Stage 5C y Stage 6 `NOT_STARTED`
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
| 2 | Cerrada exitosamente; gate visual humano A |
| 3 | Cerrada exitosamente; gate visual humano A |
| 4 | `CLOSED_SUCCESSFULLY`; gate humano A; 10 eventos procesados |
| 5A | `CLOSED_WITH_REFINED_VERTICAL_CALIBRATION` |
| 5A.1 | `CLOSED_SUCCESSFULLY`; cuatro referencias y jitter aprobados |
| 5B | `IN_PROGRESS`; baseline balístico ejecutado, pendiente gate humano 3D |
| 5C | `NOT_STARTED`; vista superior derivada de X,Y |
| 6 | `NOT_STARTED`; vista lateral derivada de distancia,Z |

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
- Exit report final: `docs/levels/level_a2/stage_2_exit_report.md`.

La ejecución CUDA procesó `527/527` frames y generó `527` registros y un overlay
canónico `2746x1536` de `527` frames. El usuario aprobó el gate visual con veredicto
`A`; Stage 2 está cerrada y no necesita repetirse para este clip.

## Stage 3 A2

- Plan y diferencias frente a Madrid: `docs/levels/level_a2/stage_3_plan.md`.
- Baseline real: `docs/levels/level_a2/stage_3_baseline_report.md`.
- Exit report final: `docs/levels/level_a2/stage_3_exit_report.md`.
- CSV local: `outputs/nivel_a2_01/stage_3/smoothed_trajectory.csv`.
- Overlays locales: `outputs/nivel_a2_01/stage_3/smoothed_trajectory_overlay.mp4` y
  `outputs/nivel_a2_01/stage_3/trajectory_debug_overlay.mp4`.
- Hoja de contacto local:
  `outputs/nivel_a2_01/stage_3/stage_3_review_contact_sheet.png`.

Stage 3 preserva los `527` timestamps VFR y la orientación canónica `2746x1536`. El
usuario aprobó la trayectoria con veredicto `A`; Stage 3 está cerrada exitosamente sin
ocultar su cobertura de `76.2808%`, `19` frames interpolados y `125` missing.

## Stage 4 A2

- Aplicación: `tools/event_annotator_app/`.
- Rediseño y verificación: `docs/levels/level_a2/stage_4_annotator_redesign.md`.
- Guía: `docs/levels/level_a2/stage_4_annotation_guide.md`.
- Ejecución: `docs/levels/level_a2/stage_4_execution_report.md`.
- Ruta final de la anotación humana:
  `data/clips/nivel_a2_01/manual_annotation.json`.

La anotación humana final contiene 10 eventos; el décimo es el bote terminal `ev_010` en
frame 463. El usuario aprobó el material con gate humano A y Stage 4 está cerrada
exitosamente. Stage 5A audita la cámara sin modificar la anotación.

WASB, RunPod y GPU no se utilizaron en esta pasada. Stage 4 está cerrada; Stage 5A y
5A.1 conservan las cuatro referencias humanas. Stage 5B generó un baseline marginal y
queda pendiente el gate visual humano 3D; Stage 5C y Stage 6 no comenzaron.
