# Stage 5B A2 — Ejecución del baseline físico

**Estado técnico:** `BALLISTIC_BASELINE_MARGINAL`
**Estado de revisión:** `IMPLEMENTED_PENDING_HUMAN_3D_GATE` no aplica porque el
baseline no alcanzó `READY_FOR_3D_HUMAN_GATE`.

## Entradas y método

Se usaron exclusivamente los artefactos aprobados de Stage 3, Stage 4, Stage 5A y
5A.1: 527 timestamps VFR, trayectoria suavizada, 10 eventos, 9 segmentos, cámara
refinada y referencia vertical humana. La gravedad es `9.80665 m/s²`. Cada vuelo usa
posición de evento compartida y velocidad inicial independiente; la proyección 3D→2D
se ajusta con pérdida `soft_l1`. Las observaciones `detected` pesan 1.0, las
`interpolated` 0.35 ajustadas por confidence, y `missing/rejected` quedan fuera del
residual pero se conservan en los CSV.

Se enumeraron las 24 combinaciones exactas. La seleccionada fue la combinación base:
`139,158,200,262,287,327,351,399,434,463`; coste `2502.8864`, segunda `2502.8874`,
margen `0.0010`. Las alternativas se conservaron en `event_frame_selection.json`.

## Resultado

Hubo 3 vuelos `FIT_ACCEPTED`, 6 `FIT_MARGINAL` y 0 `FIT_REJECTED`. Reproyección global:
media `13.961 px`, mediana `10.410 px`, p95 `50.258 px`, máximo `51.143 px`. La
continuidad máxima es `1.511 m` y la penetración mínima observada `-0.354 m`; por eso
no se declara readiness humana final. `flight_07` conserva cobertura `0.776` y su
incertidumbre mayor no se oculta. Las alturas y velocidades por vuelo están en
`segment_fits.json`, con apex, cruce de red, clearance y métricas p05/p50/p95 de
incertidumbre documentadas en el reporte conjunto.

## Artefactos

- `outputs/nivel_a2_01/stage_5b/trajectory_3d.csv` (527 filas, 0–526)
- `outputs/nivel_a2_01/stage_5b/trajectory_3d_segments.csv`
- `outputs/nivel_a2_01/stage_5b/segment_fits.json`
- `outputs/nivel_a2_01/stage_5b/joint_fit_report.json`
- `outputs/nivel_a2_01/stage_5b/reconstruction_quality_report.json`
- `outputs/nivel_a2_01/stage_5b/reprojection_3d_overlay.mp4`
- `outputs/nivel_a2_01/stage_5b/top_view_3d_diagnostic.mp4`
- `outputs/nivel_a2_01/stage_5b/side_view_3d_diagnostic.mp4`
- `outputs/nivel_a2_01/stage_5b/stage_5b_human_gate.mp4`
- las tres hojas de contacto PNG y `event_frame_selection.json`.

Los videos de diagnóstico conservan 527 frames y la orientación canónica; no sustituyen
Stage 5C ni Stage 6. El baseline no usa homografía como posición final elevada, ni
impone ápice en la red, alturas iguales o líneas rectas entre eventos.

No se ejecutaron WASB, RunPod, SSH, GPU, PyTorch, Stage 2/3/4, Stage 5C ni Stage 6.
