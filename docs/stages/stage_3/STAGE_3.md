# STAGE 3 - Trayectoria temporalmente suavizada

**Estado:** Cerrada exitosa  
**Nivel:** A  
**Fecha de implementacion:** 2026-05-19
**Fecha de cierre:** 2026-05-19

## Proposito

Convertir las detecciones crudas de WASB en una trayectoria continua y fisicamente plausible de la pelota, robusta a falsos positivos puntuales y frames con deteccion debil o perdida.

Stage 3 no detecta eventos, botes ni golpes. Tampoco renderiza la vista superior final. Su unico objetivo es mejorar la continuidad temporal de la pelota en coordenadas de imagen 2D.

## Entradas

- `data/reference_clip/wasb_detections.csv`
- `data/reference_clip/homography.json`
- `data/reference_clip/madrid_R1.mov`

La homografia se conserva como input de continuidad para etapas posteriores, pero el suavizado de Stage 3 trabaja en coordenadas de imagen 2D. No asume fisica 3D, botes ni golpes.

## Entregables

Versionados:

- `src/tracker/trajectory_io.py`
- `src/tracker/trajectory_smoothing.py`
- `src/tracker/render_trajectory_overlay.py`
- `tests/test_trajectory_smoothing.py`
- `docs/stages/stage_3/STAGE_3.md`
- `docs/stages/stage_3/trajectory_smoothing_report.md`

Locales ignorados por Git:

- `outputs/stage_3/smoothed_trajectory.csv`
- `outputs/stage_3/smoothed_trajectory_overlay.mp4`
- `outputs/stage_3/trajectory_debug_overlay.mp4`
- `outputs/stage_3/trajectory_quality_report.json`

## Metodo implementado

Pipeline:

1. Leer detecciones WASB crudas desde CSV.
2. Marcar detecciones con `confidence < 0.5` como `missing`.
3. Mantener detecciones con `confidence >= 0.5` como candidatas `detected`.
4. Rechazar spikes aislados y saltos imposibles con reglas locales en pixeles/frame.
5. Interpolar gaps cortos de hasta 10 frames.
6. Aplicar media movil centrada de 5 frames dentro de segmentos continuos validos.
7. Exportar CSV suavizado, reporte JSON y overlays MP4.

Estados por frame:

- `detected`
- `rejected`
- `interpolated`
- `missing`

## Parametros actuales

- `threshold_min`: `0.5`
- `max_gap_frames`: `10`
- `max_jump_px`: `220.0`
- `local_window`: `7`
- `isolated_outlier_px`: `140.0`
- `residual_prediction_px`: `120.0`
- `residual_neighbor_jump_px`: `135.0`
- `low_confidence_break_max_conf`: `0.6`
- `low_confidence_prediction_px`: `55.0`
- `low_confidence_neighbor_jump_px`: `50.0`
- `smoothing_window`: `5`

## Metricas del run actual

- Frames totales: `949`
- Frames `detected`: `798`
- Frames `rejected`: `6`
- Frames `interpolated`: `95`
- Frames `missing`: `50`
- Cobertura final: `899 / 949` (`94.73%`)
- Saltos rechazados: `3`
- Anomalias residuales rechazadas: `3`
- Gaps interpolados: `41`
- Maximo gap interpolado: `9`

Frames rechazados automaticamente:

- `202`
- `329`
- `545`

Frames rechazados por refinamiento posterior a validacion humana:

- `81`
- `132`
- `745`

## Relacion con limitaciones de Stage 2

Stage 2 fue cerrado como visualmente viable con 4 errores/desvios puntuales observados por el usuario, principalmente cerca de impactos del jugador far/lejos de la camara.

La primera version de Stage 3 rechazo automaticamente 3 spikes aislados y relleno esos frames mediante interpolacion local. Tras validacion humana inicial `C`, se agrego una segunda pasada `local_prediction_break` para eliminar dos artefactos residuales visibles. El maximo salto frame-a-frame bajo de `73.717790 px` a `35.363514 px` sin reducir la cobertura final.

Tras una segunda validacion humana, el artefacto del saque quedo corregido y solo permanecio un artefacto residual alrededor del segundo 12. Se agrego `low_confidence_prediction_break`, que rechazo el frame `745` y lo reinterpolo localmente sin reducir cobertura.

Reporte de refinamiento:

- `docs/stages/stage_3/anomaly_refinement_report.md`

## Definition of Done

- Leer detecciones crudas WASB desde CSV.
- Clasificar cada frame como `detected`, `rejected`, `interpolated` o `missing`.
- Rechazar outliers con reglas fisicas simples en 2D.
- Interpolar gaps cortos de hasta 10 frames.
- Suavizar trayectoria sin destruir movimientos reales rapidos.
- Generar CSV nuevo con trayectoria suavizada.
- Generar overlay visual con raw WASB, punto suavizado, estado por frame y trayectoria reciente.
- Generar reporte con metricas de calidad.
- Tests unitarios pasando.
- Gate visual listo para validacion humana.

## Gate

El usuario debe revisar:

```text
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\smoothed_trajectory_overlay.mp4
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\trajectory_debug_overlay.mp4
```

Veredicto esperado:

- `A`: trayectoria suavizada aceptable.
- `B`: trayectoria suavizada peor/no sirve.
- `C`: dudoso, requiere ajuste de parametros.

## Criterios de exito

- La trayectoria suavizada no presenta saltos visualmente absurdos.
- Los errores puntuales de Stage 2 quedan rechazados o absorbidos sin destruir la trayectoria.
- Los gaps cortos se interpolan de forma razonable.
- El overlay suavizado se ve mas estable que el overlay crudo.
- No se introducen trayectorias falsas largas.
- La cobertura final es suficiente para pasar a Stage 4.

## Criterios de falla

- El suavizado sigue falsos positivos en vez de rechazarlos.
- La trayectoria suavizada se despega claramente de la pelota real.
- Se inventan tramos largos sin evidencia.
- Los errores de impacto del lado far contaminan el resto de la trayectoria.
- El output es peor que el overlay crudo.

## Cierre

Stage 3 fue aprobada por validacion visual humana. El usuario confirmo que la trayectoria suavizada ya es aceptable para continuar.

Resumen de cierre:

- El artefacto del saque quedo corregido.
- El artefacto residual alrededor del segundo 12 quedo corregido o visualmente aceptable.
- La trayectoria suavizada pasa el gate visual de Nivel A.
- No se inicio Stage 4 durante el cierre.

Reporte de cierre:

- `docs/stages/stage_3/exit_report.md`

## Estado final

Stage 3 queda cerrada exitosamente. El siguiente paso es iniciar Stage 4 con un prompt especifico.
