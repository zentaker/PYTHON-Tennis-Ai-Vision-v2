# Exit Report - Stage 3

**Estado:** Cerrada exitosa  
**Fecha de cierre:** 2026-05-19  
**Nivel:** A

## Resumen

Stage 3 convirtio las detecciones crudas de WASB en una trayectoria temporalmente suavizada y visualmente aceptable. La etapa incluyo rechazo de outliers, interpolacion de gaps cortos, suavizado temporal y dos refinamientos guiados por validacion visual humana.

El usuario emitio veredicto humano final:

```text
La trayectoria suavizada es aceptable para continuar a Stage 4.
```

## Inputs usados

- `data/reference_clip/wasb_detections.csv`
- `data/reference_clip/madrid_R1.mov`
- `data/reference_clip/homography.json`

## Outputs locales generados

- `outputs/stage_3/smoothed_trajectory.csv`
- `outputs/stage_3/smoothed_trajectory_overlay.mp4`
- `outputs/stage_3/trajectory_debug_overlay.mp4`
- `outputs/stage_3/trajectory_quality_report.json`

Los outputs son locales e ignorados por Git por diseno. No deben commitearse.

## Metodo usado

- Limpieza de detecciones WASB por umbral de confidence.
- Rechazo de outliers aislados.
- Interpolacion lineal de gaps cortos.
- Suavizado temporal mediante media movil centrada.
- Refinamientos por coherencia local:
  - `local_prediction_break`
  - `low_confidence_prediction_break`

El suavizado opera en coordenadas 2D de imagen. No asume botes, golpes ni fisica 3D.

## Metricas finales

- Frames totales: `949`
- Frames `detected`: `798`
- Frames `rejected`: `6`
- Frames `interpolated`: `95`
- Frames `missing`: `50`
- Cobertura final: `899 / 949` (`94.73%`)
- Saltos rechazados iniciales: `3`
- Anomalias residuales rechazadas: `3`
- Gaps interpolados: `41`
- Maximo gap interpolado: `9`

## Problemas detectados durante gate visual

Durante las revisiones visuales se detectaron:

- Artefacto cerca del saque / bote del saque.
- Artefacto residual alrededor del segundo 12, en el lado far / jugador lejano.

## Resultado de refinamientos

Ambos problemas quedaron corregidos o visualmente aceptables.

Frames clave rechazados por refinamientos:

- `81`
- `132`
- `745`

Los cambios quedaron documentados en:

- `docs/stages/stage_3/trajectory_smoothing_report.md`
- `docs/stages/stage_3/anomaly_refinement_report.md`

## Veredicto humano final

La trayectoria suavizada es aceptable para continuar a Stage 4.

## Limitaciones conocidas

- La trayectoria sigue siendo 2D en imagen.
- No se han detectado eventos todavia.
- No hay inferencia de altura todavia.
- Botes/golpes se resolveran en Stage 4.
- Gaps mayores a `10` frames quedan como `missing`.

## Decision

Cerrar Stage 3 y continuar a Stage 4.

## Gate

Aprobado por validacion visual humana.

## Estado final

Stage 3 queda cerrada exitosamente para Nivel A. No se implemento Stage 4 en esta sesion; solo se prepara su handoff documental.
